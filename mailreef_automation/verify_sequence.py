import os
import sys
import sqlite3
from datetime import datetime, timedelta

# Add paths
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)
sys.path.insert(0, current_dir)

from contact_manager import ContactManager
from scheduler import EmailScheduler
from logger_util import get_logger
import automation_config

logger = get_logger("VERIFY_SCRIPT")

DB_PATH = "test_sequence.db"

def setup_test_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    cm = ContactManager(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. New Lead (Stage 1 pending)
    c.execute("INSERT INTO contacts (email, first_name, status) VALUES (?, ?, ?)", 
              ('new@test.com', 'New', 'active'))
    
    # 2. Follow-up Lead (Stage 1 sent 5 days ago, Stage 2 pending)
    c.execute("INSERT INTO contacts (email, first_name, status) VALUES (?, ?, ?)", 
              ('followup@test.com', 'Followup', 'active'))
    last_id = c.lastrowid
    
    five_days_ago = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d %H:%M:%S')
    c.execute("INSERT INTO send_log (contact_id, inbox_id, sequence_stage, sent_at, status) VALUES (?, ?, ?, ?, ?)",
              (last_id, 1, 1, five_days_ago, 'sent'))
    
    conn.commit()
    conn.close()
    return cm

def main():
    print("\n" + "="*50)
    print("VERIFYING SEQUENCE LOGIC & PRIORITIZATION")
    print("="*50)
    
    cm = setup_test_db()
    
    class MockMailreef:
        def send_email(self, **kwargs):
            print(f"  [MOCK SEND] To: {kwargs['to_email']}, Subject: {kwargs['subject']}")
            return {"message_id": "mock_id"}
    
    class ConfigWrapper:
        pass
    cfg = ConfigWrapper()
    for name in dir(automation_config):
        if not name.startswith("__"): setattr(cfg, name, getattr(automation_config, name))

    scheduler = EmailScheduler(MockMailreef(), cm, cfg)
    
    print("\nStep 1: Checking for Stage 2 prospects (Expect 'Followup')...")
    stage2 = cm.get_pending_for_inbox(inbox_id=1, count=1, sequence_stage=2)
    if stage2 and stage2[0]['email'] == 'followup@test.com':
        print("  ✓ Correct: Found lead due for follow-up.")
    else:
        print(f"  ✗ Error: Stage 2 query failed. Result: {stage2}")

    print("\nStep 2: Testing Scheduler Prioritization (Stage 2 takes precedence)...")
    # This should trigger a Stage 2 send first
    scheduler._execute_slot(inbox_id=1, scheduled_time=datetime.now())
    
    # Record that send for the follow-up lead so they are no longer pending
    # (Actually execute_send does this in the real scheduler)
    
    print("\nStep 3: Checking for Stage 1 (Expect 'New' after Stage 2 is done)...")
    # Since we didn't actually clear Stage 2 in the DB for this test script, 
    # Stage 2 will still be found. We'll manually mark it as sent in send_log for Stage 2.
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO send_log (contact_id, inbox_id, sequence_stage, status) VALUES ((SELECT id FROM contacts WHERE email='followup@test.com'), 1, 2, 'sent')")
    conn.commit()
    conn.close()
    
    # Now it should pick Stage 1
    scheduler._execute_slot(inbox_id=1, scheduled_time=datetime.now())

    print("\n" + "="*50)
    print("VERIFICATION COMPLETE")
    print("="*50)
    
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

if __name__ == "__main__":
    main()
