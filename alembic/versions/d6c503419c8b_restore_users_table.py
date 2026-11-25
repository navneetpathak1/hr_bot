"""restore users table

Revision ID: d6c503419c8b
Revises: 261515f7eb82
Create Date: 2026-11-25 16:36:52.406444

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6c503419c8b'
down_revision: Union[str, Sequence[str], None] = '261515f7eb82'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
