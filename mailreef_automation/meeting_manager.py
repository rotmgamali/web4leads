import logging
import sqlite3
import json
import os
import sys
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from openai import AsyncOpenAI

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load Check Config
try:
    from mailreef_automation import automation_config
    TOKEN = getattr(automation_config, 'TELEGRAM_BOT_TOKEN', None)
except ImportError:
    try:
        import automation_config
        TOKEN = getattr(automation_config, 'TELEGRAM_BOT_TOKEN', None)
    except ImportError:
        TOKEN = "7224632370:AAFgWL94FbffWBO6COKnYyhrMKymFJQV0po" 

# OpenAI Config
try:
    # Ensure doten is loaded if not already
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("❌ OPENAI_API_KEY not found in environment. Bot will fail to parse.")

aclient = AsyncOpenAI(api_key=OPENAI_API_KEY)

DB_FILE = "meetings.db"

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS meetings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  chat_id INTEGER,
                  topic TEXT,
                  meeting_time TIMESTAMP,
                  link TEXT,
                  context TEXT,
                  reminder_60_sent BOOLEAN DEFAULT 0,
                  reminder_15_sent BOOLEAN DEFAULT 0,
                  reminder_start_sent BOOLEAN DEFAULT 0)''')
    
    # Migrations
    try: c.execute("ALTER TABLE meetings ADD COLUMN reminder_60_sent BOOLEAN DEFAULT 0")
    except: pass 
    try: c.execute("ALTER TABLE meetings ADD COLUMN context TEXT")
    except: pass
        
    conn.commit()
    conn.close()

# --- Helpers ---
def save_meeting(chat_id, topic, meeting_time, link, context_text=""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO meetings (chat_id, topic, meeting_time, link, context) VALUES (?, ?, ?, ?, ?)",
              (chat_id, topic, meeting_time, link, context_text))
    conn.commit()
    conn.close()

def get_upcoming_meetings(chat_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now()
    c.execute("SELECT topic, meeting_time, link, context FROM meetings WHERE chat_id=? AND meeting_time > ? ORDER BY meeting_time ASC", (chat_id, now))
    rows = c.fetchall()
    conn.close()
    return rows

# --- OpenAI Parsing ---
async def extract_meeting_details(text: str, current_time: str):
    """Uses GPT-4o to parse meeting details from text."""
    system_prompt = f"""
    You are a helpful meeting assistant. Extract meeting details from the user's message.
    Current Date/Time: {current_time}
    
    Return a valid JSON object with:
    - "topic": Short title (e.g. "Team Sync"). If unknown, infer or use "Meeting".
    - "datetime_iso": ISO 8601 format datetime (YYYY-MM-DDTHH:MM:SS) for the meeting start. 
      - Adjust relative terms like "tomorrow" based on current time.
      - If no time specified, do NOT guess. Return null.
    - "link": The video call link (Zoom, Meet, Teams). If none, null.
    - "summary": A brief 1-sentence summary of the context/agenda found in the message (excluding the link/boilerplate).
    
    If it is NOT a meeting request or lacks a time/link, return field as null.
    """
    
    try:
        response = await aclient.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"},
            temperature=0
        )
        data = json.loads(response.choices[0].message.content)
        return data
    except Exception as e:
        logger.error(f"OpenAI Parse Error: {e}")
        return None

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="👋 I am Raizen (Meeting Bot).\n\n"
             "I use AI to understand your invites. Just paste **any** text or link:\n"
             "_'Zoom block...'_ or _'Chat with Bob tomorrow at 2pm...'_"
    )

async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns the chat ID to the user (helpful for API integration)."""
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Private Chat"
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🆔 **Chat ID:** `{chat_id}`\nPop this into your website automation.",
        parse_mode='Markdown'
    )

async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcomes new members to the Inception Sales Team."""
    chat_title = update.effective_chat.title or ""
    
    # Check if it's the right chat
    if "inception sales team" in chat_title.lower():
        logger.info(f"👋 New member in '{chat_title}' (ID: {update.effective_chat.id})")
        
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                continue # Don't welcome myself
                
            # Try to get a name
            name = member.first_name or "Team Member"
            
            # Short, punchy welcome as requested
            welcome_msg = (
                f"🚀 **Welcome, {name}!**\n"
                "🎥 **Inception AI Training:**\n"
                "Watch how the system works here: [web4guru.com/inception-ai](https://web4guru.com/inception-ai)\n\n" 
                "Let's crush some targets! 🎯"
            )
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=welcome_msg,
                parse_mode='Markdown'
            )
    else:
        logger.info(f"New member in '{chat_title}' - Not sending welcome (wrong chat).")

async def manual_announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually triggers the welcome/announcement message. Usage: /announce [Name]"""
    
    # Get name from arguments (e.g. "/announce John")
    if context.args:
        name_to_welcome = " ".join(context.args)
    else:
        name_to_welcome = "Team Member"
        
    welcome_msg = (
        f"🚀 **Welcome, {name_to_welcome}!**\n"
        "🎥 **Inception AI Training:**\n"
        "Watch how the system works here: [web4guru.com/inception-ai](https://web4guru.com/inception-ai)\n\n" 
        "Let's crush some targets! 🎯"
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=welcome_msg,
        parse_mode='Markdown'
    )

async def list_meetings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    meetings = get_upcoming_meetings(update.effective_chat.id)
    if not meetings:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No upcoming meetings found.")
        return

    msg = "📅 *Upcoming Meetings:*\n\n"
    for m in meetings:
        topic, m_time, link, ctx = m
        if isinstance(m_time, str):
            try:
                dt = datetime.fromisoformat(m_time)
                nice_time = dt.strftime("%A, %b %d at %I:%M %p")
            except:
                nice_time = m_time
        else:
            nice_time = m_time.strftime("%A, %b %d at %I:%M %p")
            
        ctx_display = f"\n  📝 _{ctx}_" if ctx else ""
        msg += f"• *{topic}*\n  🕒 {nice_time}{ctx_display}\n  🔗 {link}\n\n"
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text: return
    
    chat_title = update.effective_chat.title
    if not chat_title:
        # Private chat? Or updated without title?
        chat_title = "Private/Unknown"
        
    logger.info(f"📩 RECEIVED: '{text}' from {update.effective_chat.id} ({chat_title})")

    # --- CHAT ROUTING ---
    # User request: Only process meeting logic in "Zoom Alerts"
    # We use lower() to be forgiving of capitalization
    if chat_title.lower() != "zoom alerts":
        if chat_title.lower() == "inception sales team":
            logger.info("🚫 Ignoring message from 'Inception Sales Team' (Reserved for Sales Function)")
        else:
            logger.info(f"🚫 Ignoring message from '{chat_title}' (Not 'Zoom Alerts')")
        return

    # Preliminary check: Does it look like a meeting request?
    # To save costs, maybe only if it has a link OR time keywords?
    # User said "Zoom invite format", so it usually has a link.
    # But let's be generous.
    
    # Send "Thinking..." or similar? No, Telegram might be fast enough.
    # await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = await extract_meeting_details(text, now_str)
    
    if not data:
        # AI failed completely?
        return 
        
    # Check what we got
    m_time = data.get("datetime_iso")
    link = data.get("link")
    topic = data.get("topic", "Meeting")
    summary = data.get("summary", "")
    
    if link and m_time:
        # Success!
        try:
            dt = datetime.fromisoformat(m_time)
            save_meeting(update.effective_chat.id, topic, dt, link, summary)
            
            nice_date = dt.strftime("%A, %b %d at %I:%M %p")
            ctx_msg = f"\n📝 *Summary:* _{summary}_" if summary else ""
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ *Scheduled:*\n{topic}\n🕒 {nice_date}\n🔗 {link}{ctx_msg}\n\n_Reminders set (1h, 15m)._",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Save error: {e}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Error saving meeting.")
            
    elif link and not m_time:
        # Found link but no time
         await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⚠️ I saw a link but couldn't determine the time. Please add the date/time."
        )
    elif not link and m_time:
         # Found time but no link
         # Maybe they want to schedule In-Person? Or add link later?
         # For now, require link as per previous logic, but let's be softer.
         pass # Ignore simple chat messages with dates unless they explicitly ask for a meeting
         
         if "meeting" in text.lower() or "schedule" in text.lower():
             await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ Time detected, but missing the Link. Please post the Zoom/Meet link."
            )

# --- Scheduler Job ---
async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Checks DB for meetings starting soon and sends alerts."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, chat_id, topic, meeting_time, link, context, reminder_60_sent, reminder_15_sent, reminder_start_sent FROM meetings WHERE reminder_start_sent = 0")
    rows = c.fetchall()
    
    now = datetime.now()
    
    for row in rows:
        m_id, chat_id, topic, m_time_str, link, ctx, rem_60, rem_15, rem_start = row
        try:
            m_time = datetime.fromisoformat(m_time_str)
        except:
            continue
            
        diff = (m_time - now).total_seconds()
        ctx_display = f"\n📝 *Summary:* _{ctx}_" if ctx else ""
        
        # 1 Hour
        if 0 < diff <= 3600 and not rem_60:
            await context.bot.send_message(chat_id=chat_id, text=f"⏰ *Meeting within 1 Hour:*\n{topic}{ctx_display}\n🔗 {link}", parse_mode='Markdown')
            c.execute("UPDATE meetings SET reminder_60_sent=1 WHERE id=?", (m_id,))
            conn.commit()

        # 15 Min
        elif 0 < diff <= 900 and not rem_15:
            await context.bot.send_message(chat_id=chat_id, text=f"⏰ *Starting in 15 mins:*\n{topic}{ctx_display}\n🔗 {link}", parse_mode='Markdown')
            c.execute("UPDATE meetings SET reminder_15_sent=1 WHERE id=?", (m_id,))
            conn.commit()
            
        # Start
        elif diff <= 0 and not rem_start:
             await context.bot.send_message(chat_id=chat_id, text=f"🚀 *Meeting Starting NOW:*\n{topic}{ctx_display}\n🔗 {link}", parse_mode='Markdown')
             c.execute("UPDATE meetings SET reminder_start_sent=1 WHERE id=?", (m_id,))
             conn.commit()
             
    conn.close()

if __name__ == '__main__':
    if not TOKEN:
        print("Error: No Token Found")
        sys.exit(1)
    
    if not OPENAI_API_KEY:
        print("Error: No OpenAI API Key Found")
        # Don't exit, just run with errors? No, exit.
        sys.exit(1)
        
    init_db()
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('meetings', list_meetings))
    application.add_handler(CommandHandler('id', get_chat_id))
    application.add_handler(CommandHandler('announce', manual_announce))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    job_queue = application.job_queue
    job_queue.run_repeating(check_reminders, interval=60, first=10)
    
    print("🤖 AI Meeting Manager Bot Started (Powered by GPT-4o)...")
    application.run_polling()
