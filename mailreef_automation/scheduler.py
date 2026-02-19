"""
Scheduler module for automated email sending
Uses APScheduler for cron-like functionality
"""

import random
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import sys
import os
import threading

# Add project root to path to ensure generators/scrapers can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generators.email_generator import EmailGenerator
from logger_util import get_logger
from suppression_manager import SuppressionManager

logger = get_logger("SCHEDULER")

class EmailScheduler:
    """Manages the scheduling logic for all email sends"""
    
    def __init__(self, mailreef_client, config, campaign_profile="IVYBOUND"):
        self.mailreef = mailreef_client
        self.config = config
        self.scheduler = BackgroundScheduler(timezone=pytz.timezone('US/Eastern'))
        
        # Cloud-Native: Sheets & Template Integration
        self.profile_config = config.CAMPAIGN_PROFILES[campaign_profile]
        
        # --- LOGGING ISOLATION ---
        log_file = self.profile_config.get("log_file", "automation.log")
        self.logger = get_logger("SCHEDULER", log_file)
        
        self.generator = EmailGenerator(
            templates_dir=self.profile_config.get("templates_dir", "templates"),
            log_file=log_file,
            archetypes=self.profile_config.get("archetypes")
        )
        
        # Cloud-Native: Sheets Integration
        profile_config = config.CAMPAIGN_PROFILES[campaign_profile]
        from sheets_integration import GoogleSheetsClient
        self.sheets = GoogleSheetsClient(
            input_sheet_name=profile_config["input_sheet"],
            replies_sheet_name=profile_config["replies_sheet"]
        )
        self.sheets.setup_sheets()
        
        # Local Cache to prevent Sheets API Rate Limits
        self._lead_cache = []
        self._followup_cache = {} # inbox_id -> list
        self._last_cache_update = datetime.min
        self._last_followup_update = datetime.min
        self.CACHE_TTL = timedelta(minutes=5)
        self.FOLLOWUP_CACHE_TTL = timedelta(minutes=10)
        
        # Inbox Identity Cache (ID -> Email)
        self.inbox_map = {} 
        self._last_inbox_refresh = datetime.min
        self.INBOX_REFRESH_TTL = timedelta(minutes=60)
        
        # Concurrency Lock
        self._cache_lock = threading.Lock()
        
        self.suppression = SuppressionManager()
        self.is_running = False
        
    def calculate_daily_send_requirements(self, day_type):
        """Calculate how many emails each inbox should send today"""
        if day_type == "business":
            active_inboxes = self.config.INBOXES_PER_DAY_BUSINESS
            emails_per_inbox = self.config.EMAILS_PER_INBOX_DAY_BUSINESS
        else:
            active_inboxes = self.config.INBOXES_PER_DAY_WEEKEND
            emails_per_inbox = self.config.EMAILS_PER_INBOX_DAY_WEEKEND
            
        return {
            "total_emails": active_inboxes * emails_per_inbox,
            "active_inboxes": active_inboxes,
            "emails_per_inbox": emails_per_inbox
        }
    
    def generate_send_slots(self, day_type, inbox_count):
        """Generate time slots for sending emails with natural variance"""
        windows = (self.config.BUSINESS_DAY_WINDOWS 
                   if day_type == "business" 
                   else self.config.WEEKEND_DAY_WINDOWS)
        
        slots = []
        
        # Fetch real inboxes from API
        try:
            all_inboxes_raw = self.mailreef.get_inboxes()
            # Sort by ID to ensure consistent rotation order
            all_inboxes_raw.sort(key=lambda x: x['id'])
            
            # HARDENING: Filter inboxes based on profile indices
            start_idx, end_idx = self.profile_config.get("inbox_indices", (0, 9999))
            # Safety: Ensure indices are within bounds
            all_inboxes = all_inboxes_raw[start_idx:end_idx]
            
            self.logger.info(f"🛡️ [HARDENING] Inbox partition: Using indices {start_idx}-{end_idx} (Total: {len(all_inboxes)} inboxes)")
            
        except Exception as e:
            print(f"Failed to fetch inboxes: {e}")
            return []

        total_inboxes_available = len(all_inboxes)
        active_inboxes = []

        if day_type == "business":
            # Rotation logic: (day_of_year * 2) % total_inboxes
            # HARDENING: Disable rotation for high-volume Web4Guru profiles
            is_high_volume = "WEB4GURU" in self.profile_config.get("log_file", "").upper() or "STRATEGY_B" in self.profile_config.get("log_file", "").upper()
            
            if total_inboxes_available > 0 and not is_high_volume:
                day_of_year = datetime.now(pytz.timezone('US/Eastern')).timetuple().tm_yday
                start_pause_index = (day_of_year * 2) % total_inboxes_available
                paused_indices = {start_pause_index, (start_pause_index + 1) % total_inboxes_available}
                
                for i, inbox in enumerate(all_inboxes):
                    if i not in paused_indices:
                        active_inboxes.append(inbox)
                
                print(f"Business day rotation: Pausing inboxes at indices {paused_indices}")
            else:
                # Weekend or high-volume profile: All inboxes active
                active_inboxes = all_inboxes
                if is_high_volume:
                    print(f"High-Volume Profile ({self.profile_config.get('log_file')}): All {len(active_inboxes)} inboxes active (Rotation disabled)")
                else:
                    print("Business day: All inboxes active (Rotation skip)")
        
        else:
            # Weekend
            active_inboxes = all_inboxes
            print("Weekend: All inboxes active")
        
        emails_assigned_per_inbox = {}
        for inbox in active_inboxes:
            emails_assigned_per_inbox[inbox['id']] = 0
            
        for window in windows:
            emails_per_inbox = window["emails_per_inbox"]
            window_start = window["start"]
            window_end = window["end"]
            
            for inbox_id in emails_assigned_per_inbox.keys():
                # We need to send 'emails_per_inbox' number of emails in this window
                for _ in range(emails_per_inbox):
                    # Add random jitter
                    random_minute = random.randint(0, 59)
                    
                    # If we are scheduling for the current hour, ensure send_time is in the future
                    now_est = datetime.now(pytz.timezone('US/Eastern'))
                    
                    if window_start == now_est.hour:
                        # Schedule in the next 2-10 minutes for "immediate" demo effect
                        jitter_minutes = now_est.minute + random.randint(2, 10)
                        if jitter_minutes >= 60: # Wrap around if at end of hour
                            jitter_minutes = 59 
                    else:
                        # Standard jitter: spread evenly across the hour
                        jitter_minutes = random.randint(5, 55)
                    
                    send_time = now_est.replace(
                        hour=window_start,
                        minute=jitter_minutes,
                        second=0,
                        microsecond=0
                    )
                    
                    # Add 1-5 minute random offset to avoid all sending at exact same second
                    offset_seconds = random.randint(60, 300)
                    send_time = send_time + timedelta(seconds=offset_seconds)
                    
                    # self.logger.debug(f"Generated slot for inbox {inbox_id} at {send_time} (Window: {window_start}:00)")
                    
                    slots.append({
                        "inbox_id": inbox_id,
                        "scheduled_time": send_time,
                        "window": f"{window_start}:00-{window_end}:00"
                    })
                    
                    emails_assigned_per_inbox[inbox_id] += 1
        
        # Sort slots by time to be nice
        slots.sort(key=lambda x: x['scheduled_time'])
        return slots
    
    def _refresh_cache_if_needed(self):
        """Refresh local lead cache if expired or empty"""
        with self._cache_lock:
            now = datetime.now()
            if not self._lead_cache or (now - self._last_cache_update) > self.CACHE_TTL:
                self.logger.info("🔄 Refreshing Stage 1 lead cache...")
                try:
                    # Use sheets_integration's fetch_all_records (which is also cached)
                    new_batch = self.sheets.get_pending_leads(limit=50) 
                    
                    if new_batch:
                        self._lead_cache = new_batch
                        self._last_cache_update = now
                        self.logger.info(f"✅ Cached {len(new_batch)} fresh Stage 1 leads.")
                    else:
                        self.logger.warning("⚠️ No pending Stage 1 leads found!")
                except Exception as e:
                    # Log only the first line of the error to avoid 429 flood noise
                    self.logger.error(f"❌ Lead cache refresh failed: {str(e).splitlines()[0]}")

    def _refresh_followup_cache_if_needed(self, sender_email, inbox_id):
        """Refresh local follow-up cache for a specific sender"""
        now = datetime.now()
        last_update = self._last_followup_update
        
        # Check if we need to refresh (global TTL for now for simplicity, or per-sender if needed)
        # Using inbox_id as key for easier direct lookup
        if inbox_id not in self._followup_cache or (now - last_update) > self.FOLLOWUP_CACHE_TTL:
            self.logger.info(f"🔄 Refreshing Stage 2 cache for {sender_email}...")
            try:
                new_batch = self.sheets.get_leads_for_followup(sender_email=sender_email, limit=20)
                self._followup_cache[inbox_id] = new_batch
                self._last_followup_update = now
                self.logger.debug(f"✅ Cached {len(new_batch)} follow-ups for {sender_email}")
            except Exception as e:
                self.logger.error(f"❌ Follow-up cache refresh failed for {sender_email}: {str(e).splitlines()[0]}")

    def _refresh_inbox_map_if_needed(self):
        """Refresh the ID->Email map for sign-offs"""
        now = datetime.now()
        if not self.inbox_map or (now - self._last_inbox_refresh) > self.INBOX_REFRESH_TTL:
            try:
                self.logger.info("REFRESHING inbox identity map...")
                inboxes = self.mailreef.get_inboxes()
                new_map = {}
                for ibx in inboxes:
                    # differnet schemas/fields sometimes
                    email = ibx.get('email') or ibx.get('address')
                    if email:
                        new_map[str(ibx['id'])] = email
                
                if new_map:
                    self.inbox_map = new_map
                    self._last_inbox_refresh = now
                    self.logger.info(f"✅ Cached {len(new_map)} inbox identities.")
                    self.logger.info(f"🔍 DEBUG INBOX MAP: {self.inbox_map}")
            except Exception as e:
                self.logger.error(f"Failed to refresh inbox map: {e}")

    def select_prospects_for_send(self, inbox_id, count, sequence_stage):
        """Select prospects for a specific send slot (Sheets-First)"""
        
        # Stage 2: Lead Consistency
        # Must find a lead that was sent Email 1 by THIS inbox
        if sequence_stage == 2:
            try:
                # Optimized: If inbox_id looks like an email, use it directly
                inbox_email = str(inbox_id) if '@' in str(inbox_id) else None
                
                if not inbox_email:
                    # Resolve ID to email
                    inboxes = self.mailreef.get_inboxes()
                    for ibx in inboxes:
                        if str(ibx.get('id')) == str(inbox_id):
                            inbox_email = ibx.get('email') or ibx.get('address')
                            break
                
                if inbox_email:
                    self._refresh_followup_cache_if_needed(inbox_email, inbox_id)
                    
                    # Pop from follow-up cache with suppression check
                    if self._followup_cache.get(inbox_id):
                        while self._followup_cache[inbox_id]:
                            candidate = self._followup_cache[inbox_id].pop(0)
                            if not self.suppression.is_suppressed(candidate.get('email')):
                                return [candidate]
                            self.logger.warning(f"🚫 [SELECTION] Skipping suppressed follow-up: {candidate.get('email')}")
                        return []
                    return []
                else:
                    self.logger.warning(f"Could not resolve email for inbox ID {inbox_id}")
                    return []
            except Exception as e:
                self.logger.error(f"Error selecting follow-up: {str(e).splitlines()[0]}")
                return []

        # Stage 1: New Leads (Use Cache)
        if sequence_stage == 1:
            self._refresh_cache_if_needed()
            
            # Pop from cache with suppression check
            selected = []
            with self._cache_lock:
                while len(selected) < count and self._lead_cache:
                    candidate = self._lead_cache.pop(0)
                    if not self.suppression.is_suppressed(candidate.get('email', '')):
                        selected.append(candidate)
                    else:
                        self.logger.warning(f"🚫 [SELECTION] Skipping suppressed lead: {candidate.get('email')}")
            
            return selected
            
        return []
    
    def execute_send(self, inbox_id, prospects, sequence_number=1):
        """Execute the actual send via Mailreef API"""
        results = []
        for prospect in prospects:
            try:
                # Resolve sender email for dynamic sign-off
                # Logic Update: If inbox_id LOOKS like an email, use it directly. 
                # Otherwise, try the map.
                if "@" in str(inbox_id):
                    sender_email = str(inbox_id)
                else:
                    self._refresh_inbox_map_if_needed()
                    sender_email = self.inbox_map.get(str(inbox_id), "unknown")
                
                self.logger.info(f"🔍 DEBUG LOOKUP: ID={inbox_id} -> Sender: {sender_email}")

                # Use High-Fidelity Generator
                self.logger.info(f"🚀 [SEND START] Generating personalized email for {prospect.get('email')} using sender {sender_email}...")
                
                # Note: Sheets Row provides 'school_name', 'domain', 'first_name', 'role', etc.
                result = self.generator.generate_email(
                    campaign_type=self.profile_config.get("campaign_type", "school"),
                    sequence_number=sequence_number,
                    lead_data=dict(prospect),
                    enrichment_data={}, # Scrapes live
                    sender_email=sender_email
                )
                
                subject = result['subject']
                body_text = result['body']
                body_html = body_text.replace('\n', '<br>')
                
                # VERBOSE LOGGING FOR USER VISIBILITY (Consolidated to prevent interleaving)
                log_msg = [
                    f"📧 [EMAIL CONTENT] To: {prospect['email']}",
                    f"Subject: {subject}",
                    f"--- BODY START ---",
                    body_text,
                    f"--- BODY END ---"
                ]
                self.logger.info("\n".join(log_msg))
                
                # --- NUCLEAR OPTION: LOCK-BEFORE-SEND ---
                # Record in suppression BEFORE the API call.
                # This ensures literal ZERO chance of retry if the API call hangs or crashes.
                self.suppression.add_to_suppression(prospect["email"], self.profile_config.get("log_file", "unknown"))

                response = self.mailreef.send_email(
                    inbox_id=inbox_id,
                    to_email=prospect["email"],
                    subject=subject,
                    body=f"<html><body>{body_html}</body></html>"
                )
                
                self.logger.info(f"✅ [SEND SUCCESS] Email sent to {prospect['email']} via inbox {inbox_id}. MsgID: {response.get('message_id')}")
                
                # Sheets-First: Update Status Immediately
                # We need the sender email to record who sent it
                # We can perform a lookup or pass it if available.
                # Optimization: get email from result/response or lookup?
                # Mailreef API response might contain 'from'? Probably not.
                # Let's resolve specific sender email again or assume rotation logic valid.
                
                # Match logic moved up (sender_email already resolved)

                status = f"email_{sequence_number}_sent"
                self.sheets.update_lead_status(
                    email=prospect["email"],
                    status=status,
                    sent_at=datetime.now(),
                    sender_email=sender_email,
                    row=prospect.get('_row') # CRITICAL FIX: Pass exact row to prevent duplicate loop
                )
                
                results.append({
                    "email": prospect["email"],
                    "status": "sent",
                    "mailreef_message_id": response.get("message_id")
                })
            except Exception as e:
                # Log failure
                self.logger.error(f"❌ [SEND FAILURE] Failed to send to {prospect.get('email')}: {e}")
                # Optional: Mark as failed in sheet?
                # self.sheets.update_lead_status(prospect["email"], "failed")
                
        return results
    
    def start(self):
        """Start the scheduler"""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            self.logger.info("🚀 Email Scheduler Started (EST Timezone)")
            self._schedule_daily_runs()
            
            # Run immediate prep for first launch
            self.logger.info("📡 Triggering immediate queue preparation...")
            self._prepare_daily_queue()
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        self.is_running = False
        print("Scheduler stopped")
    
    def _schedule_daily_runs(self):
        """Schedule the daily send preparation"""
        # Run at 5:00 AM EST to prepare the day's queue
        self.scheduler.add_job(
            self._prepare_daily_queue,
            CronTrigger(hour=5, minute=0, day_of_week='0-6', timezone='US/Eastern'),
            id='daily_prepare',
            replace_existing=True
        )
        print("Daily preparation job scheduled for 5:00 AM EST")
    
    def _prepare_daily_queue(self):
        """Prepare and queue all sends for the day"""
        self.logger.info("📅 Starting daily queue preparation...")
        now = datetime.now(pytz.timezone('US/Eastern'))
        day_of_week = now.weekday()
        
        if day_of_week in [5, 6]:  # Weekend
            day_type = "weekend"
            inbox_count = self.config.INBOXES_PER_DAY_WEEKEND
        else:  # Business day
            day_type = "business"
            inbox_count = self.config.INBOXES_PER_DAY_BUSINESS
        
        # Generate slots
        slots = self.generate_send_slots(day_type, inbox_count)
        self.logger.info(f"🎯 Generated {len(slots)} send slots for today ({day_type}).")
        
        # Schedule each slot
        for slot in slots:
            self.scheduler.add_job(
                self._execute_slot,
                'date',
                run_date=slot["scheduled_time"],
                args=[slot["inbox_id"], slot["scheduled_time"]],
                id=f'slot_{slot["inbox_id"]}_{slot["scheduled_time"].strftime("%Y%m%d%H%M%S")}_{random.randint(1000,9999)}',
                misfire_grace_time=3600 # Allow catchup if system was briefly down
            )
        
        # Log upcoming sends for peace of mind
        self.log_upcoming_sends(limit=5)
    
    def _execute_slot(self, inbox_id, scheduled_time):
        """Execute a single send slot with sequence prioritization"""
        # Prioritize Follow-ups (Stage 2) first
        prospects = self.select_prospects_for_send(inbox_id, count=1, sequence_stage=2)
        stage = 2
        
        if not prospects:
            # If no follow-ups due, pick a new Stage 1 lead
            prospects = self.select_prospects_for_send(inbox_id, count=1, sequence_stage=1)
            stage = 1
        
        if prospects:
            self.logger.info(f"⏰ [SLOT FIRE] Executing Stage {stage} send for {prospects[0].get('email')} from inbox {inbox_id}")
            self.execute_send(inbox_id, prospects, sequence_number=stage)
        else:
             # self.logger.debug(f"🔇 [SLOT FIRE] No prospects (Stage 1 or 2) found for inbox {inbox_id} at {scheduled_time}")
             pass

    def log_upcoming_sends(self, limit=5):
        """Prints the next N scheduled sends to the log for visibility."""
        jobs = self.scheduler.get_jobs()
        # Filter for slot jobs and sort by next_run_time
        slot_jobs = [j for j in jobs if j.id.startswith('slot_')]
        slot_jobs.sort(key=lambda x: x.next_run_time)
        
        if not slot_jobs:
            self.logger.info("📅 No upcoming send slots found in queue.")
            return

        self.logger.info(f"📅 UPCOMING SENDS (Next {min(len(slot_jobs), limit)}):")
        for i, job in enumerate(slot_jobs[:limit]):
            run_time = job.next_run_time.strftime("%I:%M:%S %p %Z")
            # Extract inbox from ID (format: slot_EMAIL_TIMESTAMP_RANDOM)
            parts = job.id.split('_')
            inbox = parts[1] if len(parts) > 1 else "unknown"
            self.logger.info(f"   {i+1}. 🕒 {run_time} -> {inbox}")
