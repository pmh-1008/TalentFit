from datetime import date, timedelta

import pandas as pd
import streamlit as st

import api_client as api
import styles
import helpers
from components import cv as cv_ui
from components import job as job_ui
from views import notifications

PAGES = ["Tổng quan", "Tin tuyển dụng", "Thông báo"]


# ---------------------------------------------------------------- Tổng quan
def dashboard_page():
    st.title("Tổng quan tuyển dụng")
    jobs = api.get("/jobs/mine")
    if not jobs:
        st.info("Công ty chưa có tin tuyển dụng. Vào mục Tin tuyển dụng để đăng tin đầu tiên.")
        return
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tin đang mở", sum(1 for j in jobs if j["status"] == "open"))
    m2.metric("Tổng lượt ứng tuyển", sum(j["total"] for j in jobs))
    m3.metric("Chờ duyệt", sum(j["pending"] for j in jobs))
    m4.metric("Đã duyệt", sum(j["approved"] for j in jobs))

    st.markdown("##### Lượt ứng tuyển theo tin")
    df = pd.DataFrame({
        "Chờ duyệt": [j["pending"] for j in jobs],
        "Đã duyệt": [j["approved"] for j in jobs],
        "Từ chối": [j["rejected"] for j in jobs],
    }, index=[j["title"] for j in jobs])
    st.bar_chart(df, color=["#98A2B3", "#0E7A55", "#B42318"], horizontal=True)

    table = pd.DataFrame([{
        "Vị trí": j["title"], "Trạng thái": styles.STATUS[j["status"]][0], "Tổng": j["total"],
        "Chờ duyệt": j["pending"], "Đã duyệt": j["approved"], "Từ chối": j["rejected"],
    } for j in jobs])
    st.dataframe(table, hide_index=True, width="stretch")


# ---------------------------------------------------------------- Tin tuyển dụng
@st.dialog("Xác nhận xóa tin tuyển dụng", width="small")
def _delete_job_dialog(job: dict):
    st.write(f"Bạn có chắc muốn xóa tin **{styles.esc(job['title'])}** cùng toàn bộ đơn ứng tuyển liên quan?")
    if st.button("Xác nhận xóa", key=f"del_{job['id']}", type="primary"):
        try:
            api.delete(f"/jobs/{job['id']}")
            helpers.flash("Đã xóa tin tuyển dụng")
            st.rerun()
        except api.ApiError as e:
            st.error(str(e))


def _delete_job_action(job: dict):
    if st.button("Xóa", key=f"delete_{job['id']}"):
        _delete_job_dialog(job)


@st.dialog("Mở lại tin tuyển dụng", width="small")
def _reopen_job_dialog(job: dict):
    default_deadline = date.today() + timedelta(days=30)
    if job.get("deadline"):
        try:
            default_deadline = max(date.today(), date.fromisoformat(job["deadline"][:10]))
        except ValueError:
            pass
    new_deadline = st.date_input("Ngày đóng đơn mới", value=default_deadline,
                                 min_value=date.today(), format="DD/MM/YYYY",
                                 key=f"reopen_deadline_{job['id']}")
    if st.button("Xác nhận mở lại", key=f"confirm_reopen_{job['id']}", type="primary"):
        try:
            api.post(f"/jobs/{job['id']}/reopen", json={"deadline": new_deadline.isoformat()})
            helpers.flash(f"Đã mở lại {job['title']}")
            st.rerun()
        except api.ApiError as e:
            st.error(str(e))


def _applicants_tab(job_id: str, job_title: str):
    st.markdown(f"##### {styles.esc(job_title)}")
    apps = api.get(f"/applications/job/{job_id}")
    if not apps:
        st.info("Tin này chưa có ứng viên nào ứng tuyển.")
        return

    decisions_key = f"application_decisions_{job_id}"
    decisions = st.session_state.setdefault(decisions_key, {})
    current_ids = {a["id"] for a in apps}
    for application in apps:
        initial = application.get("draft_decision") or (
            application["status"] if application["status"] in ("approved", "rejected") else None)
        decisions.setdefault(application["id"], initial)
    for application_id in list(decisions):
        if application_id not in current_ids:
            del decisions[application_id]

    status = st.selectbox("Trạng thái", ["Tất cả", "Chờ duyệt", "Đã duyệt", "Từ chối"],
                          key=f"applicant_status_{job_id}")
    unscored = sum(1 for a in apps if not a["match"])
    t1, t2, t3 = st.columns([5, 2, 2])
    t1.markdown(f"**{len(apps)}** ứng viên, **{unscored}** chưa chấm điểm")
    redo = t2.checkbox("Chấm lại tất cả", key=f"redo_{job_id}")
    if t3.button("Chấm điểm bằng AI", type="primary", width="stretch", disabled=not (unscored or redo),
                 key=f"score_{job_id}"):
        try:
            with st.spinner("AI đang chấm điểm hồ sơ…"):
                api.post(f"/matching/applications/{job_id}", params={"force": redo}, timeout=600)
            helpers.flash("Đã chấm điểm xong các hồ sơ")
            st.rerun()
        except api.ApiError as e:
            st.error(str(e))

    wanted = {"Chờ duyệt": "pending", "Đã duyệt": "approved", "Từ chối": "rejected"}.get(status)
    visible = [a for a in apps if not wanted or a["status"] == wanted]
    for i, a in enumerate(visible, 1):
        _applicant_card(i, a, decisions_key, decisions.get(a["id"]))

    save_col, finalize_col = st.columns(2)
    payload = [{"application_id": application_id, "decision": decision}
               for application_id, decision in decisions.items() if decision]
    has_unfinalized_decisions = any(
        application["status"] == "pending" or decisions.get(application["id"]) != application["status"]
        for application in apps
    )
    if save_col.button("Lưu tiến độ tạm thời", key=f"save_decisions_{job_id}", width="stretch"):
        try:
            api.put(f"/applications/job/{job_id}/decision-draft", json={"decisions": payload})
            helpers.flash("Đã lưu tiến độ xét duyệt tạm thời")
            st.rerun()
        except api.ApiError as e:
            st.error(str(e))
    approved_n = sum(1 for d in decisions.values() if d == "approved")
    undecided_n = sum(1 for a in apps if not decisions.get(a["id"]))
    finalize_error_key = f"finalize_error_{job_id}"
    if finalize_col.button("Lưu & thông báo kết quả", key=f"open_finalize_{job_id}", width="stretch",
                           disabled=not has_unfinalized_decisions):
        st.session_state.pop(finalize_error_key, None)
        _finalize_decisions_dialog(job_id, payload, decisions_key, len(apps), approved_n,
                                   undecided_n, finalize_error_key)
    if error := st.session_state.get(finalize_error_key):
        st.error(error)


@st.dialog("Xác nhận gửi kết quả", width="small")
def _finalize_decisions_dialog(job_id: str, payload: list[dict], decisions_key: str,
                               total_n: int, approved_n: int, undecided_n: int, error_key: str):
    st.write(f"Gửi thông báo tới **{approved_n}** ứng viên đã được duyệt và **{total_n - approved_n}** bị từ chối "
             "Thao tác này không thể hoàn tác.")
    if st.button("Xác nhận gửi kết quả", key=f"finalize_decisions_{job_id}", type="primary"):
        try:
            result = api.post(f"/applications/job/{job_id}/finalize-decisions", json={"decisions": payload})
            helpers.flash(f"Đã gửi kết quả tới {result['notified']} ứng viên")
            st.session_state.pop(decisions_key, None)
            st.session_state.pop(error_key, None)
        except api.ApiError as e:
            st.session_state[error_key] = str(e)
        st.rerun()


def _job_cards(jobs: list[dict], status: str):
    visible = [job for job in jobs if job["status"] == status]
    if not visible:
        empty_text = {"open": "Chưa có tin đang mở.", "scheduled": "Chưa có tin chờ mở.",
                      "closed": "Chưa có tin đã đóng."}[status]
        st.info(empty_text)
        return

    for job in visible:
        with st.container(border=True):
            head, actions = st.columns([6, 5], vertical_alignment="top")
            with head:
                if st.button(job["title"], key=f"job_title_{job['id']}", type="tertiary"):
                    st.session_state["recruiter_job_id"] = job["id"]
                    st.rerun()
                st.markdown(styles.job_meta(job), unsafe_allow_html=True)
            with actions:
                with st.container(key=f"jact_{job['id']}", horizontal=True, horizontal_alignment="right",
                                  gap="small"):
                    _job_actions(job, status)
            st.markdown(styles.job_stats(job, helpers.open_range_text(job)), unsafe_allow_html=True)
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)


def _job_actions(job: dict, status: str):
    if status == "open":
        if st.button("Đóng đơn", key=f"close_{job['id']}"):
            api.post(f"/jobs/{job['id']}/close")
            helpers.flash(f"Đã đóng đơn {job['title']}")
            st.rerun()
    elif status == "scheduled":
        if st.button("Mở ngay", key=f"open_now_{job['id']}", type="primary"):
            api.post(f"/jobs/{job['id']}/open-now")
            helpers.flash(f"Đã mở đơn {job['title']}")
            st.rerun()
    elif job.get("decisions_finalized"):
        st.caption("Đã gửi kết quả · không thể mở lại")
    else:
        if st.button("Mở lại", key=f"reopen_{job['id']}"):
            _reopen_job_dialog(job)
    _delete_job_action(job)


def jobs_page():
    jobs = api.get("/jobs/mine")
    selected_job_id = st.session_state.get("recruiter_job_id")
    selected_job = next((job for job in jobs if job["id"] == selected_job_id), None)
    if selected_job:
        _recruiter_job_page(selected_job)
        return
    st.session_state.pop("recruiter_job_id", None)

    st.title("Tin tuyển dụng")
    tab_open, tab_scheduled, tab_closed, tab_new = st.tabs(
        ["Đang mở", "Chưa mở", "Đã đóng", "Đăng tin mới"])

    with tab_open:
        _job_cards(jobs, "open")
    with tab_scheduled:
        _job_cards(jobs, "scheduled")
    with tab_closed:
        _job_cards(jobs, "closed")
    with tab_new:
        job_ui.job_form("job_new", None, "Lưu",
                 lambda p: (api.post("/jobs", json=p), helpers.flash("Đã lưu tin tuyển dụng")),
                 with_ai=True)


def _recruiter_job_page(job: dict):
    if st.button("← Quay lại danh sách tin", type="tertiary", key="back_to_job_list"):
        st.session_state.pop("recruiter_job_id", None)
        st.rerun()

    head, actions = st.columns([7, 4], vertical_alignment="top")
    with head:
        st.markdown(styles.job_title_head(job), unsafe_allow_html=True)
    with actions:
        with st.container(key=f"jact_{job['id']}", horizontal=True, horizontal_alignment="right", gap="small"):
            _job_actions(job, job["status"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ứng tuyển", job["total"])
    m2.metric("Chờ duyệt", job["pending"])
    m3.metric("Đã duyệt", job["approved"])
    m4.metric("Từ chối", job["rejected"])

    applicants_label = "Danh sách ứng viên"
    job_tabs = {
        "detail": "Chi tiết công việc",
        "applicants": applicants_label,
        "edit": "Chỉnh sửa",
    }
    with st.container(key="subtabs"):
        selected_tab = st.radio("Mục", list(job_tabs), format_func=job_tabs.get, horizontal=True,
                                label_visibility="collapsed", key=f"recruiter_job_tab_{job['id']}")
    if selected_tab == "detail":
        job_ui.job_detail(job, with_header=False)
    elif selected_tab == "applicants":
        _applicants_tab(job["id"], job["title"])
    else:
        job_ui.job_form(f"job_edit_{job['id']}", job, "Lưu thay đổi",
                        lambda payload: (api.put(f"/jobs/{job['id']}", json=payload),
                                         helpers.flash("Đã cập nhật tin")))


def _set_applicant_decision(decisions_key: str, application_id: str, decision: str):
    st.session_state[decisions_key][application_id] = decision


def _applicant_card(i: int, a: dict, decisions_key: str, decision: str | None):
    cand, m = a["candidate"], a["match"]
    with st.container(border=True):
        c1, c2, c3 = st.columns([5, 3, 3])
        rank = f"<span class='rank match-rank'>{i}</span>" if m else ""
        c1.markdown(f"<div style='display:flex;align-items:flex-start;gap:10px'>{rank}<div>"
                    f"<div class='jt'>{styles.esc(cand['name'])}</div>"
                    f"<div class='jm'><span>{styles.esc(cand['email'])}</span><span>{styles.esc(cand['phone'])}</span></div>"
                    f"</div></div>", unsafe_allow_html=True)
        if m:
            c2.markdown(styles.overall_html(m["overall_fit"]), unsafe_allow_html=True)
        else:
            c2.caption("Chưa chấm điểm")
        with c3:
            b1, b2 = st.columns(2)
            b1.button("Đã duyệt" if decision == "approved" else "Duyệt",
                      key=f"app_decision_approve_{a['id']}",
                      type="primary" if decision == "approved" else "secondary", width="stretch",
                      disabled=a["status"] != "pending",
                      on_click=_set_applicant_decision,
                      args=(decisions_key, a["id"], "approved"))
            b2.button("Đã từ chối" if decision == "rejected" else "Từ chối",
                      key=f"app_decision_reject_{a['id']}",
                      type="primary" if decision == "rejected" else "secondary", width="stretch",
                      disabled=a["status"] != "pending",
                      on_click=_set_applicant_decision,
                      args=(decisions_key, a["id"], "rejected"))
        if m:
            st.markdown(styles.score_bars(m), unsafe_allow_html=True)
        with st.container(key=f"applicant_details_{a['id']}", gap=3):
            with st.expander("Hồ sơ ứng viên"):
                cv_ui.render_cv(a["cv"])
            if m:
                with st.expander("Nhận xét chi tiết", expanded=(i == 1)):
                    st.markdown(styles.explanation_html(m), unsafe_allow_html=True)


def notifications_page():
    notifications.render()


ROUTES = {"Tổng quan": dashboard_page, "Tin tuyển dụng": jobs_page, "Thông báo": notifications_page}