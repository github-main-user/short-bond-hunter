from t_tech.invest import MoneyValue, Quotation


def normalize_quotation(money: MoneyValue | Quotation) -> float:
    return money.units + (money.nano / 1e9)


def denormalize_quotation(value: float) -> Quotation:
    units = int(value)
    nano = int(round((value - units) * 1e9))
    return Quotation(units=units, nano=nano)
