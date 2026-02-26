
import logging
from sheets_integration import GoogleSheetsClient

# Configure logging to stdout
logging.basicConfig(level=logging.INFO)

def diagnose_sheets():
    print("="*50)
    print("DIAGNOSING GOOGLE SHEETS CONNECTION")
    print("="*50)
    
    try:
        sheets = GoogleSheetsClient()
        sheets.setup_sheets()
        
        print("\n[1] Sheet Info:")
        print(f"Input Sheet Name: {sheets.input_sheet.title}")
        print(f"Sheet URL: {sheets.input_sheet.url}")
        
        worksheet = sheets.input_sheet.sheet1
        print(f"Worksheet Name: {worksheet.title}")
        
        print("\n[2] Fetching First 5 Raw Records...")
        raw_records = worksheet.get_all_records()
        print(f"Total Rows Found: {len(raw_records)}")
        
        if len(raw_records) > 0:
            print("\nFirst Record Keys (Headers):")
            print(list(raw_records[0].keys()))
            
            print("\nFirst Record Sample:")
            print(raw_records[0])
            
            # Check row 7753 index if exists
            target_index = 7753 - 2 # 1-based index, minus 1 for 0-based list, minus 1 for header row? 
            # get_all_records returns list of dicts. Row 2 in sheet is index 0.
            # So Row 7753 is index 7751.
            
            if len(raw_records) > 7751:
                print(f"\n[3] Record at Row 7753 (Index 7751):")
                print(raw_records[7751])
            else:
                print(f"\n[3] Sheet only has {len(raw_records)} records, cannot reach row 7753.")
        else:
            print("\n[WARNING] Sheet appears to be empty!")

    except Exception as e:
        print(f"\n[ERROR] Diagnostic failed: {e}")

if __name__ == "__main__":
    diagnose_sheets()
