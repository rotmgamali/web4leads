import os
import sys
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from mailreef_automation.automation_config import MAILREEF_API_KEY, MAILREEF_API_BASE

def get_sent_emails():
    headers = {"Content-Type": "application/json"}
    auth = (MAILREEF_API_KEY, '')
    
    url = f"{MAILREEF_API_BASE}/mail/outbound"
    print(f"Trying GET {url} ...")
    
    # Just try with no params first to see what the 400 error says
    res = requests.get(url, headers=headers, auth=auth)
    print(f"Status: {res.status_code}")
    print(f"Response: {res.text}")

if __name__ == "__main__":
    get_sent_emails()
