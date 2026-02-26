import os
import sys
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from mailreef_automation.mailreef_client import MailreefClient
from mailreef_automation.automation_config import CAMPAIGN_PROFILES, MAILREEF_API_KEY
from sheets_integration import GoogleSheetsClient
from mailreef_automation.suppression_manager import SuppressionManager

def sync_replies(days_back: int = 14):
    print(f"🔄 Starting Ivy Bound 14-day reply sync...")
    
    # 1. Setup Clients
    sheets = GoogleSheetsClient(
        input_sheet_name=CAMPAIGN_PROFILES['IVYBOUND']['input_sheet'],
        replies_sheet_id=CAMPAIGN_PROFILES['IVYBOUND']['replies_sheet_id']
    )
    sheets.setup_sheets()
    
    mailreef = MailreefClient(api_key=MAILREEF_API_KEY)
    suppression = SuppressionManager()
    
    # 2. Load Ivy Bound Leads
    print("📡 Fetching Ivy Bound leads from Google Sheets...")
    all_leads = sheets._fetch_all_records()
    # Create a set for fast lookup
    ivy_leads_emails = {str(lead.get('email', '')).lower().strip() for lead in all_leads if lead.get('email')}
    # Create a domain mapping for fallback
    ivy_leads_domains = {}
    for email in ivy_leads_emails:
        if '@' in email:
            domain = email.split('@')[-1].strip()
            if domain:
                ivy_leads_domains[domain] = email
    print(f"✅ Loaded {len(ivy_leads_emails)} unique Ivy Bound lead emails ({len(ivy_leads_domains)} domains).")
    
    # 2.5 Check existing entries in tracking sheet to avoid duplicates
    print("📋 Fetching existing replies from tracking sheet...")
    existing_entries = sheets.replies_sheet.sheet1.get_all_records()
    existing_threads = {str(r.get('Thread ID', r.get('thread_id', ''))).strip() for r in existing_entries if r.get('Thread ID') or r.get('thread_id')}
    existing_email_dates = {(str(r.get('From Email', '')).lower(), str(r.get('Received At', '')).split('T')[0]) for r in existing_entries}
    print(f"✅ Found {len(existing_threads)} existing threads in tracking sheet.")
    
    # 3. Calculate Cutoff Time
    cutoff_ts = int((datetime.now() - timedelta(days=days_back)).timestamp())
    print(f"📅 Scanning messages since: {datetime.fromtimestamp(cutoff_ts).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 4. Fetch and Filter Inbound Messages
    found_replies = []
    sync_run_seeds = set() # (email, date) to avoid duplicates in the same run
    page = 1
    scanning = True
    
    while scanning:
        print(f"🔎 Scanning Mailreef Inbound Page {page}...")
        res = mailreef.get_global_inbound(page=page, display=100)
        messages = res.get('data', [])
        
        if not messages:
            print("🏁 No more messages found.")
            break
            
        for msg in messages:
            msg_ts = msg.get('ts', 0)
            
            # Stop if we hit messages older than cutoff
            if msg_ts < cutoff_ts:
                print(f"🛑 Reached message from {datetime.fromtimestamp(msg_ts)} (Older than 14 days). Stopping scan.")
                scanning = False
                break
                
            from_email = str(msg.get('from_email', '')).lower().strip()
            subject = str(msg.get('subject_line', '')).strip()
            body = str(msg.get('body_text', '')).strip()
            
            # Handle standard email cleanup
            if '<' in from_email and '>' in from_email:
                from_email = from_email.split('<')[-1].split('>')[0].strip()
                
            if from_email in ivy_leads_emails:
                match_email = from_email
                match_type = "Exact Match"
            elif '@' in from_email and from_email.split('@')[-1] in ivy_leads_domains:
                match_email = ivy_leads_domains[from_email.split('@')[-1]]
                match_type = f"Domain Match ({from_email})"
            else:
                match_email = None

            if match_email:
                thread_id = msg.get('id', '')
                msg_date = datetime.fromtimestamp(msg_ts).strftime('%Y-%m-%d')
                
                if thread_id in existing_threads or (from_email, msg_date) in existing_email_dates or (from_email, msg_date) in sync_run_seeds:
                    # Already logged or processed in this run
                    continue

                # Filter out obvious warmup noise
                if "warmup" in from_email or "noise" in subject.lower():
                    continue
                
                sync_run_seeds.add((from_email, msg_date))
                found_replies.append({
                    'received_at': datetime.fromtimestamp(msg_ts).isoformat(),
                    'from_email': match_email, # Use the lead's email for sheet enrichment
                    'real_sender': from_email, # Keep the actual sender
                    'subject': subject,
                    'snippet': body[:500],
                    'original_sender': msg.get('to_email', ''),
                    'thread_id': thread_id,
                    'action_taken': f'Recovered via 14-Day Audit ({match_type})',
                    'notes': f'Historical Sync Run on {datetime.now().strftime("%Y-%m-%d")}'
                })
        
        if scanning:
            page += 1
            # Rate limit safety
            time.sleep(0.5)
            
    print(f"✨ Found {len(found_replies)} potential Ivy Bound replies.")
    
    # 5. Log to Sheets and Update Status
    if found_replies:
        print("📝 Logging replies to Ivy Bound tracking sheets...")
        for reply in found_replies:
            try:
                # log_reply handles update_lead_status('replied') internally
                sheets.log_reply(reply)
                # Also add to hard suppression
                suppression.add_to_suppression(reply['from_email'], "IVYBOUND_SYNC")
                print(f"✅ Synced reply from {reply['from_email']}")
            except Exception as e:
                print(f"❌ Failed to sync {reply['from_email']}: {e}")
                
    print(f"🏁 Historical sync complete. Processed {len(found_replies)} replies.")

if __name__ == "__main__":
    sync_replies(days_back=14)
