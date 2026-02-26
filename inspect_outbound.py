import os
import sys
import requests
import json
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from mailreef_automation.automation_config import MAILREEF_API_KEY, MAILREEF_API_BASE

def inspect_outbound():
    headers = {"Content-Type": "application/json"}
    auth = (MAILREEF_API_KEY, '')
    
    url = f"{MAILREEF_API_BASE}/mail/outbound"
    print(f"Fetching outbound emails from {url}...")
    res = requests.get(url, headers=headers, auth=auth, params={"page": 1, "display": 20})
    
    if res.status_code != 200:
        print(f"Error: {res.status_code} - {res.text}")
        return

    data = res.json()
    messages = data.get('data', [])
    
    now = datetime.now()
    today_count = 0
    
    print(f"Scanning {len(messages)} messages...")
    for msg in messages:
        ts = msg.get('ts')
        msg_date = datetime.fromtimestamp(ts) if ts else None
        
        # Check if sent today (Feb 20)
        # We can just check if it's within 12 hours
        is_today = msg_date and (now - msg_date) < timedelta(hours=24)
        
        print(f"--- Message ---")
        print(f"Subject: {msg.get('subject_line') or msg.get('subject')}")
        print(f"To: {msg.get('to')}")
        print(f"Date: {msg_date}")
        print(f"ID (root): {msg.get('id')}")
        print(f"Message ID: {msg.get('message_id')}")
        print(f"Conversation ID: {msg.get('conversation_id')}")
        
        if is_today:
            today_count += 1
            
    print(f"\nFound {today_count} messages from today.")

if __name__ == "__main__":
    inspect_outbound()
