import os
import sys
import requests
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from mailreef_automation.automation_config import MAILREEF_API_KEY, MAILREEF_API_BASE

def test_forward():
    auth = (MAILREEF_API_KEY, '')
    target_email = "andrew@web4guru.com"
    
    # One of today's message IDs
    raw_id = "31b1b187-7823-f298-a6f4-575b8a1466a5@web5info.online"
    encoded_id = urllib.parse.quote(raw_id)
    uuid_only = raw_id.split('@')[0]
    
    tests = [
        ("Raw ID", f"{MAILREEF_API_BASE}/email/forward/{raw_id}"),
        ("Encoded ID", f"{MAILREEF_API_BASE}/email/forward/{encoded_id}"),
        ("UUID Only", f"{MAILREEF_API_BASE}/email/forward/{uuid_only}")
    ]
    
    for label, url in tests:
        print(f"\n--- Testing {label} ---")
        print(f"URL: {url}")
        res = requests.post(url, auth=auth, json={"to": target_email})
        print(f"Status: {res.status_code}")
        print(f"Response: {res.text}")

if __name__ == "__main__":
    test_forward()
