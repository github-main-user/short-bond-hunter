#!/usr/bin/env python
import logging

from src.market.streaming import run_streaming_logic

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

if __name__ == "__main__":
    try:
        run_streaming_logic()
    except KeyboardInterrupt:
        pass
