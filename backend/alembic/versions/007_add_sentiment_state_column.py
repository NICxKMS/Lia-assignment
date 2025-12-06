"""Add sentiment_state column to conversations table.

This column stores the rolling cumulative sentiment state (summary, score, count, label)
for O(1) incremental sentiment analysis instead of re-analyzing all messages.

Revision ID: 007_add_sentiment_state_column
Revises: 006_remove_redundant_user_id_index
Create Date: 2024-12-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add sentiment_state JSON column to conversations table."""
    op.add_column(
        'conversations',
        sa.Column('sentiment_state', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    """Remove sentiment_state column from conversations table."""
    op.drop_column('conversations', 'sentiment_state')
