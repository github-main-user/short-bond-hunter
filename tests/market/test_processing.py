from unittest.mock import MagicMock

import pytest

from src.config import settings
from src.market.processing import is_bond_eligible_for_purchase
from src.market.schemas import NBond


@pytest.fixture
def mock_settings():
    original_settings = {
        "BLACK_LIST_TICKERS": settings.BLACK_LIST_TICKERS,
        "ANNUAL_YIELD_MIN": settings.ANNUAL_YIELD_MIN,
        "ANNUAL_YIELD_MAX": settings.ANNUAL_YIELD_MAX,
    }
    settings.BLACK_LIST_TICKERS = ["BLOCKED"]
    settings.ANNUAL_YIELD_MIN = 5.0
    settings.ANNUAL_YIELD_MAX = 10.0
    yield
    settings.BLACK_LIST_TICKERS = original_settings["BLACK_LIST_TICKERS"]
    settings.ANNUAL_YIELD_MIN = original_settings["ANNUAL_YIELD_MIN"]
    settings.ANNUAL_YIELD_MAX = original_settings["ANNUAL_YIELD_MAX"]


@pytest.fixture
def mock_bond():
    bond = MagicMock(spec=NBond)
    bond.ticker = "TEST"
    bond.annual_yield = 7.5
    bond.real_price = 100.0
    return bond


def test_bond_eligible_for_purchase(mock_bond, mock_settings):
    """
    Test case for a bond that is eligible for purchase.
    """
    assert is_bond_eligible_for_purchase(mock_bond) is True


def test_bond_in_blacklist(mock_bond, mock_settings):
    """
    Test case for a bond that is in the blacklist.
    """
    mock_bond.ticker = "BLOCKED"
    assert is_bond_eligible_for_purchase(mock_bond) is False


def test_bond_annual_yield_below_min(mock_bond, mock_settings):
    """
    Test case for a bond with annual yield below the minimum.
    """
    mock_bond.annual_yield = 4.0
    assert is_bond_eligible_for_purchase(mock_bond) is False


def test_bond_annual_yield_above_max(mock_bond, mock_settings):
    """
    Test case for a bond with annual yield above the maximum.
    """
    mock_bond.annual_yield = 11.0
    assert is_bond_eligible_for_purchase(mock_bond) is False


def test_bond_real_price_zero(mock_bond, mock_settings):
    """
    Test case for a bond with real price of zero.
    """
    mock_bond.real_price = 0.0
    assert is_bond_eligible_for_purchase(mock_bond) is False


def test_bond_real_price_negative(mock_bond, mock_settings):
    """
    Test case for a bond with negative real price.
    """
    mock_bond.real_price = -10.0
    assert is_bond_eligible_for_purchase(mock_bond) is False


def test_bond_annual_yield_at_min_boundary(mock_bond, mock_settings):
    """
    Test case for a bond with annual yield exactly at the minimum boundary.
    """
    mock_bond.annual_yield = settings.ANNUAL_YIELD_MIN
    assert is_bond_eligible_for_purchase(mock_bond) is True


def test_bond_annual_yield_at_max_boundary(mock_bond, mock_settings):
    """
    Test case for a bond with annual yield exactly at the maximum boundary.
    """
    mock_bond.annual_yield = settings.ANNUAL_YIELD_MAX
    assert is_bond_eligible_for_purchase(mock_bond) is True
