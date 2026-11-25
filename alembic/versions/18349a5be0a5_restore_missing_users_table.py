
"""restore missing users table"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '18349a5be0a5'
down_revision: Union[str, Sequence[str], None] = 'd6c503419c8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password', sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )

    op.create_index(
        'ix_users_id',
        'users',
        ['id'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_users_id', table_name='users')
    op.drop_table('users')
