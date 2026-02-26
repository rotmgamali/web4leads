import os
import sys
import requests
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from mailreef_automation.automation_config import MAILREEF_API_KEY, MAILREEF_API_BASE
from mailreef_automation.mailreef_client import MailreefClient

def fetch_and_forward():
    print("Fetching recent outbound emails...")
    headers = {"Content-Type": "application/json"}
    auth = (MAILREEF_API_KEY, '')
    
    # Needs the "page" parameter as per API error
    url = f"{MAILREEF_API_BASE}/mail/outbound"
    res = requests.get(url, headers=headers, auth=auth, params={"page": 1, "display": 10})
    
    if res.status_code != 200:
        print(f"❌ Failed to fetch emails: {res.status_code} - {res.text}")
        return
        
    data = res.json()
    messages = data.get('data', []) if isinstance(data, dict) else data
    
    if not messages:
        print("❌ No recent outbound messages found.")
        return
        
    client = MailreefClient(api_key=MAILREEF_API_KEY)
    target_email = "andrew@web4guru.com"
    print(f"Found {len(messages)} recent messages. Forwarding the first 3 to {target_email}...")
    
    count = 0
    for msg in messages:
        if count >= 3:
            break
            
        msg_id = msg.get('id') or msg.get('message_id')
        to_address = msg.get('to', ['Unknown'])[0] if isinstance(msg.get('to'), list) else msg.get('to', 'Unknown')
        subj = msg.get('subject_line', msg.get('subject', 'No Subject'))
        
        if not msg_id:
            continue
            
        print(f"\n[{count+1}/3] Forwarding Message to {to_address}")
        print(f"      ID: {msg_id}")
        print(f"      Subject: {subj}")
        
        try:
            forward_res = client.forward_email(msg_id, target_email)
            print(f"      Result: {forward_res}")
            count += 1
        except Exception as e:
            print(f"      ❌ Error forwarding: {e}")
            
    print("\n✅ Process complete!")

if __name__ == "__main__":
    fetch_and_forward()
