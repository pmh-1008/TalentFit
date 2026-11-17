"""Chuyển model sang dict trả về cho API."""
from .models import Job, User
from .schemas import requirements_text


def iso(d):
    return d.isoformat(timespec="seconds") if d else None


def user_to_dict(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "role": u.role, "full_name": u.full_name, "phone": u.phone,
        "company": {"id": u.company.id, "name": u.company.name} if u.company else None,
    }


def job_to_dict(job: Job, **extra) -> dict:
    return {
        "id": job.id, "title": job.title, "company": job.company.name, "company_id": job.company_id,
        "email": job.email, "phone": job.phone, "description": job.description,
        "requirements": {"text": requirements_text(job.requirements)},
        "location": job.location, "job_type": job.job_type,
        "salary_range": job.salary_range, "status": job.status,
        "decisions_finalized": job.decisions_finalized,
        "created_at": iso(job.created_at), "closed_at": iso(job.closed_at),
        "open_date": job.open_date.isoformat(), "deadline": job.deadline.isoformat(),
        "benefits": job.benefits or "", **extra,
    }
