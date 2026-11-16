from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import recruiter_only
from ..models import Company, User
from ..schemas import CompanyIn

router = APIRouter(prefix="/company", tags=["company"])


def _dict(c: Company) -> dict:
    return {"id": c.id, "name": c.name, "industry": c.industry, "description": c.description}


@router.get("/me")
def get_company(user: User = Depends(recruiter_only), db: Session = Depends(get_db)):
    return _dict(db.get(Company, user.company_id))


@router.put("/me")
def update_company(body: CompanyIn, user: User = Depends(recruiter_only), db: Session = Depends(get_db)):
    company = db.get(Company, user.company_id)
    clash = db.query(Company).filter(Company.name == body.name.strip(), Company.id != company.id).first()
    if clash:
        raise HTTPException(409, "Tên công ty đã tồn tại")
    company.name, company.industry, company.description = body.name.strip(), body.industry, body.description
    db.commit()
    return _dict(company)
