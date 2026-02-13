"""
School Website Scraper

Extracts clean, useful content from school homepages for hyper-personalization.
Removes navigation, footers, and noise. Focuses on:
- Mission statements
- Values
- Programs 
- Recent news/achievements
"""

import requests
from bs4 import BeautifulSoup
import logging
import re
from typing import Optional, Dict
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

# Suppress SSL warnings for some school sites
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Elements to remove (navigation, footers, etc.)
NOISE_TAGS = [
    'nav', 'header', 'footer', 'script', 'style', 'noscript', 
    'iframe', 'form', 'aside', 'button', 'input', 'select'
]

NOISE_CLASSES = [
    'popup', 'modal', 'advertisement', 'social', 'share',
    'breadcrumb', 'pagination', 'comment'
    # Removed 'widget', 'sidebar', 'footer' - too aggressive for some school layouts
]

# Keywords that indicate valuable content
VALUE_KEYWORDS = [
    'mission', 'vision', 'values', 'about', 'welcome', 'philosophy',
    'tradition', 'faith', 'community', 'excellence', 'program',
    'academics', 'college', 'students', 'learning', 'founded',
    'history', 'accredited', 'award', 'achievement'
]


def scrape_school_website(url: str, timeout: int = 10) -> Dict:
    """
    Scrape a school website and extract clean, useful content.
    
    Args:
        url: Website URL (with or without protocol)
        timeout: Request timeout in seconds
        
    Returns:
        Dict with extracted content organized by section
    """
    if not url:
        return {"error": "No URL provided", "content": ""}
    
    # Normalize URL
    if not url.startswith("http"):
        url = "https://" + url
    
    result = {
        "url": url,
        "title": "",
        "mission": "",
        "description": "",
        "values": "",
        "programs": "",
        "achievements": "",
        "full_text": "",
        "error": None
    }
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=timeout, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        logger.info(f"Raw HTML length: {len(response.text)}")
        
        # Get page title
        if soup.title:
            result["title"] = soup.title.get_text(strip=True)
        
        # Remove noise elements
        for tag in NOISE_TAGS:
            for element in soup.find_all(tag):
                element.decompose()
        
        # Remove elements with noisy classes
        for class_name in NOISE_CLASSES:
            for element in soup.find_all(class_=re.compile(class_name, re.I)):
                # CRITICAL: Do not delete the body tag itself, even if it has a noisy class
                if element.name == 'body':
                    continue
                element.decompose()
                
        logger.info(f"HTML length after cleaning: {len(str(soup))}")

        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            result["description"] = meta_desc.get('content', '')
        
        # Find mission statement
        result["mission"] = _find_section(soup, ['mission', 'about us', 'our story', 'who we are'])
        
        # Find values
        result["values"] = _find_section(soup, ['values', 'philosophy', 'faith', 'tradition', 'beliefs'])
        
        # Find programs/academics
        result["programs"] = _find_section(soup, ['program', 'academics', 'curriculum', 'college prep'])
        
        # Find achievements
        result["achievements"] = _find_section(soup, ['achievement', 'award', 'recognition', 'accreditation'])
        
        # Get main content text (cleaned)
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        if main_content:
            text = main_content.get_text(separator=' ', strip=True)
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text)
            # Limit length to 2000 chars (approx 500 tokens) to respect user constraints
            result["full_text"] = text[:2000]
        else:
            # Fallback for sites where main/article/body tags weren't found or were filtered
            # Try to grab paragraphs directly from soup (since noise is already gone)
            paragraphs = soup.find_all('p')
            content = []
            for p in paragraphs:
                txt = p.get_text(strip=True)
                if len(txt) > 50: # Only substantial paragraphs
                    content.append(txt)
            
            if content:
                result["full_text"] = " ".join(content)[:2000]
            else:
                # Last resort: just grab body text if body exists
                if soup.body:
                     raw_text = soup.body.get_text(separator=' ', strip=True)
                     result["full_text"] = re.sub(r'\s+', ' ', raw_text)[:2000]
        
        logger.info(f"✓ Scraped {url}: {len(result['full_text'])} chars")
        
    except requests.Timeout:
        result["error"] = "Timeout"
        logger.warning(f"Timeout scraping {url}")
    except requests.RequestException as e:
        result["error"] = str(e)[:100]
        logger.warning(f"Failed to scrape {url}: {e}")
    except Exception as e:
        result["error"] = str(e)[:100]
        logger.error(f"Error scraping {url}: {e}")
    
    return result


def _find_section(soup: BeautifulSoup, keywords: list) -> str:
    """Find and extract a section based on keywords in headings or class names."""
    for keyword in keywords:
        # Look for headings containing the keyword
        for tag in ['h1', 'h2', 'h3', 'h4']:
            headings = soup.find_all(tag, string=re.compile(keyword, re.I))
            for heading in headings:
                # Get the next sibling paragraphs
                content = []
                for sibling in heading.find_next_siblings(['p', 'div', 'ul'])[:3]:
                    text = sibling.get_text(strip=True)
                    if len(text) > 20:  # Skip short snippets
                        content.append(text)
                if content:
                    return ' '.join(content)[:500]
        
        # Look for divs/sections with keyword in class or id
        elements = soup.find_all(['div', 'section'], 
                                  class_=re.compile(keyword, re.I)) or \
                   soup.find_all(['div', 'section'], 
                                  id=re.compile(keyword, re.I))
        for element in elements[:2]:
            text = element.get_text(separator=' ', strip=True)
            if len(text) > 50:
                return text[:500]
    
    return ""


def format_for_ai(scraped: Dict) -> str:
    """
    Format scraped content into a clean context string for AI.
    
    Args:
        scraped: Dict from scrape_school_website()
        
    Returns:
        Formatted string for AI prompt
    """
    if scraped.get("error"):
        return f"[Website scraping failed: {scraped['error']}]"
    
    sections = []
    
    if scraped.get("title"):
        sections.append(f"PAGE TITLE: {scraped['title']}")
    
    if scraped.get("description"):
        sections.append(f"SITE DESCRIPTION: {scraped['description']}")
    
    if scraped.get("mission"):
        sections.append(f"MISSION/ABOUT: {scraped['mission']}")
    
    if scraped.get("values"):
        sections.append(f"VALUES/PHILOSOPHY: {scraped['values']}")
    
    if scraped.get("programs"):
        sections.append(f"PROGRAMS: {scraped['programs']}")
    
    if scraped.get("achievements"):
        sections.append(f"ACHIEVEMENTS: {scraped['achievements']}")
    
    # If we didn't find structured sections, use full text
    if len(sections) <= 2 and scraped.get("full_text"):
        sections.append(f"HOMEPAGE TEXT: {scraped['full_text'][:1500]}")
    
    return "\n\n".join(sections) if sections else "[No content extracted]"


def scrape_website_text(url: str) -> str:
    """
    Simple wrapper that returns just the formatted text.
    For backwards compatibility with email_generator.py
    """
    scraped = scrape_school_website(url)
    return format_for_ai(scraped)


# Test function
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO)
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.staugustineprep.org"
    
    print(f"\nScraping: {test_url}")
    print("=" * 60)
    
    result = scrape_school_website(test_url)
    formatted = format_for_ai(result)
    
    print(formatted)
    print("=" * 60)
    print(f"Total chars: {len(formatted)}")
