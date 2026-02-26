import os
import sys
import time
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from mailreef_automation.mailreef_client import MailreefClient
from mailreef_automation.automation_config import MAILREEF_API_KEY

def search_specific_sender(target_sender):
    print(f"🔎 Searching for {target_sender} in all Mailreef inbound...")
    mailreef = MailreefClient(api_key=MAILREEF_API_KEY)
    
    page = 1
    while True:
        print(f"Checking Page {page}...")
        res = mailreef.get_global_inbound(page=page, display=100)
        messages = res.get('data', [])
        
        if not messages:
            break
            
        for msg in messages:
            from_email = str(msg.get('from_email', '')).lower().strip()
            if target_sender.lower() in from_email:
                print(f"🎯 FOUND! Page {page}")
                print(f"From: {from_email}")
                print(f"Subject: {msg.get('subject_line')}")
                print(f"Body Sample: {str(msg.get('body_text'))[:200]}")
                return
        
        page += 1
        time.sleep(0.3)
        if page > 100: break

if __name__ == "__main__":
    search_specific_sender("ryan.wantuch@tampalanguagecenter.com")
