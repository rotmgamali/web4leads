import requests
import logging
import json
import os
import sys

# Add project root path for config import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import config
    # Fallback if config import fails or attrs missing
    TOKEN = getattr(config, 'TELEGRAM_BOT_TOKEN', None)
    CHAT_ID = getattr(config, 'TELEGRAM_CHAT_ID', None)
except ImportError:
    TOKEN = None
    CHAT_ID = None

class TelegramNotifier:
    def __init__(self, token=None, chat_id=None):
        self.token = token or TOKEN
        self.chat_id = chat_id or CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else None
        self.logger = logging.getLogger("TELEGRAM_NOTIFIER")

    def send_message(self, message: str):
        """Send a message to the configured chat"""
        if not self.token:
            self.logger.warning("No Telegram token configured. Alert suppressed.")
            return False
            
        if not self.chat_id:
            # Try to auto-discover
            if not self._discover_chat_id():
                self.logger.warning("No Telegram Chat ID known. Alert suppressed.")
                return False

        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True
            else:
                self.logger.error(f"Failed to send Telegram alert: {resp.text}")
                return False
        except Exception as e:
            self.logger.error(f"Telegram connection error: {e}")
            return False

    def _discover_chat_id(self):
        """Attempt to auto-discover chat ID from updates"""
        if not self.base_url: return False
        
        try:
            url = f"{self.base_url}/getUpdates"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            
            if not data.get('ok'):
                return False
                
            results = data.get('result', [])
            if results:
                # Get the most recent message's chat ID
                last_msg = results[-1]
                chat = last_msg.get('message', {}).get('chat', {})
                discovered_id = chat.get('id')
                
                if discovered_id:
                    self.chat_id = str(discovered_id)
                    self.logger.info(f"✅ Auto-discovered Telegram Chat ID: {self.chat_id}")
                    # In a real persistence layer, we'd save this back to .env or config
                    return True
            
            return False
        except Exception:
            return False

class TelegramLogHandler(logging.Handler):
    """Sends log records to Telegram"""
    def __init__(self, notifier):
        super().__init__()
        self.notifier = notifier

    def emit(self, record):
        try:
            msg = self.format(record)
            level_emoji = "🚨" if record.levelno >= 50 else "⚠️"
            
            # Prevent loops
            if "Telegram" in msg:
                return
                
            text = f"{level_emoji} *{record.levelname}* from *{record.name}*\n\n`{msg}`"
            
            # Send (blocking is acceptable for critical alerts to ensure dispatch)
            self.notifier.send_message(text)
        except Exception:
            self.handleError(record)

# Quick test if run directly
if __name__ == "__main__":
    notifier = TelegramNotifier()
    if notifier.token:
        print(f"Testing with Token: {notifier.token[:5]}...")
        if notifier.send_message("🔔 *System Alert Verification*\n\nThis is a test of the Ivybound Production Alert System."):
            print("✅ Message sent successfully!")
        else:
            print("❌ Failed to send message. Make sure you have messaged the bot at least once.")
            # Print getUpdates for debugging
            print("Checking updates...")
            print(notifier._discover_chat_id())
    else:
        print("No token found in config.")
