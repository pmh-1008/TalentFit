import streamlit as st

import api_client as api
import helpers


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
                helpers.flash("Đã cập nhật thông tin")
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
                    helpers.flash("Đã cập nhật thông tin công ty")
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
                    helpers.flash("Đã đổi mật khẩu")
                    st.rerun()
                except api.ApiError as e:
                    st.error(str(e))
