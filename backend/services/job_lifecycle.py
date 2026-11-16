from datetime import date

from sqlalchemy.orm import Session

from ..models import Application, Job, Notification, User, now


def notify_job_closed(db: Session, job: Job, reason: str) -> bool:
    if job.status == "closed":
        return False

    job.status = "closed"
    job.closed_at = now()
    total = db.query(Application).filter_by(job_id=job.id).count()
    recruiters = db.query(User.id).filter_by(company_id=job.company_id, role="recruiter").all()
    closure_reason = "do hết hạn" if reason == "expired" else "theo thao tác của nhà tuyển dụng"
    message = f'Tin tuyển dụng "{job.title}" đã đóng đơn {closure_reason}. Đã nhận {total} đơn ứng tuyển.'
    for (user_id,) in recruiters:
        db.add(Notification(user_id=user_id, title="Tin tuyển dụng đã đóng đơn", message=message))
    return True


def close_expired_jobs(db: Session, company_id: str | None = None) -> int:
    if company_id is None:
        return 0

    jobs = db.query(Job).filter(
        Job.status == "open",
        Job.company_id == company_id,
        Job.deadline.is_not(None),
        Job.deadline < date.today(),
    ).with_for_update().all()
    closed = sum(notify_job_closed(db, job, "expired") for job in jobs)
    if closed:
        db.commit()
    return closed
