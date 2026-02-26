import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sheets_integration import GoogleSheetsClient
from mailreef_automation.automation_config import CAMPAIGN_PROFILES

def test_log():
    print("🧪 Running Trace-Log test...")
    # Use explicit config for Ivy Bound
    sheets = GoogleSheetsClient(
        input_sheet_name=CAMPAIGN_PROFILES['IVYBOUND']['input_sheet'],
        replies_sheet_id=CAMPAIGN_PROFILES['IVYBOUND']['replies_sheet_id']
    )
    sheets.setup_sheets()
    
    test_email = f"test_trace_{int(datetime.now().timestamp())}@example.com"
    reply_data = {
        'received_at': datetime.now().isoformat(),
        'from_email': test_email,
        'subject': "TRACE TEST",
        'snippet': "This is a trace test to find where data goes.",
        'sentiment': 'positive',
        'original_sender': 'andrew@agentsdirect.online',
        'thread_id': 'TEST_THREAD_123'
    }
    
    print(f"Logging test reply for {test_email}...")
    sheets.log_reply(reply_data)
    
    # Now Find it
    ws = sheets.replies_sheet.sheet1
    print(f"Searching in Worksheet: {ws.title} of Spreadsheet: {sheets.replies_sheet.title}")
    cell = ws.find(test_email)
    if cell:
        print(f"🎯 FOUND TRACE! Row {cell.row}, Col {cell.col}")
        print(f"Entire Row Content: {ws.row_values(cell.row)}")
    else:
        print("❌ TRACE NOT FOUND in sheet1.")

if __name__ == "__main__":
    test_log()
