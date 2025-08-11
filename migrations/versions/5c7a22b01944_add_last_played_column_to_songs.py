"""Add last_played column to songs

Revision ID: 5c7a22b01944
Revises: b7fdafff5477
Create Date: 2025-08-10 19:45:33.050649

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c7a22b01944'
down_revision: Union[str, Sequence[str], None] = 'b7fdafff5477'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add last_played column to songs table
    op.add_column('songs', sa.Column('last_played', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove last_played column from songs table
    op.drop_column('songs', 'last_played')
