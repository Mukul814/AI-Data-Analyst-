"""initial schema"""

from alembic import op
from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, Text

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "projects",
        Column("id", String(36), primary_key=True),
        Column("name", String(160), nullable=False),
        Column("description", Text),
        Column("created_at", DateTime(timezone=True)),
    )
    op.create_table(
        "datasets",
        Column("id", String(36), primary_key=True),
        Column(
            "project_id", String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
        ),
        Column("filename", String(255), nullable=False),
        Column("storage_key", String(512), nullable=False),
        Column("profile", JSON, nullable=False),
        Column("created_at", DateTime(timezone=True)),
    )
    op.create_index("ix_datasets_project_id", "datasets", ["project_id"])
    op.create_table(
        "dataset_columns",
        Column("id", String(36), primary_key=True),
        Column(
            "dataset_id", String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
        ),
        Column("name", String(255), nullable=False),
        Column("dtype", String(80), nullable=False),
        Column("semantic_type", String(40), nullable=False),
        Column("details", JSON, nullable=False),
    )
    op.create_index("ix_dataset_columns_dataset_id", "dataset_columns", ["dataset_id"])
    op.create_table(
        "conversations",
        Column("id", String(36), primary_key=True),
        Column(
            "dataset_id", String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
        ),
        Column("title", String(255)),
        Column("created_at", DateTime(timezone=True)),
    )
    op.create_index("ix_conversations_dataset_id", "conversations", ["dataset_id"])
    op.create_table(
        "messages",
        Column("id", String(36), primary_key=True),
        Column(
            "conversation_id",
            String(36),
            ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        Column("role", String(20), nullable=False),
        Column("content", Text, nullable=False),
        Column("created_at", DateTime(timezone=True)),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index(
        "ix_messages_conversation_created", "messages", ["conversation_id", "created_at"]
    )
    op.create_table(
        "analysis_sessions",
        Column("id", String(36), primary_key=True),
        Column(
            "conversation_id",
            String(36),
            ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        Column("status", String(24)),
        Column("created_at", DateTime(timezone=True)),
    )
    op.create_index(
        "ix_analysis_sessions_conversation_id", "analysis_sessions", ["conversation_id"]
    )
    op.create_table(
        "analysis_results",
        Column("id", String(36), primary_key=True),
        Column(
            "session_id",
            String(36),
            ForeignKey("analysis_sessions.id", ondelete="CASCADE"),
            unique=True,
        ),
        Column("payload", JSON, nullable=False),
        Column("code", Text),
    )


def downgrade():
    for table in [
        "analysis_results",
        "analysis_sessions",
        "messages",
        "conversations",
        "dataset_columns",
        "datasets",
        "projects",
    ]:
        op.drop_table(table)
