# Movie Streaming Telegram Bot

A Telegram bot that helps users find movies and TV shows and watch them through VidSrc links. The bot integrates with the TMDB API to fetch movie metadata and provides a secure way to watch content after viewing ads.

## Features

- Search for movies and TV shows by name or IMDb link
- Fetch detailed movie information from TMDB
- Secure redirection to VidSrc player
- Ad integration with countdown timer
- Support for both movies and TV shows

## Setup

1. Clone this repository:
```bash
git clone <your-repo-url>
cd <your-repo-directory>
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

4. Fill in the required environment variables in `.env`:
- `TELEGRAM_BOT_TOKEN`: Get from [@BotFather](https://t.me/BotFather)
- `TMDB_API_KEY`: Get from [TMDB API Settings](https://www.themoviedb.org/settings/api)
- `BASE_URL`: Your deployed application URL (use `http://localhost:8000` for local development)

## Running the Application

1. Start the FastAPI server:
```bash
python server.py
```

2. In a separate terminal, start the Telegram bot:
```bash
python bot.py
```

## Usage

1. Start a chat with your bot on Telegram
2. Send a movie/TV show name or IMDb link
3. Select from the search results
4. Wait for the ad countdown to complete
5. Enjoy your content!

## Deployment

The application can be deployed to platforms like Heroku or AWS:

1. Create a new Heroku app
2. Set the environment variables in Heroku settings
3. Deploy the code to Heroku
4. Update the `BASE_URL` in your `.env` file to your Heroku app URL

## Security

- API keys are stored securely in environment variables
- VidSrc links are never exposed to the frontend
- All sensitive operations are handled on the backend

## Contributing

Feel free to open issues or submit pull requests for any improvements.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 