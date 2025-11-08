from dataclasses import replace
from datetime import datetime, timedelta

import pytest
from tinkoff.invest import MoneyValue, OrderBook, Quotation
from tinkoff.invest.schemas import RiskLevel

from src.market.schemas import NBond
from src.market.utils import filter_bonds, normalize_quotation


@pytest.fixture
def sample_orderbook() -> OrderBook:
    return OrderBook(figi="some_figi", depth=1, bids=[], asks=[])


@pytest.fixture
def sample_bond(sample_orderbook: OrderBook) -> NBond:
    return NBond(
        figi="some_figi",
        ticker="some_ticker",
        nominal=1000.0,
        aci_value=0.0,
        maturity_date=datetime.now() + timedelta(days=30),
        risk_level=RiskLevel.RISK_LEVEL_LOW,
        is_unlimited=False,
        currency="rub",
        nominal_currency="rub",
        for_qual_investor=False,
        trading_status=1,
        fee_percent=0.1,
        _coupons_sum=0.0,
        _orderbook=sample_orderbook,
    )


def test_normalize_quotation():
    value = MoneyValue(units=19, nano=150000000)
    normalized_value = normalize_quotation(value)
    assert normalized_value == 19.15

    value = Quotation(units=19, nano=150000000)
    normalized_value = normalize_quotation(value)
    assert normalized_value == 19.15


def test_filter_bonds(sample_bond: NBond):
    bonds = [
        sample_bond,
        replace(sample_bond, for_qual_investor=True),
        replace(sample_bond, is_unlimited=True),
        replace(sample_bond, currency="usd"),
        replace(sample_bond, nominal_currency="usd"),
        replace(sample_bond, maturity_date=datetime.now() + timedelta(days=100)),
        replace(sample_bond, risk_level=RiskLevel.RISK_LEVEL_HIGH),
        replace(sample_bond, risk_level=RiskLevel.RISK_LEVEL_UNSPECIFIED),
    ]
    filtered_bonds = filter_bonds(bonds, maximum_days=90)
    assert len(filtered_bonds) == 1
    assert filtered_bonds[0] == sample_bond
