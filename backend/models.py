import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now().replace(microsecond=0)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    industry: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('candidate', 'recruiter')", name="ck_users_role"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))  # candidate | recruiter
    full_name: Mapped[str] = mapped_column(String(150), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    company_id: Mapped[Optional[str]] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    company: Mapped[Optional[Company]] = relationship(lazy="joined")


class CandidateProfile(Base):
    """CV chung của ứng viên."""
    __tablename__ = "candidate_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    github: Mapped[str] = mapped_column(String(255), default="")
    linkedin: Mapped[str] = mapped_column(String(255), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    education: Mapped[list] = mapped_column(JSON, default=list)
    experience: Mapped[list] = mapped_column(JSON, default=list)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    certifications_awards: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'closed')", name="ck_jobs_status"),
        Index("ix_jobs_company_status_deadline", "company_id", "status", "deadline"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    requirements: Mapped[dict] = mapped_column(JSON, default=dict)
    location: Mapped[str] = mapped_column(String(120), default="")
    job_type: Mapped[str] = mapped_column(String(40), default="Full-time")
    salary_range: Mapped[str] = mapped_column(String(80), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)  # open | closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    open_date: Mapped[date] = mapped_column(Date, default=date.today)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    decisions_finalized: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    deadline: Mapped[date] = mapped_column(Date)
    benefits: Mapped[str] = mapped_column(Text, default="")

    company: Mapped[Company] = relationship(lazy="joined")


class CustomCV(Base):
    """CV tùy chỉnh theo từng công việc."""
    __tablename__ = "custom_cvs"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_custom_cv"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    data: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("job_id", "candidate_id", name="uq_application"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_applications_status"),
        CheckConstraint("draft_decision IS NULL OR draft_decision IN ('approved', 'rejected')",
                        name="ck_applications_draft_decision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    cv_data: Mapped[dict] = mapped_column(JSON)  # bản chụp CV tại thời điểm nộp
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | approved | rejected
    draft_decision: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class MatchResult(Base):
    """Kết quả chấm điểm của LLM, cache theo nội dung JD + CV để không gọi LLM lặp lại."""
    __tablename__ = "match_results"
    __table_args__ = (UniqueConstraint("job_id", "user_id", "jd_hash", "cv_hash", name="uq_match"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    jd_hash: Mapped[str] = mapped_column(String(32))
    cv_hash: Mapped[str] = mapped_column(String(32))
    skill_match: Mapped[float] = mapped_column(Float)
    experience_match: Mapped[float] = mapped_column(Float)
    education_match: Mapped[float] = mapped_column(Float)
    overall_fit: Mapped[float] = mapped_column(Float)
    explanations: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "is_read"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
