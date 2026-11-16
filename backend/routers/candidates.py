from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import candidate_only
from ..models import CandidateProfile, CustomCV, Job, User
from ..schemas import CVData
from ..utils import cv_from_profile

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get("/me/cv")
def get_cv(user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    return cv_from_profile(user, db.get(CandidateProfile, user.id))


@router.put("/me/cv")
def save_cv(body: CVData, user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    profile = db.get(CandidateProfile, user.id)
    if not profile:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
    profile.summary = body.summary
    profile.education = [e.model_dump() for e in body.education]
    profile.experience = [e.model_dump() for e in body.experience]
    profile.skills = [s.strip() for s in body.skills if s.strip()]
    profile.certifications_awards = [c.model_dump() for c in body.certifications_awards]
    if body.name.strip():
        user.full_name = body.name.strip()
    user.phone = body.phone.strip()
    db.add(user)
    db.commit()
    return cv_from_profile(user, profile)


def _job_or_404(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Không tìm thấy công việc")
    return job


@router.get("/me/cv/job/{job_id}")
def get_job_cv(job_id: str, user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    _job_or_404(db, job_id)
    custom = db.query(CustomCV).filter_by(user_id=user.id, job_id=job_id).first()
    if custom:
        return {"customized": True, "cv": custom.data}
    return {"customized": False, "cv": cv_from_profile(user, db.get(CandidateProfile, user.id))}


@router.put("/me/cv/job/{job_id}")
def save_job_cv(job_id: str, body: CVData, user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    _job_or_404(db, job_id)
    data = body.model_dump()
    data.update(name=user.full_name, email=user.email, phone=user.phone)
    data["skills"] = [s.strip() for s in data["skills"] if s.strip()]
    custom = db.query(CustomCV).filter_by(user_id=user.id, job_id=job_id).first()
    if custom:
        custom.data = data
    else:
        db.add(CustomCV(user_id=user.id, job_id=job_id, data=data))
    db.commit()
    return {"customized": True, "cv": data}


@router.delete("/me/cv/job/{job_id}")
def reset_job_cv(job_id: str, user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    db.query(CustomCV).filter_by(user_id=user.id, job_id=job_id).delete()
    db.commit()
    return {"ok": True}
