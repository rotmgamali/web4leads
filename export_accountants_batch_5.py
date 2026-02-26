import sys
import os
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sheets_integration import GoogleSheetsClient

def export_accountants_batch_5():
    print("🚀 Exporting Final Accountant Leads Batch #5 (11800-12847)...")
    sheets = GoogleSheetsClient()
    sheets.setup_sheets()
    
    # 1. Open Master Sheet
    master_ss = sheets.client.open_by_key('1G7chSKGCdc4_uzbd2iPmHiwv0XxbRGtb11CmEKPhPQU')
    master_ws = master_ss.sheet1
    
    # 2. Extract Rows (11800 to 12847)
    headers = master_ws.row_values(1)
    rows = master_ws.get_values('A11800:O12847')
    
    print(f"📊 Extracted {len(rows)} rows.")
    
    # 3. Format Headers for Template Compatibility
    new_headers = list(headers)
    if 'School Name' in new_headers:
        idx = new_headers.index('School Name')
        new_headers[idx] = 'company_name'
    if 'School Type' in new_headers:
        idx = new_headers.index('School Type')
        new_headers[idx] = 'industry'
        
    # 4. Use Existing Campaign Leads Sheet
    target_ss_id = '13Ogz2xvyjns5ezkBQcrggRvDFPONWvPMezJXzIY6wTA'
    worksheet_name = "Batch #5 (11800-12847)"
    print(f"✨ Adding worksheet to existing spreadsheet: {worksheet_name}")
    
    try:
        target_ss = sheets.client.open_by_key(target_ss_id)
        
        # Check if worksheet exists, delete if so to overwrite
        try:
            existing_ws = target_ss.worksheet(worksheet_name)
            target_ss.del_worksheet(existing_ws)
            print(f"🗑️ Deleted existing worksheet: {worksheet_name}")
        except:
            pass
            
        new_ws = target_ss.add_worksheet(title=worksheet_name, rows=len(rows)+1, cols=len(new_headers))
        
        # 5. Upload
        data_to_upload = [new_headers] + rows
        new_ws.update('A1', data_to_upload)
        
        print(f"✅ Final Upload Complete!")
        print(f"🔗 URL: {target_ss.url}")
        
    except Exception as e:
        print(f"❌ Error during final upload: {e}")

if __name__ == "__main__":
    export_accountants_batch_5()
