from dataclasses import dataclass
from datetime import datetime


@dataclass
class AppState:
    last_deal_datetime: datetime | None = None
    last_deal_annual_yield: float | None = None


app_state = AppState()
