from typing import Optional

from sqlalchemy.orm import Session

from .models import CandidateProfile, CustomCV, Job, User


def iso(d):
    return d.isoformat(timespec="seconds") if d else None


def user_to_dict(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "role": u.role, "full_name": u.full_name, "phone": u.phone,
        "company": {"id": u.company.id, "name": u.company.name} if u.company else None,
    }


def job_to_dict(job: Job, **extra) -> dict:
    return {
        "id": job.id, "title": job.title, "company": job.company.name, "company_id": job.company_id,
        "email": job.email, "phone": job.phone, "description": job.description,
        "requirements": job.requirements or {}, "location": job.location, "job_type": job.job_type,
        "salary_range": job.salary_range, "status": job.status,
        "decisions_finalized": job.decisions_finalized,
        "opened_at": iso(job.opened_at), "closed_at": iso(job.closed_at),
        "open_date": job.open_date.isoformat() if job.open_date else None,
        "deadline": job.deadline.isoformat() if job.deadline else None, **extra,
        "benefits": job.benefits or "",
    }


def cv_from_profile(user: User, p: Optional[CandidateProfile]) -> dict:
    return {
        "name": user.full_name, "email": user.email, "phone": user.phone,
        "summary": p.summary if p else "",
        "education": p.education if p else [],
        "experience": p.experience if p else [],
        "skills": p.skills if p else [],
        "certifications_awards": p.certifications_awards if p else [],
    }


def cv_is_empty(cv: dict) -> bool:
    return not (cv.get("skills") or cv.get("experience") or cv.get("education"))


def effective_cv(db: Session, user: User, job_id: str) -> tuple[dict, str]:
    """CV tùy chỉnh theo job nếu có, nếu không dùng CV chung."""
    custom = db.query(CustomCV).filter_by(user_id=user.id, job_id=job_id).first()
    if custom:
        return custom.data, "custom"
    return cv_from_profile(user, db.get(CandidateProfile, user.id)), "general"
