import argparse
import csv
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any, List

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sheets_integration import GoogleSheetsClient
from mailreef_automation import automation_config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("SETUP_SHEETS")

def parse_args():
    parser = argparse.ArgumentParser(description="Import Outscraper Leads to Web4Guru Sheets")
    parser.add_argument("--file", help="Path to Outscraper CSV/XLSX file")
    parser.add_argument("--source-sheet", help="Name of source Google Sheet")
    parser.add_argument("--profile", default="WEB4GURU_ACCOUNTANTS", help="Campaign Profile")
    parser.add_argument("--live", action="store_true", help="Actually write to sheets")
    return parser.parse_args()

def clean_value(val):
    return str(val).strip() if val else ""

def map_outscraper_row(row: Dict) -> Dict:
    """Maps Outscraper columns (from CSV or Sheet) to our schema."""
    # Normalize keys to handle CSV vs Sheet differences
    # Sheet get_all_records might return keys as they appear in header row
    
    # Helper to find key case-insensitively
    def get_val(keys):
        for k in keys:
            for row_k in row.keys():
                if str(row_k).strip().lower() == k.lower():
                    return row[row_k]
        return ""

    email = clean_value(get_val(["Email", "email", "Email Address"]))
    email_status = clean_value(get_val(["Email Validation", "email_validation", "Email Status", "verification_status", "email.emails_validator.status"]))
    
    if not email:
        return None
        
    # Strict Verification Check
    # Outscraper values: "Valid", "Invalid", "Catch-all", "Unknown"
    # User asked for "verified".
    if email_status.lower() not in ["valid", "verified", "safe", "receiving"]: 
         return None

    # Name parsing
    # STRICT: Don't use "Name" or "name" generic keys as they often contain Company Name in B2B results
    full_name = clean_value(get_val(["Full Name", "full_name", "contact_full_name"]))
    first = clean_value(get_val(["First Name", "first_name", "contact_first_name"]))
    last = clean_value(get_val(["Last Name", "last_name", "contact_last_name"]))

    if not first and full_name:
        parts = full_name.split()
        first = parts[0]
        if len(parts) > 1 and not last:
            last = " ".join(parts[1:])
            
    # Fallback: Parse from Email? (User might prefer "Hi there" over "Hi Office")
    # if not first and email:
    #     name_part = email.split('@')[0]
    #     if '.' in name_part:
    #         first = name_part.split('.')[0].title()

    company = clean_value(get_val(["Company", "company", "Business Name", "Start_Date", "name", "Name", "query"])) 
    # In this dataset, 'name' IS the company name.
    
    raw_domain = clean_value(get_val(["Website", "website", "domain", "site"]))
    
    # Strict filter: Ensure we aren't using the Google Business Profile link
    if "google.com" in raw_domain.lower() or "goo.gl" in raw_domain.lower():
        domain = "" # Discard it
    else:
        domain = raw_domain
        
    city = clean_value(get_val(["City", "city", "company_insights.city"]))
    state = clean_value(get_val(["State", "state", "state_code", "company_insights.state"]))
    phone = clean_value(get_val(["Phone", "phone", "contact_phone", "company_phone"]))
    
    categories = clean_value(get_val(["Categories", "categories", "Type", "subtypes"]))
    
    # Context
    role = "Accountant" # Default
    if "Bookkeeper" in categories:
        role = "Bookkeeper"
        
    # Capture all raw data for the "metadata" column
    # Convert dict to string for storage
    import json
    metadata = json.dumps(row, default=str)
    
    return {
        "email": email,
        "first_name": first,
        "last_name": last,
        "role": role,
        "school_name": company, # Mapping Company -> School Name column
        "domain": domain,
        "state": state,
        "city": city,
        "phone": phone,
        "status": "pending",
        "notes": f"Imported from Outscraper. Status: {email_status}",
        "custom_data": metadata # New field
    }

def main():
    args = parse_args()
    
    if not args.file and not args.source_sheet:
        logger.error("Must provide either --file or --source-sheet")
        return

    # 1. Config Check
    if args.profile not in automation_config.CAMPAIGN_PROFILES:
        logger.error(f"Profile {args.profile} not found in automation_config.")
        return

    profile = automation_config.CAMPAIGN_PROFILES[args.profile]
    
    # 2. Setup Sheets
    logger.info(f"Connecting to Google Sheets for {args.profile}...")
    client = GoogleSheetsClient(
        input_sheet_name=profile["input_sheet"],
        replies_sheet_name=profile["replies_sheet"]
    )
    
    urls = client.setup_sheets()
    logger.info(f"Leads Sheet: {urls['input_sheet_url']}")
    logger.info(f"Replies Sheet: {urls['replies_sheet_url']}")
    
    if args.live:
        client.clear_replies()
    
    valid_leads = []
    
    # 3. Read Data
    if args.source_sheet:
        logger.info(f"Reading from Google Sheet: {args.source_sheet}...")
        try:
            source = client.client.open(args.source_sheet).sheet1
            records = source.get_all_records()
            logger.info(f"Fetched {len(records)} rows from source sheet.")
            
            if records:
                print(f"DEBUG: First row keys: {list(records[0].keys())}")
                print(f"DEBUG: First row values: {list(records[0].values())}")

            for row in records:
                mapped = map_outscraper_row(row)
                if mapped:
                    valid_leads.append(mapped)
                    
        except Exception as e:
            logger.error(f"Failed to read source sheet: {e}")
            return

    elif args.file:
        logger.info(f"Reading {args.file}...")
        try:
            with open(args.file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    mapped = map_outscraper_row(row)
                    if mapped:
                        valid_leads.append(mapped)
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            return

    logger.info(f"Found {len(valid_leads)} VERIFIED leads ready for import.")

    # 4. Upload
    if args.live and valid_leads:
        logger.info("Uploading to Google Sheets...")
        
        # Headers matching sheets_integration.py _setup_input_sheet_headers
        # NOTE: metadata/custom_data must be added to sheets_integration.py too if we want a dedicated column
        # Or we can just append it here if the sheet allows loose columns?
        # Better to align with the schema.
        headers = [
            "email", "first_name", "last_name", "role", "school_name", "school_type",
            "domain", "state", "city", "phone", "status", 
            "email_1_sent_at", "email_2_sent_at", "sender_email", "notes", "custom_data"
        ]
        
        # We need to map our dict to this list
        rows_to_append = []
        for lead in valid_leads:
            row_data = []
            for h in headers:
                row_data.append(lead.get(h, ""))
            rows_to_append.append(row_data)
            
        # Append
        # Need to expose the sheet object
        sheet = client.input_sheet.sheet1
        
        # Clear existing? User didn't say clear, but "export all". 
        # Safest is to append or clear-then-append. 
        # Let's append, but maybe check duplicates?
        # For a clean setup, clearing is better if it's a fresh campaign.
        # I'll clear contents (keeping headers).
        if len(valid_leads) > 0:
            sheet.clear()
            # Restore headers
            client._setup_input_sheet_headers()
            
            # Batch append
            chunk_size = 500
            for i in range(0, len(rows_to_append), chunk_size):
                chunk = rows_to_append[i:i+chunk_size]
                logger.info(f"Writing batch {i}-{i+len(chunk)}...")
                sheet.append_rows(chunk)
                
        logger.info("✅ Upload Complete.")
    else:
        logger.info("Dry run complete (or no valid leads). Use --live to upload.")

if __name__ == "__main__":
    main()
