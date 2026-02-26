import os
import sys
import requests
import json
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from mailreef_automation.automation_config import MAILREEF_API_KEY, MAILREEF_API_BASE

def find_real_sent():
    headers = {"Content-Type": "application/json"}
    auth = (MAILREEF_API_KEY, '')
    
    url = f"{MAILREEF_API_BASE}/mail/outbound"
    print(f"Fetching outbound emails...")
    
    # Check multiple pages to find real ones
    for page in range(1, 4):
        res = requests.get(url, headers=headers, auth=auth, params={"page": page, "display": 100})
        if res.status_code != 200: break
        
        messages = res.json().get('data', [])
        for msg in messages:
            subj = msg.get('subject_line') or msg.get('subject')
            if subj and subj != "None":
                print(f"✅ Found real email!")
                print(f"   From: {msg.get('from')}")
                print(f"   To: {msg.get('to')}")
                print(f"   Subject: {subj}")
                print(f"   ID: {msg.get('message_id')}")
                print("-" * 20)

if __name__ == "__main__":
    find_real_sent()
