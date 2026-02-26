import csv
import sys
import os

# Add the project root to the python path to import sheets_integration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
    
from sheets_integration import GoogleSheetsClient

SHEET_ID = "10s6UPA9QS9CDNOi1ds9Uvqy2hVZ49s1ZFSMCQxQCxtM"
CSV_FILE = "web4guru_leads_7800_8800.csv"

def upload_csv():
    print(f"Loading CSV data from {CSV_FILE}...")
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            data = list(reader)
    except FileNotFoundError:
        print(f"Error: {CSV_FILE} not found.")
        sys.exit(1)
        
    print(f"Loaded {len(data)} rows from CSV.")
    
    # Check and fix headers for accountants
    headers = data[0]
    fixed_headers = []
    for h in headers:
        if h == "school_name":
            fixed_headers.append("company_name")
        elif h == "school_type":
            fixed_headers.append("industry")
        else:
            fixed_headers.append(h)
    
    data[0] = fixed_headers
    print(f"Verified Correct Headers: {data[0]}")
    
    print("Connecting to Google Sheets...")
    try:
        # Initialize client. We don't need input_sheet_name to open by ID directly
        client = GoogleSheetsClient()
        client._authenticate()
        
        print(f"Opening Google Sheet with ID: {SHEET_ID}...")
        spreadsheet = client.client.open_by_key(SHEET_ID)
        worksheet = spreadsheet.sheet1
        
        print("Clearing existing data in the sheet...")
        worksheet.clear()
        
        print("Uploading data...")
        # Upload in batches to avoid payload limits if it was huge, but 1000 rows is fine for a single update
        worksheet.update('A1', data)
        
        print("✅ Data uploaded successfully!")
        
    except Exception as e:
        print(f"❌ Error uploading data: {e}")

if __name__ == "__main__":
    upload_csv()
