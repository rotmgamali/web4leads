import os
import sys
import json
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from mailreef_automation.mailreef_client import MailreefClient
from mailreef_automation.automation_config import MAILREEF_API_KEY

def inspect_inbound():
    client = MailreefClient(api_key=MAILREEF_API_KEY)
    res = client.get_global_inbound(page=1, display=1)
    data = res.get('data', [])
    if data:
        print(json.dumps(data[0], indent=2))
    else:
        print("No inbound messages found.")

if __name__ == "__main__":
    inspect_inbound()
