import sys
import os
import logging
import json

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sheets_integration import GoogleSheetsClient
from mailreef_automation import automation_config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("INSPECT_DATA")

def main():
    profile = automation_config.CAMPAIGN_PROFILES["WEB4GURU_ACCOUNTANTS"]
    
    logger.info("Connecting to Google Sheets...")
    client = GoogleSheetsClient(
        input_sheet_name=profile["input_sheet"],
        replies_sheet_name=profile["replies_sheet"]
    )
    
    # Read first 5 rows
    sheet = client.client.open(profile["input_sheet"]).sheet1
    rows = sheet.get_all_records()[:5]
    
    logger.info(f"Inspecting first {len(rows)} rows:")
    if rows:
        print(f"DEBUG: Sheet Keys: {list(rows[0].keys())}")
        
    for i, row in enumerate(rows):
        print(f"\n--- ROW {i+1} ---")
        print(f"Email: {row.get('email')}")
        print(f"First Name: '{row.get('first_name')}'") # Quote to see empty strings
        print(f"Company: {row.get('school_name')}")
        print(f"Role: {row.get('role')}")
        
        custom = row.get('custom_data')
        if custom:
            try:
                data = json.loads(custom)
                if i == 0:
                    print(f"FULL JSON (Row 1): {json.dumps(data, indent=2)}")
                else:
                    print(f"Custom Data Keys: {list(data.keys())[:5]}...")
            except:
                print("Custom Data: Invalid JSON")
        else:
            print("Custom Data: EMPTY/MISSING")

if __name__ == "__main__":
    main()
