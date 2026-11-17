import html
from functools import lru_cache
from pathlib import Path

import streamlit as st

CSS_FILE = Path(__file__).parent / "static" / "style.css"



@lru_cache(maxsize=1)
def _css() -> str:
    return f"<style>\n{CSS_FILE.read_text(encoding='utf-8')}</style>"


def inject():
    st.markdown(_css(), unsafe_allow_html=True)


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def badge(text: str, kind: str = "info") -> str:
    return f"<span class='badge b-{kind}'>{esc(text)}</span>"


STATUS = {"pending": ("Chờ duyệt", "warn"), "approved": ("Đã duyệt", "ok"), "rejected": ("Từ chối", "bad"),
          "open": ("Đang mở", "ok"), "scheduled": ("Chưa mở", "mute"), "closed": ("Đã đóng", "mute")}


def status_badge(status: str) -> str:
    label, kind = STATUS.get(status, (status, "mute"))
    return badge(label, kind)


def skills_badges(skills, limit: int = 12) -> str:
    return "".join(badge(s, "mute") for s in (skills or [])[:limit])


def job_meta(j: dict) -> str:
    company = f"<div class='jm-company'>{esc(j['company'])}</div>"
    meta = []
    for key in ("location", "job_type", "salary_range"):
        if j.get(key):
            meta.append(f"<span>{esc(j[key])}</span>")
    return f"{company}<div class='jm'>{''.join(meta)}</div>"


def job_header(j: dict) -> str:
    return f"<div class='jt'>{esc(j['title'])}</div>{job_meta(j)}"


def job_stats(j: dict, open_range: str) -> str:
    sep = "<span class='sep'>·</span>"
    parts = [f"<span><b>{j['total']}</b> ứng tuyển</span>",
             f"<span><b class='warn'>{j['pending']}</b> chờ duyệt</span>",
             f"<span><b>{j.get('approved', 0)}</b> đã duyệt</span>",
             f"<span><b>{j.get('rejected', 0)}</b> từ chối</span>"]
    return f"<div class='jstats'>{sep.join(parts)}<span class='end'>Mở đơn: {esc(open_range)}</span></div>"


def job_title_head(j: dict) -> str:
    return (f"<div class='jd-head'><span class='jd-title'>{esc(j['title'])}</span>{status_badge(j['status'])}</div>"
            f"{job_meta(j)}")


def job_info_card(j: dict, open_range: str, expiring: bool = False) -> str:
    rows = [(label, esc(j[key])) for label, key in
            (("Mức lương", "salary_range"), ("Địa điểm", "location"), ("Hình thức", "job_type")) if j.get(key)]
    soon = f"<br>{badge('Sắp hết hạn', 'bad')}" if expiring else ""
    rows.append(("Mở đơn", esc(open_range) + soon))
    contact = "<br>".join(esc(j[k]) for k in ("email", "phone") if j.get(k))
    if contact:
        rows.append(("Liên hệ", contact))
    body = "".join(f"<dt>{label}</dt><dd>{value}</dd>" for label, value in rows)
    return f"<div class='jd-side'><div class='sec-t'>Thông tin chung</div><dl>{body}</dl></div>"


def tier(score: float) -> str:
    return "t-hi" if score >= 75 else "t-mid" if score >= 50 else "t-low"


def overall_html(score: float) -> str:
    return f"<div class='overall {tier(score)}'>{score:.0f}<small>/100 phù hợp</small></div>"


def score_bars(m: dict) -> str:
    rows = [("Kỹ năng", m["skill_match"]), ("Kinh nghiệm", m["experience_match"]), ("Học vấn", m["education_match"])]
    body = "".join(
        f"<div class='score-row'><span>{label}</span><div class='track'><div class='fill' style='width:{v:.0f}%'></div></div>"
        f"<b>{v:.0f}</b></div>" for label, v in rows)
    return f"<div class='score'>{body}</div>"


def explanation_html(m: dict) -> str:
    ex = m.get("explanations") or {}
    parts = [("Kỹ năng", "skill_match"), ("Kinh nghiệm", "experience_match"), ("Học vấn", "education_match"),
             ("Nhận xét chung", "overall_comment")]
    return "".join(f"<div class='note'><b>{label}</b>{esc(ex.get(k, ''))}</div>" for label, k in parts if ex.get(k))