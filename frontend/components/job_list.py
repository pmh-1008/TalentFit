"""Thanh lọc, tải danh sách tin và liên kết mở chi tiết, dùng chung cho trang khách và trang ứng viên."""
import streamlit as st

import api_client as api
from components import job as job_ui


@st.dialog("Thông tin công việc", width="large")
def job_dialog(j: dict):
    job_ui.job_detail(j)


def title_link(j: dict, key: str):
    """Tên công việc dạng liên kết, bấm vào để mở pop-up thông tin."""
    if st.button(j["title"], key=key, type="tertiary"):
        job_dialog(j)


def search(meta: dict, key_prefix: str, endpoint: str) -> list[dict]:
    """Vẽ bộ lọc và trả về các tin phù hợp. `key_prefix` giữ trạng thái bộ lọc tách riêng giữa các trang."""
    f1, f2, f3, f4 = st.columns([3, 2, 2, 2])
    q = f1.text_input("Tìm kiếm", placeholder="Tên chức danh", label_visibility="collapsed",
                      key=f"{key_prefix}_search")
    loc = f2.selectbox("Địa điểm", ["Tất cả địa điểm"] + meta["locations"], label_visibility="collapsed",
                       key=f"{key_prefix}_location")
    typ = f3.selectbox("Loại hình", ["Tất cả loại hình"] + meta["job_types"], label_visibility="collapsed",
                       key=f"{key_prefix}_type")
    comp = f4.selectbox("Công ty", [("", "Tất cả công ty")] + [(c["id"], c["name"]) for c in meta["companies"]],
                        format_func=lambda x: x[1], label_visibility="collapsed", key=f"{key_prefix}_company")

    jobs = api.get(endpoint, cache=True, params={
        "q": q, "location": "" if loc.startswith("Tất cả") else loc,
        "job_type": "" if typ.startswith("Tất cả") else typ, "company_id": comp[0]})
    if not jobs:
        st.info("Không có công việc phù hợp với bộ lọc hiện tại.")
    return jobs
