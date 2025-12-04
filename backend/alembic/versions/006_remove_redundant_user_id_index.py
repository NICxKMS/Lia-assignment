"""Remove redundant single-column user_id index on conversations table.

The composite indexes (user_id, created_at) and (user_id, updated_at) already
cover queries that filter by user_id, making the single-column index redundant.

Revision ID: 006_remove_redundant_user_id_index
Revises: 005_add_conversation_updated_index
Create Date: 2024-12-03

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove the redundant single-column index on user_id."""
    # Only drop if exists to avoid errors if already removed
    op.execute("""
        DROP INDEX IF EXISTS ix_conversations_user_id;
    """)


def downgrade() -> None:
    """Recreate the single-column index on user_id if needed."""
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_conversations_user_id ON conversations (user_id);
    """)
