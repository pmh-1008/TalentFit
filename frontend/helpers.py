import io
import re
from datetime import date

import streamlit as st

import styles


# ---------------------------------------------------------------- thông báo nhanh
def flash(message: str, kind: str = "success"):
    st.session_state.setdefault("flash", []).append((message, kind))


def show_flash():
    for message, kind in st.session_state.pop("flash", []):
        {"success": st.success, "warning": st.warning, "error": st.error}.get(kind, st.info)(message)


def fmt_date(value: str | None) -> str:
    if not value:
        return ""
    y, m, d = value[:10].split("-")
    return f"{d}/{m}/{y}"


def open_range_text(j: dict) -> str:
    """Mở đơn: dd/mm/yyyy - dd/mm/yyyy (ngày mở - hạn nộp)."""
    return f"{fmt_date(j['open_date'])} - {fmt_date(j['deadline'])}"


def is_expiring(j: dict) -> bool:
    """Còn từ 0 đến 7 ngày là hết hạn nộp đơn."""
    try:
        left = (date.fromisoformat(j["deadline"][:10]) - date.today()).days
    except (KeyError, TypeError, ValueError):
        return False
    return 0 <= left <= 7


def open_period_html(j: dict) -> str:
    soon = styles.badge("Sắp hết hạn", "bad") if is_expiring(j) else ""
    return f"<div class='jm' style='align-items:center'><span>Mở đơn: {open_range_text(j)}</span>{soon}</div>"


def split_list(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[,\n;]", text or "") if s.strip()]


def read_upload(file) -> str:
    """Đọc nội dung tệp PDF hoặc TXT đã tải lên."""
    if file.name.lower().endswith(".pdf"):
        return read_pdf(file).strip()
    return file.getvalue().decode("utf-8", errors="ignore").strip()


def read_pdf(file) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(file.getvalue()))
    return "\n".join((p.extract_text() or "") for p in reader.pages)
