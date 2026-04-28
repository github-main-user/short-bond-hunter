from t_tech.invest import MoneyValue, Quotation


def normalize_quotation(money: MoneyValue | Quotation) -> float:
    return money.units + (money.nano / 1e9)
