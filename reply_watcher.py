import os
import json
import logging
import time
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Add project root path
import sys
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "mailreef_automation"))
sys.path.insert(0, BASE_DIR)

from mailreef_automation.mailreef_client import MailreefClient
from mailreef_automation.telegram_alert import TelegramNotifier
import mailreef_automation.automation_config as automation_config
from sheets_integration import GoogleSheetsClient
from generators.email_generator import EmailGenerator
import lock_util

# Configuration
MAILREEF_API_KEY = os.getenv("MAILREEF_API_KEY")
if not MAILREEF_API_KEY:
    load_dotenv()
    MAILREEF_API_KEY = os.getenv("MAILREEF_API_KEY")

STATE_FILE = "mailreef_automation/logs/reply_watcher_state.json"
CHECK_INTERVAL_MINUTES = 5

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
from logger_util import get_logger

# We need to defer logger creation until we know the profile... 
# OR just create a generic one and re-init later?
# ReplyWatcher class handles profile. Let's let the class handle logging?
# But `logger` is global. 
# Let's remove the global logger init or make it generic.
logger = get_logger("REPLY_WATCHER", "automation.log") # Default initially


class ReplyWatcher:
    def __init__(self, profile_name="IVYBOUND"):
        self.profile_name = profile_name.upper()
        self.lock_name = f'watcher_{self.profile_name.lower()}'
        
        # Ensure only one instance runs per profile
        lock_util.ensure_singleton(self.lock_name)
        
        self.state_file = f"mailreef_automation/logs/reply_watcher_{self.profile_name.lower()}_state.json"
        
        self.mailreef = MailreefClient(api_key=MAILREEF_API_KEY)
        
        profile_config = automation_config.CAMPAIGN_PROFILES[self.profile_name]
        
        # --- LOGGING ISOLATION ---
        # Re-bind the global logger to the profile-specific file
        # and remove the default 'automation.log' handler to prevent leakage.
        global logger
        log_file = profile_config.get("log_file", "automation.log")
        logger = get_logger("REPLY_WATCHER", log_file)
        
        # Clean up default handler if we switched to a specific one
        # (This ensures "strategy_b.log" doesn't also get written to "automation.log")
        if log_file != "automation.log":
            for h in logger.handlers[:]:
                if isinstance(h, logging.FileHandler) and "automation.log" in h.baseFilename:
                    logger.removeHandler(h)
                    
        self.sheets_client = GoogleSheetsClient(
            input_sheet_name=profile_config["input_sheet"],
            replies_sheet_name=profile_config["replies_sheet"],
            replies_sheet_id=profile_config.get("replies_sheet_id")
        )
        self.sheets_client.setup_sheets() # Ensure sheet1 is available
        self.telegram = TelegramNotifier()
        self.generator = EmailGenerator() # Used for sentiment analysis
        
        # --- CAMPAIGN INBOX ISOLATION ---
        self.campaign_inboxes = set()
        self._load_campaign_inboxes()
        
        # --- LEAD-FIRST FILTERING ---
        # Cache all lead emails to ensure we NEVER filter out a real reply
        self.lead_emails = set()
        self.lead_domains = set()
        self.generic_domains = {
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com', 
            'aol.com', 'msn.com', 'live.com', 'protonmail.com', 'me.com', 'comcast.net'
        }
        self._load_lead_emails()

    def _load_campaign_inboxes(self):
        """Identifies which inboxes belong to this specific campaign profile."""
        try:
            profile_config = automation_config.CAMPAIGN_PROFILES[self.profile_name]
            indices = profile_config.get("inbox_indices")
            
            if not indices:
                logger.warning(f"⚠️ [WATCHER] No inbox indices defined for {self.profile_name}. Monitoring ALL inboxes (Risk of leakage).")
                return

            all_inboxes = self.mailreef.get_inboxes()
            start, end = indices
            campaign_list = all_inboxes[start:end]
            
            for f in campaign_list:
                email = f.get("email", "").lower().strip()
                if email:
                    self.campaign_inboxes.add(email)
            
            logger.info(f"📋 [WATCHER] Monitoring {len(self.campaign_inboxes)} dedicated inboxes for {self.profile_name}.")
            # logger.debug(f"Monitored emails: {self.campaign_inboxes}")
            
        except Exception as e:
            logger.error(f"❌ [WATCHER] Failed to load campaign inboxes: {e}")

    def _load_lead_emails(self):
        """Loads all lead emails and domains from the current profile's input sheet."""
        try:
            logger.info(f"📋 [WATCHER] Loading lead list for {self.profile_name} to guarantee no missed replies...")
            records = self.sheets_client.input_sheet.sheet1.get_all_records()
            for r in records:
                email = str(r.get('email', '')).lower().strip()
                if email:
                    self.lead_emails.add(email)
                    if '@' in email:
                        domain = email.split('@')[-1]
                        if domain not in self.generic_domains:
                            self.lead_domains.add(domain)
            logger.info(f"✅ [WATCHER] Loaded {len(self.lead_emails)} lead emails and {len(self.lead_domains)} lead domains.")
        except Exception as e:
            logger.error(f"❌ [WATCHER] Failed to load lead list: {e}")
        
    def load_state(self) -> dict:
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {"last_check": (datetime.now() - timedelta(hours=24)).isoformat()}

    def save_state(self, state: dict):
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(state, f)

    def is_warmup(self, from_email: str, subject: str) -> bool:
        """
        Differentiate between Ivy Bound system emails and Mailreef warmup service.
        1. Lead-First: If the sender is in our lead list, it is NEVER warmup.
        2. Subject check: Normal filtering logic.
        """
        if not from_email:
            return True
            
        # 1. LEAD-FIRST CHECK (Exact Email)
        email_clean = from_email.lower().strip()
        if email_clean in self.lead_emails:
            logger.info(f"📬 [REPLY] Exact match found for lead: {email_clean}")
            return False

        # 1b. LEAD-DOMAIN CHECK (Exclude generic domains)
        if '@' in email_clean:
            domain = email_clean.split('@')[-1]
            if domain in self.lead_domains:
                logger.info(f"📬 [REPLY] Domain match found for lead: {email_clean} (@{domain})")
                return False

        if not subject:
            # If no subject, but we have a body, it might be a reply from a phone or app.
            # Don't filter out if from a known lead or lead domain (already handled above).
            return False
        
        subj_lower = subject.lower()
        
        # 1. High-Confidence Warmup patterns only (Technical bot noise)
        warmup_patterns = [
            "bug fixes", "software training", "expense reports",
            "sales report", "performance reviews",
            "volunteer day", "vendor negotiations", "health benefits",
            "team building", "intern welcome",
            "strategic planning", "remote work", "client meeting",
            "project update", "policy reminder", "office move",
            "company picnic", "birthday celebration", "quarterly goals",
            "tax compliance", "w-8ben", "documentation notice", "productivity tips",
            "celebration planning", "management system update", "achievement recognition",
            "maintenance notice", "hr policies", "marketing strategies",
            "training session", "retreat planning", "improvement suggestions",
            "challenge discussion", "publication discussion", "contact person",
            "new hire", "it support", "leave request", "w-8", "tax forms",
            "security update", "account action", "mandatory account", 
            "office recycling", "employee satisfaction", "project timeline"
        ]
        
        for pattern in warmup_patterns:
            if pattern in subj_lower:
                logger.info(f"🗑️ [FILTER] Filtered as warmup (Pattern: {pattern}): {from_email}")
                return True
                
        # 3. DEFAULT TO FALSE: If we aren't sure, let it through.
        return False

    def get_inbox_replies(self, since: str) -> List[Dict]:
        """Fetch all inbound replies using the global scan endpoint."""
        replies = []
        try:
            # INCREASED ROBUSTNESS: Fetch top 3 pages (300 emails) 
            # to ensure high-volume warmup doesn't push real replies out of sight.
            for page in range(1, 4):
                logger.debug(f"Fetching global inbound page {page}...")
                result = self.mailreef.get_global_inbound(page=page, display=100)
                batch = result.get("data", [])
                if not batch:
                    break
                
                # Filter by date if since is provided
                if since:
                    try:
                        since_dt = datetime.fromisoformat(since)
                    except ValueError:
                        since_dt = datetime.now() - timedelta(hours=24)
                else:
                    since_dt = datetime.now() - timedelta(hours=24)

                for msg in batch:
                    from_email = str(msg.get("from_email", "")).lower().strip()
                    subject = msg.get("subject_line", "")
                    
                    # FILTER: Skip warmup emails
                    if self.is_warmup(from_email, subject):
                        continue

                    # FILTER: Skip if not for this campaign's inboxes
                    to_email = msg.get("to")[0] if msg.get("to") else "unknown"
                    if self.campaign_inboxes and to_email.lower().strip() not in self.campaign_inboxes:
                        # logger.debug(f"⏭️ [SKIP] Message for {to_email} does not belong to {self.profile_name}")
                        continue

                    ts = msg.get("ts")
                    if ts:
                        # ts is unix timestamp
                        msg_dt = datetime.fromtimestamp(ts)
                        if msg_dt > since_dt:
                            # Normalize keys for the rest of the script
                            msg["from_email"] = msg.get("from_email")
                            # 1. Try body_text (full), 2. Try body_html (stripped), 3. Snippet
                            body_text = msg.get("body_text")
                            if not body_text and msg.get("body_html"):
                                import re
                                body_text = re.sub('<[^<]+?>', '', msg.get("body_html"))
                                
                            msg["body"] = body_text if body_text else msg.get("snippet_preview", "")
                            msg["subject"] = subject
                            msg["date"] = msg_dt.isoformat()
                            # Extra context
                            msg["inbox_email"] = msg.get("to")[0] if msg.get("to") else "unknown"
                            
                            replies.append(msg)
                            
        except Exception as e:
            logger.error(f"Error in global reply fetch: {e}")
        
        return replies

    def analyze_sentiment(self, text: str) -> str:
        """Use GPT-4o-mini to check for high interest/positive sentiment."""
        
        # Load custom prompt if defined in profile
        profile_config = automation_config.CAMPAIGN_PROFILES[self.profile_name]
        prompt_file = profile_config.get("reply_prompt")
        
        if prompt_file and os.path.exists(os.path.join(BASE_DIR, prompt_file)):
            with open(os.path.join(BASE_DIR, prompt_file), 'r') as f:
                base_prompt = f.read()
            prompt = base_prompt.replace("{{ body }}", text)
        else:
            # Fallback to default prompt
            prompt = f"""Analyze the sentiment of this email reply from a school administrator.
Status options: 'positive' (interested, wants meeting, asks for info), 'negative' (not interested, stop), 'neutral' (acknowledged, away).

REPLY:
{text}

Return ONLY one word: positive, negative, or neutral."""
        
        try:
            response = self.generator.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=10
            )
            return response.choices[0].message.content.strip().lower()
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return "neutral"

    def send_auto_reply(self, to_email: str, thread_id: str, inbox_id: str):
        """Sends the follow-up pitch (Email 2) as an auto-reply."""
        profile_config = automation_config.CAMPAIGN_PROFILES[self.profile_name]
        template_file = profile_config.get("auto_reply_template")
        
        if not template_file:
            logger.warning("No auto-reply template configured for this profile.")
            return

        # Construct full path to template
        # templates_dir is base, auto_reply_template is relative to it? 
        # Config says: "templates_dir": "templates/web4guru/accountants"
        # "auto_reply_template": "partner/email_2.txt"
        base_tpl_dir = profile_config.get("templates_dir", "templates")
        full_tpl_path = os.path.join(BASE_DIR, base_tpl_dir, template_file)
        
        if not os.path.exists(full_tpl_path):
             logger.error(f"Auto-reply template not found at {full_tpl_path}")
             return

        try:
            with open(full_tpl_path, 'r') as f:
                body_template = f.read()
                
            # Basic personalization (firstname)
            # We need the lead's name. Check input sheet or derive from email?
            # For speed, let's try to lookup in self.lead_map if we had it, 
            # or just generic greeting if name is missing.
            # actually `process_replies` doesn't pass lead details.
            # Let's simple check if we can get name from display name or just use "Hi"
            # For now, let's just use "Hi there," if we can't find it easily? 
            # Or better, read the input sheet again? We loaded emails.
            # Let's assume we can regex the first name from the to_email line or just say "Hi,"
            
            # Simple variable injection
            # Variables: {{ first_name }}, {{ sender_name }}
            # Sender Name: "Web4Guru Team" (or specific sender if we knew who sent it)
            # The inbox_id has the sender name in mailreef?
            
            # Get sender from inbox for consistency?
            inbox_status = self.mailreef.get_inbox_status(inbox_id)
            sender_name = inbox_status.get("sender_name", "Web4Guru Team")
            
            # Use a safe fallback for first name
            first_name = "there"
            
            body = body_template.replace("{{ first_name }}", first_name) \
                                .replace("{{ sender_name }}", sender_name)
                                
            # Subject: Re: <Original Subject>? Mailreef usually handles threading if we reply to thread?
            # Mailreef send API doesn't fully support "Reply-To-Thread" natively in the simple `send_email` method
            # we typically just send a new email with the same subject prefixed "Re:"?
            # Wait, `send_email` just takes to/subj/body.
            # To thread properly, we usually need References headers.
            # Mailreef API v1 might not support custom headers in the simple endpoint.
            # But if we send to the same person with "Re: <Subject>", clients often thread it.
            
            # Let's try to find original subject from the reply object? 
            # Passed to this method? No.
            # We need to pass logic.
            pass # Implemented in process_replies
            
        except Exception as e:
            logger.error(f"Error preparing auto-reply: {e}")

    def process_replies(self):
        state = self.load_state()
        last_check_str = state.get("last_check")
        
        # Add a 1-hour safety overlap to catch anything missed by transient errors
        try:
            last_check_dt = datetime.fromisoformat(last_check_str)
        except:
            last_check_dt = datetime.now() - timedelta(hours=24)
            
        safety_check_dt = last_check_dt - timedelta(hours=1)
        safety_check_str = safety_check_dt.isoformat()
        
        logger.info(f"Checking for replies since {safety_check_str} (Safety Overlap: 1h)")
        replies = self.get_inbox_replies(safety_check_str)
        logger.info(f"Found {len(replies)} potential replies in window")
        
        # Sort replies by date to process chronologically
        replies.sort(key=lambda x: x.get('date', ''))
        
        latest_successful_dt = last_check_dt
        
        for reply in replies:
            from_email = reply.get('from_email')
            body = reply.get('body', '')
            subject = reply.get('subject', '')
            reply_date_str = reply.get('date')
            
            logger.info(f"📩 Processing reply from {from_email}...")
            
            # 2. Sentiment Analysis
            sentiment = self.analyze_sentiment(body)
            logger.info(f"Sentiment for {from_email}: {sentiment}")
            
            # 3. Log to Google Sheets
            reply_data = {
                'received_at': reply_date_str or datetime.now().isoformat(),
                'from_email': from_email,
                'subject': subject,
                'snippet': body,
                'sentiment': sentiment,
                'original_sender': reply.get('inbox_email'),
                'thread_id': reply.get('thread_id', reply.get('conversation_id'))
            }
            try:
                self.sheets_client.log_reply(reply_data)
                
                # Update latest successful timestamp
                if reply_date_str:
                    try:
                        reply_dt = datetime.fromisoformat(reply_date_str.replace('Z', '+00:00'))
                        # Remove timezone info for comparison with last_check_dt if needed
                        reply_dt = reply_dt.replace(tzinfo=None)
                        if reply_dt > latest_successful_dt:
                            latest_successful_dt = reply_dt
                    except Exception as te:
                        logger.error(f"Time parse error: {te}")
            except Exception as e:
                logger.error(f"❌ Failed to log to sheets: {e}")
                
            
            # 4. Telegram Alert for Positive Sentiment
            if sentiment == 'positive':
                alert_text = f"🔥 *HOT LEAD REPLY*\n\n*From:* {from_email}\n*Subject:* {subject}\n\n*Snippet:*\n`{body[:300]}...`"
                self.telegram.send_message(alert_text)
                logger.info(f"🚀 Telegram alert sent for {from_email}")
                
                # 5. AUTO-REPLY LOGIC
                profile_config = automation_config.CAMPAIGN_PROFILES[self.profile_name]
                if profile_config.get("auto_reply_template"):
                    logger.info(f"🤖 [AUTO-REPLY] Attempting to auto-reply to {from_email}")
                    # Need inbox_id. we have inbox_email from 'original_sender'
                    inbox_email = reply.get('inbox_email')
                    if inbox_email and '@' in inbox_email:
                        self.send_auto_reply(from_email, reply_data['thread_id'], inbox_email, subject)
                    else:
                        logger.error(f"Cannot auto-reply: Inbox email not found in reply data")
                        
    def send_auto_reply(self, to_email: str, thread_id: str, inbox_id: str, original_subject: str):
        """Sends the follow-up pitch (Email 2) as an auto-reply."""
        profile_config = automation_config.CAMPAIGN_PROFILES[self.profile_name]
        template_file = profile_config.get("auto_reply_template")
        
        if not template_file:
            return

        base_tpl_dir = profile_config.get("templates_dir", "templates")
        full_tpl_path = os.path.join(BASE_DIR, base_tpl_dir, template_file)
        
        if not os.path.exists(full_tpl_path):
             logger.error(f"Auto-reply template not found at {full_tpl_path}")
             return

        try:
            with open(full_tpl_path, 'r') as f:
                body_template = f.read()
                
            # Get sender from inbox for consistency
            try:
                inbox_status = self.mailreef.get_inbox_status(inbox_id)
                sender_name = inbox_status.get("sender_name", "Web4Guru Team")
            except:
                sender_name = "Web4Guru Team"
            
            # Prepare Subject
            new_subject = original_subject
            if not new_subject.lower().startswith("re:"):
                new_subject = f"Re: {new_subject}"
            
            # Extract first name (naive)
            # Try to grab from sheet if available? 
            # self.sheets_client.input_sheet might have it but loading all records is expensive just for lookup
            # Let's try to infer from name, or use "there"
            # Actually, `send_email` is just a fire-and-forget.
            # Let's use "there" for safety unless we really want it.
            first_name = "there"
            
            body = body_template.replace("{{ first_name }}", first_name) \
                                .replace("{{ sender_name }}", sender_name)
            
            logger.info(f"Sending auto-reply to {to_email} from {inbox_id}...")
            res = self.mailreef.send_email(inbox_id, to_email, new_subject, body)
            
            if res.get("success"):
                logger.info(f"✅ Auto-reply sent successfully to {to_email}")
                self.telegram.send_message(f"🤖 *AUTO-REPLY SENT*\nTo: {to_email}\nFrom: {inbox_id}")
            else:
                 logger.error(f"❌ Auto-reply failed: {res.get('error')}")

        except Exception as e:
            logger.error(f"Error preparing auto-reply: {e}")

    def run_daemon(self):
        logger.info(f"Starting Reply Watcher daemon (every {CHECK_INTERVAL_MINUTES}m)")
        while True:
            try:
                self.process_replies()
            except Exception as e:
                logger.error(f"Error in daemon: {e}")
            time.sleep(CHECK_INTERVAL_MINUTES * 60)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--profile", type=str, default="IVYBOUND", help="Campaign profile (IVYBOUND or STRATEGY_B)")
    args = parser.parse_args()
    
    watcher = ReplyWatcher(profile_name=args.profile)
    try:
        if args.daemon:
            watcher.run_daemon()
        else:
            watcher.process_replies()
    finally:
        lock_util.release_lock(watcher.lock_name)

if __name__ == "__main__":
    main()
