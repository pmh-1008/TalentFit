import streamlit as st

import api_client as api
import helpers
import styles


def render(empty_text: str = "Chưa có thông báo."):
    st.title("Thông báo")
    data = api.get("/notifications")
    if data["unread"] and st.button("Đánh dấu tất cả đã đọc"):
        api.post("/notifications/read-all")
        st.rerun()
    if not data["items"]:
        st.info(empty_text)
    for n in data["items"]:
        with st.container(border=True):
            cls = "unread" if not n["is_read"] else ""
            st.markdown(f"<div class='{cls}'><div class='jt'>{styles.esc(n['title'])}</div>"
                        f"<div class='note' style='border:0;padding:0'>{styles.esc(n['message'])}</div></div>",
                        unsafe_allow_html=True)
            st.caption(helpers.fmt_date(n["created_at"]) + " " + n["created_at"][11:16])
            if not n["is_read"] and st.button("Đánh dấu đã đọc", key=f"read_{n['id']}"):
                api.post(f"/notifications/{n['id']}/read")
                st.rerun()
