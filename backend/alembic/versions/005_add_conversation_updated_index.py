"""Add index for conversation history queries.

Revision ID: 005_add_conversation_updated_index
Revises: 004_fix_conversation_id_type
Create Date: 2025-12-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add index for conversation history queries sorted by updated_at."""
    op.create_index(
        'ix_conversations_user_updated',
        'conversations',
        ['user_id', 'updated_at'],
        unique=False
    )


def downgrade() -> None:
    """Remove the index."""
    op.drop_index('ix_conversations_user_updated', table_name='conversations')
