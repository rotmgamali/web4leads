import gspread
from google.oauth2.service_account import Credentials
import os

# Define the scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def setup_law_firm_sheet():
    service_account_path = 'credentials/service_account.json'
    if not os.path.exists(service_account_path):
        print(f"Error: {service_account_path} not found.")
        return

    creds = Credentials.from_service_account_file(service_account_path, scopes=SCOPES)
    client = gspread.authorize(creds)

    sheet_name = "Florida Law Firm Leads"
    user_email = "andrew@web4guru.com"

    try:
        # Check if already exists
        sh = client.open(sheet_name)
        print(f"✓ Found existing sheet: {sheet_name}")
    except gspread.SpreadsheetNotFound:
        # Create new
        sh = client.create(sheet_name)
        print(f"✓ Created new sheet: {sheet_name}")
        
    # Share with user
    try:
        sh.share(user_email, perm_type='user', role='editor', notify=False)
        print(f"✓ Shared sheet with: {user_email}")
    except Exception as e:
        print(f"Warning: Could not share with {user_email}: {e}")

    print(f"Spreadsheet URL: {sh.url}")
    return sheet_name

if __name__ == "__main__":
    setup_law_firm_sheet()
