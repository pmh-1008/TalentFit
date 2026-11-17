"""Generate and replace local demo data with Gemini-generated companies, jobs, and candidates.

Run with: python -m scripts.seed --replace
All existing rows in the local application tables are replaced.
"""
import argparse
import sys
import time
from datetime import date, timedelta
from typing import Callable, Literal, TypeVar

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import delete
from sqlalchemy.engine import make_url

from backend.config import settings
from backend import migrate
from backend.constants import JOB_TYPES
from backend.database import Base, SessionLocal, engine
from backend.models import Application, CandidateProfile, Company, Job, User
from backend.schemas import CVData, CompanyIn, JobIn
from backend.security import hash_password
from backend.services.llm import LLMError, generate_json

PASSWORD = "123456"
MAX_CONSECUTIVE_FAILURES = 10  # số lần thử liên tiếp thất bại thì mới báo không tạo được dữ liệu
RETRY_DELAY_SECONDS = 2
T = TypeVar("T")


class SeedGenerationError(Exception):
    """Gemini không trả về dữ liệu dùng được sau MAX_CONSECUTIVE_FAILURES lần thử liên tiếp."""
SYSTEM_PROMPT = (
    "Bạn là chuyên gia tạo dữ liệu mẫu hư cấu cho hệ thống tuyển dụng Việt Nam. "
    "Tuân thủ chính xác cấu trúc JSON được yêu cầu, chỉ dùng dữ liệu hư cấu, "
    "không tạo thông tin cá nhân có thật."
)


class GeneratedCandidate(BaseModel):
    name: str = Field(min_length=2)
    fit_band: Literal["high", "medium", "other"]
    cv: CVData


def _company_prompt(index: int, today: date) -> str:
    return f"""Tạo dữ liệu cho công ty mẫu số {index} trong tổng số 3 công ty.
Ngày hiện tại là {today.isoformat()}.

Sinh một công ty hư cấu tại Việt Nam và chính xác 5 vị trí tuyển dụng khác nhau
thuộc các nhóm nghề nghiệp khác nhau. Mọi nội dung phải thực tế, rõ ràng, bằng tiếng Việt.
Mô tả công việc cần nêu nhiệm vụ cụ thể; requirements.text cần nêu kỹ năng, kinh nghiệm
và học vấn cần thiết. Không tạo email, số điện thoại, ngày mở đơn hay hạn nộp đơn.

Mỗi job phải có đúng các trường:
title, description, requirements: {{"text": "..."}}, location, job_type,
salary_range, benefits.
job_type chỉ được là một trong: {', '.join(JOB_TYPES)}.

Trả về JSON theo dạng:
{{"company": {{"name": "...", "industry": "...", "description": "..."}},
  "jobs": [5 object job theo đúng thứ tự]}}
"""


def _candidate_prompt(company: dict, jobs: list[dict]) -> str:
    return f"""Tạo ứng viên mẫu cho 5 vị trí của công ty bên dưới.
Mỗi vị trí cần chính xác 3 hồ sơ CV, theo thứ tự:
1. fit_band="high": hồ sơ khớp chặt với yêu cầu, có phần lớn kỹ năng bắt buộc,
kinh nghiệm đáp ứng/vượt yêu cầu và học vấn liên quan; hướng tới điểm phù hợp AI trên 80%.
2. fit_band="medium": có một phần kỹ năng phù hợp, thiếu một phần kinh nghiệm hoặc học vấn
chỉ liên quan một phần; hướng tới điểm phù hợp AI từ 50 đến 75%.
3. fit_band="other": hồ sơ hợp lệ, nhưng không cần đạt dải điểm cụ thể.

Điểm tổng của hệ thống ưu tiên kỹ năng 40%, kinh nghiệm 40%, học vấn 20%.
Không ghi điểm dự đoán vào CV. Mỗi CV cần có giới thiệu, ít nhất một học vấn,
ít nhất một kinh nghiệm và danh sách kỹ năng. Dùng tên hư cấu khác nhau.
CV phải có các trường đúng với biểu mẫu:
summary, education[{{degree, school, year, gpa}}],
experience[{{title, company, duration_months, description}}],
skills, certifications_awards[{{title, year}}], github, linkedin.
Không sinh email, điện thoại hay thông tin liên hệ. gpa theo thang 10.
Ứng viên loại other của mỗi vị trí nên có kỹ năng chuyển đổi hợp lý để cũng có thể
ứng tuyển vị trí kế tiếp trong danh sách (vị trí cuối nối với vị trí đầu).

Công ty:
{company}

Các vị trí theo thứ tự, đánh số từ 0:
{jobs}

Trả về JSON dạng:
{{"jobs": [{{"candidates": [
  {{"name": "...", "fit_band": "high", "cv": {{...}}}},
  {{"name": "...", "fit_band": "medium", "cv": {{...}}}},
  {{"name": "...", "fit_band": "other", "cv": {{...}}}}
]}}]}}
Mảng jobs phải có đúng 5 phần tử, cùng thứ tự với đầu vào.
"""


def _require_list(data: dict, key: str, count: int) -> list:
    value = data.get(key)
    if not isinstance(value, list) or len(value) != count:
        raise ValueError(f"Gemini cần trả về đúng {count} phần tử trong '{key}'.")
    return value


def _generate_company(index: int, today: date) -> dict:
    data = generate_json(_company_prompt(index, today), SYSTEM_PROMPT)
    company = CompanyIn.model_validate(data.get("company")).model_dump()
    raw_jobs = _require_list(data, "jobs", 5)
    recruiter_email = f"hr{index:02d}@example.test"
    recruiter_phone = f"09000000{index:02d}"
    jobs = []
    for raw_job in raw_jobs:
        job = JobIn.model_validate({
            **raw_job,
            "open_date": today,
            "deadline": today + timedelta(days=45),
            "email": recruiter_email,
            "phone": recruiter_phone,
        })
        if not job.requirements.text.strip():
            raise ValueError(f"Job '{job.title}' chưa có yêu cầu tuyển dụng.")
        jobs.append(job.model_dump())
    if len({job["title"].casefold() for job in jobs}) != 5:
        raise ValueError(f"Công ty {company['name']} cần có 5 chức danh khác nhau.")
    return {"company": company, "jobs": jobs}


def _generate_candidates(company_plan: dict) -> list[list[dict]]:
    data = generate_json(
        _candidate_prompt(company_plan["company"], company_plan["jobs"]),
        SYSTEM_PROMPT,
    )
    raw_jobs = _require_list(data, "jobs", 5)
    candidate_groups = []
    expected_bands = ("high", "medium", "other")
    for job_index, raw_job in enumerate(raw_jobs):
        raw_candidates = _require_list(raw_job, "candidates", 3)
        candidates = []
        for raw_candidate, expected_band in zip(raw_candidates, expected_bands):
            candidate = GeneratedCandidate.model_validate(raw_candidate)
            if candidate.fit_band != expected_band:
                raise ValueError(
                    f"Ứng viên của job {job_index + 1} phải theo thứ tự {expected_bands}."
                )
            cv = candidate.cv.model_dump()
            if not cv["summary"].strip() or not cv["education"] or not cv["experience"] or not cv["skills"]:
                raise ValueError(f"CV của {candidate.name} chưa đủ trường để dùng trong biểu mẫu.")
            candidates.append({"name": candidate.name.strip(), "fit_band": candidate.fit_band, "cv": cv})
        candidate_groups.append(candidates)
    return candidate_groups


def _retry(label: str, attempt: Callable[[], T]) -> T:
    """Gọi `attempt` (gọi Gemini + kiểm tra dữ liệu) cho tới khi thành công.

    Lỗi API hoặc dữ liệu trả về không hợp lệ đều tính là một lần thất bại; chỉ khi thất bại
    MAX_CONSECUTIVE_FAILURES lần liên tiếp mới dừng và báo lỗi.
    """
    last_error = ""
    for number in range(1, MAX_CONSECUTIVE_FAILURES + 1):
        try:
            return attempt()
        except LLMError as error:
            last_error = f"lỗi gọi Gemini: {error.message}"
        except (ValidationError, ValueError, KeyError, TypeError) as error:
            last_error = f"dữ liệu không hợp lệ: {error}"
        print(f"  [{label}] Lần thử {number}/{MAX_CONSECUTIVE_FAILURES} thất bại, {last_error}", file=sys.stderr)
        if number < MAX_CONSECUTIVE_FAILURES:
            time.sleep(RETRY_DELAY_SECONDS)
    raise SeedGenerationError(
        f"{label}: thất bại {MAX_CONSECUTIVE_FAILURES} lần liên tiếp. Lỗi cuối cùng: {last_error}")


def generate_dataset() -> list[dict]:
    today = date.today()
    plans = []
    company_names: set[str] = set()
    for index in range(1, 4):
        def make_company() -> dict:
            plan = _generate_company(index, today)
            name = plan["company"]["name"].strip()
            if name.casefold() in company_names:
                raise ValueError(f"Gemini tạo tên công ty trùng nhau: {name}")
            plan["company"]["name"] = name
            return plan

        print(f"Đang tạo công ty {index}/3 và các công việc...")
        plan = _retry(f"Công ty {index}", make_company)
        company_names.add(plan["company"]["name"].casefold())
        print(f"Đang tạo hồ sơ ứng viên cho công ty {index}/3...")
        plan["candidate_groups"] = _retry(f"Ứng viên của công ty {index}", lambda: _generate_candidates(plan))
        plans.append(plan)
    return plans


def _applications_for_job(job_index: int) -> list[int]:
    own_candidates = [job_index * 3, job_index * 3 + 1, job_index * 3 + 2]
    previous_job_other_candidate = ((job_index - 1) % 5) * 3 + 2
    return [*own_candidates, previous_job_other_candidate]


def replace_database(plans: list[dict]) -> tuple[int, int, int, int]:
    password_hash = hash_password(PASSWORD)
    companies_count = jobs_count = candidates_count = applications_count = 0

    with SessionLocal.begin() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))

        candidate_number = 0
        for company_index, plan in enumerate(plans, 1):
            company = Company(**plan["company"])
            db.add(company)
            db.flush()

            recruiter_email = f"hr{company_index:02d}@example.test"
            recruiter_phone = f"09000000{company_index:02d}"
            db.add(User(
                email=recruiter_email,
                password_hash=password_hash,
                role="recruiter",
                full_name=f"Nhân sự {company.name}",
                phone=recruiter_phone,
                company_id=company.id,
            ))

            jobs = [Job(company_id=company.id, **job_data) for job_data in plan["jobs"]]
            db.add_all(jobs)
            db.flush()

            candidate_users = []
            candidate_cvs = []
            candidate_profile_data = []
            for group in plan["candidate_groups"]:
                for candidate in group:
                    candidate_number += 1
                    email = f"cand{candidate_number:03d}@example.test"
                    phone = f"091{candidate_number:07d}"
                    cv = {
                        **candidate["cv"],
                        "name": candidate["name"],
                        "email": email,
                        "phone": phone,
                    }
                    user = User(
                        email=email,
                        password_hash=password_hash,
                        role="candidate",
                        full_name=candidate["name"],
                        phone=phone,
                    )
                    db.add(user)
                    candidate_users.append(user)
                    candidate_cvs.append(cv)
                    candidate_profile_data.append((user, cv))
            db.flush()
            db.add_all(CandidateProfile(
                user_id=user.id,
                github=cv.get("github", ""),
                linkedin=cv.get("linkedin", ""),
                summary=cv["summary"],
                education=cv["education"],
                experience=cv["experience"],
                skills=cv["skills"],
                certifications_awards=cv["certifications_awards"],
            ) for user, cv in candidate_profile_data)

            for job_index, job in enumerate(jobs):
                for candidate_index in _applications_for_job(job_index):
                    db.add(Application(
                        job_id=job.id,
                        candidate_id=candidate_users[candidate_index].id,
                        cv_data=candidate_cvs[candidate_index],
                    ))
                    applications_count += 1

            companies_count += 1
            jobs_count += len(jobs)
            candidates_count += len(candidate_users)

    return companies_count, jobs_count, candidates_count, applications_count


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Replace local data with generated recruitment demo data.")
    parser.add_argument("--replace", action="store_true", help="Confirm replacing all current application data.")
    args = parser.parse_args()
    if not args.replace:
        parser.error("This script deletes current data; pass --replace to confirm.")

    database_url = make_url(settings.DATABASE_URL)
    if database_url.host not in {"localhost", "127.0.0.1", "::1"}:
        sys.exit("Refusing to delete data: scripts/seed.py only supports a local database.")
    if not settings.GEMINI_API_KEY:
        sys.exit("GEMINI_API_KEY chưa được cấu hình; dữ liệu hiện tại chưa bị thay đổi.")

    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        print("Đang yêu cầu Gemini tạo công ty, công việc và hồ sơ ứng viên...")
        plans = generate_dataset()
    except SeedGenerationError as error:
        sys.exit(f"Không tạo được dữ liệu qua Gemini; dữ liệu hiện tại chưa bị thay đổi.\n{error}")

    print("Đã kiểm tra dữ liệu: 3 công ty, 15 job, 45 hồ sơ ứng viên.")
    print("Mỗi job có một hồ sơ hướng tới fit cao, một fit trung bình và đúng 4 đơn ứng tuyển.")
    migrate.upgrade()  # đảm bảo bảng tồn tại và đúng phiên bản trước khi thay dữ liệu
    counts = replace_database(plans)
    print(
        f"Đã thay dữ liệu local: {counts[0]} công ty, {counts[1]} job, "
        f"{counts[2]} ứng viên, {counts[3]} đơn ứng tuyển."
    )
    print(f"Mật khẩu dùng chung cho tài khoản mẫu: {PASSWORD}")
    print("Tài khoản HR: hr01@example.test ... hr03@example.test")
    print("Tài khoản ứng viên: cand001@example.test ... cand045@example.test")


if __name__ == "__main__":
    main()
