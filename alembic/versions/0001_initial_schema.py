"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-27 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


risk_level = sa.Enum(
    "UNSPECIFIED", "LOW", "MODERATE", "HIGH", name="risklevel", create_type=False
)
strategy = sa.Enum(
    "ASK_SNIPER", "BID_WAITER", name="purchasestrategy", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    risk_level.create(bind, checkfirst=True)
    strategy.create(bind, checkfirst=True)

    op.create_table(
        "bond_purchases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bond_name", sa.String(), nullable=False),
        sa.Column("bond_figi", sa.String(), nullable=False),
        sa.Column("bond_ticker", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("nominal", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("aci_value", sa.Float(), nullable=False),
        sa.Column("commission_percent", sa.Float(), nullable=False),
        sa.Column("real_price", sa.Float(), nullable=False),
        sa.Column("coupons_sum", sa.Float(), nullable=False),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("tmon_price_at_buy", sa.Float(), nullable=True),
        sa.Column("expected_maturity_date", sa.DateTime(), nullable=False),
        sa.Column("strategy", strategy, nullable=False),
        sa.Column("bought_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "bond_maturities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bond_name", sa.String(), nullable=False),
        sa.Column("bond_figi", sa.String(), nullable=False),
        sa.Column("bond_ticker", sa.String(), nullable=False),
        sa.Column("tmon_price_at_maturity", sa.Float(), nullable=True),
        sa.Column("tmon_price_at_money_received", sa.Float(), nullable=True),
        sa.Column("principal_received", sa.Float(), nullable=True),
        sa.Column("coupon_received", sa.Float(), nullable=True),
        sa.Column("matured_at", sa.DateTime(), nullable=False),
        sa.Column("money_received_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bond_figi", name="uq_bond_maturities_bond_figi"),
    )


def downgrade() -> None:
    op.drop_table("bond_maturities")
    op.drop_table("bond_purchases")

    bind = op.get_bind()
    strategy.drop(bind, checkfirst=True)
    risk_level.drop(bind, checkfirst=True)
