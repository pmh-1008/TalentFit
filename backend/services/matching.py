import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Job, MatchResult
from . import llm


def _hash(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def jd_payload(job: Job) -> dict:
    return {
        "title": job.title, "company": job.company.name, "description": job.description,
        "requirements": job.requirements or {},
    }


def cv_payload(cv: dict) -> dict:
    # Không gửi thông tin liên hệ cho LLM để tránh ảnh hưởng đánh giá
    return {k: v for k, v in cv.items() if k not in ("email", "phone", "name", "github", "linkedin")}


def result_to_dict(r: MatchResult) -> dict:
    return {
        "skill_match": r.skill_match, "experience_match": r.experience_match,
        "education_match": r.education_match, "overall_fit": r.overall_fit,
        "explanations": r.explanations, "scored_at": r.created_at.isoformat(timespec="seconds"),
    }


def get_cached(db: Session, job: Job, user_id: str, cv: dict) -> Optional[MatchResult]:
    return db.query(MatchResult).filter_by(
        job_id=job.id, user_id=user_id, jd_hash=_hash(jd_payload(job)), cv_hash=_hash(cv_payload(cv))
    ).first()


def score_many(db: Session, tasks: list[tuple[Job, str, dict]], force: bool = False) -> list[MatchResult]:
    """tasks: [(job, user_id, cv)]. Các cặp chưa có cache sẽ được LLM chấm song song.
    Kết quả thành công được lưu lại; nếu có cặp nào lỗi, ném LLMError sau khi lưu."""
    results: list[Optional[MatchResult]] = [None] * len(tasks)
    todo = []
    for i, (job, uid, cv) in enumerate(tasks):
        jd, prof = jd_payload(job), cv_payload(cv)
        jh, ch = _hash(jd), _hash(prof)
        row = None if force else db.query(MatchResult).filter_by(
            job_id=job.id, user_id=uid, jd_hash=jh, cv_hash=ch).first()
        if row:
            results[i] = row
        else:
            todo.append((i, job.id, uid, jd, prof, jh, ch))

    errors: list[llm.LLMError] = []
    if todo:
        def run(t):
            try:
                return llm.score_candidate(t[3], t[4]), None
            except llm.LLMError as e:
                return None, e

        with ThreadPoolExecutor(max_workers=max(1, min(settings.LLM_CONCURRENCY, len(todo)))) as ex:
            outputs = list(ex.map(run, todo))

        for (i, job_id, uid, _jd, _prof, jh, ch), (out, err) in zip(todo, outputs):
            if err:
                errors.append(err)
                continue
            db.query(MatchResult).filter_by(job_id=job_id, user_id=uid, jd_hash=jh, cv_hash=ch).delete()
            row = MatchResult(job_id=job_id, user_id=uid, jd_hash=jh, cv_hash=ch, **out)
            db.add(row)
            results[i] = row
        db.commit()

    if errors:
        first = errors[0]
        done = len(todo) - len(errors)
        msg = first.message
        if done:
            msg += f" (Đã chấm xong {done}/{len(todo)} hồ sơ, phần còn lại có thể chấm lại sau.)"
        raise llm.LLMError(msg, first.status_code)
    return results  # type: ignore[return-value]
