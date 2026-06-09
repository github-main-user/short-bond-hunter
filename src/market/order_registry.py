from dataclasses import dataclass


@dataclass
class ActiveBidOrder:
    order_id: str
    figi: str
    price: float
    quantity: int


class OrderRegistry:
    def __init__(self) -> None:
        self._by_figi: dict[str, dict[str, ActiveBidOrder]] = {}

    def add(self, order: ActiveBidOrder) -> None:
        self._by_figi.setdefault(order.figi, {})[order.order_id] = order

    def remove(self, figi: str, order_id: str) -> None:
        bucket = self._by_figi.get(figi)
        if not bucket:
            return
        bucket.pop(order_id, None)
        if not bucket:
            self._by_figi.pop(figi, None)

    def get(self, figi: str, order_id: str) -> ActiveBidOrder | None:
        return self._by_figi.get(figi, {}).get(order_id)

    def bids_for(self, figi: str) -> list[ActiveBidOrder]:
        return list(self._by_figi.get(figi, {}).values())

    def reserved_value_for(self, figi: str) -> float:
        return sum(o.price * o.quantity for o in self.bids_for(figi))

    def set_quantity(self, figi: str, order_id: str, quantity: int) -> None:
        order = self.get(figi, order_id)
        if order is None:
            return
        order.quantity = quantity

    def has_order_id(self, order_id: str) -> bool:
        return any(order_id in bucket for bucket in self._by_figi.values())
