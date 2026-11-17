from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .constants import DEFAULT_JOB_TYPE, JOB_TYPES

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def requirements_text(req) -> str:
    """Yêu cầu công việc dạng văn bản. Tin cũ lưu theo trường rời (kỹ năng, kinh nghiệm, học vấn) được gộp lại."""
    if not isinstance(req, dict):
        return ""
    text = str(req.get("text") or "").strip()
    if text:
        return text
    parts = []
    experience = req.get("min_experience_years")
    if experience is not None and str(experience).strip():
        parts.append(f"Kinh nghiệm tối thiểu: {experience} năm")
    education = req.get("education")
    if education is not None and str(education).strip():
        parts.append(f"Học vấn: {education}")
    required_skills = req.get("required_skills")
    if isinstance(required_skills, str):
        required_skills = [required_skills]
    if isinstance(required_skills, (list, tuple)):
        skills = [str(skill).strip() for skill in required_skills if skill is not None and str(skill).strip()]
        if skills:
            parts.append(f"Kỹ năng: {', '.join(skills)}")
    return "\n".join(parts)


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
    degree: str = Field(min_length=1)
    school: str = Field(min_length=1)
    year: int = Field(ge=1)
    gpa: Optional[float] = None

    @field_validator("degree", "school", mode="before")
    @classmethod
    def _required_text(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Trường này là bắt buộc")
        return value.strip()


class Experience(_Base):
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    duration_months: int = Field(ge=0)
    description: str = ""

    @field_validator("title", "company", mode="before")
    @classmethod
    def _required_text(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Trường này là bắt buộc")
        return value.strip()

    @field_validator("duration_months", mode="before")
    @classmethod
    def _round(cls, v):
        try:
            months = float(v)
        except (TypeError, ValueError):
            raise ValueError("Số tháng là bắt buộc và phải là số nguyên") from None
        if not months.is_integer():
            raise ValueError("Số tháng phải là số nguyên")
        return int(months)


class Certification(_Base):
    title: str = Field(min_length=1)
    year: int = Field(ge=1)

    @field_validator("title", mode="before")
    @classmethod
    def _required_text(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Tên là bắt buộc")
        return value.strip()


class CVData(_Base):
    name: str = ""
    email: str = ""
    phone: str = ""
    github: str = ""
    linkedin: str = ""
    summary: str = ""
    education: list[Education] = []
    experience: list[Experience] = []
    skills: list[str] = Field(min_length=1)
    certifications_awards: list[Certification] = []

    @field_validator("skills", mode="before")
    @classmethod
    def _remove_blank_skills(cls, values):
        if isinstance(values, list):
            return [value.strip() if isinstance(value, str) else value
                    for value in values if not isinstance(value, str) or value.strip()]
        return values


# ---------- Job ----------
class Requirements(_Base):
    text: str

    @model_validator(mode="before")
    @classmethod
    def _fold_legacy(cls, v):
        # Dữ liệu cũ có thể còn các trường rời: gộp vào text để chỉ lưu một dạng duy nhất
        return {"text": requirements_text(v)} if isinstance(v, dict) else v

    @field_validator("text", mode="before")
    @classmethod
    def _required_text(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Yêu cầu đối với ứng viên là bắt buộc")
        return value.strip()


class JobIn(_Base):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=1)
    requirements: Requirements
    location: str = ""
    job_type: str = DEFAULT_JOB_TYPE
    salary_range: str = ""
    open_date: date
    deadline: date
    benefits: str = ""
    email: str = ""
    phone: str = ""

    @field_validator("job_type")
    @classmethod
    def _valid_job_type(cls, v):
        if v not in JOB_TYPES:
            raise ValueError(f"Loại hình phải là một trong: {', '.join(JOB_TYPES)}")
        return v

    @field_validator("title", mode="before")
    @classmethod
    def _required_title(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Chức danh là bắt buộc")
        return value.strip()

    @field_validator("description", mode="before")
    @classmethod
    def _required_description(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Mô tả công việc là bắt buộc")
        return value.strip()

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


class ApplicationDecision(_Base):
    application_id: str
    decision: Literal["approved", "rejected"]


class ApplicationDecisionsIn(_Base):
    decisions: list[ApplicationDecision] = Field(default_factory=list)


class CompareIn(BaseModel):
    job_ids: list[str]


class TextIn(BaseModel):
    text: str = Field(min_length=20)
