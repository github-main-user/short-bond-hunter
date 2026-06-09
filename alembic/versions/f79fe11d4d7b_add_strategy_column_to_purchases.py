"""add strategy column to purchases

Revision ID: f79fe11d4d7b
Revises: 4dcc64c92227
Create Date: 2026-06-09 15:28:31.411459

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f79fe11d4d7b"
down_revision: Union[str, Sequence[str], None] = "4dcc64c92227"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    strategy_enum = sa.Enum("ASK_SNIPER", "BID_WAITER", name="strategy")
    op.add_column(
        "bond_purchases",
        sa.Column("strategy", strategy_enum, nullable=True),
    )
    op.execute(
        "UPDATE bond_purchases SET strategy = 'ASK_SNIPER' WHERE strategy IS NULL"
    )
    with op.batch_alter_table("bond_purchases") as batch_op:
        batch_op.alter_column("strategy", existing_type=strategy_enum, nullable=False)


def downgrade() -> None:
    op.drop_column("bond_purchases", "strategy")
