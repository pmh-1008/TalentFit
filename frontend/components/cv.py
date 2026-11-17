import re

import pandas as pd
import streamlit as st

import api_client as api
import helpers
import styles


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
        is_blank = lambda value: value is None or (isinstance(value, str) and not value.strip())
        if is_blank(row.get(key)) and all(is_blank(value) for field, value in row.items() if field != key):
            continue
        row = {k: v.strip() if isinstance(v, str) else v for k, v in row.items()}
        for k in ints:
            if row.get(k) is not None:
                try:
                    number = float(row[k])
                    row[k] = int(number) if number.is_integer() else number
                except (TypeError, ValueError):
                    pass
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
    github = g1.text_input("Link GitHub", cv.get("github", ""), key=f"{k}_github",
                           placeholder="https://github.com/ten-cua-ban")
    linkedin = g2.text_input("Link LinkedIn", cv.get("linkedin", ""), key=f"{k}_linkedin",
                             placeholder="https://www.linkedin.com/in/ten-cua-ban")
    summary = st.text_area("Giới thiệu bản thân", cv.get("summary", ""), height=100, key=f"{k}_sum")

    st.markdown("##### Học vấn")
    edu = st.data_editor(
        _frame(cv.get("education"), ["degree", "school", "year", "gpa"], ["year", "gpa"]),
        num_rows="dynamic", width="stretch", hide_index=True, key=f"{k}_edu", row_height=40,
        column_config={
            "degree": st.column_config.TextColumn("Bằng cấp & ngành học", width="medium"),
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
        education = _clean(edu, "degree", ints=("year",), floats=("gpa",))
        experience = _clean(exp, "title", ints=("duration_months",))
        certifications = _clean(certs, "title", ints=("year",))
        skill_list = helpers.split_list(skills)
        errors = []
        for i, item in enumerate(education, 1):
            if not item["degree"] or not item["school"] or not item["year"]:
                errors.append(f"Học vấn dòng {i}: cần nhập bằng cấp, trường và năm tốt nghiệp.")
        for i, item in enumerate(experience, 1):
            months = item["duration_months"]
            if not item["title"] or not item["company"] or months is None or (
                    type(months) is not int):
                errors.append(f"Kinh nghiệm dòng {i}: cần nhập vị trí, công ty và số tháng nguyên.")
        for i, item in enumerate(certifications, 1):
            if not item["title"] or not item["year"]:
                errors.append(f"Chứng chỉ/giải thưởng dòng {i}: cần nhập tên và năm.")
        if not skill_list:
            errors.append("Cần nhập ít nhất một kỹ năng.")
        if errors:
            st.error("Không thể lưu CV:\n\n- " + "\n- ".join(errors))
            return

        payload = {
            "name": name, "email": cv.get("email", ""), "phone": phone,
            "github": github.strip(), "linkedin": linkedin.strip(), "summary": summary,
            "education": education,
            "experience": experience,
            "skills": skill_list,
            "certifications_awards": certifications,
        }
        try:
            on_save(payload)
        except api.ApiError as e:
            st.error(str(e))
            return
        for old in [x for x in st.session_state if x.startswith(f"{key}_")]:  # dọn trạng thái form
            del st.session_state[old]
        helpers.flash(done_msg)
        st.rerun()  # chạy lại cả trang (đóng pop-up nếu có)


def _ai_import(key: str, cv: dict, ver: int):
    with st.expander("Đọc từ PDF"):
        file = st.file_uploader("Tải lên CV dạng PDF", type=["pdf"], key=f"{key}_file")
        if st.button("Trích xuất thông tin", key=f"{key}_parse"):
            if not file:
                st.warning("Hãy tải lên tệp PDF CV của bạn.")
                return
            try:
                raw = helpers.read_pdf(file)
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
