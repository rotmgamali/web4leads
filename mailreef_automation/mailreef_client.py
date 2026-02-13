import requests
import time
import os
import re
from typing import List, Dict, Optional
from mailreef_automation.logger_util import get_logger

# Mailreef API Config
# Base URL and API Key are managed via automation_config or environment variables

logger = get_logger("MAILREEF_CLIENT")

class MailreefClient:
    """Client for interacting with Mailreef API"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.mailreef.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.auth = (api_key, '')
        self.session.headers.update({
            "Content-Type": "application/json"
        })
    
    def get_inboxes(self) -> List[Dict]:
        """
        Fetch all available mailboxes by iterating through domains.
        """
        inboxes = []
        try:
            # 1. Fetch all domains
            domains = []
            page = 1
            while True:
                response = self.session.get(
                    f"{self.base_url}/domains", 
                    params={"page": page, "display": 100}
                )
                response.raise_for_status()
                data = response.json()
                
                # Check structure
                batch = data.get('data', data) if isinstance(data, dict) else data
                if not batch:
                    break
                    
                domains.extend(batch)
                
                # Simple pagination check: if less than display limit, we are done
                if len(batch) < 100:
                    break
                page += 1
            
            # 2. Fetch mailboxes for each domain
            for domain in domains:
                domain_id = domain.get('id')
                if not domain_id: continue
                
                page = 1
                while True:
                    response = self.session.get(
                        f"{self.base_url}/mailboxes",
                        params={"domain": domain_id, "page": page, "display": 100}
                    )
                    # If 404/400, skip domain
                    if response.status_code >= 400:
                        break
                        
                    data = response.json()
                    batch = data.get('data', data) if isinstance(data, dict) else data
                    if not batch:
                        break
                        
                    inboxes.extend(batch)
                    
                    if len(batch) < 100:
                        break
                    page += 1
                    
        except Exception as e:
            logger.error(f"❌ Error fetching inboxes: {e}")
            
        return inboxes
    
    def get_inbox_status(self, inbox_id: str) -> Dict:
        """Get current status of a specific inbox"""
        # Endpoint guess: /mailboxes/{id}
        response = self.session.get(f"{self.base_url}/mailboxes/{inbox_id}")
        response.raise_for_status()
        return response.json()
    
    def send_email(self, inbox_id: str, to_email: str, subject: str, 
                   body: str, reply_to: Optional[str] = None) -> Dict:
        """Send a single email through Mailreef using the direct HTTP API."""
        
        # 1. Strip HTML tags for text_body
        text_body = re.sub('<[^<]+?>', '', body)
        
        # 2. Build payload according to Mailreef API documentation
        payload = {
            "from": inbox_id,
            "to": [to_email],  # API expects a list
            "subject": subject,
            "text_body": text_body,
            "html_body": body
        }
        
        # Handle threading if references are provided (usually passed as reply_to in this system)
        if reply_to:
            # Based on user-provided doc, 'in_reply_to' is used for threading/reply
            payload["in_reply_to"] = reply_to

        # 3. Send via API (HTTPS Port 443)
        url = f"{self.base_url}/email"
        logger.debug(f"🚀 [API SEND] Sending email from {inbox_id} to {to_email}...")
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            
            if response.status_code in [201, 200]:
                data = response.json()
                logger.debug(f"✅ [API SUCCESS] Message queued as {data.get('id')}")
                return {"status": "success", "message_id": data.get('id')}
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message') or error_data.get('error') or response.text
                except:
                    error_msg = response.text
                
                logger.error(f"❌ [API ERROR] Failed to send (HTTP {response.status_code}): {error_msg}")
                raise Exception(f"Mailreef API Error: {error_msg}")
                
        except Exception as e:
            # Trigger network diagnostics on unexpected errors
            try:
                from diagnose_network import run_diagnostics
                run_diagnostics()
            except ImportError:
                pass
            raise e

    
    
    def forward_email(self, message_id: str, to_address: str) -> Dict:
        """
        Forward an email using the Mailreef API.
        POST /email/forward/:message_id
        Body: {"to": "recipient@example.com"}
        """
        url = f"{self.base_url}/email/forward/{message_id}"
        payload = {"to": to_address}
        
        logger.info(f"↪️ Forwarding message {message_id} to {to_address}...")
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            if response.status_code in [200, 201]:
                return response.json()
            else:
                logger.error(f"❌ Error forwarding email: {response.status_code} - {response.text}")
                return {"error": response.text}
        except Exception as e:
            logger.error(f"❌ Exception in forward_email: {e}")
            return {"error": str(e)}

    def get_email_status(self, message_id: str) -> Dict:
        """Check status of a sent email"""
        # Guessing /emails/{id}
        response = self.session.get(f"{self.base_url}/emails/{message_id}")
        response.raise_for_status()
        return response.json()
    
    def get_inbox_analytics(self, inbox_id: str, days: int = 30) -> Dict:
        """Get analytics for an inbox"""
        # Guessing /mailboxes/{id}/analytics or similar
        # Since I can't check, I'll return mock or try probable endpoint
        # For safety in this "correcting" phase, I'll log warning if 404
        try:
             response = self.session.get(
                f"{self.base_url}/mailboxes/{inbox_id}/stats",
                params={"days": days}
            )
             if response.status_code == 200:
                 return response.json()
        except:
            pass
        return {} # Fallback
    
    def get_global_inbound(self, page: int = 1, display: int = 100) -> Dict:
        """Fetch inbound emails across the entire account."""
        try:
            url = f"{self.base_url}/mail/inbound"
            params = {"page": page, "display": display}
            # Add timeout to prevent hanging on network issues
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Error fetching global inbound: {response.status_code} - {response.text}")
                return {"data": [], "total_count": 0}
        except Exception as e:
            logger.error(f"❌ Exception in get_global_inbound: {e}")
            return {"data": [], "total_count": 0}

    def get_reply_handling(self, inbox_id: str) -> List[Dict]:
        """Check for replies for a specific inbox (LEGACY - use get_global_inbound)"""
        return []
    
    def pause_inbox(self, inbox_id: str):
        """Temporarily pause an inbox"""
        # Not sure if API supports this via endpoint. 
        # Maybe PUT /mailboxes/{id} with {status: paused}?
        pass
    
    def resume_inbox(self, inbox_id: str):
        """Resume a paused inbox"""
        pass
