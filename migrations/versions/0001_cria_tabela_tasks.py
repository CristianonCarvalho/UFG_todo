"""Cria a tabela tasks.

Revision ID: 0001
Revises:
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _enum(nome: str, *valores: str) -> sa.Enum:
    """Cria um enum compatível com os valores armazenados pelo modelo."""
    return sa.Enum(*valores, name=nome, native_enum=False, length=20)


def upgrade() -> None:
    """Cria a tabela de tarefas."""
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("status", _enum("taskstatus", "pendente", "concluida"), nullable=False),
        sa.Column("priority", _enum("taskpriority", "baixa", "media", "alta"), nullable=False),
        sa.Column(
            "priority_source",
            _enum("prioritysource", "jev", "fallback", "manual"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """Remove a tabela de tarefas."""
    op.drop_table("tasks")
