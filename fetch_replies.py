import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from mailreef_automation.mailreef_client import MailreefClient
from mailreef_automation.automation_config import MAILREEF_API_KEY

def fetch_replies():
    target_emails = [
        "info@cdtx.cpa", "info@jaffermerchantcpa.com", "info@houstonsbestt.com",
        "support@optuno.com", "msscpas@suddenlink.net", "smoraw@rjpcpa.com",
        "lori@stoufferbookkeeping.com", "gmockbee@co.hood.tx.us", "deepti.kurien@indusind.com",
        "info@t-mbizsol.com", "help@countingworkspro.com", "karla@apveltman.com",
        "idalia@rlroyalty.com", "ssadh@sadhcpa.com", "completetaxservicegrp@mail.com",
        "stahmann@gvtc.com", "support@intertaxblock.com", "phishing@irs.gov", "matt@pixelspread.com"
    ]
    target_emails = [e.lower().strip() for e in target_emails]
    
    client = MailreefClient(api_key=MAILREEF_API_KEY)
    
    print(f"📡 Deep scanning for replies from {len(target_emails)} leads...")
    print(f"Targeting up to 50 pages (5,000 messages) of inbound history.")
    
    found_replies = {} # email -> list of messages
    messages_processed = 0
    
    # Scan up to 50 pages
    for page in range(1, 51):
        if page % 10 == 0 or page == 1:
            print(f"   Searching page {page} ({messages_processed} messages scanned)...")
        else:
            print(f"   Fetching page {page}...", end="\r")
            
        res = client.get_global_inbound(page=page, display=100)
        messages = res.get('data', [])
        
        if not messages:
            print(f"\nReached end of inbound logs at page {page}.")
            break
            
        messages_processed += len(messages)
        
        for msg in messages:
            # CORRECT KEYS: from_email, subject_line, body_text
            sender = str(msg.get('from_email', '')).lower().strip()
            # Handle formats like "Name <email@domain.com>"
            if '<' in sender and '>' in sender:
                sender = sender.split('<')[-1].split('>')[0].lower().strip()
                
            if sender in target_emails:
                if sender not in found_replies:
                    found_replies[sender] = []
                found_replies[sender].append(msg)
                print(f"\n✨ FOUND reply from {sender} on page {page}!")
                
    print(f"\n✅ Scan complete. Processed {messages_processed} messages.")
    print(f"Total leads found: {len(found_replies)}")
    
    # Generate Markdown Output
    output = "# Lead Replies Summary (Deep API Scan)\n\n"
    output += f"**Total leads targeted**: {len(target_emails)}\n"
    output += f"**Total messages scanned**: {messages_processed}\n"
    output += f"**Leads found**: {len(found_replies)}\n\n"
    
    for email in target_emails:
        output += f"## {email}\n"
        msgs = found_replies.get(email, [])
        if not msgs:
            output += "*No reply content found in the last 5,000 inbound messages.*\n\n"
        else:
            for m in msgs:
                # CORRECT KEYS: subject_line, ts_pretty_long, body_text
                subject = m.get('subject_line', 'No Subject')
                date = m.get('ts_pretty_long') or m.get('created_at') or 'Unknown Date'
                body = m.get('body_text') or m.get('snippet_preview') or "No body content available."
                body = body.replace('\r\n', '\n').strip()
                
                output += f"### Date: {date} | Subject: {subject}\n"
                output += f"```\n{body}\n```\n\n"
        output += "-----" # Using a marker for split if needed
        output += "\n\n"
        
    # Write to a file
    output_path = "/Users/mac/Desktop/web4leads/lead_replies_summary.md"
    with open(output_path, "w") as f:
        f.write(output)
    
    print(f"✅ Summary written to {output_path}")

if __name__ == "__main__":
    fetch_replies()
