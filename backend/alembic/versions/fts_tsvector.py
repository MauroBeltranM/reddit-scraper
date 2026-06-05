"""Add tsvector columns and GIN index for full-text search

Revision ID: fts_tsvector
Revises: e22012f52762
Create Date: 2026-06-05 00:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "fts_tsvector"
down_revision = "e22012f52762"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add tsvector generated columns and GIN indexes for full-text search on posts.

    Only applies to PostgreSQL. SQLite does not support tsvector or generated columns.
    """
    dialect = op.get_context().dialect.name
    if dialect != "postgresql":
        return

    # Add generated tsvector columns
    op.execute("""
        ALTER TABLE posts
        ADD COLUMN title_tsvector tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', COALESCE(title, ''))) STORED
    """)
    op.execute("""
        ALTER TABLE posts
        ADD COLUMN body_tsvector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('spanish', COALESCE(title, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(selftext, '')), 'B') ||
            setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(selftext, '')), 'B')
        ) STORED
    """)

    # GIN indexes for fast full-text search
    op.execute("CREATE INDEX ix_posts_title_tsvector ON posts USING GIN (title_tsvector)")
    op.execute("CREATE INDEX ix_posts_body_tsvector ON posts USING GIN (body_tsvector)")


def downgrade() -> None:
    """Remove tsvector columns and GIN indexes."""
    dialect = op.get_context().dialect.name
    if dialect != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS ix_posts_body_tsvector")
    op.execute("DROP INDEX IF EXISTS ix_posts_title_tsvector")
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS body_tsvector")
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS title_tsvector")
