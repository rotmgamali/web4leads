"""
Deliverability monitoring and alerting
Ensures sender reputation stays healthy
"""

import time
from datetime import datetime
from threading import Thread

class DeliverabilityMonitor:
    """Monitors deliverability metrics and adjusts sending"""
    
    def __init__(self, mailreef_client, config):
        self.mailreef = mailreef_client
        self.config = config
        self.is_running = False
        self.alert_thresholds = {
            "bounce_rate": 0.05,  # Alert if bounce rate > 5%
            "complaint_rate": 0.01,  # Alert if complaint rate > 1%
            # "open_rate_min": 0.20,  # Alert if open rate < 20%
            # "reply_rate_min": 0.02,  # Alert if reply rate < 2%
        }
        self.thread = None
    
    def start(self):
        """Start the monitoring loop"""
        if not self.is_running:
            self.is_running = True
            self.thread = Thread(target=self._monitor_loop)
            self.thread.daemon = True
            self.thread.start()
            print("Deliverability monitor started")
    
    def stop(self):
        """Stop monitoring"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("Deliverability monitor stopped")
    
    def _monitor_loop(self):
        """Continuous monitoring of deliverability metrics"""
        while self.is_running:
            try:
                self.check_all_inboxes()
                # Check every hour
                for _ in range(3600):
                    if not self.is_running: break
                    time.sleep(1)
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(300)  # Wait 5 minutes on error
    
    def check_all_inboxes(self):
        """Check all inboxes for health issues"""
        try:
            inboxes = self.mailreef.get_inboxes()
            
            for inbox in inboxes:
                if not self.is_running: break
                
                if inbox.get("id") in self.config.INBOX_PAUSED_IDS:
                    continue
                    
                analytics = self.mailreef.get_inbox_analytics(inbox.get("id"), days=7)
                
                bounce_rate = analytics.get("bounce_rate", 0)
                if bounce_rate > self.alert_thresholds["bounce_rate"]:
                    self._handle_high_bounce(inbox.get("id"), bounce_rate)
                
                complaint_rate = analytics.get("complaint_rate", 0)
                if complaint_rate > self.alert_thresholds["complaint_rate"]:
                    self._handle_high_complaints(inbox.get("id"), complaint_rate)
        except Exception as e:
            print(f"Error checking inboxes: {e}")
    
    def _handle_high_bounce(self, inbox_id, rate):
        """Handle inbox with high bounce rate"""
        # Pause the inbox
        try:
            self.mailreef.pause_inbox(inbox_id)
            print(f"ALERT: Inbox {inbox_id} paused for high bounce rate: {rate}")
        except Exception as e:
             print(f"Failed to pause inbox {inbox_id}: {e}")
    
    def _handle_high_complaints(self, inbox_id, rate):
        """Handle inbox with high complaint rate"""
        # Immediately pause the inbox
        try:
            self.mailreef.pause_inbox(inbox_id)
            print(f"CRITICAL: Inbox {inbox_id} paused for spam complaints: {rate}")
        except Exception as e:
            print(f"Failed to pause inbox {inbox_id}: {e}")
