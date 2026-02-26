import os
import re
from collections import defaultdict
from datetime import datetime

LOG_DIRS = [
    "/Users/mac/Desktop/web4leads/mailreef_automation/logs",
    "/Users/mac/Desktop/Ivybound/mailreef_automation/logs"
]

def analyze_logs():
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # regexes
    # e.g.: 2026-02-13 21:27:18 | SCHEDULER            | INFO     | ✅ [SEND SUCCESS] Email sent to lynn@woodrichards.com via inbox alex@mailboxai.online.
    sent_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}).*?\[SEND SUCCESS\] Email sent to ([^\s]+) via inbox ([^\s]+)")
    reply_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}).*?Replying to") # simple check if any reply logic fired wrongly
    
    sent_records = []
    
    for log_dir in LOG_DIRS:
        if not os.path.exists(log_dir):
            continue
            
        for filename in os.listdir(log_dir):
            if filename.endswith(".log"):
                filepath = os.path.join(log_dir, filename)
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if today_str in line:
                            # Check for sends
                            sent_match = sent_pattern.search(line)
                            if sent_match:
                                timestamp, target, sender = sent_match.groups()
                                sent_records.append({
                                    "time": timestamp,
                                    "target": target.lower().strip(),
                                    "sender": sender.lower().strip(),
                                    "file": filename
                                })
                            
                            if "reply" in line.lower() and "sent" in line.lower() and "reply_watcher" not in filename:
                                # Just flag potential reply sends for review
                                if "Sending reply" in line or "Sent reply" in line:
                                    print(f"⚠️ POSSIBlE REPLY SENT in {filename}: {line.strip()}")

    print(f"Found {len(sent_records)} total sent emails today across logs.")
    
    # Check for duplicates: target
    target_counts = defaultdict(list)
    for rec in sent_records:
        target_counts[rec["target"]].append(rec)
        
    duplicates = {k: v for k, v in target_counts.items() if len(v) > 1}
    
    if duplicates:
        print(f"\n❌ FOUND {len(duplicates)} TARGET(S) WITH MULTIPLE EMAILS SENT TODAY! ❌")
        for target, records in list(duplicates.items())[:5]: # Show first 5
            print(f"\nTarget: {target} received {len(records)} emails:")
            for r in records:
                print(f"  - At {r['time']} from {r['sender']} ({r['file']})")
        if len(duplicates) > 5:
            print(f"... and {len(duplicates) - 5} more.")
    else:
        print("\n✅ No duplicate targets found today. Each person received exactly 1 email.")

    # Check for senders hitting the same target (covered by overall duplicate check, but let's check sender distribution)
    sender_targets = defaultdict(set)
    for rec in sent_records:
        sender_targets[rec["sender"]].add(rec["target"])
    
    print(f"\n✅ {len(sender_targets)} unique inboxes sent emails today.")
    
    print("\n--- Audit Complete ---")

if __name__ == "__main__":
    analyze_logs()
