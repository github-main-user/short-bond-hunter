#!/usr/bin/env python
import asyncio
import logging

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

if __name__ == "__main__":
    logging.info("Starting market streaming session")

    try:
        asyncio.run(start_market_streaming_session())
    except KeyboardInterrupt:
        pass

    logging.info("Ending market streaming session")
