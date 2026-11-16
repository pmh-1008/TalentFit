import io
import re
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import api_client as api
import styles

JOB_TYPES = ["Full-time", "Part-time", "Internship", "Contract", "Remote"]


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
    end = fmt_date(j["deadline"]) if j.get("deadline") else "Không giới hạn"
    return f"{fmt_date(j.get('open_date') or j.get('opened_at'))} - {end}"


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


# ---------------------------------------------------------------- biểu mẫu CV (dạng bảng, tự xuống dòng)
def _frame(rows, cols, numeric=()):
    df = pd.DataFrame(rows or [], columns=cols)
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _clean(df, key, ints=(), floats=()):
    out = []
    for row in df.to_dict("records"):
        row = {k: (None if pd.isna(v) else v) for k, v in row.items()}
        if not str(row.get(key) or "").strip():
            continue
        for k in ints:
            row[k] = int(row[k]) if row.get(k) is not None else (0 if k == "duration_months" else None)
        for k in floats:
            row[k] = float(row[k]) if row.get(k) is not None else None
        for k, v in row.items():
            if v is None and k not in ints and k not in floats:
                row[k] = ""
        out.append(row)
    return out


def _duration_text(months) -> str:
    y, m = divmod(int(months or 0), 12)
    return " ".join(x for x in (f"{y} năm" if y else "", f"{m} tháng" if m else "") if x)


@st.fragment
def cv_editor(key: str, cv: dict, on_save, save_label: str = "Lưu CV", done_msg: str = "Đã lưu CV",
              ai_import: bool = False):
    """Form chỉnh sửa CV. ai_import=True chỉ dùng cho CV chung (không hiện khi ứng tuyển vị trí cụ thể)."""
    ver = st.session_state.get(f"{key}_ver", 0)
    cv = st.session_state.get(f"{key}_prefill") or cv
    if ai_import:
        _ai_import(key, cv, ver)
    k = f"{key}_{ver}"

    c1, c2, c3 = st.columns(3)
    name = c1.text_input("Họ và tên", cv.get("name", ""), disabled=True, key=f"{k}_name")
    c2.text_input("Email", cv.get("email", ""), disabled=True, key=f"{k}_email")
    phone = c3.text_input("Số điện thoại", cv.get("phone", ""), disabled=True, key=f"{k}_phone")
    g1, g2 = st.columns(2)
    github = g1.text_input("Link GitHub (không bắt buộc)", cv.get("github", ""), key=f"{k}_github",
                           placeholder="https://github.com/ten-cua-ban")
    linkedin = g2.text_input("Link LinkedIn (không bắt buộc)", cv.get("linkedin", ""), key=f"{k}_linkedin",
                             placeholder="https://www.linkedin.com/in/ten-cua-ban")
    summary = st.text_area("Giới thiệu bản thân", cv.get("summary", ""), height=100, key=f"{k}_sum")

    st.markdown("##### Học vấn")
    edu = st.data_editor(
        _frame(cv.get("education"), ["degree", "school", "year", "gpa"], ["year", "gpa"]),
        num_rows="dynamic", width="stretch", hide_index=True, key=f"{k}_edu", row_height=40,
        column_config={
            "degree": st.column_config.TextColumn("Bằng cấp / ngành học", width="medium"),
            "school": st.column_config.TextColumn("Trường", width="medium"),
            "year": st.column_config.NumberColumn("Năm tốt nghiệp", min_value=1970, max_value=2100, step=1, format="%d"),
            "gpa": st.column_config.NumberColumn("GPA", min_value=0.0, max_value=10.0, step=0.01),
        })

    st.markdown("##### Kinh nghiệm làm việc")
    exp = st.data_editor(
        _frame(cv.get("experience"), ["title", "company", "duration_months", "description"], ["duration_months"]),
        num_rows="dynamic", width="stretch", hide_index=True, key=f"{k}_exp", row_height=40,
        column_config={
            "title": st.column_config.TextColumn("Vị trí", width="medium"),
            "company": st.column_config.TextColumn("Công ty", width="medium"),
            "duration_months": st.column_config.NumberColumn("Số tháng", min_value=0, step=1, format="%d"),
            "description": st.column_config.TextColumn("Mô tả công việc", width="large"),
        })

    st.markdown("##### Kỹ năng")
    skills = st.text_area("Kỹ năng", ", ".join(cv.get("skills", [])), key=f"{k}_skills",
                          help="Ngăn cách bằng dấu phẩy hoặc xuống dòng", label_visibility="collapsed",
                          placeholder="Python, FastAPI, MySQL, Docker")

    st.markdown("##### Chứng chỉ và giải thưởng")
    certs = st.data_editor(
        _frame(cv.get("certifications_awards"), ["title", "year"], ["year"]),
        num_rows="dynamic", width="stretch", hide_index=True, key=f"{k}_cert", row_height=40,
        column_config={
            "title": st.column_config.TextColumn("Tên", width="large"),
            "year": st.column_config.NumberColumn("Năm", min_value=1970, max_value=2100, step=1, format="%d"),
        })

    if st.button(save_label, type="primary", key=f"{k}_save"):
        payload = {
            "name": name, "email": cv.get("email", ""), "phone": phone,
            "github": github.strip(), "linkedin": linkedin.strip(), "summary": summary,
            "education": _clean(edu, "degree", ints=("year",), floats=("gpa",)),
            "experience": _clean(exp, "title", ints=("duration_months",)),
            "skills": split_list(skills),
            "certifications_awards": _clean(certs, "title", ints=("year",)),
        }
        try:
            on_save(payload)
        except api.ApiError as e:
            st.error(str(e))
            return
        for old in [x for x in st.session_state if x.startswith(f"{key}_")]:  # dọn trạng thái form
            del st.session_state[old]
        flash(done_msg)
        st.rerun()  # chạy lại cả trang (đóng pop-up nếu có)


def _ai_import(key: str, cv: dict, ver: int):
    with st.expander("Đọc từ PDF"):
        file = st.file_uploader("Tải lên CV dạng PDF", type=["pdf"], key=f"{key}_file")
        if st.button("Trích xuất thông tin", key=f"{key}_parse"):
            if not file:
                st.warning("Hãy tải lên tệp PDF CV của bạn.")
                return
            try:
                raw = read_pdf(file)
            except Exception:
                st.error("Không đọc được tệp PDF này. Hãy thử tệp khác.")
                return
            if len(raw.strip()) < 20:
                st.warning("Không đọc được chữ trong PDF (có thể là bản scan hoặc ảnh). Hãy dùng PDF có thể chọn chữ.")
                return
            try:
                with st.spinner("AI đang đọc CV…"):
                    parsed = api.post("/ai/parse-cv", json={"text": raw})
            except api.ApiError as e:
                st.error(str(e))
                return
            fields = ("summary", "education", "experience", "skills", "certifications_awards")
            merged = {**cv, **{f: parsed.get(f, cv.get(f)) for f in fields}}
            for f in ("github", "linkedin"):  # không ghi đè link đã có nếu CV không có
                merged[f] = parsed.get(f) or cv.get(f, "")
            st.session_state[f"{key}_prefill"] = merged
            st.session_state[f"{key}_ver"] = ver + 1
            st.rerun(scope="fragment")


# ---------------------------------------------------------------- biểu mẫu tin tuyển dụng
def job_form(key: str, job: dict | None, submit_label: str, on_submit, with_ai: bool = False):
    ver = st.session_state.get(f"{key}_ver", 0)
    job = st.session_state.get(f"{key}_prefill") or job or {}
    req = job.get("requirements") or {}
    k = f"{key}_{ver}"

    if with_ai:
        with st.expander("Điền nhanh từ nội dung tin tuyển dụng có sẵn bằng AI"):
            file = st.file_uploader("Tải lên tệp PDF hoặc TXT", type=["pdf", "txt"], key=f"{key}_file")
            raw_text = st.text_area("Hoặc dán nội dung JD", height=130, key=f"{key}_raw")
            if st.button("Trích xuất yêu cầu", key=f"{key}_parse"):
                raw = raw_text.strip() or (read_upload(file) if file else "")
                if len(raw) < 20:
                    st.warning("Hãy tải lên tệp hoặc dán nội dung JD.")
                else:
                    try:
                        with st.spinner("AI đang đọc JD…"):
                            parsed = api.post("/ai/parse-jd", json={"text": raw})
                        st.session_state[f"{key}_prefill"] = parsed
                        st.session_state[f"{key}_ver"] = ver + 1
                        st.rerun()
                    except api.ApiError as e:
                        st.error(str(e))

    c1, c2 = st.columns(2)
    title = c1.text_input("Chức danh", job.get("title", ""), key=f"{k}_title")
    location = c2.text_input("Địa điểm", job.get("location", ""), key=f"{k}_loc")
    c3, c4 = st.columns(2)
    cur_type = job.get("job_type", "Full-time")
    types = JOB_TYPES if cur_type in JOB_TYPES else JOB_TYPES + [cur_type]
    job_type = c3.selectbox("Loại hình", types, index=types.index(cur_type), key=f"{k}_type")
    salary = c4.text_input("Mức lương", job.get("salary_range", ""), key=f"{k}_sal", placeholder="20 - 30 triệu")

    def parse_date(value):
        try:
            return date.fromisoformat(value[:10]) if value else None
        except (TypeError, ValueError):
            return None

    d1, d2 = st.columns(2)
    open_date = d1.date_input("Ngày mở đơn", value=parse_date(job.get("open_date")) or date.today(),
                              format="DD/MM/YYYY", key=f"{k}_open_date")
    default_deadline = parse_date(job.get("deadline")) or (open_date + timedelta(days=30))
    deadline = d2.date_input("Hạn nộp đơn", value=default_deadline, format="DD/MM/YYYY", key=f"{k}_deadline")

    req_text = (req.get("text") or "").strip()
    if not req_text:
        legacy = []
        if req.get("min_experience_years"):
            legacy.append(f"Kinh nghiệm tối thiểu: {req['min_experience_years']} năm")
        if req.get("education"):
            legacy.append(f"Học vấn: {req['education']}")
        if req.get("required_skills"):
            legacy.append(f"Kỹ năng: {', '.join(req['required_skills'])}")
        req_text = "\n".join(legacy)
    description = st.text_area("Mô tả công việc", job.get("description", ""), height=200, key=f"{k}_desc")
    requirements = st.text_area("Yêu cầu đối với ứng viên", req_text, height=120, key=f"{k}_requirements")
    benefits = st.text_area("Quyền lợi", job.get("benefits", ""), height=100, key=f"{k}_benefits")
    user = st.session_state.get("user") or {}
    c6, c7 = st.columns(2)
    email = c6.text_input("Email liên hệ", job.get("email") or user.get("email", ""), key=f"{k}_mail")
    phone = c7.text_input("Số điện thoại liên hệ", job.get("phone") or user.get("phone", ""), key=f"{k}_phone")

    if st.button(submit_label, type="primary", key=f"{k}_submit"):
        if len(title.strip()) < 2 or not description.strip():
            st.error("Vui lòng nhập chức danh và mô tả công việc.")
            return
        if not open_date or not deadline:
            st.error("Vui lòng chọn ngày mở đơn và hạn nộp đơn.")
            return
        if deadline < open_date:
            st.error("Hạn nộp đơn phải từ ngày mở đơn trở đi.")
            return
        payload = {
            "title": title, "description": description, "location": location, "job_type": job_type,
            "salary_range": salary, "email": email, "phone": phone, "open_date": open_date.isoformat(),
            "deadline": deadline.isoformat(), "benefits": benefits,
            "requirements": {"text": requirements},
        }
        try:
            on_submit(payload)
        except api.ApiError as e:
            st.error(str(e))
            return
        st.session_state.pop(f"{key}_prefill", None)
        st.session_state[f"{key}_ver"] = ver + 1
        st.rerun()


def job_detail(j: dict, with_header: bool = True):
    """Thông tin chi tiết một công việc: nội dung bên trái, thẻ thông tin chung bên phải."""
    if with_header:
        st.markdown(styles.job_header(j), unsafe_allow_html=True)
    req = j.get("requirements") or {}
    requirements = req.get("text", "").strip()
    if not requirements:
        legacy = []
        if req.get("min_experience_years"):
            legacy.append(f"Kinh nghiệm tối thiểu {req['min_experience_years']} năm")
        if req.get("education"):
            legacy.append(f"Học vấn: {req['education']}")
        if req.get("required_skills"):
            legacy.append(f"Kỹ năng: {', '.join(req['required_skills'])}")
        requirements = "\n".join(legacy)

    main, side = st.columns([5, 2], gap="large")
    with main:
        st.markdown("**Mô tả công việc**")
        st.write(j.get("description", ""))
        if requirements:
            st.markdown("**Yêu cầu đối với ứng viên**")
            st.write(requirements)
        if j.get("benefits"):
            st.markdown("**Quyền lợi**")
            st.write(j["benefits"])
    with side:
        st.markdown(styles.job_info_card(j, open_range_text(j), is_expiring(j)), unsafe_allow_html=True)


def _href(url: str) -> str:
    return url if re.match(r"https?://", url, re.I) else f"https://{url}"


def render_cv(cv: dict):
    """Hiển thị CV ở dạng chỉ đọc (dòng thời gian)."""
    e = styles.esc
    links = [f"<a href='{e(_href(cv[f]))}' target='_blank' rel='noopener noreferrer'>{label}</a>"
             for f, label in (("github", "GitHub"), ("linkedin", "LinkedIn")) if (cv.get(f) or "").strip()]
    if links:
        st.markdown(f"<div class='cv-links'>{''.join(links)}</div>", unsafe_allow_html=True)
    if cv.get("summary"):
        st.write(cv["summary"])
    if cv.get("skills"):
        st.markdown("<div class='cv-h'>Kỹ năng</div>", unsafe_allow_html=True)
        st.markdown(styles.skills_badges(cv["skills"], 40), unsafe_allow_html=True)
    if cv.get("experience"):
        rows = []
        for x in cv["experience"]:
            dur = _duration_text(x.get("duration_months"))
            pill = f"<span class='pill'>{e(dur)}</span>" if dur else ""
            desc = f"<div class='tl-d'>{e(x.get('description'))}</div>" if x.get("description") else ""
            rows.append(f"<div class='tl-i'><div class='tl-t'>{e(x.get('title'))}{pill}</div>"
                        f"<div class='tl-s'>{e(x.get('company'))}</div>{desc}</div>")
        st.markdown(f"<div class='cv-h'>Kinh nghiệm</div><div class='tl'>{''.join(rows)}</div>", unsafe_allow_html=True)
    if cv.get("education"):
        rows = []
        for x in cv["education"]:
            sub = ", ".join(v for v in (x.get("school"), str(x["year"]) if x.get("year") else "",
                                         f"GPA {x['gpa']}" if x.get("gpa") else "") if v)
            rows.append(f"<div class='tl-i'><div class='tl-t'>{e(x.get('degree'))}</div><div class='tl-s'>{e(sub)}</div></div>")
        st.markdown(f"<div class='cv-h'>Học vấn</div><div class='tl'>{''.join(rows)}</div>", unsafe_allow_html=True)
    if cv.get("certifications_awards"):
        rows = []
        for x in cv["certifications_awards"]:
            pill = f"<span class='pill'>{e(x['year'])}</span>" if x.get("year") else ""
            rows.append(f"<div class='tl-i'><div class='tl-t'>{e(x.get('title'))}{pill}</div></div>")
        st.markdown(f"<div class='cv-h'>Chứng chỉ và giải thưởng</div><div class='tl'>{''.join(rows)}</div>",
                    unsafe_allow_html=True)


# ---------------------------------------------------------------- tài khoản (mở từ menu tên tài khoản)
def profile_page(user: dict):
    st.title("Thông tin cá nhân")
    with st.form("profile_form", border=False):
        c1, c2 = st.columns(2)
        name = c1.text_input("Họ và tên", user.get("full_name", ""))
        phone = c2.text_input("Số điện thoại", user.get("phone", ""))
        st.text_input("Email đăng nhập", user["email"], disabled=True)
        if st.form_submit_button("Lưu thay đổi", type="primary"):
            try:
                st.session_state["user"] = api.put("/auth/me", json={"full_name": name, "phone": phone})
                flash("Đã cập nhật thông tin")
                st.rerun()
            except api.ApiError as e:
                st.error(str(e))

    if user["role"] == "recruiter":
        st.divider()
        st.markdown("##### Thông tin công ty")
        company = api.get("/company/me")
        with st.form("company_form", border=False):
            cname = st.text_input("Tên công ty", company["name"])
            industry = st.text_input("Lĩnh vực", company["industry"])
            desc = st.text_area("Giới thiệu", company["description"])
            if st.form_submit_button("Lưu thông tin công ty", type="primary"):
                try:
                    api.put("/company/me", json={"name": cname, "industry": industry, "description": desc})
                    st.session_state["user"] = api.get("/auth/me")
                    flash("Đã cập nhật thông tin công ty")
                    st.rerun()
                except api.ApiError as e:
                    st.error(str(e))


def password_page():
    st.title("Đổi mật khẩu")
    with st.form("password_form", border=False, clear_on_submit=True):
        old = st.text_input("Mật khẩu hiện tại", type="password")
        new = st.text_input("Mật khẩu mới (tối thiểu 6 ký tự)", type="password")
        again = st.text_input("Nhập lại mật khẩu mới", type="password")
        if st.form_submit_button("Đổi mật khẩu", type="primary"):
            if new != again:
                st.error("Mật khẩu nhập lại không khớp")
            else:
                try:
                    api.post("/auth/change-password", json={"old_password": old, "new_password": new})
                    flash("Đã đổi mật khẩu")
                    st.rerun()
                except api.ApiError as e:
                    st.error(str(e))