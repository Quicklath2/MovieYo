import os
import sys
import logging
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
BASE_URL = os.getenv('BASE_URL')

# Create a session with retry strategy
session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["GET"]
)
session.mount('https://', HTTPAdapter(max_retries=retries))

# Check if required environment variables are set
if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN environment variable is not set!")
    sys.exit(1)
if not TMDB_API_KEY:
    logger.error("TMDB_API_KEY environment variable is not set!")
    sys.exit(1)
if not BASE_URL:
    logger.warning("BASE_URL environment variable is not set! Using default: http://localhost:8000")
    BASE_URL = "http://localhost:8000"

def fetch_tmdb_data(url: str, params: dict) -> dict:
    """Fetch data from TMDB API with retries and error handling."""
    for attempt in range(3):
        try:
            response = session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            if attempt == 2:  # Last attempt
                raise
            time.sleep(1)  # Wait 1 second before retrying
    raise requests.RequestException("Failed after 3 attempts")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    welcome_message = (
        "👋 Welcome to the Movie Search Bot!\n\n"
        "You can:\n"
        "1. Send me a movie/TV show name to search\n"
        "2. Send me an IMDb link\n\n"
        "I'll help you find what you're looking for! 🎬"
    )
    await update.message.reply_text(welcome_message)

async def search_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle movie/TV show search requests."""
    query = update.message.text.strip()
    
    try:
        # Check if the input is an IMDb link
        if "imdb.com/title/" in query.lower():
            # Extract IMDb ID using more robust method
            imdb_id = query.split("title/")[-1].split("/")[0].strip()
            if imdb_id.startswith("tt"):
                # Search by IMDb ID
                url = f"https://api.themoviedb.org/3/find/{imdb_id}"
                params = {
                    "api_key": TMDB_API_KEY,
                    "external_source": "imdb_id"
                }
                
                data = fetch_tmdb_data(url, params)
                
                # For IMDb links, we need to check movie_results and tv_results
                results = []
                if data.get("movie_results"):
                    for r in data["movie_results"]:
                        r["media_type"] = "movie"
                        r["imdb_id"] = imdb_id  # Store the IMDb ID for later use
                        results.append(r)
                if data.get("tv_results"):
                    for r in data["tv_results"]:
                        r["media_type"] = "tv"
                        results.append(r)
                
                if results:
                    await display_results(update, results, 1)
                else:
                    await update.message.reply_text("Sorry, I couldn't find this title in our database. 😕")
                return
        
        # If not an IMDb link, search by title
        url = "https://api.themoviedb.org/3/search/multi"
        params = {
            "api_key": TMDB_API_KEY,
            "query": query,
            "page": context.user_data.get('page', 1)  # Get current page from user data
        }
        
        data = fetch_tmdb_data(url, params)
        
        if "results" in data and data["results"]:
            # Filter for movies and TV shows only
            results = [r for r in data["results"] if r.get("media_type") in ["movie", "tv"]]
            
            # Sort results by release date (newest first)
            results.sort(key=lambda x: (
                x.get("release_date", "") if x["media_type"] == "movie" 
                else x.get("first_air_date", "")
            ), reverse=True)
            
            # Store results in user data for pagination
            context.user_data['search_results'] = results
            context.user_data['total_pages'] = (len(results) + 4) // 5  # 5 results per page
            
            # Display the first page of results
            await display_results(update, results, 1)
        else:
            await update.message.reply_text("Sorry, I couldn't find any results for your search. 😕")
            
    except requests.RequestException as e:
        logger.error(f"Error searching media: {e}")
        await update.message.reply_text(
            "Sorry, I'm having trouble connecting to the movie database. "
            "Please wait a moment and try again. 😔"
        )
    except Exception as e:
        logger.error(f"Unexpected error searching media: {e}")
        await update.message.reply_text(
            "Sorry, something unexpected happened. "
            "Please try again or try a different search. 😔"
        )

async def display_results(update: Update, results: list, page: int) -> None:
    """Display search results with pagination."""
    start_idx = (page - 1) * 5
    end_idx = start_idx + 5
    page_results = results[start_idx:end_idx]
    
    keyboard = []
    
    # Add result buttons
    for result in page_results:
        title = result.get("title") or result.get("name")
        year = result.get("release_date", "")[:4] if result.get("release_date") else \
              result.get("first_air_date", "")[:4]
        media_type = result["media_type"].upper()
        
        button_text = f"{title} ({year}) - {media_type}"
        if result["media_type"] == "movie" and "imdb_id" in result:
            callback_data = f"{result['media_type']}_{result['id']}_{result['imdb_id']}"
        else:
            callback_data = f"{result['media_type']}_{result['id']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # Add navigation buttons if there are multiple pages
    total_pages = (len(results) + 4) // 5
    if total_pages > 1:
        nav_buttons = []
        
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page_{page-1}"))
        
        nav_buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="current_page"))
        
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
        
        keyboard.append(nav_buttons)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if page == 1:
        await update.message.reply_text("Here's what I found:", reply_markup=reply_markup)
    else:
        # Try to edit the existing message for pagination
        try:
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)
        except:
            await update.message.reply_text("Here's what I found:", reply_markup=reply_markup)

async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pagination button callbacks."""
    query = update.callback_query
    await query.answer()
    
    # Extract page number from callback data
    page = int(query.data.split('_')[1])
    
    # Get stored search results
    results = context.user_data.get('search_results', [])
    if results:
        # Update current page in user data
        context.user_data['page'] = page
        # Display the requested page
        await display_results(update, results, page)
    else:
        await query.edit_message_text("Search results expired. Please try your search again.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks from search results."""
    try:
        query = update.callback_query
        await query.answer()
        
        # Parse callback data - now might include IMDb ID for movies
        data_parts = query.data.split("_")
        media_type = data_parts[0]
        tmdb_id = data_parts[1]
        imdb_id = data_parts[2] if len(data_parts) > 2 else None
        
        watch_url = f"{BASE_URL}/watch/{media_type}/{tmdb_id}"
        if media_type == "movie" and imdb_id:
            watch_url = f"{BASE_URL}/watch/{media_type}/{tmdb_id}?imdb={imdb_id}"
        
        message = (
            f"🎬 Ready to watch!\n\n"
            f"🔗 Watch here: {watch_url}\n\n"
            f"⚠️ Note: You'll see a brief ad before your content loads.\n\n"
            f"💡Tip: Use your mobile/tablet browser instead of Telegram's in-built browser to avoid issues.\nTo do that just hold on link and click on Open in option."
        )
        await query.edit_message_text(text=message)
    except Exception as e:
        logger.error(f"Error in button callback: {e}")
        await query.edit_message_text(
            text="Sorry, something went wrong. Please try searching again."
        )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by Updates."""
    logger.error(f"Update {update} caused error {context.error}")

async def run_bot():
    """Run the bot."""
    try:
        # Create the Application
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_media))
        application.add_handler(CallbackQueryHandler(button_callback, pattern="^(movie|tv)_"))
        application.add_handler(CallbackQueryHandler(handle_pagination, pattern="^page_"))
        
        # Add error handler
        application.add_error_handler(error_handler)

        # Initialize and start the bot
        logger.info("Starting bot polling...")
        await application.initialize()
        await application.start()
        
        # Start polling in the background
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        # Create a never-ending task to keep the bot running
        stop_signal = asyncio.Event()
        while not stop_signal.is_set():
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise
    finally:
        # Properly shutdown the bot if something goes wrong
        try:
            await application.stop()
            await application.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down bot: {e}")

if __name__ == '__main__':
    asyncio.run(run_bot()) 
