import csv
import gspread
from sheets_integration import GoogleSheetsClient

SOURCE_SHEET_ID = "13Ogz2xvyjns5ezkBQcrggRvDFPONWvPMezJXzIY6wTA" # Web4Guru Accountants
START_ROW = 7800
END_ROW = 8800
OUTPUT_FILE = "web4guru_leads_7800_8800.csv"

def export_to_csv():
    print("Connecting to Google Sheets...")
    client = GoogleSheetsClient()
    client.setup_sheets()
    
    print(f"Opening Source Sheet (ID: {SOURCE_SHEET_ID})...")
    sheet = client.client.open_by_key(SOURCE_SHEET_ID)
    ws = sheet.sheet1
    
    # Get Headers (Row 1)
    print("Fetching headers...")
    headers = ws.row_values(1)
    
    # Get Data Range
    # Note: get_all_values() and slicing locally is often faster/cheaper on quota than range calls if sheet isn't massive.
    # But for 100k rows, range is better.
    # A1 notation: A{START_ROW}:Z{END_ROW} (assuming Z covers all cols)
    
    # Let's verify col count first or just use a safe large range like AZ
    print(f"Fetching rows {START_ROW} to {END_ROW}...")
    # gspread uses 1-based indexing.
    data = ws.get(f"A{START_ROW}:Z{END_ROW}")
    
    print(f"Extracted {len(data)} rows.")
    
    print(f"Writing to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data)
        
    print("Done!")

if __name__ == "__main__":
    export_to_csv()
