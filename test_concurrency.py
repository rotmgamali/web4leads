import threading
import time
from mailreef_automation.scheduler import EmailScheduler
from sheets_integration import GoogleSheetsClient

# Mock Mailreef Client
class MockMailreef:
    def get_inboxes(self):
        return [
            {"id": "inbox1", "email": "sender1@example.com"},
            {"id": "inbox2", "email": "sender2@example.com"},
            {"id": "inbox3", "email": "sender3@example.com"}
        ]
    def send_email(self, *args, **kwargs):
        return {"message_id": "test_123"}

# Mock Config
class MockConfig:
    CAMPAIGN_PROFILES = {
        "TEST": {
            "input_sheet": "Ivy Bound - Campaign Leads", # Using real sheet for test read
            "replies_sheet": "Ivy Bound - Reply Tracking",
            "log_file": "test.log",
            "templates_dir": "templates",
            "campaign_type": "school",
            "inbox_indices": (0, 100)
        }
    }
    
def worker_thread(scheduler, inbox_id, results_list):
    print(f"[{inbox_id}] Thread started. Attempting to get 1 lead...")
    # Give all threads a chance to start and race
    leads = scheduler.select_prospects_for_send(inbox_id, count=1, sequence_stage=1)
    if leads:
        email = leads[0].get('email')
        print(f"[{inbox_id}] Got lead: {email}")
        results_list.append(email)
    else:
        print(f"[{inbox_id}] No leads retrieved.")

def test_concurrency():
    scheduler = EmailScheduler(MockMailreef(), MockConfig(), campaign_profile="TEST")
    # Clear cache to force API call
    scheduler._lead_cache = []
    
    threads = []
    results = []
    
    print("--- STARTING CONCURRENCY TEST ---")
    print("Spawning 3 threads simultaneously to fetch leads...")
    
    for i in range(1, 4):
        inbox_id = f"inbox{i}"
        t = threading.Thread(target=worker_thread, args=(scheduler, inbox_id, results))
        threads.append(t)
    
    # Start all threads essentially at the exact same millisecond
    for t in threads:
        t.start()
        
    for t in threads:
        t.join()
        
    print("\n--- RESULTS ---")
    print(f"Total leads popped: {len(results)}")
    
    duplicates = len(results) - len(set(results))
    if duplicates > 0:
        print(f"❌ TEST FAILED: Overlapping/Duplicate leads detected! ({duplicates} duplicates)")
    else:
        print(f"✅ TEST PASSED: All {len(results)} threads received unique leads.")

if __name__ == "__main__":
    test_concurrency()
