#!/usr/bin/env python3
"""
Google Sheets Integration for Ivy Bound Email Campaign

Handles:
1. Reading leads from input sheet
2. Writing replies to tracking sheet
3. Updating lead status after sending

Usage:
    python sheets_integration.py --setup  # First-time OAuth setup
    python sheets_integration.py --test   # Test connection
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any

import time
from functools import wraps
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from gspread.exceptions import APIError

# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
from mailreef_automation.logger_util import get_logger
logger = get_logger("SHEETS_CLIENT")

# OAuth scopes needed
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive.readonly'
]

# File paths
CREDENTIALS_FILE = Path(__file__).parent / 'credentials' / 'google_oauth.json'
TOKEN_FILE = Path(__file__).parent / 'credentials' / 'token.json'
SERVICE_ACCOUNT_FILE = Path(__file__).parent / 'credentials' / 'service_account.json'

# Sheet names
INPUT_SHEET_NAME = "Ivy Bound - Campaign Leads"
REPLIES_SHEET_NAME = "Ivy Bound - Reply Tracking"


class GoogleSheetsClient:
    """Handles all Google Sheets operations for the campaign."""
    
    def __init__(self, input_sheet_name=INPUT_SHEET_NAME, replies_sheet_name=REPLIES_SHEET_NAME, replies_sheet_id=None):
        self.input_sheet_name = input_sheet_name
        self.replies_sheet_name = replies_sheet_name or REPLIES_SHEET_NAME
        self.replies_sheet_id = replies_sheet_id
        self.logger = logger
        
        self.client: Optional[gspread.Client] = None
        self.input_sheet: Optional[gspread.Spreadsheet] = None
        self.replies_sheet: Optional[gspread.Spreadsheet] = None
        
        # Caching
        self._cache = {} # email -> record
        self._all_records_cache = None
        self._last_all_records_fetch = datetime.min
        self.CACHE_TTL = timedelta(minutes=5)
        
        self._authenticate()

    def retry_on_quota(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            max_retries = 3
            for i in range(max_retries):
                try:
                    return f(*args, **kwargs)
                except APIError as e:
                    if "[429]" in str(e) and i < max_retries - 1:
                        wait = (i + 1) * 30 
                        logger.warning(f"⚠️ Google Sheets Quota hit. Waiting {wait}s before retry {i+1}/{max_retries}...")
                        time.sleep(wait)
                        continue
                    raise
            return f(*args, **kwargs)
        return wrapper

    @retry_on_quota
    def _fetch_all_records(self):
        """Internal helper to fetch all records with caching."""
        now = datetime.now()
        if self._all_records_cache is None or (now - self._last_all_records_fetch) > self.CACHE_TTL:
            logger.info("📡 Fetching fresh records from Google Sheets...")
            worksheet = self.input_sheet.sheet1
            raw_records = worksheet.get_all_records()
            
            # Normalize Headers: lowercase and map synonyms
            normalized = []
            for i, raw in enumerate(raw_records):
                record = {}
                for k, v in raw.items():
                    norm_k = str(k).lower().strip().replace(' ', '_')
                    # Map common synonyms
                    if norm_k in ['job_title', 'title', 'position']: norm_k = 'role'
                    if norm_k in ['website', 'url', 'site']: norm_k = 'domain'
                    if norm_k in ['job_title', 'title', 'position']: norm_k = 'role'
                    if norm_k in ['website', 'url', 'site']: norm_k = 'domain'
                    if norm_k in ['school', 'company', 'organization']: norm_k = 'school_name'
                    if norm_k in ['type', 'school_type', 'category']: norm_k = 'school_type'
                    
                    record[norm_k] = v
                
                if record.get('email'):
                    record['_row'] = i + 2
                    normalized.append(record)
                    self._cache[record['email']] = record
            
            self._all_records_cache = normalized
            self._last_all_records_fetch = now
        return self._all_records_cache
    
    def _authenticate(self):
        """Authenticate with Google using OAuth credentials or a service account/token from env."""
        creds = None
        
        # 1. Try to load from environment variable (Best for Railway/Cloud)
        # 1. Try to load from environment variable (Best for Railway/Cloud)
        env_creds = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
        env_creds_b64 = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_B64")
        
        try:
            creds_dict = None
            if env_creds:
                creds_dict = json.loads(env_creds)
            elif env_creds_b64:
                import base64
                decoded = base64.b64decode(env_creds_b64).decode('utf-8')
                creds_dict = json.loads(decoded)
                
            if creds_dict:
                # Check if it's an authorized user token or a service account
                if "refresh_token" in creds_dict:
                    creds = Credentials.from_authorized_user_info(creds_dict, SCOPES)
                    logger.info("✓ Authenticated via Environment Variable (User Token)")
                else:
                    # Fallback to service account if that's what's provided
                    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
                    logger.info("✓ Authenticated via Environment Variable (Service Account)")
        except Exception as e:
            logger.warning(f"Failed to load credentials from environment: {e}")

        # 1.5 Try Service Account JSON file (Permanent stability)
        if not creds and SERVICE_ACCOUNT_FILE.exists():
            try:
                creds = service_account.Credentials.from_service_account_file(
                    str(SERVICE_ACCOUNT_FILE), scopes=SCOPES
                )
                logger.info("✓ Authenticated via Service Account JSON (Persistent)")
            except Exception as e:
                logger.warning(f"Could not load service account JSON: {e}")

        # 2. Fallback to local token file (Best for local development)
        if not creds and TOKEN_FILE.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
                logger.info("✓ Authenticated via local token file")
            except Exception as e:
                logger.warning(f"Could not load token: {e}")
        
        if not creds or not creds.valid:
            # If we have creds but they aren't valid, try to refresh first
            if creds:
                try:
                    logger.info("Refreshing credentials...")
                    creds.refresh(Request())
                except Exception as e:
                    logger.debug(f"Initial refresh attempt failed: {e}")

            # If still not valid, handle fallback
            if not creds or not creds.valid:
                if os.environ.get("RAILWAY_ENVIRONMENT") or not sys.stdin.isatty():
                    logger.critical("🛑 No valid Google credentials found.")
                    raise Exception("Missing credentials in non-interactive environment.")
                
                # Only run OAuth flow if we don't have a Service Account
                # (Service accounts shouldn't trigger OAuth browser flows)
                if creds and isinstance(creds, service_account.Credentials):
                    logger.error("❌ Service Account authentication failed. Please check your JSON key.")
                    raise Exception("Service Account authentication failed.")
                else:
                    creds = self._run_oauth_flow()
            
            # Save credentials locally for future use (OAuth tokens only)
            if creds and not env_creds and not isinstance(creds, service_account.Credentials):
                TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(TOKEN_FILE, 'w') as f:
                    f.write(creds.to_json())
        
        if creds:
            self.client = gspread.authorize(creds)
            logger.info("✓ Final Authentication Successful")
        else:
            raise Exception("Failed to authenticate with Google")
    
    def _run_oauth_flow(self) -> Optional[Credentials]:
        """Run the OAuth flow to get new credentials."""
        if not CREDENTIALS_FILE.exists():
            logger.error(f"OAuth credentials file not found at {CREDENTIALS_FILE}")
            logger.info("Please download OAuth credentials from Google Cloud Console")
            logger.info("1. Go to https://console.cloud.google.com/apis/credentials")
            logger.info("2. Create OAuth 2.0 Client ID (Desktop application)")
            logger.info("3. Download JSON and save to: credentials/google_oauth.json")
            return None
        
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
        creds = flow.run_local_server(port=8080)
        return creds
    
    @retry_on_quota
    def setup_sheets(self) -> Dict[str, str]:
        """Create the input and replies sheets if they don't exist."""
        results = {}
        
        # Create or get input sheet
        try:
            self.input_sheet = self.client.open(self.input_sheet_name)
            logger.info(f"✓ Found existing input sheet: {self.input_sheet_name}")
        except gspread.SpreadsheetNotFound:
            self.input_sheet = self.client.create(self.input_sheet_name)
            self._setup_input_sheet_headers()
            logger.info(f"✓ Created input sheet: {self.input_sheet_name}")
        
        results['input_sheet_url'] = self.input_sheet.url
        
        # Create or get replies sheet
        try:
            if self.replies_sheet_id:
                self.replies_sheet = self.client.open_by_key(self.replies_sheet_id)
                logger.info(f"✓ Found existing replies sheet by ID: {self.replies_sheet_id}")
            else:
                self.replies_sheet = self.client.open(self.replies_sheet_name)
                logger.info(f"✓ Found existing replies sheet: {self.replies_sheet_name}")
        except gspread.SpreadsheetNotFound:
            if self.replies_sheet_id:
                logger.warning(f"Could not find/access sheet with ID {self.replies_sheet_id}")
                # Fallback to name if ID fails? Or just fail? 
                # Let's fallback to name to be safe if ID is invalid but Name exists
                try:
                    self.replies_sheet = self.client.open(self.replies_sheet_name)
                    logger.info(f"✓ Fallback: Found existing replies sheet by name: {self.replies_sheet_name}")
                except gspread.SpreadsheetNotFound:
                    self.replies_sheet = self.client.create(self.replies_sheet_name)
                    self._setup_replies_sheet_headers()
                    logger.info(f"✓ Created replies sheet: {self.replies_sheet_name}")
            else:
                self.replies_sheet = self.client.create(self.replies_sheet_name)
                self._setup_replies_sheet_headers()
                logger.info(f"✓ Created replies sheet: {self.replies_sheet_name}")
        
        results['replies_sheet_url'] = self.replies_sheet.url
        
        return results
    
    def _setup_input_sheet_headers(self):
        """Set up headers for the input leads sheet."""
        worksheet = self.input_sheet.sheet1
        worksheet.update_title("Leads")
        
        headers = [
            "email",
            "first_name",
            "last_name",
            "role",
            "school_name",
            "school_type",
            "domain",
            "state",
            "city",
            "phone",
            "status",           # pending, email_1_sent, email_2_sent, replied, bounced
            "email_1_sent_at",
            "email_2_sent_at",
            "sender_email",
            "notes",
            "custom_data"
        ]
        
        # Calculate exactly based on headers list to avoid [400] error
        num_cols = len(headers)
        end_col_char = chr(ord('A') + num_cols - 1)
        range_label = f'A1:{end_col_char}1'
        
        worksheet.update(range_label, [headers])
        worksheet.format(range_label, {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.2, 'green': 0.4, 'blue': 0.6}
        })
        
        logger.info("✓ Set up input sheet headers")
    
    def _setup_replies_sheet_headers(self):
        """Set up headers for the replies tracking sheet."""
        worksheet = self.replies_sheet.sheet1
        worksheet.update_title("Replies")
        
        headers = [
            "Received At",
            "From Email",
            "From Name",
            "School Name",
            "Role",
            "Subject",
            "Snippet",          # First 200 chars of reply
            "Sentiment",        # positive, neutral, negative, meeting_request
            "Original Sender",  # Which inbox sent the original
            "Original Subject",
            "Thread ID",
            "Action Taken",     # replied, forwarded, scheduled_meeting
            "Notes"
        ]
        
        worksheet.update('A1:M1', [headers])
        worksheet.format('A1:M1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.4}
        })
        
        logger.info("✓ Set up replies sheet headers")
    
    def get_pending_leads(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get leads that haven't been contacted yet."""
        all_records = self._fetch_all_records()
        
        # --- NUCLEAR OPTION: HARD FILTER ---
        # Double-check against suppression DB in case the sheet is out of sync
        try:
            from mailreef_automation.suppression_manager import SuppressionManager
            sm = SuppressionManager()
        except:
            sm = None

        pending = []
        for record in all_records:
            if record.get('status', '').lower() in ['', 'pending']:
                email = record.get('email', '').lower().strip()
                if sm and email and sm.is_suppressed(email):
                    logger.warning(f"🚫 [HARD FILTER] Skipping suppressed lead found in pending list: {email}")
                    continue
                pending.append(record)
            
            if len(pending) >= limit:
                break
        
        logger.info(f"Found {len(pending)} pending leads (returning up to {limit})")
        return pending
    
    def get_leads_for_followup(self, days_since_email_1: int = 3, 
                               sender_email: Optional[str] = None,
                               limit: int = 100) -> List[Dict[str, Any]]:
        """Get leads that received Email 1 and are due for Email 2."""
        all_records = self._fetch_all_records()
        
        followup_leads = []
        now = datetime.now()
        
        for record in all_records:
            # Must match sender email if specified
            if sender_email and record.get('sender_email') != sender_email:
                continue
                
            if record.get('status') == 'email_1_sent':
                sent_at_str = record.get('email_1_sent_at', '')
                if sent_at_str:
                    try:
                        sent_at = datetime.fromisoformat(sent_at_str)
                        days_elapsed = (now - sent_at).days
                        if days_elapsed >= days_since_email_1:
                            followup_leads.append(record)
                    except ValueError:
                        pass
            
            if len(followup_leads) >= limit:
                break
        
        logger.info(f"Found {len(followup_leads)} leads due for follow-up (Sender: {sender_email or 'Any'})")
        return followup_leads
    
    @retry_on_quota
    def update_lead_status(self, email: str, status: str, 
                           sent_at: Optional[datetime] = None,
                           sender_email: Optional[str] = None):
        """Update a lead's status after sending an email."""
        worksheet = self.input_sheet.sheet1
        
        # Find the row with this email
        try:
            # Check cache for row if possible
            cached_record = self._cache.get(email)
            if cached_record and cached_record.get('_row'):
                row = cached_record['_row']
            else:
                # Fallback to search if not in cache (should be rare)
                cell = worksheet.find(email)
                if not cell:
                    logger.warning(f"Lead not found in sheet: {email}")
                    return
                row = cell.row
            
            # Get column indices (Use a small cache for headers too)
            if not hasattr(self, '_headers_cache') or not self._headers_cache:
                self._headers_cache = worksheet.row_values(1)
            headers = self._headers_cache
            
            # Prepare batch updates
            cell_list = []
            
            status_col = headers.index('status') + 1
            cell_list.append(gspread.Cell(row, status_col, status))
            
            if sent_at:
                if status == 'email_1_sent':
                    col = headers.index('email_1_sent_at') + 1
                elif status == 'email_2_sent':
                    col = headers.index('email_2_sent_at') + 1
                elif status == 'replied':
                     # We don't have a 'replied_at' column necessarily, but we can add one if needed.
                     # For now, just update status.
                     col = None
                else:
                    col = None
                
                if col:
                    cell_list.append(gspread.Cell(row, col, sent_at.isoformat()))
            
            if sender_email:
                try:
                    sender_col = headers.index('sender_email') + 1
                    cell_list.append(gspread.Cell(row, sender_col, sender_email))
                except ValueError:
                    pass # sender_email column might not exist
            # Perform Batch Update
            worksheet.update_cells(cell_list)
            
            # Invalidate local cache for this email
            if email in self._cache:
                self._cache[email].update({
                    'status': status,
                    'sender_email': sender_email or self._cache[email].get('sender_email')
                })
            
            logger.info(f"Updated {email} status to {status} (Batch)")
            
        except Exception as e:
            # Fallback: If exact email fails, try domain if it's a 'replied' status
            if status == 'replied' and '@' in email:
                domain = email.split('@')[-1]
                if domain not in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']:
                    records = self._fetch_all_records()
                    for rec in records:
                        rec_email = str(rec.get('email', '')).lower()
                        if f"@{domain}" in rec_email:
                            logger.info(f"🔄 [DOMAIN FALLBACK] Retrying status update for {rec_email} (from {email})")
                            return self.update_lead_status(rec_email, status, sent_at, sender_email)
            
            logger.error(f"Error updating status for {email}: {e}")
    
    @retry_on_quota
    def log_reply(self, reply_data: Dict[str, Any]):
        """Log a reply to the replies sheet, auto-enriching with lead data if possible."""
        worksheet = self.replies_sheet.sheet1
        
        from_email = str(reply_data.get('from_email', '')).lower().strip()
        
        # --- AUTO-ENRICHMENT ---
        school_name = reply_data.get('school_name', '')
        role = reply_data.get('role', '')
        lead = None
        
        # If missing, try to find in the leads sheet
        if not school_name or not role:
            # This uses the cached _all_records_cache from _fetch_all_records
            all_records = self._fetch_all_records()
            lead = self._cache.get(from_email)
            
            # DOMAIN FALLBACK: If not found by email, try by domain
            if not lead and '@' in from_email:
                domain = from_email.split('@')[-1]
                # Ignore common generic domains
                if domain not in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']:
                    for rec in all_records:
                        rec_email = str(rec.get('email', '')).lower()
                        if f"@{domain}" in rec_email or domain == rec.get('domain', '').lower():
                            lead = rec
                            logger.info(f"🔍 [DOMAIN MATCH] Associated {from_email} with lead {rec_email} via domain {domain}")
                            break

            if lead:
                school_name = school_name or lead.get('school_name', '')
                role = role or lead.get('role', '')
                logger.info(f"✨ [ENRICH] Found lead info for {from_email}: {school_name} / {role}")
            else:
                # SUBJECT-BASED FALLBACK: Look for recent sends with this subject
                # Subject in reply is usually "Re: Boosting Enrollment"
                reply_subject = str(reply_data.get('subject', '')).lower()
                clean_subject = reply_subject.replace('re:', '').replace('fwd:', '').strip()
                
                if len(clean_subject) > 10: # Only try for non-generic subjects
                    logger.info(f"🔍 [SUBJECT MATCH] Attempting to find lead for subject: {clean_subject}")
                    
                    # Heuristic list of known subject fragments from templates
                    known_fragments = ["quick question", "supporting families", "boosting enrollment", 
                                       "academic outcomes", "differentiation", "merit scholarship",
                                       "college readiness", "student-athletes", "test prep", 
                                       "enhancing value", "enrollment value"]
                    
                    if any(frag in clean_subject for frag in known_fragments):
                        # Find leads who were contacted TODAY or have a suspicious status
                        # and whose school name might be in the subject (Dynamic templates)
                        for rec in all_records:
                            if rec.get('status') in ['email_1_sent', 'email_2_sent']:
                                # If school name is in the subject, it's a very high confidence match
                                s_name = str(rec.get('school_name', '')).lower()
                                if s_name and s_name in clean_subject:
                                    lead = rec
                                    logger.info(f"🎯 [ENRICH] Dynamic Subject Match! {from_email} -> {rec.get('email')} (School: {s_name})")
                                    break
                        
                        # Fallback: if we still don't have a lead, but it's clearly a reply to us
                        # we still log it as 'Neutral' sender in log_reply (already handled by defaults)

        row = [
            reply_data.get('received_at', datetime.now().isoformat()),
            from_email,
            reply_data.get('from_name', ''),
            school_name,
            role,
            reply_data.get('subject', ''),
            reply_data.get('snippet', ''),
            reply_data.get('sentiment', 'neutral'),
            reply_data.get('original_sender', ''),
            reply_data.get('original_subject', ''),
            reply_data.get('thread_id', ''),
            reply_data.get('action_taken', ''),
            reply_data.get('notes', '')
        ]
        
        worksheet.append_row(row)
        logger.info(f"Logged reply from {from_email}")
        
        # Also update the lead status in input sheet
        # CRITICAL: Use the lead's actual email if found via domain/enrichment
        update_email = lead.get('email', from_email) if lead else from_email
        self.update_lead_status(update_email, 'replied')

    @retry_on_quota
    def clear_replies(self):
        """Truncate the replies sheet and write FRESH HEADERS."""
        worksheet = self.replies_sheet.sheet1
        worksheet.clear()
        
        headers = [
            "Received At",
            "From Email",
            "From Name",
            "School Name",
            "Role",
            "Subject",
            "Snippet",
            "Sentiment",
            "Original Sender",
            "Original Subject",
            "Thread ID",
            "Action Taken",
            "Notes"
        ]
        
        worksheet.append_row(headers)
        self.apply_formatting()
        logger.info("🧹 Cleared replies sheet and reset headers.")

    @retry_on_quota
    def apply_formatting(self):
        """Apply layout and conditional formatting to the replies sheet."""
        worksheet = self.replies_sheet.sheet1
        
        # 1. Freeze Header
        worksheet.freeze(rows=1)
        
        # 2. Resize Columns
        # Column F (Subject) -> 400px
        # Column G (Full Message) -> 600px
        # Note: set_column_width uses 1-based index? gspread documentation says set_column_width(col_index, width)
        # However, standard gspread might not have set_column_width in all versions, or uses batchUpdate.
        # Let's use format() for wrapping and specific set calls if available.
        
        try:
            # Fixing the "pixelSize" error. In the Google Sheets API, 
            # column width is set via updateDimensionProperties.
            # Using gspread's format() with "pixelSize" is for some cell properties, 
            # but for column width we should use the specific requests.
            
            body = {
                'requests': [
                    {
                        'updateDimensionProperties': {
                            'range': {
                                'sheetId': worksheet.id,
                                'dimension': 'COLUMNS',
                                'startIndex': 1, # B
                                'endIndex': 2
                            },
                            'properties': {'pixelSize': 250},
                            'fields': 'pixelSize'
                        }
                    },
                    {
                        'updateDimensionProperties': {
                            'range': {
                                'sheetId': worksheet.id,
                                'dimension': 'COLUMNS',
                                'startIndex': 5, # F
                                'endIndex': 7  # G
                            },
                            'properties': {'pixelSize': 500},
                            'fields': 'pixelSize'
                        }
                    }
                ]
            }
            self.replies_sheet.batch_update(body)
            
            # Text Wrapping
            worksheet.format("G:G", {"wrapStrategy": "WRAP"})
            
            # 4. Conditional Formatting
            # Rules:
            # - Sentiment (Col H = 8) is "positive" -> Green background
            # - Sentiment is "negative" -> Red background
            # - Sentiment is "neutral" -> Light Gray background
            
            # We need to construct the requests manually if add_conditional_formatting_rule isn't easy
            # But gspread typically handles basic rules.
            # Let's use specific Logic.
            
            # Green for Positive
            rule_pos = {
                'ranges': [gspread.utils.a1_range_to_grid_range('A2:M1000', sheet_id=worksheet.id)],
                'booleanRule': {
                    'condition': {
                        'type': 'CUSTOM_FORMULA',
                        'values': [{'userEnteredValue': '=$H2="positive"'}]
                    },
                    'format': {'backgroundColor': {'red': 0.85, 'green': 0.93, 'blue': 0.83}} # Light Green
                }
            }
            
            # Red for Negative
            rule_neg = {
                'ranges': [gspread.utils.a1_range_to_grid_range('A2:M1000', sheet_id=worksheet.id)],
                'booleanRule': {
                    'condition': {
                        'type': 'CUSTOM_FORMULA',
                        'values': [{'userEnteredValue': '=$H2="negative"'}]
                    },
                    'format': {'backgroundColor': {'red': 0.96, 'green': 0.85, 'blue': 0.85}} # Light Red
                }
            }
            
            # Gray for Neutral
            rule_neu = {
                'ranges': [gspread.utils.a1_range_to_grid_range('A2:M1000', sheet_id=worksheet.id)],
                'booleanRule': {
                    'condition': {
                        'type': 'CUSTOM_FORMULA',
                        'values': [{'userEnteredValue': '=$H2="neutral"'}]
                    },
                    'format': {'backgroundColor': {'red': 0.95, 'green': 0.95, 'blue': 0.95}} # Light Gray
                }
            }
            
            # Batch update the rules
            body = {
                'requests': [
                    {'addConditionalFormatRule': {'rule': rule_pos, 'index': 0}},
                    {'addConditionalFormatRule': {'rule': rule_neg, 'index': 1}},
                    {'addConditionalFormatRule': {'rule': rule_neu, 'index': 2}}
                ]
            }
            self.replies_sheet.batch_update(body)
            logger.info("🎨 Applied formatting rules to replies sheet.")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not apply some formatting: {e}")


def setup_oauth():
    """Interactive setup for OAuth credentials."""
    print("\n" + "="*60)
    print("GOOGLE SHEETS OAUTH SETUP")
    print("="*60 + "\n")
    
    credentials_dir = Path(__file__).parent / 'credentials'
    credentials_dir.mkdir(exist_ok=True)
    
    if not CREDENTIALS_FILE.exists():
        print("To connect to Google Sheets, you need OAuth credentials.\n")
        print("STEPS:")
        print("1. Go to: https://console.cloud.google.com/apis/credentials")
        print("2. Create a project (or select existing)")
        print("3. Enable 'Google Sheets API' and 'Google Drive API'")
        print("4. Create OAuth 2.0 Client ID (Desktop application)")
        print("5. Download the JSON file")
        print(f"6. Save it as: {CREDENTIALS_FILE}")
        print("\nOnce done, run this script again with --setup")
        return
    
    print("OAuth credentials found. Authenticating...")
    client = GoogleSheetsClient()
    
    print("\nCreating/connecting to sheets...")
    urls = client.setup_sheets()
    
    print("\n" + "="*60)
    print("✓ SETUP COMPLETE!")
    print("="*60)
    print(f"\nInput Sheet:  {urls['input_sheet_url']}")
    print(f"Replies Sheet: {urls['replies_sheet_url']}")
    print("\nYou can now add leads to the input sheet and the system will")
    print("automatically pull from it and track replies.")


def test_connection():
    """Test the Google Sheets connection."""
    print("Testing Google Sheets connection...")
    
    try:
        client = GoogleSheetsClient()
        urls = client.setup_sheets()
        
        # Test reading from input sheet
        leads = client.get_pending_leads(limit=5)
        print(f"✓ Connected to input sheet ({len(leads)} pending leads found)")
        
        # Test reading from replies sheet
        worksheet = client.replies_sheet.sheet1
        rows = worksheet.get_all_values()
        print(f"✓ Connected to replies sheet ({len(rows)-1} replies logged)")
        
        print("\n✓ All connections working!")
        
    except Exception as e:
        print(f"✗ Connection failed: {e}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Google Sheets Integration')
    parser.add_argument('--setup', action='store_true', help='Run first-time setup')
    parser.add_argument('--test', action='store_true', help='Test connection')
    
    args = parser.parse_args()
    
    if args.setup:
        setup_oauth()
    elif args.test:
        test_connection()
    else:
        parser.print_help()
