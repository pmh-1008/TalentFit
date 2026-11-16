from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException

from ..deps import candidate_only, recruiter_only
from ..models import User
from ..schemas import CVData, JobIn, TextIn
from ..services import llm

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/parse-cv")
def parse_cv(body: TextIn, user: User = Depends(candidate_only)):
    """CV (văn bản) -> JSON có cấu trúc."""
    data = llm.parse_cv(body.text)
    try:
        return CVData.model_validate(data).model_dump()
    except Exception:
        raise HTTPException(502, "LLM trả về CV không đúng cấu trúc. Vui lòng thử lại.")


@router.post("/parse-jd")
def parse_jd(body: TextIn, user: User = Depends(recruiter_only)):
    """JD (văn bản) -> JSON có cấu trúc."""
    data = llm.parse_jd(body.text)
    data.setdefault("requirements", {})
    data["open_date"] = data.get("open_date") or date.today().isoformat()
    data["deadline"] = data.get("deadline") or (date.today() + timedelta(days=30)).isoformat()
    try:
        job = JobIn.model_validate({**data, "title": data.get("title") or "Vị trí tuyển dụng",
                                    "description": data.get("description") or body.text})
        return job.model_dump()
    except Exception:
        raise HTTPException(502, "LLM trả về JD không đúng cấu trúc. Vui lòng thử lại.")
