import sys
import json
import time
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from mailreef_automation.mailreef_client import MailreefClient
from mailreef_automation.automation_config import MAILREEF_API_KEY

def scan_inbound():
    print("🔎 Scanning Errorskin Inbound for 'inquiry' and 'question' subjects...")
    
    mailreef = MailreefClient(api_key=MAILREEF_API_KEY)
    
    inquiry_replies = []
    question_replies = []
    
    page = 1
    total_scanned = 0
    
    while True:
        print(f"  📡 Page {page}...")
        try:
            res = mailreef.get_global_inbound(page=page, display=100)
            messages = res.get('data', [])
            if not messages:
                break
                
            for msg in messages:
                total_scanned += 1
                subject = str(msg.get('subject_line', '')).strip()
                subject_lower = subject.lower()
                from_email = str(msg.get('from_email', '')).strip()
                if '<' in from_email:
                    from_email = from_email.split('<')[-1].split('>')[0].strip()
                body = str(msg.get('body_text', '')).strip()
                ts = msg.get('ts', 0)
                date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M') if ts else 'Unknown'
                
                entry = {
                    'date': date_str,
                    'from': from_email,
                    'subject': subject,
                    'body_preview': body[:400].replace('\n', ' ')
                }
                
                has_inquiry = 'inquiry' in subject_lower
                has_question = 'question' in subject_lower
                
                if has_inquiry and has_question:
                    # Both words — add to inquiry (primary) and note it
                    entry['note'] = 'Contains BOTH "inquiry" and "question"'
                    inquiry_replies.append(entry)
                elif has_inquiry:
                    inquiry_replies.append(entry)
                elif has_question:
                    question_replies.append(entry)
            
            page += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"  ❌ Error on page {page}: {e}")
            time.sleep(2)
            page += 1
    
    print(f"\n📊 Scan Complete!")
    print(f"   Total Scanned: {total_scanned}")
    print(f"   'Inquiry' Matches: {len(inquiry_replies)}")
    print(f"   'Question' Matches: {len(question_replies)}")
    print(f"   Combined Total: {len(inquiry_replies) + len(question_replies)}")
    
    # Sort both lists by date (newest first)
    inquiry_replies.sort(key=lambda x: x['date'], reverse=True)
    question_replies.sort(key=lambda x: x['date'], reverse=True)
    
    # Generate Markdown Report
    report_lines = []
    report_lines.append("# Errorskin Inbound Replies: Inquiry & Question Analysis\n")
    report_lines.append(f"**Scan Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report_lines.append(f"**Total Emails Scanned**: {total_scanned}")
    report_lines.append(f"**Total Matching Emails**: {len(inquiry_replies) + len(question_replies)}\n")
    
    report_lines.append("| Category | Count |")
    report_lines.append("| --- | --- |")
    report_lines.append(f"| 📋 **\"Inquiry\"** in Subject | {len(inquiry_replies)} |")
    report_lines.append(f"| ❓ **\"Question\"** in Subject | {len(question_replies)} |")
    report_lines.append(f"| **Total** | {len(inquiry_replies) + len(question_replies)} |\n")
    
    # --- INQUIRY SECTION ---
    report_lines.append("---\n")
    report_lines.append(f"## 📋 Emails with \"Inquiry\" in Subject ({len(inquiry_replies)})\n")
    if inquiry_replies:
        report_lines.append("| # | Date | From | Subject |")
        report_lines.append("| --- | --- | --- | --- |")
        for idx, r in enumerate(inquiry_replies, 1):
            note = f" ⚡ {r.get('note', '')}" if r.get('note') else ""
            report_lines.append(f"| {idx} | {r['date']} | {r['from']} | {r['subject']}{note} |")
    else:
        report_lines.append("*No emails found with \"inquiry\" in the subject.*")
    
    # --- QUESTION SECTION ---
    report_lines.append("\n---\n")
    report_lines.append(f"## ❓ Emails with \"Question\" in Subject ({len(question_replies)})\n")
    if question_replies:
        report_lines.append("| # | Date | From | Subject |")
        report_lines.append("| --- | --- | --- | --- |")
        for idx, r in enumerate(question_replies, 1):
            report_lines.append(f"| {idx} | {r['date']} | {r['from']} | {r['subject']} |")
    else:
        report_lines.append("*No emails found with \"question\" in the subject.*")
    
    # --- DETAILED BODY PREVIEWS ---
    report_lines.append("\n---\n")
    report_lines.append("## 📝 Detailed Body Previews\n")
    
    report_lines.append("### 📋 Inquiry Replies\n")
    for idx, r in enumerate(inquiry_replies, 1):
        report_lines.append(f"**{idx}. {r['from']}** — _{r['date']}_")
        report_lines.append(f"> **Subject**: {r['subject']}")
        report_lines.append(f"> {r['body_preview'][:300]}\n")
    
    report_lines.append("### ❓ Question Replies\n")
    for idx, r in enumerate(question_replies, 1):
        report_lines.append(f"**{idx}. {r['from']}** — _{r['date']}_")
        report_lines.append(f"> **Subject**: {r['subject']}")
        report_lines.append(f"> {r['body_preview'][:300]}\n")
    
    report_path = BASE_DIR / 'errorskin_inquiry_question_report.md'
    with open(report_path, 'w') as f:
        f.write('\n'.join(report_lines))
    
    print(f"\n✅ Report saved to {report_path}")
    
    # Also save raw JSON for programmatic use
    with open(BASE_DIR / 'errorskin_matches.json', 'w') as f:
        json.dump({'inquiry': inquiry_replies, 'question': question_replies}, f, indent=2)

if __name__ == "__main__":
    scan_inbound()
