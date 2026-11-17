"""Require complete job descriptions on new or changed job records.

Revision ID: 0004
Revises: 0003
"""
from alembic import op

from backend.job_database import create_trigger_statements, drop_trigger_statements

revision = "0004"
down_revision = "0003"
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
