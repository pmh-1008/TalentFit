"""Enforce required CV fields for new or changed CV data.

Revision ID: 0003
Revises: 0002
"""
from alembic import op

from backend.cv_database import create_trigger_statements, drop_trigger_statements

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    dialect = connection.dialect.name
    for statement in create_trigger_statements(dialect):
        connection.exec_driver_sql(statement)


def downgrade() -> None:
    connection = op.get_bind()
    dialect = connection.dialect.name
    for statement in drop_trigger_statements(dialect):
        connection.exec_driver_sql(statement)
