import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from mailreef_automation.mailreef_client import MailreefClient
from mailreef_automation.automation_config import MAILREEF_API_KEY

def check_inbox():
    client = MailreefClient(api_key=MAILREEF_API_KEY)
    print("Fetching inboxes...")
    inboxes = client.get_inboxes()
    
    target = "alex@web5info.online"
    found = False
    for i in inboxes:
        email = i.get('email', '').lower()
        if email == target:
            print(f"✅ Found inbox: {target}")
            found = True
            break
            
    if not found:
        print(f"❌ Inbox NOT FOUND: {target}")
        print(f"Total inboxes found: {len(inboxes)}")
        if inboxes:
            print("First 5 inboxes:")
            for i in inboxes[:5]:
                print(f" - {i.get('email')}")

if __name__ == "__main__":
    check_inbox()
