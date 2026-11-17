from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..constants import JOB_TYPES
from ..database import get_db
from ..deps import get_current_user, own_job, recruiter_only
from ..models import Application, Company, Job, User
from ..schemas import JobIn, ReopenJobIn
from ..serializers import job_to_dict
from ..services import job_lifecycle
from ..services.job_lifecycle import already_open, close_expired_jobs, display_status, not_expired, notify_job_closed

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _apply_fields(job: Job, body: JobIn) -> None:
    job.title = body.title.strip()
    job.description = body.description
    job.requirements = body.requirements.model_dump()
    job.location = body.location.strip()
    job.job_type = body.job_type
    job.salary_range = body.salary_range
    job.open_date = body.open_date
    job.deadline = body.deadline
    job.benefits = body.benefits.strip()
    job.email = body.email
    job.phone = body.phone


@router.get("/meta")
def meta(db: Session = Depends(get_db)):
    open_jobs = db.query(Job).filter(Job.status == "open", not_expired(), already_open())
    return {
        "locations": sorted({j.location for j in open_jobs if j.location}),
        "job_types": sorted({j.job_type for j in open_jobs if j.job_type}),
        "all_job_types": list(JOB_TYPES),
        "companies": [{"id": c.id, "name": c.name} for c in db.query(Company).order_by(Company.name)],
        "limits": {"max_compare": settings.MAX_COMPARE_JOBS, "max_active": settings.MAX_ACTIVE_APPLICATIONS},
    }


@router.get("/mine")
def my_jobs(user: User = Depends(recruiter_only), db: Session = Depends(get_db)):
    """Tin của công ty kèm trạng thái và thống kê số lượt ứng tuyển."""
    close_expired_jobs(db, user.company_id)
    jobs = db.query(Job).filter(Job.company_id == user.company_id).order_by(Job.created_at.desc()).all()
    counts: dict[str, dict[str, int]] = {}
    if jobs:
        effective_status = func.coalesce(Application.draft_decision, Application.status)
        rows = (db.query(Application.job_id, effective_status, func.count(Application.id))
                .filter(Application.job_id.in_([j.id for j in jobs]))
                .group_by(Application.job_id, effective_status).all())
        for job_id, status, n in rows:
            counts.setdefault(job_id, {})[status] = n
    out = []
    for j in jobs:
        c = counts.get(j.id, {})
        out.append(job_to_dict(j, status=display_status(j), pending=c.get("pending", 0), approved=c.get("approved", 0),
                               rejected=c.get("rejected", 0), total=sum(c.values())))
    return out


def _list_open_jobs(q: str, location: str, job_type: str, company_id: str,
                    user: User | None, db: Session) -> list[dict]:
    qs = db.query(Job).join(Company, Company.id == Job.company_id).filter(
        Job.status == "open", not_expired(), already_open())
    if q.strip():
        like = f"%{q.strip()}%"
        qs = qs.filter(Job.title.like(like))
    if location:
        qs = qs.filter(Job.location == location)
    if job_type:
        qs = qs.filter(Job.job_type == job_type)
    if company_id:
        qs = qs.filter(Job.company_id == company_id)
    jobs = qs.order_by(Job.created_at.desc()).all()
    mine = {}
    if user and user.role == "candidate":
        mine = {r[0]: {"id": r[1], "status": r[2]} for r in db.query(
            Application.job_id, Application.id, Application.status).filter(Application.candidate_id == user.id)}
    return [job_to_dict(j, applied=j.id in mine, application=mine.get(j.id)) for j in jobs]


@router.get("")
def list_open_jobs(q: str = "", location: str = "", job_type: str = "", company_id: str = "",
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _list_open_jobs(q, location, job_type, company_id, user, db)


@router.get("/public")
def list_public_jobs(q: str = "", location: str = "", job_type: str = "", company_id: str = "",
                     db: Session = Depends(get_db)):
    return _list_open_jobs(q, location, job_type, company_id, None, db)


@router.get("/{job_id}")
def get_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Không tìm thấy công việc")
    return job_to_dict(job)


@router.post("", status_code=201)
def create_job(body: JobIn, user: User = Depends(recruiter_only), db: Session = Depends(get_db)):
    job = Job(company_id=user.company_id)
    _apply_fields(job, body)
    job.email = body.email or user.email
    job.phone = body.phone or user.phone
    db.add(job)
    db.commit()
    db.refresh(job)
    return job_to_dict(job)


@router.put("/{job_id}")
def update_job(job_id: str, body: JobIn, user: User = Depends(recruiter_only), db: Session = Depends(get_db)):
    job = own_job(db, user, job_id)
    _apply_fields(job, body)
    db.commit()
    return job_to_dict(job)


@router.post("/{job_id}/close")
def close_job(job_id: str, user: User = Depends(recruiter_only), db: Session = Depends(get_db)):
    job = own_job(db, user, job_id)
    notify_job_closed(db, job, "manual")
    db.commit()
    return job_to_dict(job)


@router.post("/{job_id}/open-now")
def open_job_now(job_id: str, user: User = Depends(recruiter_only), db: Session = Depends(get_db)):
    job = own_job(db, user, job_id)
    if job.status != "open" or job.open_date <= date.today():
        raise HTTPException(400, "Chỉ có thể mở ngay tin chưa mở")
    job.open_date = date.today()
    db.commit()
    return job_to_dict(job, status="open")


@router.post("/{job_id}/reopen")
def reopen_job(job_id: str, body: ReopenJobIn, user: User = Depends(recruiter_only),
               db: Session = Depends(get_db)):
    job = own_job(db, user, job_id)
    if job.decisions_finalized:
        raise HTTPException(400, "Tin đã gửi kết quả ứng viên và không thể mở lại")
    if job.status != "closed":
        raise HTTPException(400, "Chỉ có thể mở lại tin đã đóng")
    if body.deadline < date.today():
        raise HTTPException(400, "Hạn nộp đơn phải từ hôm nay trở đi")
    job.status, job.open_date, job.deadline, job.closed_at = "open", date.today(), body.deadline, None
    db.commit()
    return job_to_dict(job, status="open")


@router.delete("/{job_id}")
def delete_job(job_id: str, user: User = Depends(recruiter_only), db: Session = Depends(get_db)):
    job_lifecycle.delete_job(db, own_job(db, user, job_id))
    return {"ok": True}
