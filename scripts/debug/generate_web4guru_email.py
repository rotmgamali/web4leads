
import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from generators.email_generator import EmailGenerator

def generate_samples():
    print("Generating Web4Guru Campaign Samples...\n")
    
    # 1. EMAIL 1 (GPT Generated)
    print("="*60)
    print("EMAIL 1: INITIAL OUTREACH (GPT-4o Generated via EmailGenerator)")
    print("="*60)
    
    # Initialize generator pointing to the specific templates dir
    # Config says: "templates_dir": "templates/web4guru/accountants"
    generator = EmailGenerator(templates_dir="templates/web4guru/accountants")
    
    lead_data = {
        "first_name": "Jorge", # Assuming principal from Miyares Group
        "last_name": "Miyares",
        "role": "Principal",
        "school_name": "Miyares Group", 
        "company_name": "Miyares Group",
        "city": "Miami",
        "state": "FL",
        "domain": "miyaresgroup.com",
        "website": "miyaresgroup.com"
    }
    
    # Use real scraper by passing empty enrichment data but VALID url in lead_data
    # EmailGenerator will trigger scraper if enrichment_data is empty but URL is present
    enrichment_data = {
        "website_content": "" 
    }
    
    try:
        # Sequence 1
        result = generator.generate_email(
            campaign_type="b2b",
            sequence_number=1,
            lead_data=lead_data,
            enrichment_data=enrichment_data,
            sender_email="andrew@web4guru.com"
        )
        
        print(f"\nSubject: {result['subject']}")
        print(f"\n{result['body']}")
        
    except Exception as e:
        print(f"Error generating Email 1: {e}")
        import traceback
        traceback.print_exc()

    # 2. EMAIL 2 (Deterministic Auto-Reply)
    print("\n" + "="*60)
    print("EMAIL 2: THE PITCH (Deterministic Auto-Reply)")
    print("="*60)
    
    try:
        # Read the template directly
        # Config says: "auto_reply_template": "b2b/general/email_2.txt"
        base_dir = "templates/web4guru/accountants"
        tpl_path = os.path.join(base_dir, "b2b/general/email_2.txt")
        
        with open(tpl_path, "r") as f:
            template = f.read()
            
        # Manually substitute variables as reply_watcher does
        body = template.replace("{{ first_name }}", "John") \
                       .replace("{{ sender_name }}", "Web4Guru Team")
                       
        print(f"\nSubject: Re: {result.get('subject', 'Inquiry')}")
        print(f"\n{body}")
        
    except Exception as e:
        print(f"Error reading Email 2: {e}")

if __name__ == "__main__":
    generate_samples()
