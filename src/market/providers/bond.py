from t_tech.invest.async_services import AsyncServices


class BondProvider:
    def __init__(self, client: AsyncServices) -> None:
        self._client = client
