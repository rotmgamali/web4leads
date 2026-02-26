"""
Test script to generate sample emails using the new Accountant campaign prompt.
Picks 3 real leads from the Google Sheet and generates emails for each.
"""
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from generators.email_generator import EmailGenerator
from sheets_integration import GoogleSheetsClient
from mailreef_automation.automation_config import CAMPAIGN_PROFILES

def run_test():
    print("🧪 TEST: Generating 3 sample Accountant emails with the new prompt...\n")
    
    profile = CAMPAIGN_PROFILES["WEB4GURU_ACCOUNTANTS"]
    
    # Setup email generator with the accountant templates directory
    templates_dir = BASE_DIR / profile.get("templates_dir", "templates/web4guru/accountants")
    generator = EmailGenerator(templates_dir=templates_dir)
    
    # Pull a few real leads from the sheet
    sheets = GoogleSheetsClient()
    ss = sheets.client.open("Web4Guru Accountants - Campaign Leads")
    ws = ss.sheet1
    records = ws.get_all_records()
    
    # Pick 3 leads that have website data
    test_leads = []
    for rec in records:
        if rec.get('website') or rec.get('domain'):
            test_leads.append(rec)
            if len(test_leads) >= 3:
                break
    
    if not test_leads:
        print("❌ No leads with websites found in the sheet.")
        return
    
    print(f"Found {len(test_leads)} test leads. Generating emails...\n")
    print("=" * 80)
    
    for i, lead in enumerate(test_leads, 1):
        company = lead.get('company_name') or lead.get('school_name') or lead.get('business_name') or 'Unknown'
        email = lead.get('email', 'unknown')
        city = lead.get('city', 'Unknown')
        
        print(f"\n📧 TEST EMAIL #{i}")
        print(f"   To: {email}")
        print(f"   Company: {company}")
        print(f"   City: {city}")
        print(f"   Website: {lead.get('website') or lead.get('domain')}")
        print("-" * 80)
        
        try:
            result = generator.generate_email(
                campaign_type="b2b",
                sequence_number=1,
                lead_data=dict(lead),
                enrichment_data={},
                sender_email="andrew@web4guru.com"
            )
            
            print(f"\n   📌 SUBJECT: {result['subject']}")
            print(f"\n   📝 BODY:")
            for line in result['body'].split('\n'):
                print(f"   {line}")
            print()
        except Exception as e:
            print(f"   ❌ Error generating email: {e}")
            import traceback
            traceback.print_exc()
        
        print("=" * 80)
    
    print("\n✅ Test complete! Review the emails above for quality.")

if __name__ == "__main__":
    run_test()
