from t_tech.invest.grpc.schemas import MoneyValue, Quotation


def to_float(money: MoneyValue | Quotation) -> float:
    return money.units + (money.nano / 1e9)


def from_float(value: float) -> Quotation:
    units = int(value)
    nano = int(round((value - units) * 1e9))
    return Quotation(units=units, nano=nano)
