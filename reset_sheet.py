import gspread
from google.oauth2.service_account import Credentials
import os
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RESET_SHEET")

# Define the scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def reset_law_firm_sheet():
    service_account_path = 'credentials/service_account.json'
    creds = Credentials.from_service_account_file(service_account_path, scopes=SCOPES)
    client = gspread.authorize(creds)

    sheet_name = "Florida Law Firm Leads"
    try:
        sh = client.open(sheet_name)
        worksheet = sh.sheet1
        
        # 1. Clear everything
        worksheet.clear()
        logger.info(f"✓ Cleared all data and formatting from {sheet_name}")
        
        # 2. Set correct headers
        expected_headers = [
            "email",
            "first_name",
            "last_name",
            "role",
            "business_name",
            "business_type",
            "domain",
            "state",
            "city",
            "phone",
            "status",
            "email_verified",
            "email_1_sent_at",
            "email_2_sent_at",
            "sender_email",
            "notes",
            "custom_data"
        ]
        
        # Perform update
        num_cols = len(expected_headers)
        end_col_char = chr(ord('A') + num_cols - 1)
        range_label = f'A1:{end_col_char}1'
        
        worksheet.update(range_label, [expected_headers])
        
        # Format headers
        worksheet.format(range_label, {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.2, 'green': 0.4, 'blue': 0.6}
        })
        
        # 3. Handle potential "Table" formatting that might be causing vertical stacking
        # (Usually clearing solves it, but we can also ensure the sheet is not grouped)
        
        logger.info("✓ Spreadsheet reset to clean state.")
            
    except Exception as e:
        logger.error(f"Error resetting sheet: {e}")

if __name__ == "__main__":
    reset_law_firm_sheet()
