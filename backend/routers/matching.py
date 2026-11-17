from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import candidate_only, own_job, recruiter_only
from ..models import Application, Job, User
from ..schemas import CompareIn
from ..services import matching
from ..serializers import job_to_dict
from ..services.cv import cv_is_empty, effective_cv

router = APIRouter(prefix="/matching", tags=["matching"])


@router.post("/jobs")
def rank_jobs(body: CompareIn, user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    """Ứng viên chọn tối đa 5 job; LLM chấm điểm CV với từng job rồi xếp hạng giảm dần."""
    ids = list(dict.fromkeys(body.job_ids))
    if not ids:
        raise HTTPException(400, "Hãy chọn ít nhất một công việc")
    if len(ids) > settings.MAX_COMPARE_JOBS:
        raise HTTPException(400, f"Mỗi lần chỉ được chọn tối đa {settings.MAX_COMPARE_JOBS} công việc")
    jobs = db.query(Job).filter(Job.id.in_(ids)).all()
    if len(jobs) != len(ids):
        raise HTTPException(404, "Có công việc không tồn tại")

    tasks, kinds = [], []
    for job in jobs:
        cv, kind = effective_cv(db, user, job.id)
        if cv_is_empty(cv):
            raise HTTPException(400, "Hãy hoàn thiện CV trước khi xếp hạng công việc")
        tasks.append((job, user.id, cv))
        kinds.append(kind)

    results = matching.score_many(db, tasks)
    ranked = [{"job": job_to_dict(job), "cv_type": kind, **matching.result_to_dict(r)}
              for job, kind, r in zip(jobs, kinds, results)]
    ranked.sort(key=lambda x: x["overall_fit"], reverse=True)
    return ranked


@router.post("/applications/{job_id}")
def score_applicants(job_id: str, force: bool = False, user: User = Depends(recruiter_only),
                     db: Session = Depends(get_db)):
    """Nhà tuyển dụng: chấm điểm bằng LLM cho các ứng viên của một job."""
    job = own_job(db, user, job_id)
    apps = db.query(Application).filter_by(job_id=job.id).all()
    if not apps:
        raise HTTPException(400, "Tin này chưa có ứng viên")
    matching.score_many(db, [(job, a.candidate_id, a.cv_data) for a in apps], force=force)
    return {"scored": len(apps)}
