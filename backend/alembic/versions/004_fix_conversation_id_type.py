"""Fix conversation_id type mismatch - convert integer to UUID.

Revision ID: 004_fix_conversation_id_type
Revises: 003_add_messages_columns
Create Date: 2024-12-03

This migration converts the conversations.id and messages.conversation_id
from INTEGER to UUID to match the ORM model definitions.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if conversations.id is already UUID type
    op.execute("""
        DO $$
        DECLARE
            col_type text;
        BEGIN
            SELECT data_type INTO col_type 
            FROM information_schema.columns 
            WHERE table_name = 'conversations' AND column_name = 'id';
            
            -- Only run the migration if the column is integer
            IF col_type = 'integer' THEN
                -- Step 1: Add a new UUID column to conversations
                ALTER TABLE conversations ADD COLUMN new_id UUID DEFAULT gen_random_uuid();
                
                -- Step 2: Update new_id with generated UUIDs for existing rows
                UPDATE conversations SET new_id = gen_random_uuid() WHERE new_id IS NULL;
                
                -- Step 3: Add a new UUID column to messages for conversation_id
                ALTER TABLE messages ADD COLUMN new_conversation_id UUID;
                
                -- Step 4: Create a mapping and update messages
                UPDATE messages m 
                SET new_conversation_id = c.new_id 
                FROM conversations c 
                WHERE m.conversation_id::text = c.id::text;
                
                -- Step 5: Drop the foreign key constraint on messages
                ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_conversation_id_fkey;
                
                -- Step 6: Drop the old columns and rename new ones
                ALTER TABLE messages DROP COLUMN conversation_id;
                ALTER TABLE messages RENAME COLUMN new_conversation_id TO conversation_id;
                
                -- Step 7: Drop old conversations.id and rename new_id
                ALTER TABLE conversations DROP CONSTRAINT conversations_pkey;
                ALTER TABLE conversations DROP COLUMN id;
                ALTER TABLE conversations RENAME COLUMN new_id TO id;
                ALTER TABLE conversations ADD PRIMARY KEY (id);
                
                -- Step 8: Recreate foreign key and index
                ALTER TABLE messages 
                    ADD CONSTRAINT messages_conversation_id_fkey 
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE;
                
                -- Step 9: Create indexes
                CREATE INDEX IF NOT EXISTS ix_messages_conversation_id ON messages(conversation_id);
                CREATE INDEX IF NOT EXISTS ix_conversations_user_created ON conversations(user_id, created_at);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Converting back from UUID to INTEGER is complex and would lose data
    # This is intentionally left as a no-op
    pass
