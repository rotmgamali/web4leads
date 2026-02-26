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

def deep_content_sync():
    print("🧠 Starting Deep Content-Based Ivy Bound Global Sync...")
    
    # 1. Setup Clients
    sheets = GoogleSheetsClient(
        input_sheet_name=CAMPAIGN_PROFILES['IVYBOUND']['input_sheet'],
        replies_sheet_id=CAMPAIGN_PROFILES['IVYBOUND']['replies_sheet_id']
    )
    sheets.setup_sheets()
    
    mailreef = MailreefClient(api_key=MAILREEF_API_KEY)
    suppression = SuppressionManager()
    
    # 2. Ivy Bound Content Signatures
    SIGNATURES = [
        "sat/act prep",
        "act and sat prep",
        "college readiness resources",
        "ivy bound team",
        "genelle",
        "casual chat",
        "dedicated to helping students learn english since 1988",
        "vibrant community you're nurturing",
        "truly impressed by the vibrant community",
        "currently approaching sat/act prep support"
    ]
    
    # 3. Load Leads for Enrichment
    print("📡 Fetching Ivy Bound leads from Google Sheets...")
    all_leads = sheets._fetch_all_records()
    ivy_leads_emails = {str(lead.get('email', '')).lower().strip() for lead in all_leads if lead.get('email')}
    ivy_leads_domains = {}
    for email in ivy_leads_emails:
        if '@' in email:
            domain = email.split('@')[-1].strip()
            if domain:
                ivy_leads_domains[domain] = email
    
    # 4. Load Existing Entries for Deduplication
    print("📋 Fetching existing replies for deduplication...")
    existing_entries = sheets.replies_sheet.sheet1.get_all_records()
    existing_threads = {str(r.get('Thread ID', r.get('thread_id', ''))).strip() for r in existing_entries if r.get('Thread ID') or r.get('thread_id')}
    existing_email_dates = {(str(r.get('From Email', '')).lower().strip(), str(r.get('Received At', '')).split('T')[0]) for r in existing_entries}
    
    # 5. Full History Scan
    found_replies = []
    page = 1
    processed_count = 0
    
    while True:
        print(f"🔎 Deep Scanning Mailreef Page {page}...")
        try:
            res = mailreef.get_global_inbound(page=page, display=100)
            messages = res.get('data', [])
            
            if not messages:
                break
                
            for msg in messages:
                processed_count += 1
                body = str(msg.get('body_text', '')).lower()
                subject = str(msg.get('subject_line', '')).lower()
                
                # CONTENT & SUBJECT MATCHING
                match_found = any(sig in body or sig in subject for sig in SIGNATURES) or "quick question" in subject
                
                if match_found:
                    from_email = str(msg.get('from_email', '')).lower().strip()
                    if '<' in from_email:
                        from_email = from_email.split('<')[-1].split('>')[0].strip()
                    
                    msg_ts = msg.get('ts', 0)
                    msg_date = datetime.fromtimestamp(msg_ts).strftime('%Y-%m-%d')
                    thread_id = msg.get('id', '')
                    
                    # Deduplicate
                    if thread_id in existing_threads or (from_email, msg_date) in existing_email_dates:
                        continue
                        
                    # Enrich matching
                    match_email = None
                    match_type = "Content Match"
                    
                    if from_email in ivy_leads_emails:
                        match_email = from_email
                        match_type += " (Exact Lead)"
                    elif '@' in from_email and from_email.split('@')[-1] in ivy_leads_domains:
                        match_email = ivy_leads_domains[from_email.split('@')[-1]]
                        match_type += " (Domain Match)"
                    
                    target_email = match_email if match_email else from_email
                    
                    found_replies.append({
                        'received_at': datetime.fromtimestamp(msg_ts).isoformat(),
                        'from_email': target_email,
                        'subject': msg.get('subject_line', ''),
                        'snippet': str(msg.get('body_text', ''))[:500],
                        'original_sender': msg.get('to_email', ''),
                        'thread_id': thread_id,
                        'action_taken': f'Recovered via Deep Content Sync ({match_type})',
                        'notes': f'Global Content Scan on {datetime.now().strftime("%Y-%m-%d")}'
                    })
                    
                    # Run-dedup
                    existing_threads.add(thread_id)
                    existing_email_dates.add((from_email, msg_date))

            page += 1
            time.sleep(0.3)
            
            if page > 100: # Final safeguard
                break
                
        except Exception as e:
            print(f"❌ Error on page {page}: {e}")
            break
            
    print(f"✨ Found {len(found_replies)} new matches by content.")
    
    # 6. Log and Update
    if found_replies:
        for reply in found_replies:
            try:
                sheets.log_reply(reply)
                suppression.add_to_suppression(reply['from_email'], "IVYBOUND_CONTENT_SYNC")
                print(f"✅ Synced: {reply['from_email']}")
            except Exception as e:
                print(f"❌ Error logging {reply['from_email']}: {e}")
                
    print(f"🏁 Sync complete. Total messages scanned: {processed_count}")

if __name__ == "__main__":
    deep_content_sync()
