from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import CandidateProfile, Company, User
from ..schemas import CandidateRegisterIn, CompanyRegisterIn, LoginIn, PasswordIn, ProfileIn
from ..security import create_token, hash_password, verify_password
from ..utils import user_to_dict

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User) -> dict:
    return {"access_token": create_token(user.id, user.role), "user": user_to_dict(user)}


@router.post("/register/candidate", status_code=201)
def register_candidate(body: CandidateRegisterIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "Email đã được sử dụng")
    user = User(email=email, password_hash=hash_password(body.password), role="candidate",
                full_name=body.full_name.strip(), phone=body.phone.strip())
    db.add(user)
    db.flush()  # sinh user.id trước khi tạo hồ sơ
    db.add(CandidateProfile(user_id=user.id))
    db.commit()
    return _token_response(user)


@router.post("/register/company", status_code=201)
def register_company(body: CompanyRegisterIn, db: Session = Depends(get_db)):
    """Mỗi công ty có đúng một tài khoản HR."""
    email = body.email.strip().lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "Email đã được sử dụng")
    if db.query(Company).filter_by(name=body.company_name.strip()).first():
        raise HTTPException(409, "Tên công ty đã tồn tại")
    company = Company(name=body.company_name.strip(), industry=body.industry, description=body.description)
    db.add(company)
    db.flush()
    user = User(email=email, password_hash=hash_password(body.password), role="recruiter",
                full_name=body.full_name.strip() or "HR", phone=body.phone.strip(), company_id=company.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email.strip().lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")
    return _token_response(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_to_dict(user)


@router.put("/me")
def update_me(body: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.full_name = body.full_name.strip()
    user.phone = body.phone.strip()
    db.add(user)
    db.commit()
    return user_to_dict(user)


@router.post("/change-password")
def change_password(body: PasswordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(400, "Mật khẩu hiện tại không đúng")
    user.password_hash = hash_password(body.new_password)
    db.add(user)
    db.commit()
    return {"ok": True}
