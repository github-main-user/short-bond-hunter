from fastapi import FastAPI

from src.state import app_state

api = FastAPI()


@api.get("/")
async def root():
    return {
        "last_deal_annual_yield": app_state.last_deal_annual_yield,
        "last_deal_datetime": app_state.last_deal_datetime,
    }
