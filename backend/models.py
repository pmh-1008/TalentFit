import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
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
    summary: Mapped[str] = mapped_column(Text, default="")
    education: Mapped[list] = mapped_column(JSON, default=list)
    experience: Mapped[list] = mapped_column(JSON, default=list)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    certifications_awards: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class Job(Base):
    __tablename__ = "jobs"

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
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    open_date: Mapped[date] = mapped_column(Date, default=date.today)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    decisions_finalized: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
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
    __table_args__ = (UniqueConstraint("job_id", "candidate_id", name="uq_application"),)

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

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
