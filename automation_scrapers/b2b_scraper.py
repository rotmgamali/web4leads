"""
B2B Website Scraper
Generalized scraper for Extracting business context (Services, Clients, Solutions).
"""

import requests
from bs4 import BeautifulSoup
import logging
import re
from typing import Optional, Dict
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

# Suppress SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NOISE_TAGS = [
    'nav', 'header', 'footer', 'script', 'style', 'noscript', 
    'iframe', 'form', 'aside', 'button', 'input', 'select'
]

NOISE_CLASSES = [
    'popup', 'modal', 'advertisement', 'social', 'share',
    'breadcrumb', 'pagination', 'comment'
]

def scrape_b2b_website(url: str, timeout: int = 15) -> Dict:
    if not url:
        return {"error": "No URL provided", "content": ""}
    
    if not url.startswith("http"):
        url = "https://" + url
    
    result = {
        "url": url,
        "title": "",
        "services": "",
        "clients": "",
        "about": "",
        "full_text": "",
        "error": None
    }
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        # Follow redirects, but limit timeout
        response = requests.get(url, headers=headers, timeout=timeout, verify=False, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get page title
        if soup.title:
            result["title"] = soup.title.get_text(strip=True)
        
        # Remove noise
        for tag in NOISE_TAGS:
            for element in soup.find_all(tag):
                element.decompose()
        
        for class_name in NOISE_CLASSES:
            for element in soup.find_all(class_=re.compile(class_name, re.I)):
                if element.name == 'body': continue
                element.decompose()

        # Find "About/Who we are"
        result["about"] = _find_section(soup, ['about', 'who we are', 'our story', 'company'])
        
        # Find "Services/Solutions"
        result["services"] = _find_section(soup, ['services', 'solutions', 'what we do', 'capabilities'])
        
        # Find "Clients/Case Studies"
        result["clients"] = _find_section(soup, ['client', 'case study', 'portfolio', 'customers', 'testimonal'])
        
        # Get main content text
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        if main_content:
            text = main_content.get_text(separator=' ', strip=True)
            text = re.sub(r'\s+', ' ', text)
            result["full_text"] = text[:3000] # Slightly longer for B2B
        
        logger.info(f"✓ Scraped B2B {url}: {len(result['full_text'])} chars")
        
    except Exception as e:
        result["error"] = str(e)[:100]
        logger.error(f"Error scraping B2B {url}: {e}")
    
    return result

def _find_section(soup: BeautifulSoup, keywords: list) -> str:
    for keyword in keywords:
        # Check headings
        for tag in ['h1', 'h2', 'h3']:
            headings = soup.find_all(tag, string=re.compile(keyword, re.I))
            for heading in headings:
                content = []
                for sibling in heading.find_next_siblings(['p', 'div', 'ul', 'section'])[:3]:
                    text = sibling.get_text(strip=True)
                    if len(text) > 30:
                        content.append(text)
                if content:
                    return ' '.join(content)[:600]
        
        # Check containers
        elements = soup.find_all(['div', 'section'], class_=re.compile(keyword, re.I))
        for element in elements[:2]:
            text = element.get_text(separator=' ', strip=True)
            if len(text) > 100:
                return text[:600]
    
    return ""

def format_for_ai(scraped: Dict) -> str:
    if scraped.get("error"):
        return f"[Website scraping failed: {scraped['error']}]"
    
    sections = []
    if scraped.get("title"): sections.append(f"COMPANY/PAGE TITLE: {scraped['title']}")
    if scraped.get("about"): sections.append(f"ABOUT THE COMPANY: {scraped['about']}")
    if scraped.get("services"): sections.append(f"SERVICES/SOLUTIONS: {scraped['services']}")
    if scraped.get("clients"): sections.append(f"CLIENTS/PROJECTS: {scraped['clients']}")
    
    if len(sections) <= 1 and scraped.get("full_text"):
        sections.append(f"WEBSITE CONTENT SUMMARY: {scraped['full_text'][:2000]}")
    
    return "\n\n".join(sections) if sections else "[No business content extracted]"

def scrape_b2b_text(url: str) -> str:
    scraped = scrape_b2b_website(url)
    return format_for_ai(scraped)

if __name__ == "__main__":
    import sys
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.web4guru.com"
    print(scrape_b2b_text(test_url))
