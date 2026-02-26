import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from mailreef_automation.mailreef_client import MailreefClient
from mailreef_automation.automation_config import MAILREEF_API_KEY
from sheets_integration import GoogleSheetsClient

def run_audit():
    print("🕵️ Starting Comprehensive Ivy Bound Inbound Audit...")
    
    # 1. Setup Clients
    sheets = GoogleSheetsClient()
    sheets.setup_sheets()
    mailreef = MailreefClient(api_key=MAILREEF_API_KEY)
    
    # 2. Load Master Leads for Domain/Email Matching
    # Ivy Bound Master Sheet ID: 1G7chSKGCdc4_uzbd2iPmHiwv0XxbRGtb11CmEKPhPQU
    print("📡 Loading master Ivy Bound lead list...")
    master_ss = sheets.client.open_by_key('1G7chSKGCdc4_uzbd2iPmHiwv0XxbRGtb11CmEKPhPQU')
    master_ws = master_ss.sheet1
    all_leads = master_ws.get_all_records()
    
    # 3. Define Generic and Known Warmup Domains
    GENERIC_DOMAINS = {
        "gmail.com", "outlook.com", "yahoo.com", "hotmail.com", "icloud.com", 
        "aol.com", "msn.com", "live.com", "me.com", "googlemail.com"
    }
    
    WARMUP_DOMAIN_PATTERNS = [
        "sendemall", "influu", "savoir", "melnyresults", "atlanticzero", "gcodepad", 
        "marketingsavoir", "rapidfab", "fabunit", "millzone", "blueink", "genup", "aimergeup"
    ]

    lead_emails = set()
    lead_domains = set()
    
    for lead in all_leads:
        email = str(lead.get('email', '')).lower().strip()
        if email and '@' in email:
            lead_emails.add(email)
            domain = email.split('@')[-1].strip()
            if domain and domain not in GENERIC_DOMAINS and len(domain) > 3:
                lead_domains.add(domain)

    print(f"✅ Loaded {len(lead_emails)} lead emails and {len(lead_domains)} private domains.")

    # 4. Load Existing Replies
    replies_ws = sheets.client.open_by_key('1jeLkdufaMub4rylaPnoTQZwDiLpHmut5hcQQStl8UxI').sheet1
    existing_replies = replies_ws.get_all_values()
    existing_thread_ids = {str(row[5]).strip() for row in existing_replies[1:] if len(row) > 5}

    # 5. Scan Mailreef Inbound
    potential_matches = []
    page = 1
    total_scanned = 0
    
    KEYWORDS = ["ivy bound", "sat", "act", "prep", "college", "readiness", "genelle", "casual chat", "prep support"]
    WARMUP_SUBJECTS = ["new joiners guide", "safety protocol", "meeting", "update on office", "weekly progress", "it security", "marketing plan", "audit", "survey", "orientation", "financial planning"]
    
    while True:
        print(f"🔎 Scanning Mailreef Page {page}...")
        try:
            res = mailreef.get_global_inbound(page=page, display=100)
            messages = res.get('data', [])
            if not messages:
                break
                
            for msg in messages:
                total_scanned += 1
                from_email = str(msg.get('from_email', '')).lower().strip()
                if '<' in from_email:
                    from_email = from_email.split('<')[-1].split('>')[0].strip()
                
                body = str(msg.get('body_text', '')).lower()
                subject = str(msg.get('subject_line', '')).lower()
                thread_id = str(msg.get('id', ''))
                
                # A. Identify Match Type
                match_type = None
                if from_email in lead_emails:
                    match_type = "Lead"
                else:
                    msg_domain = from_email.split('@')[-1] if '@' in from_email else ""
                    if msg_domain in lead_domains:
                        match_type = "Domain"
                    elif any(kw in body or kw in subject for kw in KEYWORDS):
                        match_type = "Keyword"

                if match_type:
                    # B. Strict Warmup Filtering
                    sentences = [s for s in body.replace('\n', '.').split('.') if len(s.strip()) > 5]
                    has_thread = any(marker in body for marker in ["from:", "sent:", "to:", "subject:", "wrote:"])
                    
                    is_warmup = False
                    
                    # 1. Warmup Domain Blacklist
                    if any(p in from_email for p in WARMUP_DOMAIN_PATTERNS):
                        is_warmup = True
                    
                    # 2. Generic Domain + Simple Body
                    if any(gen in from_email for gen in GENERIC_DOMAINS):
                        if len(sentences) <= 1 and not has_thread:
                            is_warmup = True
                            
                    # 3. Keyword Match MUST have thread or complexity to be "Authorized"
                    if match_type == "Keyword" and not has_thread and len(sentences) <= 2:
                        is_warmup = True
                        
                    # 4. Filter suspicious subjects that lack thread history
                    if any(ws in subject for ws in WARMUP_SUBJECTS) and not has_thread:
                        is_warmup = True

                    if not is_warmup:
                        status = "NEW" if thread_id not in existing_thread_ids else "ALREADY LOGGED"
                        
                        potential_matches.append({
                            'status': status,
                            'received_at': datetime.fromtimestamp(msg.get('ts', 0)).isoformat(),
                            'from': from_email,
                            'subject': msg.get('subject_line', ''),
                            'body_preview': body[:300].replace('\n', ' '),
                            'thread_id': thread_id,
                            'has_thread': has_thread,
                            'sentence_count': len(sentences),
                            'match_reason': f"{match_type} Match"
                        })

            page += 1
            if page > 50: # Safeguard
                break
            time.sleep(0.2)
        except Exception as e:
            print(f"❌ Error on page {page}: {e}")
            break

    # 5. Save Report
    report_path = "ivybound_audit_report.json"
    with open(report_path, 'w') as f:
        json.dump(potential_matches, f, indent=4)
        
    # Generate Markdown Summary
    md_path = "ivybound_audit_report.md"
    with open(md_path, 'w') as f:
        f.write("# Ivy Bound Inbound Audit Report\n\n")
        f.write(f"**Total Scanned**: {total_scanned}\n")
        f.write(f"**Potential Matches Found**: {len(potential_matches)}\n")
        f.write(f"**New Candidates (Not in Sheet)**: {len([m for m in potential_matches if m['status'] == 'NEW'])}\n\n")
        f.write("| Status | Date | From | Subject | Match Reason |\n")
        f.write("| --- | --- | --- | --- | --- |\n")
        for m in potential_matches:
            f.write(f"| {m['status']} | {m['received_at'][:10]} | {m['from']} | {m['subject']} | {m['match_reason']} |\n")
            
    print(f"✨ Audit complete. Report saved to {md_path}")

if __name__ == "__main__":
    run_audit()
