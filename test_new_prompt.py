
import sys
import os
import logging
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from generators.email_generator import EmailGenerator
from sheets_integration import GoogleSheetsClient

# Configure logging to stdout
logging.basicConfig(level=logging.INFO)


def test_generation():
    # 1. Fetch Real Lead
    print("Connecting to Google Sheets...")
    
    try:
        client = GoogleSheetsClient(input_sheet_name="Web4Guru Accountants - Campaign Leads")
        client.setup_sheets()
        
        # FETCH ROW 7754 (Next lead)
        pending_leads = client.get_pending_leads(limit=1, min_row=7754) 
        
        if not pending_leads:
            print("❌ No leads found starting from row 7754.")
            return

        lead_data = pending_leads[0]
        print(f"\n✅ Fetched Lead: {lead_data.get('email')} (Row {lead_data.get('_row')})")
        print(f"   Name: {lead_data.get('first_name')} {lead_data.get('last_name')}")
        print(f"   Company: {lead_data.get('business_name')}")
        print(f"   Location: {lead_data.get('city')}, {lead_data.get('state')}")
        
        # 2. Enrichment (Mock or Real)
        # Different context to prove AI adaptability
        enrichment_data = {
            "website_content": f"""
            About {lead_data.get('business_name') or 'This Firm'}:
            We are the leading CPAs for the Construction Industry in {lead_data.get('city')}.
            Specializing in job costing, WIP reports, and contractor tax credits.
            Helping builders build wealth since 2005.
            """
        }
    except Exception as e:
        print(f"❌ Error fetching lead: {e}")
        return

    # 3. Real Generation (No Mocks)
    print("\n" + "="*50)
    print("STARTING REAL GENERATION (Live OpenAI Call)")
    print("="*50)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n⚠️  OPENAI_API_KEY not found in environment.")
        api_key = input("Please enter your OpenAI API Key to run the test: ").strip()
        if not api_key:
            print("❌ No API key provided. Cannot run test.")
            return
        os.environ["OPENAI_API_KEY"] = api_key

    try:
        # Initialize generator normally
        generator = EmailGenerator(templates_dir="templates")
        
        # Generate Email
        print("Calling OpenAI...")
        result = generator.generate_email(
            campaign_type="school", 
            sequence_number=1,
            lead_data=lead_data,
            enrichment_data=enrichment_data,
            sender_email="andrew@web4guru.com"
        )
        
        print("\n" + "-"*30)
        print(f"SUBJECT: {result['subject']}")
        print("-"*30)
        print(result['body'])
        print("-"*30 + "\n")
        
    except Exception as e:
        print(f"\n❌ Generation Failed: {e}")
    
    print("\n" + "-"*30)
    print(f"SUBJECT: {result['subject']}")
    print("-"*30)
    print(result['body'])
    print("-"*30 + "\n")

if __name__ == "__main__":
    test_generation()
