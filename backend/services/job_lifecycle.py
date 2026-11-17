from datetime import date

from sqlalchemy.orm import Session

from ..errors import BusinessError
from ..models import Application, CustomCV, Job, MatchResult, Notification, User, now


# ---------------------------------------------------------------- điều kiện hiển thị
def not_expired():
    """Hạn nộp từ hôm nay trở đi (hết ngày hạn mới ẩn)."""
    return Job.deadline >= date.today()


def already_open():
    return Job.open_date <= date.today()


def display_status(job: Job) -> str:
    if job.status == "closed" or job.deadline < date.today():
        return "closed"
    if job.open_date > date.today():
        return "scheduled"
    return "open"


# ---------------------------------------------------------------- đóng / xóa tin
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


def close_expired_jobs(db: Session, company_id: str) -> int:
    expired = (Job.status == "open", Job.company_id == company_id,
               Job.deadline < date.today())
    # Gọi ở mỗi lần tải trang: kiểm tra nhẹ trước, chỉ khóa hàng khi thật sự có tin hết hạn
    if not db.query(Job.id).filter(*expired).first():
        return 0
    jobs = db.query(Job).filter(*expired).with_for_update().all()
    closed = sum(notify_job_closed(db, job, "expired") for job in jobs)
    if closed:
        db.commit()
    return closed


def delete_job(db: Session, job: Job) -> None:
    if db.query(Application.id).filter_by(job_id=job.id, status="approved").first():
        raise BusinessError("Tin đã có ứng viên được duyệt nên không thể xóa. Hãy đóng tin thay vì xóa.", 409)
    company_name = job.company.name
    for (candidate_id,) in db.query(Application.candidate_id).filter_by(job_id=job.id, status="pending"):
        db.add(Notification(
            user_id=candidate_id, title="Tin tuyển dụng đã bị gỡ",
            message=f'Tin "{job.title}" tại {company_name} đã bị nhà tuyển dụng gỡ nên đơn ứng tuyển của bạn đã được hủy.'))
    for model in (Application, MatchResult, CustomCV):
        db.query(model).filter(model.job_id == job.id).delete()
    db.delete(job)
    db.commit()
