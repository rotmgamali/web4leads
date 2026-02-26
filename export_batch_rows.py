import gspread
import sys
import os
from datetime import datetime

# Add the project root to the python path to import sheets_integration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
    
from sheets_integration import GoogleSheetsClient

SOURCE_SHEET_ID = "13Ogz2xvyjns5ezkBQcrggRvDFPONWvPMezJXzIY6wTA"
START_ROW = 9800
END_ROW = 10800
TARGET_SS_NAME = f"Web4Guru Leads {START_ROW}-{END_ROW}"

def export_and_upload():
    print(f"🚀 Starting export for leads {START_ROW} to {END_ROW}...")
    
    client = GoogleSheetsClient()
    client.setup_sheets()
    gc = client.client
    
    # 1. Fetch data from source
    print(f"Fetching rows from master sheet (ID: {SOURCE_SHEET_ID})...")
    source_ss = gc.open_by_key(SOURCE_SHEET_ID)
    source_ws = source_ss.sheet1
    
    headers = source_ws.row_values(1)
    fixed_headers = []
    for h in headers:
        if h == "school_name":
            fixed_headers.append("company_name")
        elif h == "school_type":
            fixed_headers.append("industry")
        else:
            fixed_headers.append(h)
    
    data = source_ws.get(f"A{START_ROW}:Z{END_ROW}")
    print(f"Extracted {len(data)} rows.")
    full_data = [fixed_headers] + data
    
    # 2. Get a separate spreadsheet (by create or reuse)
    ss = None
    print(f"Attempting to create/reuse a separate spreadsheet...")
    
    # TRY TO CREATE
    try:
        ss = gc.create(TARGET_SS_NAME)
        ss.share('', perm_type='anyone', role='writer')
        print(f"✅ Created BRAND NEW spreadsheet: {ss.url}")
    except Exception as e:
        print(f"⚠️ Creation failed (Quota?): {e}")
        print("Searching for an existing temporary sheet to repurpose...")
        files = gc.list_spreadsheet_files()
        # Find something we can reuse (like 'web4guru leads 4')
        reusable_id = None
        for f in files:
            name = f['name'].lower()
            # DON'T reuse sheets that we've already labeled with a range
            if "8800-9800" in name or "7800-8800" in name:
                continue
            if "web4guru leads" in name or "untitled" in name:
                reusable_id = f['id']
                break
        
        if reusable_id:
            try:
                ss = gc.open_by_key(reusable_id)
                ss.update_title(TARGET_SS_NAME)
                print(f"♻️ Repurposing existing sheet ({reusable_id}) -> {TARGET_SS_NAME}")
            except Exception as e2:
                print(f"Could not repurpose: {e2}")
        
    if not ss:
        print("❌ CRITICAL: Could not create or find a separate spreadsheet to use.")
        sys.exit(1)

    # 3. Upload data
    print("Uploading data...")
    ws = ss.sheet1
    ws.clear()
    ws.update('A1', full_data)
    
    print(f"\n✨ SUCCESS!")
    print(f"New Spreadsheet URL: {ss.url}")
    print(f"Total Rows: {len(full_data)}")

if __name__ == "__main__":
    export_and_upload()
