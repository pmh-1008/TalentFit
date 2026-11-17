from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Notification, User
from ..services.job_lifecycle import close_expired_jobs
from ..serializers import iso

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _unread_count(db: Session, user: User) -> int:
    return db.query(func.count(Notification.id)).filter_by(user_id=user.id, is_read=False).scalar()


@router.get("/unread-count")
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Nhẹ, dùng cho chuông trên thanh điều hướng (được gọi ở mỗi lần tải trang)."""
    if user.role == "recruiter":
        close_expired_jobs(db, user.company_id)
    return {"unread": _unread_count(db, user)}


@router.get("")
def list_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == "recruiter":
        close_expired_jobs(db, user.company_id)
    rows = db.query(Notification).filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(100).all()
    return {
        "unread": _unread_count(db, user),
        "items": [{"id": n.id, "title": n.title, "message": n.message, "is_read": n.is_read,
                   "created_at": iso(n.created_at)} for n in rows],
    }


@router.post("/read-all")
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Notification).filter_by(user_id=user.id, is_read=False).update({"is_read": True})
    db.commit()
    return {"ok": True}


@router.post("/{notification_id}/read")
def read_one(notification_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(404, "Không tìm thấy thông báo")
    n.is_read = True
    db.commit()
    return {"ok": True}
