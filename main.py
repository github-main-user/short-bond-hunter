#!/usr/bin/env python
import asyncio
import logging

from uvicorn import Config, Server

from src.api import api
from src.market.streaming import start_market_streaming_session

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/app.log"),
        logging.FileHandler("logs/latest.log", mode="w"),
    ],
)


async def run_api(app, host: str = "0.0.0.0", port: int = 8000):
    config = Config(app=app, host=host, port=port)
    server = Server(config)
    await server.serve()


async def main():
    logging.info("Starting market streaming session and API server")

    api_task = asyncio.create_task(run_api(api))
    bot_task = asyncio.create_task(start_market_streaming_session())

    await asyncio.gather(api_task, bot_task)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

    logging.info("Ending market streaming session")
