from collections.abc import Iterable

from src.market.domain import EnrichedBond


class BondCatalog:
    def __init__(self) -> None:
        self._by_figi: dict[str, EnrichedBond] = {}

    def replace_all(self, bonds: Iterable[EnrichedBond]) -> None:
        self._by_figi = {bond.figi: bond for bond in bonds}

    def get(self, figi: str) -> EnrichedBond | None:
        return self._by_figi.get(figi)

    def all(self) -> list[EnrichedBond]:
        return list(self._by_figi.values())
