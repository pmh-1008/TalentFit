from datetime import date

import streamlit as st

import api_client as api
import styles
import helpers
from components import cv as cv_ui
from components import job as job_ui
from components import job_list
from views import notifications

PAGES = ["Việc làm", "Đã ứng tuyển", "CV của tôi", "Thông báo"]


# ---------------------------------------------------------------- pop-up
@st.dialog("Tùy chỉnh CV để ứng tuyển", width="large")
def apply_dialog(j: dict):
    st.markdown(f"Vị trí: **{styles.esc(j['title'])}** tại {styles.esc(j['company'])}")
    st.caption("CV bên dưới lấy từ CV chung của bạn. Hãy chỉnh cho phù hợp với vị trí này: "
               "bản tùy chỉnh chỉ dùng cho đơn ứng tuyển vào công việc này.")
    data = api.get(f"/candidates/me/cv/job/{j['id']}")

    def submit(payload):
        api.put(f"/candidates/me/cv/job/{j['id']}", json=payload)
        api.post("/applications", json={"job_id": j["id"]})

    cv_ui.cv_editor(f"cv_apply_{j['id']}", data["cv"], submit, save_label="Lưu CV và ứng tuyển",
                     done_msg=f"Đã nộp đơn vào {j['title']}")


@st.dialog("Đơn ứng tuyển", width="large")
def application_dialog(a: dict):
    decided = "" if a["status"] == "pending" else styles.status_badge(a["status"])
    st.markdown(f"Nộp ngày {helpers.fmt_date(a['applied_at'])} {decided}", unsafe_allow_html=True)
    t_job, t_cv = st.tabs(["Thông tin công việc", "CV đã nộp"])
    with t_job:
        job_ui.job_detail(a["job"])
    with t_cv:
        st.caption("Đây là CV tại thời điểm bạn nộp đơn.")
        cv_ui.render_cv(a.get("cv") or {})


# ---------------------------------------------------------------- Việc làm
def _on_pick(job_id: str):
    ids = st.session_state.setdefault("compare_ids", [])
    if st.session_state.get(f"sel_{job_id}"):
        if job_id not in ids:
            ids.append(job_id)
    elif job_id in ids:
        ids.remove(job_id)
    st.session_state.pop("rank_results", None)


def _on_unpick(job_id: str):
    ids = st.session_state.get("compare_ids", [])
    if job_id in ids:
        ids.remove(job_id)
    st.session_state.pop(f"sel_{job_id}", None)
    st.session_state.pop("rank_results", None)


def _rank_card(i: int, r: dict):
    j = r["job"]
    with st.container(border=True):
        a, b = st.columns([6, 3])
        with a:
            c_rank, c_job = st.columns([1, 11], vertical_alignment="top")
            c_rank.markdown(f"<span class='rank match-rank'>{i}</span>", unsafe_allow_html=True)
            with c_job:
                job_list.title_link(j, f"rank_title_{j['id']}")
                st.markdown(styles.job_meta(j), unsafe_allow_html=True)
        b.markdown(styles.overall_html(r["overall_fit"]), unsafe_allow_html=True)
        st.markdown(styles.score_bars(r), unsafe_allow_html=True)
        if r["cv_type"] == "custom":
            st.caption("Chấm theo CV tùy chỉnh cho công việc này")
        with st.container(key=f"rank_expl_{j['id']}"):
            with st.expander("Nhận xét chi tiết", expanded=(i == 1)):
                st.markdown(styles.explanation_html(r), unsafe_allow_html=True)


def _app_state(app: dict | None, title: str, key: str) -> bool:
    """Nút Rút đơn (chờ duyệt) / nhãn Đã duyệt / Không được duyệt. Trả về False nếu chưa có đơn."""
    if not app:
        return False
    if app["status"] == "pending":
        if st.button("Rút đơn", key=f"jobwd_{key}", width="stretch"):
            try:
                api.delete(f"/applications/{app['id']}")
                helpers.flash(f"Đã rút đơn ứng tuyển {title}")
                st.rerun()  # chạy lại cả trang để cập nhật danh sách
            except api.ApiError as e:
                st.error(str(e))
    elif app["status"] == "approved":
        st.markdown("<span class='app-state ok'>Đã duyệt</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span class='app-state bad'>Không được duyệt</span>", unsafe_allow_html=True)
    return True


def _apply_state(j: dict):
    """Cột bên phải thẻ việc làm: Rút đơn / Đã duyệt / Ứng tuyển / Hết hạn."""
    if _app_state(j.get("application"), j["title"], f"j_{j['id']}"):
        return
    if j.get("deadline") and j["deadline"] < date.today().isoformat():
        st.markdown("<span class='app-state mute'>Đã hết hạn nộp</span>", unsafe_allow_html=True)
    elif st.button("Ứng tuyển", key=f"apply_{j['id']}", type="primary", width="stretch"):
        apply_dialog(j)


@st.fragment
def job_list_tab(meta: dict, max_pick: int):
    ids = st.session_state.setdefault("compare_ids", [])
    jobs = job_list.search(meta, "candidate_jobs", "/jobs")
    st.markdown(f"Đã chọn **{len(ids)}/{max_pick}** vị trí để so sánh.")

    for j in jobs:
        picked = j["id"] in ids
        full = not picked and len(ids) >= max_pick
        with st.container(border=True):
            c0, c1, c2 = st.columns([0.5, 7, 2], vertical_alignment="center")
            c0.checkbox("Chọn để so sánh", value=picked, key=f"sel_{j['id']}", label_visibility="collapsed",
                        on_change=_on_pick, args=(j["id"],), disabled=full,
                        help=f"Đã chọn tối đa {max_pick} vị trí" if full else None)
            with c1:
                job_list.title_link(j, f"title_{j['id']}")
                st.markdown(styles.job_meta(j), unsafe_allow_html=True)
                st.markdown(helpers.open_period_html(j), unsafe_allow_html=True)
            with c2:
                _apply_state(j)


def _compare_tab(max_pick: int):
    ids = st.session_state.get("compare_ids", [])
    if not ids:
        st.info("Bạn chưa chọn công việc nào. Quay lại tab Danh sách và tick chọn tối đa "
                f"{max_pick} vị trí để AI xếp hạng mức độ phù hợp với CV của bạn.")
        return

    by_id = {j["id"]: j for j in api.get("/jobs", cache=True)}
    chosen = [by_id[i] for i in ids if i in by_id]
    if len(chosen) != len(ids):  # có tin đã đóng hoặc bị xóa
        st.session_state["compare_ids"] = [j["id"] for j in chosen]
        st.rerun()

    st.markdown(f"##### Công việc đã chọn ({len(chosen)}/{max_pick})")
    for j in chosen:
        with st.container(border=True):
            c1, c2 = st.columns([8, 2], vertical_alignment="center")
            with c1:
                job_list.title_link(j, f"cmp_title_{j['id']}")
                st.markdown(styles.job_meta(j), unsafe_allow_html=True)
            c2.button("Bỏ chọn", key=f"unpick_{j['id']}", width="stretch", on_click=_on_unpick, args=(j["id"],))

    if st.button("Đánh giá mức độ phù hợp", type="primary"):
        try:
            with st.spinner("AI đang đối chiếu CV với từng công việc…"):
                st.session_state["rank_results"] = api.post("/matching/jobs", json={"job_ids": ids})
        except api.ApiError as e:
            st.session_state.pop("rank_results", None)
            st.error(str(e))

    if st.session_state.get("rank_results"):
        st.markdown("##### Kết quả xếp hạng")
        for i, r in enumerate(st.session_state["rank_results"], 1):
            _rank_card(i, r)


def jobs_page():
    st.title("Việc làm")
    meta = api.get("/jobs/meta", cache=True)
    max_pick = meta["limits"]["max_compare"]
    labels = {"list": "Danh sách việc làm", "compare": "So sánh"}
    with st.container(key="subtabs"):
        tab = st.radio("Mục", list(labels), format_func=labels.get, horizontal=True,
                       label_visibility="collapsed", key="jobs_tab")
    if tab == "compare":
        _compare_tab(max_pick)
    else:
        job_list_tab(meta, max_pick)


# ---------------------------------------------------------------- Đã ứng tuyển
def applications_page():
    st.title("Đã ứng tuyển")
    data = api.get("/applications/mine")
    st.caption(f"Đang ứng tuyển {data['active']}/{data['limit']} công việc. Rút đơn đang chờ duyệt để có thêm lượt. "
               "Bấm vào tên công việc để xem thông tin và CV bạn đã nộp.")
    if not data["items"]:
        st.info("Bạn chưa nộp đơn nào. Vào mục Việc làm để bắt đầu.")
    for a in data["items"]:
        with st.container(border=True):
            c1, c2 = st.columns([7, 2], vertical_alignment="center")
            with c1:
                if st.button(a["job"]["title"], key=f"app_title_{a['id']}", type="tertiary"):
                    application_dialog(a)
                st.markdown(styles.job_meta(a["job"]), unsafe_allow_html=True)
                st.markdown(f"<div class='jm'><span>Nộp ngày {helpers.fmt_date(a['applied_at'])}</span></div>",
                            unsafe_allow_html=True)
            with c2:
                _app_state({"id": a["id"], "status": a["status"]}, a["job"]["title"], f"a_{a['id']}")


# ---------------------------------------------------------------- CV
def cv_page():
    st.title("CV của tôi")
    st.caption("CV chung được dùng mặc định khi xếp hạng công việc. Khi ứng tuyển, bạn có thể tùy chỉnh CV riêng cho từng vị trí.")
    cv = api.get("/candidates/me/cv")
    cv_ui.cv_editor("cv_general", cv, lambda p: api.put("/candidates/me/cv", json=p), ai_import=True)


def notifications_page():
    notifications.render("Chưa có thông báo. Bạn sẽ nhận tin ở đây khi nhà tuyển dụng gửi kết quả hồ sơ.")


ROUTES = {"Việc làm": jobs_page, "Đã ứng tuyển": applications_page, "CV của tôi": cv_page,
          "Thông báo": notifications_page}