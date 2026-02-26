import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from mailreef_automation.mailreef_client import MailreefClient
from mailreef_automation.automation_config import MAILREEF_API_KEY

def inspect_inbox_obj():
    client = MailreefClient(api_key=MAILREEF_API_KEY)
    inboxes = client.get_inboxes()
    if inboxes:
        import json
        print("Keys in first inbox object:")
        print(json.dumps(list(inboxes[0].keys()), indent=2))
        print("\nFirst inbox data:")
        print(json.dumps(inboxes[0], indent=2))
    else:
        print("No inboxes found.")

if __name__ == "__main__":
    inspect_inbox_obj()
