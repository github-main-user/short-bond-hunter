import time

from src.stats.models import PurchaseStrategy


class CooldownRegistry:
    def __init__(self) -> None:
        self._last: dict[tuple[PurchaseStrategy, str], float] = {}

    def on_cooldown(
        self, strategy: PurchaseStrategy, figi: str, window_s: float
    ) -> bool:
        last = self._last.get((strategy, figi))
        return last is not None and time.monotonic() - last < window_s

    def mark(self, strategy: PurchaseStrategy, figi: str) -> None:
        self._last[(strategy, figi)] = time.monotonic()
