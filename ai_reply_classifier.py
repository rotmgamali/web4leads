import os
import sys
import json
import time
import requests
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sheets_integration import GoogleSheetsClient

# --- CONFIGURATION ---
OPENAI_MODEL = "gpt-4o"
SYSTEM_PROMPT = """You are a strictly objective Sales Lead Analyst evaluating email responses for an educational tutoring company (Ivy Bound).
Your ONLY goal is to classify if an email is "ACTIONABLE" (a warm/hot lead) or "NOT_ACTIONABLE".

An email IS ACTIONABLE IF:
1. The sender explicitly asks to schedule a meeting, phone call, or provides availability to talk.
2. The sender asks specific, relevant questions about your services, pricing, or logistics.
3. The sender expresses positive interest in learning more about the tutoring/prep programs.
4. The sender connects you directly with a decision-maker who expresses interest.

An email is NOT ACTIONABLE IF:
1. It is an auto-reply, Out-of-Office, "Return to Sender", or Mail Delivery Failure.
2. It is an automated system asking for email verification.
3. The sender explicitly states "Not interested", "No thank you", "Take us off your list", "unsubscribe", or "remove".
4. The sender says they already have testing/prep programs in place and do not need external help.
5. The email contains irrelevant internal company chatter, single non-sequitur sentences, or gibberish (Warmup noise).

You must output valid JSON containing:
- "classification": Must be exactly "ACTIONABLE" or "NOT_ACTIONABLE".
- "reason": A concise, strict 1-sentence justification for your choice based on the rules above.
"""

def load_openai_key():
    env_path = BASE_DIR / '.env'
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('OPENAI_API_KEY='):
                    return line.strip().split('=', 1)[1]
    return os.environ.get('OPENAI_API_KEY')

def classify_reply_with_openai(subject, snippet, api_key):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    user_prompt = f"Subject: {subject}\n\nEmail Body Snippet:\n{snippet}"
    
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0  # Keep it deterministic and strict
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        content = data['choices'][0]['message']['content']
        return json.loads(content)
    except Exception as e:
        print(f"❌ OpenAI API Error: {e}")
        if 'response' in locals() and hasattr(response, 'text'):
            print(f"Response details: {response.text}")
        return None

def main():
    api_key = load_openai_key()
    if not api_key:
        print("❌ ERROR: Could not find OPENAI_API_KEY in .env")
        return

    print("🚀 Starting AI-Powered Reply Classification using GPT-4o...")
    
    sheets = GoogleSheetsClient()
    # Explicitly open only the replies sheet
    ss = sheets.client.open_by_key('1jeLkdufaMub4rylaPnoTQZwDiLpHmut5hcQQStl8UxI')
    ws = ss.sheet1
    
    records = ws.get_all_values()
    if len(records) < 2:
        print("Empty sheet, nothing to process.")
        return
        
    headers = records[0]
    # Find column indices (0-indexed)
    try:
        sentiment_idx = headers.index('Sentiment')
        notes_idx = headers.index('Notes')
        subject_idx = headers.index('Subject')
        snippet_idx = headers.index('Entire Thread')
    except ValueError as e:
        print(f"❌ Header missing: {e}")
        return
        
    print(f"📊 Processing {len(records)-1} rows...")
    
    processed_count = 0
    actionable_count = 0
    
    # We will batch updates for notes and sentiment to avoid quota issues
    # but gspread allows format updates on ranges easily.
    
    for i, row in enumerate(records[1:], start=2): # +2 because 1-indexed for gspread and skipping header
        # Pad row if too short
        while len(row) <= max(sentiment_idx, notes_idx, subject_idx, snippet_idx):
            row.append("")
            
        sentiment = row[sentiment_idx]
        notes = row[notes_idx]
        
        # Skip if already AI processed
        if "AI Reason:" in notes or "ACTIONABLE" in sentiment:
            continue
            
        subject = row[subject_idx].strip()
        snippet = row[snippet_idx].strip()
        from_email = row[1] if len(row) > 1 else "Unknown"
        
        if not subject and not snippet:
            continue # Empty row
            
        print(f"🧠 Classifying Row {i} from {from_email}...")
        
        result = classify_reply_with_openai(subject, snippet, api_key)
        if not result:
            time.sleep(2)
            continue
            
        classification = result.get('classification', 'UNKNOWN')
        reason = result.get('reason', '')
        
        print(f"   -> Result: {classification} ({reason})")
        
        new_sentiment = f"{classification} 🟢" if classification == "ACTIONABLE" else f"{classification} 🔴"
        new_notes = f"[AI Reason: {reason}] {notes}".strip()
        
        # Update specific cells
        for attempt in range(3):
            try:
                ws.update_cell(i, sentiment_idx + 1, new_sentiment)
                ws.update_cell(i, notes_idx + 1, new_notes)
                
                # Format row
                if classification == "ACTIONABLE":
                    actionable_count += 1
                    ws.format(f"A{i}:M{i}", {
                        "backgroundColor": {"red": 0.85, "green": 0.95, "blue": 0.85},
                        "textFormat": {"bold": True}
                    })
                else:
                     ws.format(f"A{i}:M{i}", {
                        "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                        "textFormat": {"foregroundColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}
                    })
                    
                processed_count += 1
                break # Success, break retry loop
            except Exception as e:
                print(f"⚠️ Quota Error updating sheet at row {i} (Attempt {attempt+1}/3): {e}")
                time.sleep(20) # Heavy sleep on quota error
                
        time.sleep(1.5) # Gentle rate limiting (40 reqs/min)
        
    print(f"\n✅ Classification Complete! Processed {processed_count} rows.")
    print(f"🔥 Found {actionable_count} ACTIONABLE leads.")

if __name__ == "__main__":
    main()
