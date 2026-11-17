import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import Job, User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(cred: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not cred:
        raise HTTPException(401, "Bạn chưa đăng nhập")
    try:
        payload = decode_token(cred.credentials)
    except jwt.PyJWTError:
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ hoặc đã hết hạn")
    user = db.get(User, payload.get("sub"))
    if not user:
        raise HTTPException(401, "Tài khoản không tồn tại")
    return user


def candidate_only(user: User = Depends(get_current_user)) -> User:
    if user.role != "candidate":
        raise HTTPException(403, "Chức năng dành cho ứng viên")
    return user


def recruiter_only(user: User = Depends(get_current_user)) -> User:
    if user.role != "recruiter" or not user.company_id:
        raise HTTPException(403, "Chức năng dành cho nhà tuyển dụng")
    return user


def own_job(db: Session, user: User, job_id: str) -> Job:
    """Tin tuyển dụng thuộc công ty của nhà tuyển dụng đang đăng nhập, nếu không trả 404."""
    job = db.get(Job, job_id)
    if not job or job.company_id != user.company_id:
        raise HTTPException(404, "Không tìm thấy tin tuyển dụng")
    return job
