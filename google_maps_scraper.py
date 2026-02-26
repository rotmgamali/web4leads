#!/usr/bin/env python3
"""
Google Maps Scraper for Lead Generation
Scrapes business details from Google Maps and extracts emails from websites.
Integrates with sheets_integration.py to save leads.
"""

import asyncio
import re
import sys
import logging
import time
import random
from typing import List, Dict, Set
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Page, BrowserContext
import nest_asyncio
import dns.resolver
import dns.exception
import smtplib
import socket

# Apply nest_asyncio to allow nested event loops (useful for some envs)
nest_asyncio.apply()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('google_maps_scraper.log')
    ]
)
logger = logging.getLogger(__name__)

# Import existing sheets integration
try:
    from sheets_integration import GoogleSheetsClient
except ImportError:
    logger.error("Could not import GoogleSheetsClient from sheets_integration.py")
    sys.exit(1)

# Regex for email extraction
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
BLOCKLIST_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.css', '.js', '.svg', '.woff', '.woff2')

import csv
from pathlib import Path

class GoogleMapsScraper:
    def __init__(self, headless: bool = True, sheet_name: str = None):
        self.headless = headless
        self.seen_leads: Set[str] = set()
        self.sheets_client = None
        self.csv_file = Path("scraped_leads.csv")
        
        # Try to initialize Sheets Client
        try:
            # Pass custom sheet name if provided
            self.sheets_client = GoogleSheetsClient(input_sheet_name=sheet_name) if sheet_name else GoogleSheetsClient()
            
            # Load existing leads to avoid duplicates
            logger.info(f"Loading existing leads from '{self.sheets_client.input_sheet_name}' to avoid duplicates...")
            
            # Ensure the sheet exists (setup_sheets will create it if needed)
            self.sheets_client.setup_sheets()
            
            existing = self.sheets_client.get_pending_leads(limit=5000) 
            all_records = self.sheets_client._fetch_all_records()
            for record in all_records:
                email = record.get('email', '').lower().strip()
                if email: self.seen_leads.add(email)
                if record.get('business_name'): self.seen_leads.add(record['business_name'].lower().strip())
                if record.get('phone'): self.seen_leads.add(record['phone'].strip())
                if record.get('domain'): self.seen_leads.add(self._clean_domain(record['domain']))
            logger.info(f"Loaded {len(self.seen_leads)} existing unique identifiers.")
            
        except Exception as e:
            logger.warning(f"Failed to initialize Google Sheets (Credentials missing?): {e}")
            logger.warning("Falling back to CSV storage: scraped_leads.csv")
            self.sheets_client = None
            
            # Initialize CSV if needed
            if not self.csv_file.exists():
                with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    # Use schema compatible with sheets
                    writer.writerow([
                        'email', 'first_name', 'last_name', 'role', 'business_name', 
                        'business_type', 'domain', 'state', 'city', 'phone', 'status', 'email_verified', 'notes', 'custom_data'
                    ])

# ... (rest of class) ...



    def _clean_domain(self, url: str) -> str:
        if not url: return ""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path
            return domain.lower().replace('www.', '')
        except:
            return url.lower()

    async def _extract_emails_from_website(self, context: BrowserContext, url: str) -> List[str]:
        """Keep for backward compatibility if needed, but redirects to new system."""
        res = await self._extract_emails_and_names(context, url, "")
        return res["emails"]

    def _extract_name_from_business(self, business_name: str) -> Dict[str, str]:
        """
        Parses a business name to find a potential personal name.
        Example: 'Law Office of John Smith' -> {'first': 'John', 'last': 'Smith'}
        """
        if not business_name:
            return {"first": "", "last": ""}
        
        # Common patterns for law firms
        patterns = [
            r"Law (?:Office|Offices|Firm) of\s+([A-Z][a-z]+)\s+([A-Z][a-z]+)",
            r"([A-Z][a-z]+)\s+([A-Z][a-z]+)\s+(?:Law|Legal|Attorney|Counsel)",
            r"([A-Z][a-z]+)\s+([A-Z][a-z]+)\s+&\s+Associates",
            r"([A-Z][a-z]+)\s+([A-Z][a-z]+)\s+L\.?L\.?C\.?",
            r"([A-Z][a-z]+)\s+([A-Z][a-z]+),\s+P\.?A\.?",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, business_name, re.I)
            if match:
                return {"first": match.group(1), "last": match.group(2)}
        
        return {"first": "", "last": ""}

    async def _extract_person_from_website(self, page: Page) -> Dict[str, str]:
        """
        Scans a page for names associated with legal titles.
        """
        try:
            content = await page.content()
            # Look for "Attorney John Smith", "Partner Jane Doe", etc.
            titles = ["Attorney", "Partner", "Founder", "Principal", "Counsel"]
            for title in titles:
                pattern = rf"{title}\s+([A-Z][a-z]+)\s+([A-Z][a-z]+)"
                match = re.search(pattern, content)
                if match:
                    return {"first": match.group(1), "last": match.group(2)}
        except:
            pass
        return {"first": "", "last": ""}

    async def _extract_emails_and_names(self, context: BrowserContext, url: str, business_name: str) -> Dict:
        """Visit the website and extract emails and potential contact name."""
        emails = set()
        person = {"first": "", "last": ""}
        page = None
        try:
            page = await context.new_page()
            
            # 1. Visit Homepage
            try:
                logger.info(f"Visiting {url} for extraction...")
                await page.goto(url, timeout=15000, wait_until='domcontentloaded')
                content = await page.content()
                
                # Emails
                found_emails = EMAIL_REGEX.findall(content)
                for email in found_emails:
                    if not email.lower().endswith(BLOCKLIST_EXTENSIONS):
                        emails.add(email.lower())
                
                # Names
                person = await self._extract_person_from_website(page)
            except Exception as e:
                logger.warning(f"Failed to load homepage {url}: {e}")
                if page: await page.close()
                return {"emails": [], "person": person}

            # 2. Look for Contact/About pages
            if len(emails) < 2 or not person["first"]:
                try:
                    # Find links
                    contact_link = ""
                    for term in ['contact', 'about', 'attorney', 'team', 'lawyer']:
                        link_el = page.get_by_text(re.compile(term, re.I)).first
                        if await link_el.count() > 0:
                            contact_link = await link_el.get_attribute('href')
                            if contact_link: break
                    
                    if contact_link:
                        # Handle relative URLs
                        if not contact_link.startswith('http'):
                            parsed_orig = urlparse(url)
                            if contact_link.startswith('/'):
                                contact_link = f"{parsed_orig.scheme}://{parsed_orig.netloc}{contact_link}"
                            else:
                                contact_link = url.rstrip('/') + '/' + contact_link
                        
                        logger.info(f"Visiting subpage: {contact_link}")
                        await page.goto(contact_link, timeout=10000, wait_until='domcontentloaded')
                        
                        # Emails
                        content = await page.content()
                        found_emails = EMAIL_REGEX.findall(content)
                        for email in found_emails:
                            if not email.lower().endswith(BLOCKLIST_EXTENSIONS):
                                emails.add(email.lower())
                        
                        # Names (if not found on home)
                        if not person["first"]:
                            person = await self._extract_person_from_website(page)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error extracting from {url}: {e}")
        finally:
            if page: await page.close()
        
        # Filter junk emails
        valid_emails = []
        for email in emails:
            if len(email) < 5 or len(email) > 60: continue
            if 'wixpress' in email or 'sentry' in email or 'example' in email: continue
            valid_emails.append(email)
            
        return {"emails": list(set(valid_emails)), "person": person}

    async def _old_extract_emails_from_website(self, context: BrowserContext, url: str) -> List[str]:
        """Visit the website and extract emails from homepage and contact page."""
        emails = set()
        page = None
        try:
            page = await context.new_page()
            
            # 1. Visit Homepage
            try:
                logger.info(f"Visiting {url} for email extraction...")
                await page.goto(url, timeout=15000, wait_until='domcontentloaded')
                content = await page.content()
                found = EMAIL_REGEX.findall(content)
                for email in found:
                    if not email.lower().endswith(BLOCKLIST_EXTENSIONS):
                        emails.add(email.lower())
            except Exception as e:
                logger.warning(f"Failed to load homepage {url}: {e}")
                if page: await page.close()
                return []

            # 2. Look for Contact/About pages links if no email found or just to be thorough
            if len(emails) < 2:
                try:
                    # Find contact link
                    contact_link = await page.get_by_text(re.compile('contact', re.I)).first.get_attribute('href')
                    if not contact_link:
                         contact_link = await page.get_by_text(re.compile('about', re.I)).first.get_attribute('href')
                    
                    if contact_link:
                        # Handle relative URLs
                        if not contact_link.startswith('http'):
                            if contact_link.startswith('/'):
                                parsed_orig = urlparse(url)
                                contact_link = f"{parsed_orig.scheme}://{parsed_orig.netloc}{contact_link}"
                            else:
                                contact_link = url.rstrip('/') + '/' + contact_link
                        
                        logger.info(f"Visiting contact page: {contact_link}")
                        await page.goto(contact_link, timeout=10000, wait_until='domcontentloaded')
                        content = await page.content()
                        found = EMAIL_REGEX.findall(content)
                        for email in found:
                            if not email.lower().endswith(BLOCKLIST_EXTENSIONS):
                                emails.add(email.lower())
                except Exception:
                    pass # It's fine if we can't find or visit contact page

        except Exception as e:
            logger.error(f"Error extracting emails from {url}: {e}")
        finally:
            if page: await page.close()
        
        # Filter junk emails
        valid_emails = []
        for email in emails:
            # Basic filters
            if len(email) < 5 or len(email) > 60: continue
            if 'wixpress' in email or 'sentry' in email or 'example' in email: continue
            valid_emails.append(email)
            
        return list(set(valid_emails))

    def _verify_email_smtp(self, email: str, mx_host: str) -> Dict:
        """
        Attempts an SMTP handshake (ping) to verify if the mailbox exists.
        This is a 'Tier 3' verification.
        """
        try:
            # Set timeout for the whole operation
            timeout = 10
            
            # Connect to MX server
            server = smtplib.SMTP(timeout=timeout)
            server.set_debuglevel(0)
            
            server.connect(mx_host)
            server.helo(socket.gethostname()) # Local hostname
            server.mail('verify@web4guru.com') # Sender identity (doesn't have to be real but should look valid)
            
            code, message = server.rcpt(email)
            server.quit()
            
            if code == 250:
                return {"valid": True, "reason": "SMTP Handshake Success (250 OK)"}
            elif code == 550:
                return {"valid": False, "reason": "SMTP Error 550: Mailbox Not Found"}
            else:
                return {"valid": True, "reason": f"SMTP Response {code}: Likely Valid"}
                
        except Exception as e:
            logger.warning(f"  SMTP Ping failed for {email} on {mx_host}: {e}")
            return {"valid": True, "reason": f"SMTP Check Failed (Skipped): {str(e)}"}

    def _verify_email_dns(self, email: str) -> Dict:
        """
        Verifies email using syntax check, DNS MX lookup, and SMTP ping.
        """
        if not email or "@" not in email:
            return {"valid": False, "reason": "Invalid format"}
        
        if not EMAIL_REGEX.match(email):
            return {"valid": False, "reason": "Regex failed"}
            
        domain = email.split("@")[-1].lower()
        
        # 1. DNS Check
        mx_host = ""
        try:
            records = dns.resolver.resolve(domain, 'MX')
            if records:
                # Get the highest priority MX host
                mx_host = str(records[0].exchange).rstrip('.')
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            try:
                dns.resolver.resolve(domain, 'A')
                return {"valid": True, "reason": "A Record Found (No MX)"}
            except:
                return {"valid": False, "reason": "No MX/A Records"}
        except Exception as e:
            return {"valid": False, "reason": f"DNS Error: {str(e)}"}

        # 2. SMTP Ping (Tier 3)
        if mx_host:
            return self._verify_email_smtp(email, mx_host)
            
        return {"valid": True, "reason": "DNS Valid (SMTP Skipped)"}

    async def run(self, specific_queries: List[str] = None):
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = await context.new_page()

            queries = specific_queries or ["Dentists in New York"] # Default fallback
            
            for query in queries:
                logger.info(f"Starting search for: {query}")
                try:
                    # Go to Google Maps
                    await page.goto("https://www.google.com/maps", timeout=60000)
                    
                    # Log where we are
                    logger.info(f"Page loaded. Title: {await page.title()}")
                    logger.info(f"URL: {page.url}")

                    # Handle Consent (if any)
                    try:
                        # Try robust consent handling
                        consent_button = page.locator('form[action^="https://consent.google.com"] button')
                        if await consent_button.count() > 0:
                             logger.info("Found consent form buttons...")
                             await consent_button.first.click()
                             await asyncio.sleep(2)
                        
                        # Fallbacks
                        if await page.get_by_text("Accept all").is_visible():
                            await page.get_by_text("Accept all").click()
                        elif await page.get_by_text("I agree").is_visible():
                            await page.get_by_text("I agree").click()
                    except:
                        pass

                    # Type query and search
                    search_box = page.locator("input#searchboxinput")
                    
                    # Fallback selectors
                    if not await search_box.is_visible(timeout=5000):
                         logger.warning("specific #searchboxinput not visible. Dumping debug info...")
                         await page.screenshot(path="debug_no_searchbox.png")
                         
                         # Try generic input
                         search_box = page.locator("input[name='q']")
                         if not await search_box.is_visible():
                             search_box = page.locator("input").first
                    
                    if await search_box.is_visible():
                        await search_box.fill(query)
                        await page.keyboard.press("Enter")
                    else:
                        raise Exception("Could not find any search box")
                    
                    # Wait for results to load
                    logger.info("Waiting for results...")
                    try:
                        await page.wait_for_selector('div[role="feed"]', timeout=15000)
                    except:
                        # Sometimes layout is different?
                        logger.warning("Feed selector not found")
                    
                    # Scroll loop
                    feed = page.locator('div[role="feed"]')
                    if not await feed.is_visible():
                        # Maybe it is not a feed but a list?
                        feed = page.locator('div[role="main"]')
                    
                    # We want to scroll until we have enough results or end of list
                    # For demo purposes, let's limit to top 20-30 to avoid getting blocked too fast initially
                    max_scrolls = 10 
                    for i in range(max_scrolls):
                        # Scroll to bottom of feed
                        await feed.evaluate("element => element.scrollTop = element.scrollHeight")
                        await asyncio.sleep(2) # Wait for load
                        
                        # Check if "You've reached the end" is visible
                        if await page.get_by_text("You've reached the end of the list").is_visible():
                            logger.info("Reached end of list.")
                            break
                            
                        # Extract current count
                        cards = await feed.locator('div[role="article"]').count()
                        logger.info(f"Loaded {cards} results so far...")
                        if cards >= 50: # Cap at 50 per query for this version
                            break
                    
                    # Now extract data from cards
                    cards = feed.locator('div[role="article"]')
                    count = await cards.count()
                    logger.info(f"Processing {count} results...")
                    
                    for i in range(count):
                        try:
                            card = cards.nth(i)
                            
                            # Debug: Dump card HTML
                            if i == 0 and not Path("card_debug.html").exists():
                                with open("card_debug.html", "w") as f:
                                    f.write(await card.inner_html())
                            
                            # Extract Name
                            # Try aria-label first
                            name = await card.get_attribute("aria-label")
                            if not name:
                                # Try link
                                link = card.locator("a").first
                                name = await link.get_attribute("aria-label")
                            
                            # Clean name
                            if name: 
                                name = name.replace("Visit ", "").strip()
                            else:
                                name = "Unknown"

                            # Extract Website
                            website_link = ""
                            # Look for 'Website' button/link
                            # Usually a link with text "Website" or icon
                            website_btn = card.locator('a[data-value="Website"]')
                            if await website_btn.count() > 0:
                                website_link = await website_btn.first.get_attribute("href")
                            else:
                                # Try generic link search
                                links = await card.locator("a").all()
                                for link in links:
                                    href = await link.get_attribute("href")
                                    if href and ("http" in href) and not ("google.com" in href):
                                        website_link = href
                                        break
                            
                            # Extract Phone
                            phone = ""
                            text_content = await card.text_content()
                            # Regex for phone in text (e.g. (555) 123-4567 or +1 ...)
                            phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text_content)
                            if phone_match:
                                phone = phone_match.group(0)

                            # Address from text
                            address = "" # Hard to parsing from raw text reliably without details, 
                                         # but we can try to find the line with city/state
                            
                            # Check duplicates
                            if self._is_duplicate(name, phone, website_link):
                                logger.info(f"Skipping duplicate: {name}")
                                continue
                            
                            logger.info(f"Found: {name} | {phone} | {website_link}")
                            
                            # Extract Emails and Names if website exists
                            emails = []
                            person_name = {"first": "", "last": ""}
                            
                            # Initial guess from business name
                            person_name = self._extract_name_from_business(name)
                            
                            if website_link:
                                extraction = await self._extract_emails_and_names(context, website_link, name)
                                emails = extraction["emails"]
                                logger.info(f"  Emails found: {emails}")
                                
                                # Use website name if business name parse failed
                                if not person_name["first"] and extraction["person"]["first"]:
                                    person_name = extraction["person"]
                            
                            # Save to Sheet/CSV
                            lead_data = {
                                "business_name": name, 
                                "first_name": person_name["first"],
                                "last_name": person_name["last"],
                                "role": "Attorney/Manager" if person_name["first"] else "Owner/Manager", 
                                "business_type": "Law Firm",
                                "domain": website_link,
                                "phone": phone,
                                "email": "",
                                "city": query.split(" in ")[-1].replace(", FL", "").rstrip(", TX").strip() if " in " in query else "",
                                "state": "FL" if " FL" in query else ("TX" if " TX" in query else ""),
                                "notes": f"Scraped from Google Maps: {query}.",
                                "status": "pending",
                                "email_verified": "unchecked",
                                "custom_data": {} # Will hold {email: verification_status}
                            }

                            # Verify all emails found
                            verification_results = {}
                            primary_email = ""
                            
                            for email in emails:
                                v_result = self._verify_email_dns(email)
                                status = "verified" if v_result["valid"] else f"invalid ({v_result['reason']})"
                                verification_results[email] = status
                                
                                if v_result["valid"] and not primary_email:
                                    primary_email = email
                            
                            lead_data["email"] = primary_email or (emails[0] if emails else "")
                            lead_data["custom_data"] = str(verification_results)
                            lead_data["email_verified"] = "verified" if primary_email else ("invalid" if emails else "unchecked")
                            
                            if primary_email:
                                lead_data["status"] = "pending" # Ready for sending
                                logger.info(f"  Primary Email Verified: {primary_email}")
                            elif emails:
                                lead_data["status"] = "invalid_email"
                                logger.warning(f"  No valid emails found among {len(emails)} discovered.")
                            
                            lead_data["notes"] += f" Emails found: {len(emails)}. Results: {verification_results}"
                            
                            self._save_lead(lead_data)
                            
                        except Exception as e:
                            logger.error(f"Error extracting card {i}: {e}")
                            continue

                except Exception as e:
                    logger.error(f"Error processing query {query}: {e}")
                
            await browser.close()

    def _is_duplicate(self, name, phone, website):
        if name and name.lower().strip() in self.seen_leads: return True
        if phone and phone.strip() in self.seen_leads: return True
        if website and self._clean_domain(website) in self.seen_leads: return True
        return False
        
    def _extract_city(self, address):
        if not address: return ""
        parts = address.split(',')
        if len(parts) >= 2:
            return parts[-2].strip()
        return ""

    def _extract_state(self, address):
        if not address: return ""
        # Very naive state extraction, assumes "City, ST Zip" format
        parts = address.split(',')
        if len(parts) >= 1:
            state_zip = parts[-1].strip()
            state_parts = state_zip.split(' ')
            if len(state_parts) > 0:
                return state_parts[0]
        return ""

    def _save_lead(self, data):
        """Append to Google Sheet or CSV."""
        if self.sheets_client:
            success = self.sheets_client.add_lead(data)
            if success:
                self._update_seen(data)
        else:
            # CSV Fallback
            try:
                with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    domain = data.get('domain', '')
                    if domain and domain.startswith("http"):
                        domain = domain.split("//")[-1].split("/")[0]
                    
                    row = [
                        data.get('email', ''),
                        data.get('first_name', ''),
                        data.get('last_name', ''),
                        data.get('role', ''),
                        data.get('business_name', ''),
                        data.get('business_type', 'Law Firm'),
                        domain,
                        data.get('state', ''),
                        data.get('city', ''),
                        data.get('phone', ''),
                        data.get('status', 'pending'),
                        data.get('email_verified', 'unchecked'),
                        "", # email_1_sent_at
                        "", # email_2_sent_at
                        "", # sender_email
                        data.get('notes', ''),
                        data.get('custom_data', '')
                    ]
                    writer.writerow(row)
                logger.info(f"Saved lead to CSV: {data['business_name']}")
                self._update_seen(data)
            except Exception as e:
                logger.error(f"Failed to save to CSV: {e}")

    def _update_seen(self, data):
        """Add to seen set to prevent duplicates in same run."""
        if data.get('email'): self.seen_leads.add(data['email'].lower().strip())
        if data.get('business_name'): self.seen_leads.add(data['business_name'].lower().strip())
        if data.get('phone'): self.seen_leads.add(data['phone'].strip())
        if data.get('domain'): self.seen_leads.add(self._clean_domain(data['domain']))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Google Maps Scraper")
    parser.add_argument("--queries", nargs="+", help="Search queries (e.g. 'Dentists in Dallas' 'Plumbers in Austin')")
    parser.add_argument("--sheet-name", help="Name of the Google Sheet to save leads to", default=None)
    parser.add_argument("--headless", action="store_true", help="Run in headless mode", default=True)
    parser.add_argument("--visible", action="store_false", dest="headless", help="Run with visible browser")
    
    args = parser.parse_args()
    
    if not args.queries:
        print("Please provide at least one query with --queries")
        sys.exit(1)
        
    scraper = GoogleMapsScraper(headless=args.headless, sheet_name=args.sheet_name)
    asyncio.run(scraper.run(args.queries))
