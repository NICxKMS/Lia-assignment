"""Add missing columns to sync with ORM models.

Revision ID: 002_add_updated_at_columns
Revises: 001_initial_schema
Create Date: 2024-12-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add updated_at to users if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'updated_at'
            ) THEN
                ALTER TABLE users ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now();
            END IF;
        END $$;
    """)
    
    # Add updated_at to conversations if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'conversations' AND column_name = 'updated_at'
            ) THEN
                ALTER TABLE conversations ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now();
            END IF;
        END $$;
    """)
    
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
    # Remove added columns
    op.drop_column('messages', 'model_info')
    op.drop_column('messages', 'sentiment_data')
    op.drop_column('conversations', 'updated_at')
    op.drop_column('users', 'updated_at')
