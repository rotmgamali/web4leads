import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import urllib3
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import pytz

# Suppress SSL warnings from scraper to keep logs clean
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import re

# Add project root to path to allow imports from sibling directories
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from mailreef_automation.logger_util import get_logger
load_dotenv()
logger = get_logger("EMAIL_GENERATOR")

# Try to import scrapers
try:
    import automation_scrapers.school_scraper as school_scraper
    logger.info("✓ Successfully imported school_scraper")
except ImportError:
    school_scraper = None

try:
    import automation_scrapers.b2b_scraper as b2b_scraper
    logger.info("✓ Successfully imported b2b_scraper")
except ImportError:
    b2b_scraper = None

class EmailGenerator:
    """
    Generates hyper-personalized email content using OpenAI + Live Website Scraping.
    Uses 'Archetypes' to select the correct template folder (e.g. /principal).
    """

    # Mapping of role keywords to template folders
    ARCHETYPES = {
        "principal": ["principal", "assistant principal", "vice principal"],
        "head_of_school": ["head of school", "headmaster", "headmistress", "head of", "president", "superintendent"],
        "academic_dean": ["dean", "academic", "curriculum", "instruction"],
        "college_counseling": ["counselor", "college", "guidance", "advisor"],
        "business_manager": ["business", "finance", "cfo", "bursar", "operations"],
        "faith_leader": ["pastor", "minister", "chaplain", "campus ministry", "religious", "father", "reverend"],
        "athletics": ["athletic", "coach", "sports", "physical education"],
        "admissions": ["admission", "enrollment", "registrar"]
    }

    def __init__(self, client=None, templates_dir="templates", log_file="automation.log", archetypes: dict = None):
        self.client = client or OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # Support both 'templates' (relative to root) and absolute paths
        if os.path.isabs(templates_dir):
            self.templates_dir = Path(templates_dir)
        else:
            self.templates_dir = BASE_DIR / templates_dir
            
        # Dynamically load archetypes, default to school ones if not provided
        self.archetypes = archetypes or {
            "principal": ["principal", "assistant principal", "vice principal"],
            "head_of_school": ["head of school", "headmaster", "headmistress", "head of", "president", "superintendent"],
            "academic_dean": ["dean", "academic", "curriculum", "instruction"],
            "college_counseling": ["counselor", "college", "guidance", "advisor"],
            "business_manager": ["business", "finance", "cfo", "bursar", "operations"],
            "faith_leader": ["pastor", "minister", "chaplain", "campus ministry", "religious", "father", "reverend"],
            "athletics": ["athletic", "coach", "sports", "physical education"],
            "admissions": ["admission", "enrollment", "registrar"]
        }
            
        # --- LOGGING ISOLATION ---
        # Re-bind the global logger for this module to the profile-specific file
        global logger
        logger = get_logger("EMAIL_GENERATOR", log_file)
        if log_file != "automation.log":
            for h in logger.handlers[:]:
                if isinstance(h, logging.FileHandler) and "automation.log" in h.baseFilename:
                    logger.removeHandler(h)

    def generate_email(
        self,
        campaign_type: str,
        sequence_number: int,
        lead_data: dict,
        enrichment_data: dict,
        sender_email: str = None
    ) -> dict:
        """
        Routing method:
        - If 'school' or 'b2b', use the Archetype + Scraper logic.
        - Otherwise, use legacy dictionary prompts.
        """
        if campaign_type in ["school", "b2b"]:
            return self._generate_templated_email(campaign_type, sequence_number, lead_data, enrichment_data, sender_email)
        else:
            return self._generate_legacy_email(campaign_type, sequence_number, lead_data, enrichment_data)

    def _generate_templated_email(self, campaign_type: str, sequence_number: int, lead_data: dict, enrichment_data: dict, sender_email: str = None) -> dict:
        """
        1. Identify Archetype (Role).
        2. Load Template (file).
        3. Scrape Website (if not already cached).
        4. Generate Email via LLM.
        """
        role = (lead_data.get("role") or "").lower()
        archetype = self._get_archetype(role)
        logger.info(f"🎯 [GEN] {campaign_type.upper()} Archetype: {archetype} (detected from role: '{role}')")
        
        # Load Template
        template_content = self._load_template_file(campaign_type, archetype, sequence_number)
        
        # Fallback to general if not found and archetype isn't already general
        if not template_content and archetype != "general":
            logger.info(f"ℹ️ Template for {archetype}/{sequence_number} not found. Falling back to general.")
            template_content = self._load_template_file(campaign_type, "general", sequence_number)
            
        if not template_content:
            logger.error(f"❌ Template missing for {campaign_type}/{archetype}/{sequence_number} and fallback general failed.")
            return {"subject": "Quick question", "body": "I'd love to connect regarding your current operations."}

        # Website Scraping
        website_content = enrichment_data.get("website_content", "")
        url = lead_data.get("website") or lead_data.get("domain")

        if not website_content and url:
            # SANITY CHECK: Ensure we aren't scraping Google Maps
            if "google.com" in url.lower() or "goo.gl" in url.lower():
                logger.warning(f"⚠️ Skipping scrape for Google URL: {url}")
                website_content = "Scraper skipped for Google URL."
            else:
                logger.info(f"🌍 [SCRAPE] Attempting to scrape {campaign_type} site: {url}...")
                try:
                    if not url.startswith("http"):
                        url = "https://" + url
                    
                    # Choose the right scraper
                    if campaign_type == "b2b" and b2b_scraper:
                        website_content = b2b_scraper.scrape_b2b_text(url)
                    elif school_scraper:
                        website_content = school_scraper.scrape_website_text(url)
                    else:
                        website_content = "Scraper unavailable."

                    if website_content and len(website_content) > 100:
                        logger.info(f"✅ [SCRAPE SUCCESS] Found {len(website_content)} characters for personalization.")
                    else:
                        logger.warning(f"⚠️ [SCRAPE WEAK] Only found {len(website_content) if website_content else 0} chars.")
                except Exception as e:
                    logger.error(f"❌ [SCRAPE ERROR] Failed for {url}: {e}")
                    website_content = "No website content available."
        
        # Parse Custom Data
        custom_json = lead_data.get("custom_data", "{}")
        custom_context = ""
        try:
            if isinstance(custom_json, str) and custom_json.strip():
                import json
                data = json.loads(custom_json)
                
                # Extract valuable fields
                desc = data.get("company_insights.description") or data.get("description") or ""
                year = data.get("company_insights.founded_year") or data.get("founded_year")
                reviews = data.get("reviews")
                rating = data.get("rating")
                city = data.get("city") or data.get("company_insights.city")
                
                context_parts = []
                if desc: context_parts.append(f"Business Description: {desc}")
                if year: context_parts.append(f"Founded: {year}")
                if reviews and rating: context_parts.append(f"Reputation: {rating} stars from {reviews} reviews")
                if city: context_parts.append(f"Location: {city}")
                
                if context_parts:
                    custom_context = "\n".join(context_parts)
                    logger.info(f"✅ [DATA] Extracted rich personalization details: {len(context_parts)} items.")
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse custom_data: {e}")

        # Build Prompts (System + User)
        system_prompt, user_prompt, envelope = self._prepare_templated_prompts(
            campaign_type, template_content, lead_data, website_content, sequence_number, sender_email, custom_context
        )
        
        # Call LLM for Body & Subject
        llm_result = self._call_llm(user_prompt, system_prompt)
        
        # --- ENVELOPE REASSEMBLY ---
        clean_body = self._strip_hallucinations(llm_result['body'], envelope['greeting'], envelope['sign_off'])
        final_body = f"{envelope['greeting']}\n\n{clean_body}\n\n{envelope['sign_off']}"
        
        return {
            "subject": llm_result['subject'],
            "body": final_body
        }

    def _get_archetype(self, role: str) -> str:
        """Map job title to archetype folder name."""
        for key, keywords in self.archetypes.items():
            if any(k in role for k in keywords):
                return key
        return "general"  # Default

    def _sanitize_name(self, name: str, lead_data: dict) -> str:
        """Sanitize first name to avoid 'Hi Harvest' or 'Hi Info'."""
        if not name: return ""
        name = name.strip()
        lower_name = name.lower()
        
        # Blocklist (expanded to catch common placeholder terms)
        blocklist = [
            "info", "admin", "administrator", "office", "contact", 
            "admissions", "principal", "head", "school", "manager",
            "leader", "team", "coordinator", "assistant", "staff"
        ]
        if any(term in lower_name for term in blocklist):
            return ""
            
        # Check against School Name
        school_name = lead_data.get("school_name", "").lower()
        if school_name:
            # If name is just the first word of school (REMOVED: Too aggressive, blocks 'Viva')
            # school_parts = school_name.split()
            # if school_parts and lower_name == school_parts[0]:
            #    return ""
            # If name matches the school name exactly
            if lower_name == school_name:
                return ""
                
        return name

    def _get_time_greeting(self) -> str:
        """Return Good morning/afternoon/evening based on EST time."""
        try:
            est = pytz.timezone('US/Eastern')
            now = datetime.now(est)
            hour = now.hour
            
            if 5 <= hour < 12:
                return "Good morning"
            elif 12 <= hour < 17:
                return "Good afternoon"
            else:
                return "Good evening"
        except Exception:
            return "Good day"

    def _load_template_file(self, campaign_type: str, archetype: str, sequence_number: int) -> Optional[str]:
        """Read template file from disk (e.g. templates/school/principal/email_1.txt)."""
        # Map sequence number to file name (email_1.txt)
        filename = f"email_{sequence_number}.txt"
        path = self.templates_dir / campaign_type / archetype / filename
        
        logger.debug(f"🔍 [PATH CHECK] Looking for template at: {path}")
        
        if path.exists():
            content = path.read_text(encoding="utf-8")
            logger.info(f"📄 [TEMPLATE CONTENT PREVIEW] {content[:100]}...")
            return content
        
        # Diagnostic: List files to see what's actually there
        try:
            if self.templates_dir.exists():
                contents = os.listdir(self.templates_dir)
                logger.debug(f"📁 [DIR LIST] Content of {self.templates_dir}: {contents}")
            else:
                logger.error(f"🚨 [DIR MISSING] Template directory NOT FOUND at {self.templates_dir}")
        except Exception as e:
            logger.debug(f"🔍 [DIR ERROR] Could not list directory: {e}")
            
        return None

    def _prepare_templated_prompts(self, campaign_type: str, template_content: str, lead_data: dict, website_content: str, sequence_number: int, sender_email: str, custom_context: str = "") -> tuple:
        """
        Constructs (system_message, user_message, envelope_dict).
        Implements the ENVELOPE PATTERN: 
        - Calculates Greeting/Sign-off in Python.
        - Strips them from the template.
        - Asks LLM for BODY ONLY.
        """
        
        # --- 1. Calculate Variables (Identity & Recipient) ---
        
        # Name & Greeting Logic
        raw_name = lead_data.get("first_name", "")
        # ... (retained logic) ...
        # (This tool call needs to be precise so I don't delete the whole body. Let's act on the signature first)
        
        # (Actually, I need to jump down to where user_prompt is constructed to inject custom_context)
        # Let's do this in two chunks if needed, or target the prompt construction block.
        pass

    # I will split this into two calls for safety. First the signature.
    # Wait, I can't use `pass` in replacement. I need to be exact.
    # I will target the signature line specifically.

        
        # Name & Greeting Logic
        raw_name = lead_data.get("first_name", "")
        sanitized = self._sanitize_name(raw_name, lead_data)
        
        if sanitized:
            first_name = sanitized
            # Religious Titles
            role = lead_data.get("role", "").lower()
            religious_titles = {"pastor": "Pastor", "reverend": "Reverend", "rev.": "Reverend", "father": "Father", "rabbi": "Rabbi"}
            for keyword, title in religious_titles.items():
                if keyword in role and title.lower() not in first_name.lower():
                    first_name = f"{title} {first_name}"
                    break
            greeting_line = f"Hi {first_name},"
        else:
            # Fallback to Time-Based
            greeting_line = f"{self._get_time_greeting()},"
            first_name = "School Leader" # Default for prompt context
            
        # Sender Logic
        sender_name = "Andrew"
        if sender_email:
            if "mark" in sender_email.lower(): sender_name = "Mark Greenstein"
            elif "genelle" in sender_email.lower(): sender_name = "Genelle"
        
        
        # --- 2. Python-Side Template Substitution (The Fix) ---
        # Regex replacement for robust handling of {{name}} vs {{ name }}
        # 1. Replace Greeting
        # We want to replace the entire "Hi {{ first_name }}," block matches if possible, 
        # or just the variable.
        
        draft_body = template_content
        
        # Strategy: Pre-fill ALL known variables in the template so the LLM sees clean text.
        school_name = lead_data.get("school_name") or lead_data.get("company_name") or "your company"
        school_type = lead_data.get("school_type", "private").lower()
        
        replacements = {
            "first_name": first_name,
            "school_name": school_name,
            "company_name": school_name, # Alias for B2B
            "city": lead_data.get("city", "your city"),
            "state": lead_data.get("state", ""),
            "role": lead_data.get("role", "executive"),
            "greeting": greeting_line # Expose the calculated greeting (e.g. "Good morning," or "Hi Andrew,")
        }
        
        # 1. Handle the Greeting specifically (remove "Hi " from template if we have a full greeting line)
        # If template has "Hi {{ first_name }}," -> replace with "Hi Andrew," (or "Good morning,")
        # But wait, greeting_line ALREADY contains "Hi " or "Good morning".
        # So we should replace "Hi {{ first_name }}" with greeting_line WITHOUT the trailing comma if possible, 
        # or just rely on the fact that greeting_line usually ends in comma? 
        # Actually my code computes `greeting_line = "Hi Andrew,"` (with comma).
        
        # Let's try to match "Hi {{ first_name }}," or "Hi {{ first_name }}"
        # Case A: Time based "Good morning,". We want to nuke the "Hi" in the template.
        
        # Robust Regex for Greeting:
        # Match "Hi" (optional), whitespace, {{ first_name }}, comma(optional)
        greeting_pattern = re.compile(r'(Hi\s*)?\{\{\s*first_name\s*\}\},?', re.IGNORECASE)
        
        # Check if we find it
        if greeting_pattern.search(draft_body):
            draft_body = greeting_pattern.sub(greeting_line, draft_body)
        else:
             # Fallback: Just simple variable replace if pattern doesn't match
             draft_body = re.sub(r'\{\{\s*first_name\s*\}\}', first_name, draft_body)

        # 2. Replace other variables (school_name, etc)
        for key, val in replacements.items():
            if key == "first_name": continue # Already handled
            pattern = re.compile(r'\{\{\s*' + key + r'\s*\}\}', re.IGNORECASE)
            draft_body = pattern.sub(str(val), draft_body)
             
        # Double check: ensure the greeting is at the top if replacement failed (e.g. template diff)
        # But for now, assume template compliance. 
        
        # --- 3. Template Stripping (The Cleaning) ---
        # We need to give the AI only the BODY of the template.
        # Logic: 
        # 1. Identify Greeting (regex match for Hi/Dear/Good... ,)
        # 2. Identify Sign-off (regex match for Best/Sincerely/SenderName)
        # 3. Remove them.
        
        # We use the regex-substituted 'draft_body' which already has 'Hi Andrew,' inside.
        
        # Strip Greeting (Start of string)
        # Matches: "Hi Andrew," or "Good morning," followed by newlines
        clean_draft = re.sub(r'^\s*(?:Hi|Dear|Good|Hello).*?,\s*\n+', '', draft_body, flags=re.IGNORECASE|re.MULTILINE)
        
        # Strip Sign-off (End of string)
        # Matches: "Best,\nMark..." or just "Mark" at end
        # We aggressively cut anything after "Best," or "Sincerely," or the sender name.
        # Note: This is heuristic.
        for marker in ["Best,", "Sincerely,", "Warmly,", "Cheers,", "Thanks,", sender_name]:
             if marker in clean_draft:
                  clean_draft = clean_draft.split(marker)[0].strip()
        
        # --- 4. Envelope Definition ---
        # Define the deterministic shell
        sign_off_block = f"Best,\n{sender_name}"
        envelope = {
            "greeting": greeting_line,
            "sign_off": sign_off_block
        }
        
        # --- 5. System Prompt (Constraint) ---
        system_prompt = f"""You are {sender_name}, a helpful consultant.
        
STYLE GUIDE:
- Tone: Human, warm, brief.
- formatting: paragraphs only.
- Absolute Rules:
  1. DO NOT include a greeting (e.g. "Hi...").
  2. DO NOT include a sign-off (e.g. "Best, Mark").
  3. OUTPUT ONLY the Subject and the Body paragraphs.

CONTEXT:
This is a {school_type} school.
- IF PUBLIC: Focus on district alignment, budget efficiency, and improving standardized test scores.
- IF PRIVATE: Focus on enrollment, prestige, and college matriculation.
"""

        # --- 6. User Prompt (Body Generation) ---
        user_prompt = f"""Here is the CORE CONTENT of an email I want to send to {first_name} ({lead_data.get('role')}) at {school_name}.

DRAFT CONTENT:
'''
{clean_draft}
'''

LEAD CONTEXT (Use this to personalize!):
{custom_context}

RESEARCH HIGHLIGHTS (Web Scrape):
{website_content[:3000]}

TASK:
Rewrite the DRAFT CONTENT to make it feel personal.
- Use the LEAD CONTEXT (Founded year, specific description, city, etc.) if available to show you know who they are.
- Weave in 1 detail from RESEARCH HIGHLIGHTS if relevant.
- write ONLY the body paragraphs.
- Output format:
SUBJECT: [Subject]
BODY: [Paragraph 1]
[Paragraph 2]...
"""
        return system_prompt, user_prompt, envelope

    def _strip_hallucinations(self, body_text: str, greeting: str, sign_off: str) -> str:
        """Failsafe: If AI wrote 'Hi Andrew,' anyway, remove it."""
        # Clean Start
        cleaned = re.sub(r'^\s*(?:Hi|Dear|Good|Hello).*?,\s*\n+', '', body_text, flags=re.IGNORECASE|re.MULTILINE)
        # Clean End (Sign-off)
        # Remove "Best," etc if strictly at end
        cleaned = re.sub(r'\n\s*(?:Best|Sincerely|Warmly|Cheers|Thanks).*?$', '', cleaned, flags=re.IGNORECASE|re.DOTALL)
        # Remove Name if at end
        cleaned = re.sub(r'\n\s*Mark.*?$', '', cleaned, flags=re.IGNORECASE|re.DOTALL)
        cleaned = re.sub(r'\n\s*Genelle.*?$', '', cleaned, flags=re.IGNORECASE|re.DOTALL)
        cleaned = re.sub(r'\n\s*Andrew.*?$', '', cleaned, flags=re.IGNORECASE|re.DOTALL)
        
        return cleaned.strip()

    def _generate_legacy_email(self, campaign_type: str, sequence_number: int, lead_data: dict, enrichment_data: dict) -> dict:
        """Fallback for non-school campaigns."""
        prompt_key = f"email_{sequence_number}"
        prompts = self.LEGACY_PROMPTS.get(campaign_type, {})
        prompt_template = prompts.get(prompt_key)
        
        if not prompt_template:
            return {"subject": "Error", "body": "Legacy prompt not found."}

        # Simple formatting for legacy
        formatted_enrichment = "\n".join([f"{k}: {v}" for k, v in enrichment_data.items() if v])
        
        prompt = prompt_template.format(
            first_name=lead_data.get("first_name", "there"),
            company=lead_data.get("company", ""),
        )
        
        result = self._call_llm(prompt)
        
        # Obsessive Content Audit
        logger.info(f"✍️  [CONTENT GEN] Generated copy for {lead_data.get('email')}")
        logger.info(f"   Subject: {result['subject']}")
        body_preview = result['body'].replace('\n', ' ')[:100] + "..."
        logger.info(f"   Body Preview: {body_preview}")
        
        return result

    def _call_llm(self, prompt: str, system_prompt: str = None) -> dict:
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7
            )
            return self._parse_response(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"OpenAI Error: {e}")
            return {"subject": "Error", "body": str(e)}

    def _parse_response(self, content: str) -> dict:
        """Robustly parse LLM response, handling common formatting variations."""
        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
        subject = ""
        body_lines = []
        
        # 1. Attempt to find Subject
        for i, line in enumerate(lines):
            clean = line.replace("**", "").replace("#", "").strip()
            if clean.upper().startswith("SUBJECT:"):
                subject = clean.split(":", 1)[1].strip()
                # Remove subject line from body consideration
                continue
            
            # If we don't have a subject yet and this looks like a subject line (short, no punctuation)
            if not subject and i == 0 and len(clean) < 100:
                subject = clean
                continue
            
            # 2. Extract Body (everything else that isn't a "BODY:" header)
            if clean.upper().startswith("BODY:"):
                remaining = clean.split(":", 1)[1].strip()
                if remaining: body_lines.append(remaining)
            else:
                body_lines.append(line)
        
        # Final fallback if subject is still empty
        if not subject and body_lines:
            subject = "Checking in" # Safe fallback
            
        return {
            "subject": subject or "Quick question",
            "body": "\n".join(body_lines).strip()
        }
