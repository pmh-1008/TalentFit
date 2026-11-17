from datetime import date, timedelta

import streamlit as st

import api_client as api
import helpers
import styles


# ---------------------------------------------------------------- biểu mẫu tin tuyển dụng
@st.fragment
def job_form(key: str, job: dict | None, submit_label: str, on_submit, with_ai: bool = False):
    ver = st.session_state.get(f"{key}_ver", 0)
    job = st.session_state.get(f"{key}_prefill") or job or {}
    req = job.get("requirements") or {}
    k = f"{key}_{ver}"

    if with_ai:
        with st.expander("Trích xuất từ văn bản"):
            raw_text = st.text_area("Nhập nội dung JD", height=130, key=f"{key}_raw")
            if st.button("Trích xuất yêu cầu", key=f"{key}_parse"):
                raw = raw_text.strip()
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
    all_types = api.get("/jobs/meta", cache=True)["all_job_types"]  # danh sách do backend quy định
    types = all_types if cur_type in all_types else all_types + [cur_type]
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
    description = st.text_area("Mô tả công việc", job.get("description", ""), height=150, key=f"{k}_desc")
    requirements = st.text_area("Yêu cầu đối với ứng viên", req_text, height=150, key=f"{k}_requirements")
    benefits = st.text_area("Quyền lợi", job.get("benefits", ""), height=120, key=f"{k}_benefits")
    user = st.session_state.get("user") or {}
    c6, c7 = st.columns(2)
    email = c6.text_input("Email liên hệ", job.get("email") or user.get("email", ""), key=f"{k}_mail")
    phone = c7.text_input("Số điện thoại liên hệ", job.get("phone") or user.get("phone", ""), key=f"{k}_phone")

    if st.button(submit_label, type="primary", key=f"{k}_submit"):
        errors = []
        if len(title.strip()) < 2:
            errors.append("Chức danh phải có ít nhất 2 ký tự.")
        if not description.strip():
            errors.append("Vui lòng nhập mô tả công việc.")
        if not requirements.strip():
            errors.append("Vui lòng nhập yêu cầu đối với ứng viên.")
        if errors:
            st.error("\n".join(errors))
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
    requirements = ((j.get("requirements") or {}).get("text") or "").strip()

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
        st.markdown(styles.job_info_card(j, helpers.open_range_text(j), helpers.is_expiring(j)), unsafe_allow_html=True)
