"""Add missing columns to messages table.

Revision ID: 003_add_messages_columns
Revises: 002_add_updated_at_columns
Create Date: 2024-12-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add sentiment_data to messages if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'messages' AND column_name = 'sentiment_data'
            ) THEN
                ALTER TABLE messages ADD COLUMN sentiment_data JSONB;
            END IF;
        END $$;
    """)
    
    # Add model_info to messages if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'messages' AND column_name = 'model_info'
            ) THEN
                ALTER TABLE messages ADD COLUMN model_info JSONB;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.drop_column('messages', 'model_info')
    op.drop_column('messages', 'sentiment_data')
