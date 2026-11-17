import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from typing import Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Application, Job, MatchResult
from ..schemas import requirements_text
from . import llm


def _hash(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def jd_payload(job: Job) -> dict:
    return {
        "title": job.title, "company": job.company.name, "description": job.description,
        "requirements": requirements_text(job.requirements),
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


def get_cached_many(db: Session, job: Job, applications: list[Application]) -> dict[str, Optional[MatchResult]]:
    """Điểm đã chấm của từng đơn (khóa là application.id), lấy bằng một truy vấn."""
    if not applications:
        return {}
    rows = db.query(MatchResult).filter(
        MatchResult.job_id == job.id, MatchResult.jd_hash == _hash(jd_payload(job)),
        MatchResult.user_id.in_({a.candidate_id for a in applications})).all()
    by_key = {(r.user_id, r.cv_hash): r for r in rows}
    return {a.id: by_key.get((a.candidate_id, _hash(cv_payload(a.cv_data)))) for a in applications}


# Mỗi ứng viên + tin có tối đa 2 CV "đang dùng" (bản chụp khi nộp đơn và CV hiện tại); giữ dư một bản
# để không xóa nhầm khi hai bản chấm trong cùng một giây.
KEEP_PER_CANDIDATE = 3


def prune_stale(db: Session, job_ids: set[str], current_jd_hashes: dict[str, str]) -> int:
    """Xóa điểm cũ không còn dùng tới: JD đã sửa, hoặc quá KEEP_PER_CANDIDATE bản chấm của một ứng viên."""
    removed = 0
    for job_id in job_ids:
        removed += db.query(MatchResult).filter(
            MatchResult.job_id == job_id, MatchResult.jd_hash != current_jd_hashes[job_id]).delete()
        seen: Counter = Counter()
        rows = db.query(MatchResult).filter_by(job_id=job_id).order_by(
            MatchResult.user_id, MatchResult.created_at.desc()).all()
        for row in rows:
            seen[row.user_id] += 1
            if seen[row.user_id] > KEEP_PER_CANDIDATE:
                db.delete(row)
                removed += 1
    return removed


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
        db.flush()
        prune_stale(db, {t[1] for t in todo}, {t[1]: t[5] for t in todo})
        db.commit()

    if errors:
        first = errors[0]
        done = len(todo) - len(errors)
        msg = first.message
        if done:
            msg += f" (Đã chấm xong {done}/{len(todo)} hồ sơ, phần còn lại có thể chấm lại sau.)"
        raise llm.LLMError(msg, first.status_code)
    return results  # type: ignore[return-value]
