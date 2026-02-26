import json
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sheets_integration import GoogleSheetsClient
from mailreef_automation.automation_config import CAMPAIGN_PROFILES

def apply_matches():
    print("🚀 Applying High-Confidence Audit Matches to Tracking Sheet...")
    
    # 1. Load Matches
    matches_path = Path("high_confidence_matches.json")
    if not matches_path.exists():
        print("❌ Error: high_confidence_matches.json not found.")
        return
        
    with open(matches_path, 'r') as f:
        matches = json.load(f)
        
    print(f"📊 Found {len(matches)} matches to log.")
    
    # 2. Setup Sheets
    sheets = GoogleSheetsClient(
        input_sheet_name=CAMPAIGN_PROFILES['IVYBOUND']['input_sheet'],
        replies_sheet_id=CAMPAIGN_PROFILES['IVYBOUND']['replies_sheet_id']
    )
    sheets.setup_sheets()
    
    # 3. Log each match
    success_count = 0
    for m in matches:
        # Map audit keys to log_reply keys
        reply_data = {
            'received_at': m.get('received_at'),
            'from_email': m.get('from'),
            'from_name': '',  # Audit doesn't capture name usually
            'subject': m.get('subject'),
            'snippet': m.get('body_preview'),
            'thread_id': m.get('thread_id'),
            'sentiment': 'neutral',
            'action_taken': 'Audit Recovered',
            'notes': f"Matched via Comprehensive Audit ({m.get('match_reason')})"
        }
        
        try:
            sheets.log_reply(reply_data)
            success_count += 1
            if success_count % 10 == 0:
                print(f"✅ Logged {success_count} matches...")
        except Exception as e:
            print(f"⚠️ Error logging match from {m.get('from')}: {e}")
            
    print(f"🏆 Successfully logged {success_count} new interactions.")

if __name__ == "__main__":
    apply_matches()
