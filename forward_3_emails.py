import os
import sys

# Add project root to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from mailreef_automation.mailreef_client import MailreefClient
from mailreef_automation.automation_config import MAILREEF_API_KEY

def forward_emails():
    print("Initializing Mailreef Client...")
    client = MailreefClient(api_key=MAILREEF_API_KEY)
    target_email = "andrew@web4guru.com"
    
    # 3 most recent outbound MsgIDs from logs
    msg_ids = [
        "5ffc8007-6010-679f-38a4-8cbce8dc6200@infoweb5.online",
        "4daaac72-45e3-b71c-2dbb-6af8b54febe4@mailboxai.online",
        "b4544eea-11e4-73f3-157c-233830ae4a32@infoweb5.online"
    ]
    
    print(f"Forwarding 3 recent emails to {target_email}...")
    for idx, msg_id in enumerate(msg_ids, 1):
        print(f"[{idx}/3] Forwarding MsgID: {msg_id}...")
        try:
            res = client.forward_email(msg_id, target_email)
            print(f"  Result: {res}")
        except Exception as e:
            print(f"  Error: {e}")
            
    print("\n✅ Done!")

if __name__ == "__main__":
    forward_emails()
