import gspread
from mailreef_automation.automation_config import TELEGRAM_CHAT_ID
from sheets_integration import GoogleSheetsClient, INPUT_SHEET_NAME

def transfer_leads():
    print("Connecting to Google Sheets...")
    client = GoogleSheetsClient()
    client.setup_sheets()
    
    # 1. Open Source Sheet
    print(f"Opening source sheet: {INPUT_SHEET_NAME}...")
    source_sheet = client.input_sheet
    source_worksheet = source_sheet.sheet1
    
    # 2. Read Data
    # Get all values (list of lists)
    print("Reading data...")
    all_values = source_worksheet.get_all_values()
    
    if not all_values:
        print("Source sheet is empty.")
        return

    header = all_values[0]
    data = all_values[1:] # Skip header
    
    # Slice first 1000
    rows_to_transfer = data[:1000]
    print(f"Found {len(data)} total rows. Extracting first {len(rows_to_transfer)}...")
    
    # 3. Create New Sheet
    new_sheet_name = "Ivy Bound - First 1000 Export"
    print(f"Creating new sheet: {new_sheet_name}...")
    
    try:
        new_sh = client.client.create(new_sheet_name)
    except Exception as e:
        print(f"Sheet might already exist, trying to open... ({e})")
        new_sh = client.client.open(new_sheet_name)
        
    new_ws = new_sh.sheet1
    new_ws.clear()
    
    # 4. Write Data
    # Combine header + rows
    final_data = [header] + rows_to_transfer
    
    print(f"Writing {len(final_data)} rows to new sheet...")
    new_ws.update(final_data)
    
    # 5. Share/Output
    print(f"Done! New Sheet URL: {new_sh.url}")
    
    # Try to share with a known email if available in config, 
    # but service account created sheets are usually accessible if folder structure is right.
    # We will just output the URL.

if __name__ == "__main__":
    transfer_leads()
