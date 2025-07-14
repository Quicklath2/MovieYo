import asyncio
import logging
from server import app
import uvicorn
from bot import run_bot
import os
import signal
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class Server(uvicorn.Server):
    """Customized uvicorn.Server
    
    Uvicorn server that handles graceful shutdown and keeps event loop running
    """
    def install_signal_handlers(self):
        # Override to prevent uvicorn from handling signals
        pass

async def run_fastapi():
    """Run the FastAPI server."""
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=int(os.getenv('PORT', 10000)),  # Render uses port 10000
        log_level="info"
    )
    server = Server(config=config)
    await server.serve()

async def main():
    """Run both the bot and FastAPI server concurrently."""
    try:
        # Create tasks for both services
        tasks = [
            asyncio.create_task(run_fastapi()),
            asyncio.create_task(run_bot())
        ]
        
        # Wait for either task to complete (or fail)
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel any pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Raise any exceptions from completed tasks
        for task in done:
            task.result()

    except Exception as e:
        logger.error(f"Error running services: {e}")
        raise

def handle_shutdown(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}. Initiating shutdown...")
    raise KeyboardInterrupt

if __name__ == "__main__":
    # Register shutdown handlers
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    try:
        # Run the main function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application crashed: {e}")
        raise 