import os
from fastapi import FastAPI, Request, HTTPException, Cookie, Response, APIRouter, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import jwt
from typing import Optional
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Constants
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
VIDSRC_BASE_URL = "https://vidsrc.xyz/embed"
JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key-here')  # Make sure to set this in .env
TOKEN_EXPIRY_HOURS = 2

# Create a session with retry strategy
session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["GET"]
)
session.mount('https://', HTTPAdapter(max_retries=retries))

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Create templates directory if it doesn't exist
os.makedirs("templates", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

api_router = APIRouter()

@api_router.get("/api/search")
async def search_tmdb(q: str = Query(...)):
    movie_url = f"https://api.themoviedb.org/3/search/movie"
    tv_url = f"https://api.themoviedb.org/3/search/tv"
    params = {"api_key": TMDB_API_KEY, "query": q}
    movie_data = fetch_tmdb_data(movie_url, params)
    tv_data = fetch_tmdb_data(tv_url, params)
    movie_results = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "image": f"https://image.tmdb.org/t/p/w200{item['poster_path']}" if item.get("poster_path") else "",
            "description": item.get("overview", ""),
            "type": "Movie",
            "media_type": "movie"
        }
        for item in movie_data.get("results", [])
    ]
    tv_results = [
        {
            "id": item.get("id"),
            "title": item.get("name"),
            "image": f"https://image.tmdb.org/t/p/w200{item['poster_path']}" if item.get("poster_path") else "",
            "description": item.get("overview", ""),
            "type": "TV Show",
            "media_type": "tv"
        }
        for item in tv_data.get("results", [])
    ]
    return JSONResponse(content=movie_results + tv_results)

@api_router.get("/api/imdb_lookup")
async def imdb_lookup(id: str = Query(...)):
    url = f"https://api.themoviedb.org/3/find/{id}"
    params = {
        "api_key": TMDB_API_KEY,
        "external_source": "imdb_id"
    }
    data = fetch_tmdb_data(url, params)
    # Try to find a movie or tv result
    if data.get("movie_results"):
        tmdb_id = data["movie_results"][0]["id"]
        return {"tmdb_id": tmdb_id, "media_type": "movie"}
    if data.get("tv_results"):
        tmdb_id = data["tv_results"][0]["id"]
        return {"tmdb_id": tmdb_id, "media_type": "tv"}
    return {"error": "Not found"}

app.include_router(api_router)

def fetch_tmdb_data(url: str, params: dict) -> dict:
    """Fetch data from TMDB API with retries and error handling."""
    try:
        for attempt in range(3):  # Try up to 3 times
            try:
                response = session.get(url, params=params, timeout=10)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                if attempt == 2:  # Last attempt
                    raise
                time.sleep(1)  # Wait 1 second before retrying
    except requests.RequestException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Error connecting to TMDB API. Please try again in a few moments. Error: {str(e)}"
        )

def generate_access_token(media_type: str, tmdb_id: str) -> str:
    """Generate a JWT token for media access."""
    expiry = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)
    payload = {
        "media_type": media_type,
        "tmdb_id": tmdb_id,
        "exp": expiry
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_access_token(token: str, media_type: str, tmdb_id: str) -> bool:
    """Verify if the token is valid and matches the requested media."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return (payload["media_type"] == media_type and 
                payload["tmdb_id"] == tmdb_id and 
                datetime.utcfromtimestamp(payload["exp"]) > datetime.utcnow())
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False

@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("static/index.html")

@app.get("/ping")
async def ping():
    """
    Simple ping endpoint that returns a 200 OK response.
    Can be used by monitoring services to check if the server is alive.
    """
    return {"status": "ok", "timestamp": time.time()}

@app.get("/watch/{media_type}/{tmdb_id}", response_class=HTMLResponse)
async def watch_page(
    request: Request, 
    media_type: str, 
    tmdb_id: str, 
    access_token: Optional[str] = Cookie(None)
):
    try:
        # If user has valid token, redirect to player page
        if access_token and verify_access_token(access_token, media_type, tmdb_id):
            return RedirectResponse(url=f"/player/{media_type}/{tmdb_id}")

        # Validate media type
        if media_type not in ["movie", "tv"]:
            raise HTTPException(status_code=400, detail="Invalid media type")

        # Fetch movie/TV show details from TMDB
        url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
        params = {"api_key": TMDB_API_KEY}
        
        # Fetch main data
        data = fetch_tmdb_data(url, params)
        
        title = data.get("title") or data.get("name", "Unknown Title")
        poster_path = data.get("poster_path")
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else ""
        
        return templates.TemplateResponse(
            "watch.html",
            {
                "request": request,
                "title": title,
                "poster_url": poster_url,
                "redirect_url": f"/player/{media_type}/{tmdb_id}",
                "countdown": 5,
                "media_type": media_type,
                "tmdb_id": tmdb_id
            }
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred. Please try again later. Error: {str(e)}"
        )

@app.post("/get-access-token/{media_type}/{tmdb_id}")
async def get_access_token(
    media_type: str,
    tmdb_id: str,
    request: Request,
    response: Response
):
    """Generate and set access token only when explicitly requested."""
    try:
        # Validate media type
        if media_type not in ["movie", "tv"]:
            raise HTTPException(status_code=400, detail="Invalid media type")

        # Generate new access token
        token = generate_access_token(media_type, tmdb_id)
        
        # Set cookie with token
        response.set_cookie(
            key="access_token",
            value=token,
            max_age=TOKEN_EXPIRY_HOURS * 3600,  # Convert hours to seconds
            httponly=True,
            secure=True,  # Only send over HTTPS
            samesite="strict"  # Strict CSRF protection
        )
        
        return {"status": "success"}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate access token: {str(e)}"
        )

@app.get("/player/{media_type}/{tmdb_id}", response_class=HTMLResponse)
async def player_page(
    request: Request, 
    media_type: str, 
    tmdb_id: str, 
    access_token: Optional[str] = Cookie(None)
):
    try:
        # Enhanced token verification
        if not access_token:
            return RedirectResponse(url=f"/watch/{media_type}/{tmdb_id}")
            
        # Verify token and check if it's expired
        try:
            payload = jwt.decode(access_token, JWT_SECRET, algorithms=["HS256"])
            if (
                payload["media_type"] != media_type or 
                payload["tmdb_id"] != tmdb_id or 
                datetime.utcfromtimestamp(payload["exp"]) <= datetime.utcnow()
            ):
                return RedirectResponse(url=f"/watch/{media_type}/{tmdb_id}")
        except jwt.InvalidTokenError:
            return RedirectResponse(url=f"/watch/{media_type}/{tmdb_id}")

        # Validate media type
        if media_type not in ["movie", "tv"]:
            raise HTTPException(status_code=400, detail="Invalid media type")

        # Fetch movie/TV show details from TMDB
        url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
        params = {"api_key": TMDB_API_KEY}
        
        # Fetch main data
        data = fetch_tmdb_data(url, params)
        
        # Get IMDb ID if available for movies
        imdb_id = ""
        if media_type == "movie":
            try:
                external_ids_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/external_ids"
                external_ids = fetch_tmdb_data(external_ids_url, params)
                imdb_id = external_ids.get("imdb_id", "")
                # Ensure IMDb ID starts with 'tt'
                if imdb_id and not imdb_id.startswith("tt"):
                    imdb_id = f"tt{imdb_id}"
            except HTTPException:
                pass
        
        title = data.get("title") or data.get("name", "Unknown Title")
        
        # Generate VidSrc URL with proper formatting
        if media_type == "movie":
            if not imdb_id:
                raise HTTPException(
                    status_code=404,
                    detail="IMDb ID not found for this movie. Please try searching with an IMDb link instead."
                )
            player_url = f"{VIDSRC_BASE_URL}/movie/{imdb_id}"
        else:
            player_url = f"{VIDSRC_BASE_URL}/tv/{tmdb_id}"

        return templates.TemplateResponse(
            "player.html",
            {
                "request": request,
                "title": title,
                "player_url": player_url,
                "media_type": media_type,
                "tmdb_id": tmdb_id,
                "tmdb_api_key": TMDB_API_KEY
            }
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred. Please try again later."
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info") 
