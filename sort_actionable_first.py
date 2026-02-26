import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sheets_integration import GoogleSheetsClient

def sort_sheet_actionable_first():
    print("🚀 Sorting Ivy Bound Replies Sheet...")
    
    sheets = GoogleSheetsClient()
    ss = sheets.client.open_by_key('1jeLkdufaMub4rylaPnoTQZwDiLpHmut5hcQQStl8UxI')
    ws = ss.sheet1
    
    # We will use the Google Sheets API batchUpdate to sort the range.
    # This ensures that cell formatting (background colors) moves with the data.
    
    # get_all_records() or get_all_values() just to get row count if we wanted it
    # but we can sort the whole sheet starting from row 1 (0-indexed).
    
    body = {
        "requests": [
            {
                "sortRange": {
                    "range": {
                        "sheetId": ws.id,
                        "startRowIndex": 1, # Skip header
                    },
                    "sortSpecs": [
                        {
                            "dimensionIndex": 7, # Column H (Sentiment: ACTIONABLE 🟢 / NOT_ACTIONABLE 🔴)
                            "sortOrder": "ASCENDING" # 'ACTIONABLE' comes before 'NOT_ACTIONABLE' alphabetically
                        },
                        {
                            "dimensionIndex": 0, # Column A (Received At: ISO Date)
                            "sortOrder": "DESCENDING" # Newest first
                        }
                    ]
                }
            }
        ]
    }
    
    print("Executing SortRangeRequest (1. Sentiment ASC, 2. Received At DESC)...")
    try:
        ss.batch_update(body)
        print("✅ Sort Complete! Actionable leads are now securely at the top.")
    except Exception as e:
        print(f"❌ Failed to sort sheet: {e}")

if __name__ == "__main__":
    sort_sheet_actionable_first()
