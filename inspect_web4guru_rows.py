import gspread
from sheets_integration import GoogleSheetsClient

SOURCE_SHEET_ID = "15i4gHk9w45i5jHk... wait let me find the ID"
# Actually let's just list the sheets first to be sure of the name
def inspect_rows():
    print("Connecting...")
    client = GoogleSheetsClient()
    client.setup_sheets()
    
    print("Listing available sheets...")
    try:
        sheets = client.client.list_spreadsheet_files()
        for s in sheets:
            print(f"Found Sheet: {s['name']} (ID: {s['id']})")
            if "Web4Guru" in s['name'] and "Leads" in s['name']:
               SOURCE_SHEET_NAME = s['name']
               print(f"--> MATCH! Using {SOURCE_SHEET_NAME}")
               sheet = client.client.open_by_key(s['id'])
               ws = sheet.sheet1
               break
    except Exception as e:
        print(f"Error listing: {e}")
        # Fallback to try opening by name directly if list fails
        try:
             sheet = client.client.open("Web4Guru - Campaign Leads")
             ws = sheet.sheet1
        except:
             return

    print("Fetching all values (this might take a moment)...")
    all_values = ws.get_all_values()
    print(f"Total rows: {len(all_values)}")
    
    start_row = 7000
    end_row = 7005
    
    print(f"\n--- EXTRACTING ROWS {start_row} to {end_row} ---")
    # Python list slicing is 0-indexed, but sheets are 1-indexed.
    # Row 1 is header (index 0).
    # Row 7000 is index 6999.
    
    if len(all_values) > start_row:
        for i in range(start_row, min(end_row, len(all_values))):
            print(f"Row {i+1}: {all_values[i]}")
    else:
        print("Sheet has fewer than 7000 rows.")

if __name__ == "__main__":
    inspect_rows()
