import os
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from mailreef_automation.mailreef_client import MailreefClient
from mailreef_automation.automation_config import MAILREEF_API_KEY

def test_api_filters():
    client = MailreefClient(api_key=MAILREEF_API_KEY)
    test_email = "info@cdtx.cpa"
    
    print(f"Testing filters for {test_email}...")
    
    # Try different parameter names
    for param in ['q', 'from', 'search', 'filter', 'email']:
        print(f"Checking param: {param}...")
        res = client.session.get(f"{client.base_url}/mail/inbound", params={param: test_email, "display": 10})
        if res.status_code == 200:
            data = res.json().get('data', [])
            print(f"  Result count: {len(data)}")
            if len(data) > 0:
                print(f"  FOUND MATCH with {param}!")
                return
        else:
            print(f"  Error {res.status_code}")

if __name__ == "__main__":
    test_api_filters()
