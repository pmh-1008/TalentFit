from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import candidate_only, own_job, recruiter_only
from ..models import Application, Job, User
from ..schemas import ApplicationDecisionsIn, ApplyIn
from ..serializers import iso, job_to_dict
from ..services import applications as service
from ..services import matching

router = APIRouter(prefix="/applications", tags=["applications"])


# ------------------------------------------------------------- ứng viên
@router.post("", status_code=201)
def apply(body: ApplyIn, user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    application, kind = service.apply_to_job(db, user, body.job_id)
    return {"id": application.id, "cv_type": kind}


@router.get("/mine")
def my_applications(user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    rows = (db.query(Application, Job).join(Job, Job.id == Application.job_id)
            .filter(Application.candidate_id == user.id).order_by(Application.applied_at.desc()).all())
    items = [{"id": a.id, "status": a.status, "applied_at": iso(a.applied_at),
              "decided_at": iso(a.decided_at), "cv": a.cv_data, "job": job_to_dict(job)} for a, job in rows]
    return {"items": items, "active": service.count_active(db, user.id),
            "limit": settings.MAX_ACTIVE_APPLICATIONS}


@router.delete("/{app_id}")
def withdraw(app_id: str, user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    app = db.get(Application, app_id)
    if not app or app.candidate_id != user.id:
        raise HTTPException(404, "Không tìm thấy đơn ứng tuyển")
    if app.status != "pending":
        raise HTTPException(400, "Chỉ có thể rút đơn đang chờ duyệt")
    db.delete(app)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------- nhà tuyển dụng
@router.get("/job/{job_id}")
def job_applicants(job_id: str, user: User = Depends(recruiter_only), db: Session = Depends(get_db)):
    job = own_job(db, user, job_id)
    apps = db.query(Application).filter_by(job_id=job.id).all()
    candidates = {u.id: u for u in db.query(User).filter(User.id.in_([a.candidate_id for a in apps]))} if apps else {}
    cached = matching.get_cached_many(db, job, apps)
    items = []
    for a in apps:
        cand, match = candidates[a.candidate_id], cached.get(a.id)
        items.append({
            "id": a.id, "status": a.status, "applied_at": iso(a.applied_at),
            "draft_decision": a.draft_decision,
            "candidate": {"id": cand.id, "name": cand.full_name, "email": cand.email, "phone": cand.phone},
            "cv": a.cv_data,
            "match": matching.result_to_dict(match) if match else None,
        })
    items.sort(key=lambda x: (x["match"] is None, -(x["match"]["overall_fit"] if x["match"] else 0)))
    return items


@router.put("/job/{job_id}/decision-draft")
def save_decision_draft(job_id: str, body: ApplicationDecisionsIn,
                        user: User = Depends(recruiter_only), db: Session = Depends(get_db)):
    job = own_job(db, user, job_id)
    return {"saved": service.save_draft(db, job, body.decisions)}


@router.post("/job/{job_id}/finalize-decisions")
def finalize_decisions(job_id: str, body: ApplicationDecisionsIn,
                       user: User = Depends(recruiter_only), db: Session = Depends(get_db)):
    job = own_job(db, user, job_id)
    return service.finalize(db, job, body.decisions)
