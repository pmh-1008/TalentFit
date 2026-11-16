from datetime import date

import streamlit as st

import api_client as api
import styles
from views import common

PAGES = ["Việc làm", "Đã ứng tuyển", "CV của tôi", "Thông báo"]


# ---------------------------------------------------------------- pop-up
@st.dialog("Thông tin công việc", width="large")
def job_dialog(j: dict):
    common.job_detail(j)


@st.dialog("Tùy chỉnh CV để ứng tuyển", width="large")
def apply_dialog(j: dict):
    st.markdown(f"Vị trí: **{styles.esc(j['title'])}** tại {styles.esc(j['company'])}")
    st.caption("CV bên dưới lấy từ CV chung của bạn. Hãy chỉnh cho phù hợp với vị trí này: "
               "bản tùy chỉnh chỉ dùng cho đơn ứng tuyển vào công việc này.")
    data = api.get(f"/candidates/me/cv/job/{j['id']}")

    def submit(payload):
        api.put(f"/candidates/me/cv/job/{j['id']}", json=payload)
        api.post("/applications", json={"job_id": j["id"]})

    common.cv_editor(f"cv_apply_{j['id']}", data["cv"], submit, save_label="Lưu CV và ứng tuyển",
                     done_msg=f"Đã nộp đơn vào {j['title']}")


@st.dialog("Đơn ứng tuyển", width="large")
def application_dialog(a: dict):
    decided = "" if a["status"] == "pending" else styles.status_badge(a["status"])
    st.markdown(f"Nộp ngày {common.fmt_date(a['applied_at'])} {decided}", unsafe_allow_html=True)
    t_job, t_cv = st.tabs(["Thông tin công việc", "CV đã nộp"])
    with t_job:
        common.job_detail(a["job"])
    with t_cv:
        st.caption("Đây là CV tại thời điểm bạn nộp đơn.")
        common.render_cv(a.get("cv") or {})


def _title_link(j: dict, key: str):
    """Tên công việc dạng liên kết, bấm vào để mở pop-up thông tin."""
    if st.button(j["title"], key=key, type="tertiary"):
        job_dialog(j)


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
            c_rank, c_job = st.columns([1, 11], vertical_alignment="center")
            c_rank.markdown(f"<span class='rank'>{i}</span>", unsafe_allow_html=True)
            with c_job:
                _title_link(j, f"rank_title_{j['id']}")
                st.markdown(styles.job_meta(j), unsafe_allow_html=True)
        b.markdown(styles.overall_html(r["overall_fit"]), unsafe_allow_html=True)
        st.markdown(styles.score_bars(r), unsafe_allow_html=True)
        cv_label = "CV tùy chỉnh cho công việc này" if r["cv_type"] == "custom" else "CV chung"
        with st.container(key=f"rank_expl_{j['id']}"):
            with st.expander(f"Nhận xét chi tiết", expanded=(i == 1)):
                st.markdown(styles.explanation_html(r), unsafe_allow_html=True)


def _app_state(app: dict | None, title: str, key: str) -> bool:
    """Nút Rút đơn (chờ duyệt) / nhãn Đã duyệt / Không được duyệt. Trả về False nếu chưa có đơn."""
    if not app:
        return False
    if app["status"] == "pending":
        if st.button("Rút đơn", key=f"jobwd_{key}", width="stretch"):
            try:
                api.delete(f"/applications/{app['id']}")
                common.flash(f"Đã rút đơn ứng tuyển {title}")
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
def _job_list_tab(meta: dict, max_pick: int, public: bool = False):
    ids = [] if public else st.session_state.setdefault("compare_ids", [])
    key_prefix = "public_jobs" if public else "candidate_jobs"
    f1, f2, f3, f4 = st.columns([3, 2, 2, 2])
    q = f1.text_input("Tìm kiếm", placeholder="Tên chức danh", label_visibility="collapsed",
                      key=f"{key_prefix}_search")
    loc = f2.selectbox("Địa điểm", ["Tất cả địa điểm"] + meta["locations"], label_visibility="collapsed",
                       key=f"{key_prefix}_location")
    typ = f3.selectbox("Loại hình", ["Tất cả loại hình"] + meta["job_types"], label_visibility="collapsed",
                       key=f"{key_prefix}_type")
    comp = f4.selectbox("Công ty", [("", "Tất cả công ty")] + [(c["id"], c["name"]) for c in meta["companies"]],
                        format_func=lambda x: x[1], label_visibility="collapsed", key=f"{key_prefix}_company")

    jobs = api.get("/jobs/public" if public else "/jobs", cache=True, params={
        "q": q, "location": "" if loc.startswith("Tất cả") else loc,
        "job_type": "" if typ.startswith("Tất cả") else typ, "company_id": comp[0]})

    if not public:
        st.markdown(f"Đã chọn **{len(ids)}/{max_pick}** vị trí để so sánh.")

    if not jobs:
        st.info("Không có công việc phù hợp với bộ lọc hiện tại.")

    for j in jobs:
        picked = j["id"] in ids
        with st.container(border=True):
            if public:
                c1, c2 = st.columns([8, 2], vertical_alignment="center")
            else:
                c0, c1, c2 = st.columns([0.5, 7, 2], vertical_alignment="center")
                c0.checkbox("Chọn để so sánh", value=picked, key=f"sel_{j['id']}", label_visibility="collapsed",
                            on_change=_on_pick, args=(j["id"],), disabled=(not picked and len(ids) >= max_pick),
                            help=f"Đã chọn tối đa {max_pick} vị trí" if (not picked and len(ids) >= max_pick) else None)
            with c1:
                _title_link(j, f"title_{j['id']}")
                st.markdown(styles.job_meta(j), unsafe_allow_html=True)
                st.markdown(common.open_period_html(j), unsafe_allow_html=True)
            with c2:
                if public:
                    if st.button("Ứng tuyển", key=f"public_apply_{j['id']}", type="primary", width="stretch"):
                        st.session_state["page"] = "Đăng ký"
                        st.rerun()
                else:
                    _apply_state(j)


def public_home_page():
    st.title("Tìm công việc phù hợp với bạn")
    st.write(
        "TalentFit kết nối ứng viên với cơ hội nghề nghiệp và hỗ trợ nhà tuyển dụng "
        "đánh giá hồ sơ bằng AI."
    )

    feature_columns = st.columns(3)
    features = [
        ("Khám phá việc làm", "Tìm kiếm tin tuyển dụng theo chức danh, địa điểm, loại hình và công ty."),
        ("Hồ sơ ứng viên", "Tạo CV và dùng hồ sơ của bạn để ứng tuyển vào công việc phù hợp."),
        ("AI matching", "Đối chiếu kỹ năng, kinh nghiệm và học vấn để xếp hạng mức độ phù hợp."),
    ]
    for column, (title, description) in zip(feature_columns, features):
        with column:
            with st.container(border=True):
                st.markdown(f"#### {title}")
                st.write(description)

    st.divider()
    st.markdown("### Việc làm đang tuyển")
    meta = api.get("/jobs/meta", cache=True)
    _job_list_tab(meta, max_pick=0, public=True)


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
                _title_link(j, f"cmp_title_{j['id']}")
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
        _job_list_tab(meta, max_pick)


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
                st.markdown(f"<div class='jm'><span>Nộp ngày {common.fmt_date(a['applied_at'])}</span></div>",
                            unsafe_allow_html=True)
            with c2:
                _app_state({"id": a["id"], "status": a["status"]}, a["job"]["title"], f"a_{a['id']}")


# ---------------------------------------------------------------- CV
def cv_page():
    st.title("CV của tôi")
    st.caption("CV chung được dùng mặc định khi xếp hạng công việc. Khi ứng tuyển, bạn có thể tùy chỉnh CV riêng cho từng vị trí.")
    cv = api.get("/candidates/me/cv")
    common.cv_editor("cv_general", cv, lambda p: api.put("/candidates/me/cv", json=p), ai_import=True)


# ---------------------------------------------------------------- Thông báo
def notifications_page():
    st.title("Thông báo")
    data = api.get("/notifications")
    if data["unread"] and st.button("Đánh dấu tất cả đã đọc"):
        api.post("/notifications/read-all")
        st.rerun()
    if not data["items"]:
        st.info("Chưa có thông báo. Bạn sẽ nhận tin ở đây khi nhà tuyển dụng duyệt hồ sơ.")
    for n in data["items"]:
        with st.container(border=True):
            cls = "unread" if not n["is_read"] else ""
            st.markdown(f"<div class='{cls}'><div class='jt'>{styles.esc(n['title'])}</div>"
                        f"<div class='note' style='border:0;padding:0'>{styles.esc(n['message'])}</div></div>",
                        unsafe_allow_html=True)
            st.caption(common.fmt_date(n["created_at"]) + " " + n["created_at"][11:16])
            if not n["is_read"] and st.button("Đánh dấu đã đọc", key=f"read_{n['id']}"):
                api.post(f"/notifications/{n['id']}/read")
                st.rerun()


ROUTES = {"Việc làm": jobs_page, "Đã ứng tuyển": applications_page, "CV của tôi": cv_page,
          "Thông báo": notifications_page}