"""add bond names, update maturities

Revision ID: d065ad18d7ed
Revises: 758073aa4291
Create Date: 2026-04-24 13:24:49.374978

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d065ad18d7ed"
down_revision: Union[str, Sequence[str], None] = "758073aa4291"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bond_purchases",
        sa.Column("bond_name", sa.String(), nullable=False, server_default=""),
    )

    with op.batch_alter_table("bond_maturities") as batch_op:
        batch_op.add_column(
            sa.Column("bond_name", sa.String(), nullable=False, server_default="")
        )
        batch_op.alter_column(
            "principal_received", existing_type=sa.FLOAT(), nullable=True
        )
        batch_op.create_unique_constraint("uq_bond_maturities_bond_figi", ["bond_figi"])
        batch_op.drop_column("operation_id")


def downgrade() -> None:
    op.drop_column("bond_purchases", "bond_name")

    with op.batch_alter_table("bond_maturities") as batch_op:
        batch_op.add_column(
            sa.Column("operation_id", sa.VARCHAR(), nullable=False, server_default="")
        )
        batch_op.drop_constraint("uq_bond_maturities_bond_figi", type_="unique")
        batch_op.alter_column(
            "principal_received", existing_type=sa.FLOAT(), nullable=False
        )
        batch_op.drop_column("bond_name")
