import streamlit as st

import api_client as api


def _login_success(data: dict):
    st.session_state["token"] = data["access_token"]
    st.session_state["user"] = data["user"]
    st.rerun()


def render(default_tab: str = "Đăng nhập"):
    _, mid, _ = st.columns([1, 1.5, 1])
    with mid:
        st.markdown("<div class='auth-brand'><i></i>TalentFit</div>", unsafe_allow_html=True)
        with st.container(border=True):
            tab_login, tab_reg = st.tabs(
                ["Đăng nhập", "Đăng ký"],
                default=default_tab,
                key=f"auth_tabs_{'register' if default_tab == 'Đăng ký' else 'login'}",
            )

            with tab_login:
                with st.form("login"):
                    email = st.text_input("Email")
                    password = st.text_input("Mật khẩu", type="password")
                    if st.form_submit_button("Đăng nhập", type="primary", width="stretch"):
                        try:
                            _login_success(api.post("/auth/login", json={"email": email, "password": password}))
                        except api.ApiError as e:
                            st.error(str(e))

            with tab_reg:
                role = st.radio("Bạn đăng ký với tư cách", ["Ứng viên", "Công ty"], horizontal=True, key="reg_role")
                if role == "Ứng viên":
                    with st.form("reg_cand"):
                        name = st.text_input("Họ và tên")
                        email = st.text_input("Email", key="rc_email")
                        phone = st.text_input("Số điện thoại", key="rc_phone")
                        pw = st.text_input("Mật khẩu (tối thiểu 6 ký tự)", type="password", key="rc_pw")
                        if st.form_submit_button("Đăng ký", type="primary", width="stretch"):
                            try:
                                _login_success(api.post("/auth/register/candidate", json={
                                    "email": email, "password": pw, "full_name": name, "phone": phone}))
                            except api.ApiError as e:
                                st.error(str(e))
                else:
                    with st.form("reg_comp"):
                        company = st.text_input("Tên công ty")
                        industry = st.text_input("Lĩnh vực")
                        email = st.text_input("Email tài khoản HR", key="rp_email")
                        pw = st.text_input("Mật khẩu (tối thiểu 6 ký tự)", type="password", key="rp_pw")
                        if st.form_submit_button("Đăng ký", type="primary", width="stretch"):
                            try:
                                _login_success(api.post("/auth/register/company", json={
                                    "company_name": company, "industry": industry, "email": email, "password": pw}))
                            except api.ApiError as e:
                                st.error(str(e))
