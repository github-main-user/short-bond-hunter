"""add expected_maturity_date to purchases

Revision ID: 4dcc64c92227
Revises: d065ad18d7ed
Create Date: 2026-06-03 20:47:30.048438

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4dcc64c92227"
down_revision: Union[str, Sequence[str], None] = "d065ad18d7ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bond_purchases",
        sa.Column("expected_maturity_date", sa.DateTime(), nullable=True),
    )
    op.execute(
        """
        UPDATE bond_purchases
        SET expected_maturity_date = (
            SELECT m.matured_at
            FROM bond_maturities AS m
            WHERE m.bond_figi = bond_purchases.bond_figi
        )
        WHERE expected_maturity_date IS NULL
        """
    )
    with op.batch_alter_table("bond_purchases") as batch_op:
        batch_op.alter_column(
            "expected_maturity_date", existing_type=sa.DateTime(), nullable=False
        )


def downgrade() -> None:
    op.drop_column("bond_purchases", "expected_maturity_date")
