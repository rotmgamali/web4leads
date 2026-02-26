import gspread
from google.oauth2.service_account import Credentials
import os
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FIX_HEADERS")

# Define the scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def fix_law_firm_headers():
    service_account_path = 'credentials/service_account.json'
    creds = Credentials.from_service_account_file(service_account_path, scopes=SCOPES)
    client = gspread.authorize(creds)

    sheet_name = "Florida Law Firm Leads"
    try:
        sh = client.open(sheet_name)
        worksheet = sh.sheet1
        
        # Check current row 1
        headers_existing = worksheet.row_values(1)
        
        expected_headers = [
            "email",
            "first_name",
            "last_name",
            "role",
            "school_name",
            "school_type",
            "domain",
            "state",
            "city",
            "phone",
            "status",
            "email_1_sent_at",
            "email_2_sent_at",
            "sender_email",
            "notes",
            "custom_data"
        ]
        
        if headers_existing != expected_headers:
            logger.info("Headers missing or incorrect. Fixing...")
            # Insert at the top
            worksheet.insert_row(expected_headers, index=1)
            
            # Format headers
            num_cols = len(expected_headers)
            end_col_char = chr(ord('A') + num_cols - 1)
            range_label = f'A1:{end_col_char}1'
            
            worksheet.format(range_label, {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.2, 'green': 0.4, 'blue': 0.6}
            })
            logger.info("✓ Headers fixed and formatted.")
        else:
            logger.info("✓ Headers already correct.")
            
    except Exception as e:
        logger.error(f"Error fixing headers: {e}")

if __name__ == "__main__":
    fix_law_firm_headers()
