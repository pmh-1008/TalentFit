"""Baseline: schema trước khi dùng Alembic.

Chạy được trên cả CSDL trống lẫn CSDL cũ do `create_all` tạo (bảng đã có thì bỏ qua,
cột thêm muộn thì bổ sung), nên mọi bản triển khai cũ đều nâng cấp được lên head.

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Cột từng được thêm sau khi bảng ra đời: (bảng, cột tạo bằng sa.Column)
LATE_COLUMNS = {
    "jobs": [
        lambda: sa.Column("deadline", sa.Date(), nullable=True),
        lambda: sa.Column("open_date", sa.Date(), nullable=True),
        lambda: sa.Column("benefits", sa.Text(), nullable=True),
        lambda: sa.Column("decisions_finalized", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    ],
    "applications": [lambda: sa.Column("draft_decision", sa.String(10), nullable=True)],
    "candidate_profiles": [
        lambda: sa.Column("github", sa.String(255), nullable=False, server_default=""),
        lambda: sa.Column("linkedin", sa.String(255), nullable=False, server_default=""),
    ],
}


def _id():
    return sa.Column("id", sa.String(36), primary_key=True)


def _fk(column: str, target: str, ondelete: str, **kw):
    return sa.Column(column, sa.String(36), sa.ForeignKey(target, ondelete=ondelete), **kw)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    def create(name, *items):
        if name not in existing:
            op.create_table(name, *items)
            return True
        # Bảng cũ: chỉ bổ sung cột thêm muộn còn thiếu
        have = {c["name"] for c in inspector.get_columns(name)}
        for make in LATE_COLUMNS.get(name, []):
            col = make()
            if col.name not in have:
                op.add_column(name, col)
        return False

    create("companies", _id(),
           sa.Column("name", sa.String(200), nullable=False), sa.Column("industry", sa.String(120), nullable=False),
           sa.Column("description", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
           sa.UniqueConstraint("name"))

    if create("users", _id(),
              sa.Column("email", sa.String(255), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False),
              sa.Column("role", sa.String(20), nullable=False), sa.Column("full_name", sa.String(150), nullable=False),
              sa.Column("phone", sa.String(30), nullable=False),
              _fk("company_id", "companies.id", "SET NULL", nullable=True),
              sa.Column("created_at", sa.DateTime(), nullable=False)):
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    create("candidate_profiles",
           _fk("user_id", "users.id", "CASCADE", primary_key=True),
           sa.Column("github", sa.String(255), nullable=False, server_default=""),
           sa.Column("linkedin", sa.String(255), nullable=False, server_default=""),
           sa.Column("summary", sa.Text(), nullable=False), sa.Column("education", sa.JSON(), nullable=False),
           sa.Column("experience", sa.JSON(), nullable=False), sa.Column("skills", sa.JSON(), nullable=False),
           sa.Column("certifications_awards", sa.JSON(), nullable=False),
           sa.Column("updated_at", sa.DateTime(), nullable=False))

    if create("jobs", _id(),
              _fk("company_id", "companies.id", "CASCADE", nullable=False),
              sa.Column("title", sa.String(200), nullable=False), sa.Column("description", sa.Text(), nullable=False),
              sa.Column("requirements", sa.JSON(), nullable=False), sa.Column("location", sa.String(120), nullable=False),
              sa.Column("job_type", sa.String(40), nullable=False), sa.Column("salary_range", sa.String(80), nullable=False),
              sa.Column("email", sa.String(255), nullable=False), sa.Column("phone", sa.String(30), nullable=False),
              sa.Column("status", sa.String(10), nullable=False),
              sa.Column("opened_at", sa.DateTime(), nullable=False),
              sa.Column("open_date", sa.Date(), nullable=True),
              sa.Column("closed_at", sa.DateTime(), nullable=True),
              sa.Column("decisions_finalized", sa.Boolean(), nullable=False, server_default=sa.text("0")),
              sa.Column("deadline", sa.Date(), nullable=True),
              sa.Column("benefits", sa.Text(), nullable=False)):
        op.create_index("ix_jobs_company_id", "jobs", ["company_id"])
        op.create_index("ix_jobs_status", "jobs", ["status"])

    if create("custom_cvs", _id(),
              _fk("user_id", "users.id", "CASCADE", nullable=False), _fk("job_id", "jobs.id", "CASCADE", nullable=False),
              sa.Column("data", sa.JSON(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
              sa.UniqueConstraint("user_id", "job_id", name="uq_custom_cv")):
        op.create_index("ix_custom_cvs_user_id", "custom_cvs", ["user_id"])
        op.create_index("ix_custom_cvs_job_id", "custom_cvs", ["job_id"])

    if create("applications", _id(),
              _fk("job_id", "jobs.id", "CASCADE", nullable=False), _fk("candidate_id", "users.id", "CASCADE", nullable=False),
              sa.Column("cv_data", sa.JSON(), nullable=False), sa.Column("status", sa.String(10), nullable=False),
              sa.Column("draft_decision", sa.String(10), nullable=True),
              sa.Column("applied_at", sa.DateTime(), nullable=False), sa.Column("decided_at", sa.DateTime(), nullable=True),
              sa.UniqueConstraint("job_id", "candidate_id", name="uq_application")):
        op.create_index("ix_applications_job_id", "applications", ["job_id"])
        op.create_index("ix_applications_candidate_id", "applications", ["candidate_id"])

    if create("match_results", _id(),
              _fk("job_id", "jobs.id", "CASCADE", nullable=False), _fk("user_id", "users.id", "CASCADE", nullable=False),
              sa.Column("jd_hash", sa.String(32), nullable=False), sa.Column("cv_hash", sa.String(32), nullable=False),
              sa.Column("skill_match", sa.Float(), nullable=False), sa.Column("experience_match", sa.Float(), nullable=False),
              sa.Column("education_match", sa.Float(), nullable=False), sa.Column("overall_fit", sa.Float(), nullable=False),
              sa.Column("explanations", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
              sa.UniqueConstraint("job_id", "user_id", "jd_hash", "cv_hash", name="uq_match")):
        op.create_index("ix_match_results_job_id", "match_results", ["job_id"])
        op.create_index("ix_match_results_user_id", "match_results", ["user_id"])

    if create("notifications", _id(),
              _fk("user_id", "users.id", "CASCADE", nullable=False),
              sa.Column("title", sa.String(200), nullable=False), sa.Column("message", sa.Text(), nullable=False),
              sa.Column("is_read", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False)):
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"])


def downgrade() -> None:
    for table in ("notifications", "match_results", "applications", "custom_cvs", "jobs",
                  "candidate_profiles", "users", "companies"):
        op.drop_table(table)
