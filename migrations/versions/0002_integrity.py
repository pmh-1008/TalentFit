"""Toàn vẹn dữ liệu: đổi opened_at -> created_at, open_date/deadline bắt buộc,
CHECK cho role/status, thêm chỉ mục, gộp yêu cầu công việc về một trường text.

Dữ liệu cũ được xử lý trước khi siết ràng buộc:
  * open_date trống  -> ngày tạo tin
  * deadline trống   -> open_date + 30 ngày
  * requirements     -> {"text": ...}

Revision ID: 0002
Revises: 0001
"""
from datetime import date, datetime, timedelta

import sqlalchemy as sa
from alembic import context, op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _requirements_text(req) -> str:
    if not isinstance(req, dict):
        return ""
    text = str(req.get("text") or "").strip()
    if text:
        return text
    parts = []
    if req.get("min_experience_years"):
        parts.append(f"Kinh nghiệm tối thiểu: {req['min_experience_years']} năm")
    if req.get("education"):
        parts.append(f"Học vấn: {req['education']}")
    if req.get("required_skills"):
        parts.append(f"Kỹ năng: {', '.join(map(str, req['required_skills']))}")
    return "\n".join(parts)


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def _fix_data(bind) -> None:
    jobs = sa.table("jobs", sa.column("id", sa.String), sa.column("opened_at", sa.DateTime),
                    sa.column("open_date", sa.Date), sa.column("deadline", sa.Date),
                    sa.column("requirements", sa.JSON), sa.column("benefits", sa.Text))
    for row in bind.execute(sa.select(jobs.c.id, jobs.c.opened_at, jobs.c.open_date, jobs.c.deadline,
                                      jobs.c.requirements, jobs.c.benefits)).all():
        values = {}
        open_date = _as_date(row.open_date) if row.open_date else _as_date(row.opened_at)
        if row.open_date is None:
            values["open_date"] = open_date
        if row.deadline is None:
            values["deadline"] = open_date + timedelta(days=30)
        req = row.requirements or {}
        if set(req) - {"text"}:
            values["requirements"] = {"text": _requirements_text(req)}
        if row.benefits is None:
            values["benefits"] = ""
        if values:
            bind.execute(jobs.update().where(jobs.c.id == row.id).values(**values))


def upgrade() -> None:
    if not context.is_offline_mode():  # chế độ --sql chỉ in DDL, không đọc được dữ liệu
        _fix_data(op.get_bind())

    with op.batch_alter_table("jobs") as batch:
        batch.alter_column("opened_at", new_column_name="created_at",
                           existing_type=sa.DateTime(), existing_nullable=False)
        batch.alter_column("open_date", existing_type=sa.Date(), nullable=False)
        batch.alter_column("deadline", existing_type=sa.Date(), nullable=False)
        batch.alter_column("benefits", existing_type=sa.Text(), nullable=False)
        batch.create_check_constraint("ck_jobs_status", "status IN ('open', 'closed')")
        batch.create_index("ix_jobs_company_status_deadline", ["company_id", "status", "deadline"])

    with op.batch_alter_table("users") as batch:
        batch.create_check_constraint("ck_users_role", "role IN ('candidate', 'recruiter')")

    with op.batch_alter_table("applications") as batch:
        batch.create_check_constraint("ck_applications_status", "status IN ('pending', 'approved', 'rejected')")
        batch.create_check_constraint("ck_applications_draft_decision",
                                      "draft_decision IS NULL OR draft_decision IN ('approved', 'rejected')")

    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"])


def downgrade() -> None:
    op.drop_index("ix_notifications_user_read", table_name="notifications")
    with op.batch_alter_table("applications") as batch:
        batch.drop_constraint("ck_applications_draft_decision", type_="check")
        batch.drop_constraint("ck_applications_status", type_="check")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("ck_users_role", type_="check")
    with op.batch_alter_table("jobs") as batch:
        batch.drop_index("ix_jobs_company_status_deadline")
        batch.drop_constraint("ck_jobs_status", type_="check")
        batch.alter_column("benefits", existing_type=sa.Text(), nullable=True)
        batch.alter_column("deadline", existing_type=sa.Date(), nullable=True)
        batch.alter_column("open_date", existing_type=sa.Date(), nullable=True)
        batch.alter_column("created_at", new_column_name="opened_at",
                           existing_type=sa.DateTime(), existing_nullable=False)
