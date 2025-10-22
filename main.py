#!/usr/bin/env python
import logging

from src.market.streaming import run_streaming_logic

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
    try:
        run_streaming_logic()
    except KeyboardInterrupt:
        pass
