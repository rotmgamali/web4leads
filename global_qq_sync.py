import os
import sys
import time
from datetime import datetime
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

def global_sync_qq_replies():
    print("🌍 Starting Global Historical 'Quick Question' Sync...")
    
    # 1. Setup Clients
    sheets = GoogleSheetsClient(
        input_sheet_name=CAMPAIGN_PROFILES['IVYBOUND']['input_sheet'],
        replies_sheet_id=CAMPAIGN_PROFILES['IVYBOUND']['replies_sheet_id']
    )
    sheets.setup_sheets()
    
    mailreef = MailreefClient(api_key=MAILREEF_API_KEY)
    suppression = SuppressionManager()
    
    # 2. Load Ivy Bound Leads for Enrichment
    print("📡 Fetching Ivy Bound leads from Google Sheets...")
    all_leads = sheets._fetch_all_records()
    ivy_leads_emails = {str(lead.get('email', '')).lower().strip() for lead in all_leads if lead.get('email')}
    
    # Domain map for fallback
    ivy_leads_domains = {}
    for email in ivy_leads_emails:
        if '@' in email:
            domain = email.split('@')[-1].strip()
            if domain:
                ivy_leads_domains[domain] = email
    print(f"✅ Loaded {len(ivy_leads_emails)} unique Ivy Bound lead emails ({len(ivy_leads_domains)} domains).")
    
    # 3. Load Existing Entries for Deduplication
    print("📋 Fetching existing replies from tracking sheet...")
    existing_entries = sheets.replies_sheet.sheet1.get_all_records()
    # Deduplicate by Thread ID or (Email + Date)
    existing_threads = {str(r.get('Thread ID', r.get('thread_id', ''))).strip() for r in existing_entries if r.get('Thread ID') or r.get('thread_id')}
    existing_email_dates = {(str(r.get('From Email', '')).lower().strip(), str(r.get('Received At', '')).split('T')[0]) for r in existing_entries}
    print(f"✅ Found {len(existing_entries)} existing entries in tracking sheet.")
    
    # 4. Fetch Global Inbound (All Pages)
    found_replies = []
    page = 1
    has_more = True
    processed_count = 0
    
    while has_more:
        print(f"🔎 Scanning Mailreef Inbound Page {page}...")
        try:
            res = mailreef.get_global_inbound(page=page, display=100)
            messages = res.get('data', [])
            
            if not messages:
                print("🏁 No more messages found.")
                break
                
            for msg in messages:
                processed_count += 1
                subject = str(msg.get('subject_line', '')).lower().strip()
                
                # TARGET CRITERIA: "quick question" in subject
                if "quick question" in subject:
                    from_email_raw = str(msg.get('from_email', '')).lower().strip()
                    from_email = from_email_raw
                    if '<' in from_email and '>' in from_email:
                        from_email = from_email.split('<')[-1].split('>')[0].strip()
                    
                    msg_ts = msg.get('ts', 0)
                    msg_date = datetime.fromtimestamp(msg_ts).strftime('%Y-%m-%d')
                    thread_id = msg.get('id', '')
                    
                    # Deduplicate
                    if thread_id in existing_threads or (from_email, msg_date) in existing_email_dates:
                        continue
                        
                    # Enrich: Check if it's an Ivy Bound lead (exact or domain)
                    match_email = None
                    match_type = ""
                    
                    if from_email in ivy_leads_emails:
                        match_email = from_email
                        match_type = "Exact Match"
                    elif '@' in from_email and from_email.split('@')[-1] in ivy_leads_domains:
                        match_email = ivy_leads_domains[from_email.split('@')[-1]]
                        match_type = f"Domain Match ({from_email})"
                    
                    # LOG ALL QUICK QUESTION REPLIES?
                    # User said "add all the ones with quick question ihn the subject line to the ivybound reply tracking sheet"
                    # But if we don't know the lead, we might be missing info. 
                    # We'll log it even if not an Ivy Bound lead but mark as "Global Match"
                    
                    target_email = match_email if match_email else from_email
                    final_match_type = match_type if match_type else "Global Discovery"
                    
                    found_replies.append({
                        'received_at': datetime.fromtimestamp(msg_ts).isoformat(),
                        'from_email': target_email,
                        'subject': msg.get('subject_line', ''),
                        'snippet': str(msg.get('body_text', ''))[:500],
                        'original_sender': msg.get('to_email', ''),
                        'thread_id': thread_id,
                        'action_taken': f'Recovered via Global Sync ({final_match_type})',
                        'notes': f'Historical Global Sync on {datetime.now().strftime("%Y-%m-%d")}'
                    })
                    
                    # Immediate deduplication for this run
                    existing_threads.add(thread_id)
                    existing_email_dates.add((from_email, msg_date))

            page += 1
            # Rate limit safety
            time.sleep(0.3)
            
            # Diagnostic stop? Let's go through all unless it's insane volume.
            if page > 50: # Safeguard 5000 messages
                print("🛑 Safeguard reached (50 pages). Stopping to prevent infinite loops.")
                break
                
        except Exception as e:
            print(f"❌ Error on page {page}: {e}")
            break
            
    print(f"✨ Found {len(found_replies)} new 'Quick Question' replies out of {processed_count} messages scanned.")
    
    # 5. Log to Sheets
    if found_replies:
        print(f"📝 Logging {len(found_replies)} new replies to Ivy Bound tracking sheet...")
        for reply in found_replies:
            try:
                sheets.log_reply(reply)
                # Only add to suppression if it was an Ivy lead match
                if "Global Discovery" not in reply['action_taken']:
                    suppression.add_to_suppression(reply['from_email'], "IVYBOUND_GLOBAL_SYNC")
                print(f"✅ Synced: {reply['from_email']}")
            except Exception as e:
                print(f"❌ Failed to log {reply['from_email']}: {e}")
                
    print(f"🏁 Global sync complete. Processed {processed_count} messages.")

if __name__ == "__main__":
    global_sync_qq_replies()
