from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import candidate_only, recruiter_only
from ..models import Application, Job, Notification, User, now
from ..schemas import ApplyIn, ApplicationDecisionsIn, DecisionIn, NotifyIn
from ..services import matching
from ..utils import cv_is_empty, effective_cv, iso, job_to_dict

router = APIRouter(prefix="/applications", tags=["applications"])
ACTIVE = ("pending", "approved")


# ------------------------------------------------------------- ứng viên
@router.post("", status_code=201)
def apply(body: ApplyIn, user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    job = db.get(Job, body.job_id)
    if not job:
        raise HTTPException(404, "Không tìm thấy công việc")
    if job.status != "open":
        raise HTTPException(400, "Tin tuyển dụng này đã đóng")
    if job.open_date and job.open_date > date.today():
        raise HTTPException(400, "Tin tuyển dụng này chưa mở nhận đơn")
    if job.deadline and job.deadline < date.today():
        raise HTTPException(400, "Đã hết hạn nộp đơn cho công việc này")
    if db.query(Application).filter_by(job_id=job.id, candidate_id=user.id).first():
        raise HTTPException(409, "Bạn đã ứng tuyển công việc này")
    active = db.query(func.count(Application.id)).filter(
        Application.candidate_id == user.id, Application.status.in_(ACTIVE)).scalar()
    if active >= settings.MAX_ACTIVE_APPLICATIONS:
        raise HTTPException(400, f"Bạn chỉ có thể ứng tuyển tối đa {settings.MAX_ACTIVE_APPLICATIONS} công việc cùng lúc")
    cv, kind = effective_cv(db, user, job.id)
    if cv_is_empty(cv):
        raise HTTPException(400, "Hãy hoàn thiện CV (học vấn, kinh nghiệm hoặc kỹ năng) trước khi ứng tuyển")
    app = Application(job_id=job.id, candidate_id=user.id, cv_data=cv)
    db.add(app)
    db.commit()
    return {"id": app.id, "cv_type": kind}


@router.get("/mine")
def my_applications(user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    apps = db.query(Application).filter_by(candidate_id=user.id).order_by(Application.applied_at.desc()).all()
    out = []
    for a in apps:
        job = db.get(Job, a.job_id)
        out.append({"id": a.id, "status": a.status, "applied_at": iso(a.applied_at),
                    "decided_at": iso(a.decided_at), "cv": a.cv_data, "job": job_to_dict(job)})
    return {"items": out, "active": sum(1 for a in apps if a.status in ACTIVE),
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
def _own_job(db: Session, user: User, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if not job or job.company_id != user.company_id:
        raise HTTPException(404, "Không tìm thấy tin tuyển dụng")
    return job


@router.get("/job/{job_id}")
def job_applicants(job_id: str, user: User = Depends(recruiter_only), db: Session = Depends(get_db)):
    job = _own_job(db, user, job_id)
    items = []
    for a in db.query(Application).filter_by(job_id=job.id).all():
        cand = db.get(User, a.candidate_id)
        cached = matching.get_cached(db, job, a.candidate_id, a.cv_data)
        items.append({
            "id": a.id, "status": a.status, "applied_at": iso(a.applied_at),
            "draft_decision": a.draft_decision,
            "candidate": {"id": cand.id, "name": cand.full_name, "email": cand.email, "phone": cand.phone},
            "cv": a.cv_data,
            "match": matching.result_to_dict(cached) if cached else None,
        })
    items.sort(key=lambda x: (x["match"] is None, -(x["match"]["overall_fit"] if x["match"] else 0)))
    return items


def _decision_map(job: Job, body: ApplicationDecisionsIn, db: Session) -> tuple[list[Application], dict[str, str]]:
    applications = db.query(Application).filter_by(job_id=job.id).all()
    decisions = {item.application_id: item.decision for item in body.decisions}
    application_ids = {application.id for application in applications}
    if not decisions.keys() <= application_ids:
        raise HTTPException(400, "Danh sách lựa chọn có đơn ứng tuyển không thuộc tin này")
    return applications, decisions


@router.put("/job/{job_id}/decision-draft")
def save_decision_draft(
    job_id: str,
    body: ApplicationDecisionsIn,
    user: User = Depends(recruiter_only),
    db: Session = Depends(get_db),
):
    job = _own_job(db, user, job_id)
    if job.decisions_finalized:
        raise HTTPException(400, "Kết quả đã được gửi; không thể thay đổi quyết định")
    applications, decisions = _decision_map(job, body, db)
    for application in applications:
        application.draft_decision = decisions.get(application.id)
    db.commit()
    return {"saved": len(decisions)}


@router.post("/job/{job_id}/finalize-decisions")
def finalize_decisions(
    job_id: str,
    body: ApplicationDecisionsIn,
    user: User = Depends(recruiter_only),
    db: Session = Depends(get_db),
):
    job = _own_job(db, user, job_id)
    if job.decisions_finalized:
        raise HTTPException(400, "Kết quả đã được gửi; tin tuyển dụng đã đóng")
    applications, decisions = _decision_map(job, body, db)
    company_name = job.company.name
    counts = {"approved": 0, "rejected": 0}
    for application in applications:
        decision = (decisions.get(application.id) or application.draft_decision
                    or (application.status if application.status != "pending" else "rejected"))
        application.status = decision
        application.draft_decision = None
        application.decided_at = now()
        counts[decision] += 1
        if decision == "approved":
            message = (f"Hồ sơ ứng tuyển vị trí {job.title} tại {company_name} đã được duyệt. "
                       f"Nhà tuyển dụng sẽ liên hệ với bạn qua {job.email or 'email'}.")
            title = "Hồ sơ của bạn đã được duyệt"
        else:
            message = f"Rất tiếc, hồ sơ ứng tuyển vị trí {job.title} tại {company_name} chưa phù hợp lần này."
            title = "Kết quả ứng tuyển"
        db.add(Notification(user_id=application.candidate_id, title=title, message=message))
    job.status = "closed"
    job.closed_at = now()
    job.decisions_finalized = True
    db.commit()
    return {"approved": counts["approved"], "rejected": counts["rejected"], "notified": len(applications)}


@router.post("/{app_id}/decision")
def decide(app_id: str, body: DecisionIn, user: User = Depends(recruiter_only), db: Session = Depends(get_db)):
    app = db.get(Application, app_id)
    job = db.get(Job, app.job_id) if app else None
    if not app or job.company_id != user.company_id:
        raise HTTPException(404, "Không tìm thấy đơn ứng tuyển")
    if job.decisions_finalized:
        raise HTTPException(400, "Kết quả đã được gửi; không thể thay đổi quyết định")
    app.status, app.decided_at = body.decision, now()
    if body.decision == "approved":
        db.add(Notification(
            user_id=app.candidate_id, title="Hồ sơ của bạn đã được duyệt",
            message=f"Hồ sơ ứng tuyển vị trí {job.title} tại {job.company.name} đã được duyệt. "
                    f"Nhà tuyển dụng sẽ liên hệ với bạn qua {job.email or 'email'}."))
    db.commit()
    return {"id": app.id, "status": app.status}


@router.post("/job/{job_id}/notify")
def notify_approved(job_id: str, body: NotifyIn, user: User = Depends(recruiter_only), db: Session = Depends(get_db)):
    job = _own_job(db, user, job_id)
    approved = db.query(Application).filter_by(job_id=job.id, status="approved").all()
    if not approved:
        raise HTTPException(400, "Chưa có ứng viên nào được duyệt cho tin này")
    for a in approved:
        db.add(Notification(user_id=a.candidate_id, title=f"{job.company.name}: {job.title}", message=body.message))
    db.commit()
    return {"sent": len(approved)}
