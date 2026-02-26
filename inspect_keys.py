import os
import sys
import requests
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from mailreef_automation.automation_config import MAILREEF_API_KEY, MAILREEF_API_BASE

def inspect_keys():
    headers = {"Content-Type": "application/json"}
    auth = (MAILREEF_API_KEY, '')
    
    url = f"{MAILREEF_API_BASE}/mail/outbound"
    res = requests.get(url, headers=headers, auth=auth, params={"page": 1, "display": 1})
    
    if res.status_code == 200:
        data = res.json()
        messages = data.get('data', [])
        if messages:
            print("Keys in message:")
            print(json.dumps(list(messages[0].keys()), indent=2))
            print("\nFull Message Data (truncated):")
            # Truncate long strings for clean output
            msg = messages[0].copy()
            for k, v in msg.items():
                if isinstance(v, str) and len(v) > 200:
                    msg[k] = v[:200] + "..."
            print(json.dumps(msg, indent=2))
        else:
            print("No messages found.")
    else:
        print(f"Error: {res.status_code}")

if __name__ == "__main__":
    inspect_keys()
