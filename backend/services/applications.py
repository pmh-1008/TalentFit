from datetime import date

from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..errors import BusinessError
from ..models import Application, Job, Notification, User, now
from ..schemas import CVData
from .cv import cv_is_empty, effective_cv

ACTIVE = ("pending", "approved")


def count_active(db: Session, user_id: str) -> int:
    """Số đơn đang giữ lượt: chờ duyệt hoặc đã duyệt, và chỉ tính tin còn mở.
    Đơn thuộc tin đã đóng không chiếm lượt, nếu không đơn đã duyệt sẽ chiếm lượt mãi mãi."""
    return db.query(func.count(Application.id)).join(Job, Job.id == Application.job_id).filter(
        Application.candidate_id == user_id, Application.status.in_(ACTIVE), Job.status == "open").scalar()


def apply_to_job(db: Session, user: User, job_id: str) -> tuple[Application, str]:
    job = db.get(Job, job_id)
    if not job:
        raise BusinessError("Không tìm thấy công việc", 404)
    if job.status != "open":
        raise BusinessError("Tin tuyển dụng này đã đóng")
    if job.open_date > date.today():
        raise BusinessError("Tin tuyển dụng này chưa mở nhận đơn")
    if job.deadline < date.today():
        raise BusinessError("Đã hết hạn nộp đơn cho công việc này")
    if db.query(Application).filter_by(job_id=job.id, candidate_id=user.id).first():
        raise BusinessError("Bạn đã ứng tuyển công việc này", 409)
    if count_active(db, user.id) >= settings.MAX_ACTIVE_APPLICATIONS:
        raise BusinessError(f"Bạn chỉ có thể ứng tuyển tối đa {settings.MAX_ACTIVE_APPLICATIONS} công việc cùng lúc")
    cv, kind = effective_cv(db, user, job.id)
    if cv_is_empty(cv):
        raise BusinessError("Hãy hoàn thiện CV (học vấn, kinh nghiệm hoặc kỹ năng) trước khi ứng tuyển")
    try:
        cv = CVData.model_validate(cv).model_dump()
    except ValidationError:
        raise BusinessError("CV chưa đủ thông tin bắt buộc. Hãy cập nhật CV trước khi ứng tuyển.")
    application = Application(job_id=job.id, candidate_id=user.id, cv_data=cv)
    db.add(application)
    try:
        db.commit()
    except IntegrityError:  # hai yêu cầu cùng lúc: ràng buộc UNIQUE chặn bản thứ hai
        db.rollback()
        raise BusinessError("Bạn đã ứng tuyển công việc này", 409)
    return application, kind


def resolve_decisions(db: Session, job: Job, items) -> tuple[list[Application], dict[str, str]]:
    applications = db.query(Application).filter_by(job_id=job.id).all()
    decisions = {item.application_id: item.decision for item in items}
    if not decisions.keys() <= {a.id for a in applications}:
        raise BusinessError("Danh sách lựa chọn có đơn ứng tuyển không thuộc tin này")
    return applications, decisions


def save_draft(db: Session, job: Job, items) -> int:
    if job.decisions_finalized:
        raise BusinessError("Kết quả đã được gửi; không thể thay đổi quyết định")
    applications, decisions = resolve_decisions(db, job, items)
    for application in applications:
        application.draft_decision = decisions.get(application.id)
    db.commit()
    return len(decisions)


def finalize(db: Session, job: Job, items) -> dict:
    """Chốt kết quả: đơn chưa có quyết định bị từ chối, gửi thông báo cho mọi ứng viên, đóng tin."""
    if job.decisions_finalized:
        raise BusinessError("Kết quả đã được gửi; tin tuyển dụng đã đóng")
    applications, decisions = resolve_decisions(db, job, items)
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
            title = "Hồ sơ của bạn đã được duyệt"
            message = (f"Hồ sơ ứng tuyển vị trí {job.title} tại {company_name} đã được duyệt. "
                       f"Nhà tuyển dụng sẽ liên hệ với bạn qua {job.email or 'email'}.")
        else:
            title = "Kết quả ứng tuyển"
            message = f"Rất tiếc, hồ sơ ứng tuyển vị trí {job.title} tại {company_name} chưa phù hợp lần này."
        db.add(Notification(user_id=application.candidate_id, title=title, message=message))
    job.status = "closed"
    job.closed_at = now()
    job.decisions_finalized = True
    db.commit()
    return {**counts, "notified": len(applications)}
