import streamlit as st

import api_client as api
import helpers
import styles
from components import job_list


def render():
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
    for j in job_list.search(meta, "public_jobs", "/jobs/public"):
        with st.container(border=True):
            info, action = st.columns([8, 2], vertical_alignment="center")
            with info:
                job_list.title_link(j, f"title_{j['id']}")
                st.markdown(styles.job_meta(j), unsafe_allow_html=True)
                st.markdown(helpers.open_period_html(j), unsafe_allow_html=True)
            with action:
                if st.button("Ứng tuyển", key=f"public_apply_{j['id']}", type="primary", width="stretch"):
                    st.session_state["page"] = "Đăng ký"
                    st.rerun()
