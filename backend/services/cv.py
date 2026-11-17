from typing import Optional

from sqlalchemy.orm import Session

from ..models import CandidateProfile, CustomCV, User


def cv_from_profile(user: User, p: Optional[CandidateProfile]) -> dict:
    return {
        "name": user.full_name, "email": user.email, "phone": user.phone,
        "github": p.github if p else "", "linkedin": p.linkedin if p else "",
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
