from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class _Base(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def _drop_nulls(cls, v):
        # LLM đôi khi trả null: bỏ khóa để dùng giá trị mặc định
        if isinstance(v, dict):
            return {k: x for k, x in v.items() if x is not None}
        return v


# ---------- CV ----------
class Education(_Base):
    degree: str = ""
    school: str = ""
    year: Optional[int] = None
    gpa: Optional[float] = None


class Experience(_Base):
    title: str = ""
    company: str = ""
    duration_months: int = 0
    description: str = ""

    @field_validator("duration_months", mode="before")
    @classmethod
    def _round(cls, v):
        try:
            return int(round(float(v)))
        except (TypeError, ValueError):
            return 0


class Certification(_Base):
    title: str = ""
    year: Optional[int] = None


class CVData(_Base):
    name: str = ""
    email: str = ""
    phone: str = ""
    github: str = ""
    linkedin: str = ""
    summary: str = ""
    education: list[Education] = []
    experience: list[Experience] = []
    skills: list[str] = []
    certifications_awards: list[Certification] = []


# ---------- Job ----------
class Requirements(_Base):
    text: str = ""
    # Legacy fields remain readable for jobs created before the unified requirements field.
    required_skills: list[str] = []
    min_experience_years: int = 0
    education: str = ""


class JobIn(_Base):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=1)
    requirements: Requirements = Field(default_factory=Requirements)
    location: str = ""
    job_type: str = "Full-time"
    salary_range: str = ""
    open_date: date
    deadline: date
    benefits: str = ""
    email: str = ""
    phone: str = ""

    @model_validator(mode="after")
    def _dates_are_ordered(self):
        if self.deadline < self.open_date:
            raise ValueError("Hạn nộp đơn phải từ ngày mở đơn trở đi")
        return self


class ReopenJobIn(BaseModel):
    deadline: date


# ---------- Auth ----------
class LoginIn(BaseModel):
    email: str
    password: str


class CandidateRegisterIn(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN)
    password: str = Field(min_length=6)
    full_name: str = Field(min_length=1)
    phone: str = ""


class CompanyRegisterIn(BaseModel):
    company_name: str = Field(min_length=2)
    industry: str = ""
    description: str = ""
    email: str = Field(pattern=EMAIL_PATTERN)
    password: str = Field(min_length=6)
    full_name: str = "HR"
    phone: str = ""


class ProfileIn(BaseModel):
    full_name: str = Field(min_length=1)
    phone: str = ""


class PasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6)


class CompanyIn(BaseModel):
    name: str = Field(min_length=2)
    industry: str = ""
    description: str = ""


# ---------- Khác ----------
class ApplyIn(BaseModel):
    job_id: str


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")


class ApplicationDecision(_Base):
    application_id: str
    decision: Literal["approved", "rejected"]


class ApplicationDecisionsIn(_Base):
    decisions: list[ApplicationDecision] = Field(default_factory=list)


class NotifyIn(BaseModel):
    message: str = Field(min_length=1)


class CompareIn(BaseModel):
    job_ids: list[str]


class TextIn(BaseModel):
    text: str = Field(min_length=20)
