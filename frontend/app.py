import streamlit as st

import api_client as api
import styles
import helpers
from views import account, auth_view, candidate, home, recruiter

st.set_page_config(page_title="TalentFit", page_icon="◆", layout="wide", initial_sidebar_state="collapsed")
styles.inject()

EXTRA_PAGES = ("profile", "password")  # mở từ menu tên tài khoản, không nằm trên thanh điều hướng
PUBLIC_PAGES = ("Trang chủ", "Đăng nhập", "Đăng ký")


def _goto(page: str):
    st.session_state["page"] = page
    st.session_state["menu_n"] = st.session_state.get("menu_n", 0) + 1  # đổi key popover để menu tự đóng


def _logout():
    st.session_state.clear()


def topbar(user: dict | None, pages: list[str]) -> str:
    if user is None:
        page = st.session_state.get("page", "Trang chủ")
        if page not in PUBLIC_PAGES:
            page = st.session_state["page"] = "Trang chủ"

        with st.container(key="topbar"):
            c_brand, _, c_user = st.columns([2, 6, 4], vertical_alignment="center")
            c_brand.markdown("<div class='brand'><i></i>TalentFit</div>", unsafe_allow_html=True)
            with c_user:
                with st.container(key="usertools", horizontal=True, horizontal_alignment="right",
                                  gap="small", vertical_alignment="center"):
                    st.button("Đăng nhập", key="guest_login", on_click=_goto, args=("Đăng nhập",))
                    st.button("Đăng ký", key="guest_register", type="primary",
                              on_click=_goto, args=("Đăng ký",))
        return page

    has_bell = "Thông báo" in pages
    nav_pages = [p for p in pages if p != "Thông báo"]  # thông báo chuyển thành nút chuông bên phải
    unread = 0
    if has_bell:
        try:
            unread = api.get("/notifications/unread-count", cache=True)["unread"]
        except api.ApiError as e:
            st.warning(f"Không tải được thông báo: {e}")
    page = st.session_state.get("page")
    if page not in pages and page not in EXTRA_PAGES:
        page = st.session_state["page"] = pages[0]

    with st.container(key="topbar"):
        c_brand, c_nav, c_user = st.columns([2, 7, 3], vertical_alignment="center")
        c_brand.markdown("<div class='brand'><i></i>TalentFit</div>", unsafe_allow_html=True)
        with c_nav:
            with st.container(key="topnav", horizontal=True, gap="small"):
                for p in nav_pages:
                    st.button(p, key=f"nav_{p}", type="primary" if p == page else "secondary",
                              on_click=_goto, args=(p,))
        with c_user:
            with st.container(key="usertools", horizontal=True, horizontal_alignment="right", gap="small", vertical_alignment="center"):
                if has_bell:
                    st.button("", icon=":material/notifications:", key="bell_unread" if unread else "bell",
                              type="primary" if page == "Thông báo" else "secondary",
                              help=f"Thông báo ({unread} chưa đọc)" if unread else "Thông báo",
                              on_click=_goto, args=("Thông báo",))
                with st.container(key="usermenu", width=35):
                    with st.popover("", icon=":material/account_circle:",
                                    key=f"usermenu_pop_{st.session_state.get('menu_n', 0)}", width=35):
                        with st.container(key="menu_items"):
                            st.button("Thông tin cá nhân", icon=":material/person:", type="tertiary", width="stretch",
                                      key="menu_profile", on_click=_goto, args=("profile",))
                            st.button("Đổi mật khẩu", icon=":material/lock:", type="tertiary", width="stretch",
                                      key="menu_password", on_click=_goto, args=("password",))
                            st.button("Đăng xuất", icon=":material/logout:", type="tertiary", width="stretch",
                                      key="menu_logout", on_click=_logout)
    return page


def main():
    user = st.session_state.get("user")
    if not user or not st.session_state.get("token"):
        page = st.session_state.get("page", "Trang chủ")
        if page not in PUBLIC_PAGES:
            page = st.session_state["page"] = "Trang chủ"
        if page == "Trang chủ":
            page = topbar(None, [])
        helpers.show_flash()
        try:
            if page == "Trang chủ":
                home.render()
            else:
                auth_view.render(default_tab=page)
        except api.ApiError as e:
            st.error(str(e))
        return

    module = candidate if user["role"] == "candidate" else recruiter
    page = topbar(user, module.PAGES)
    helpers.show_flash()
    try:
        if page == "profile":
            account.profile_page(user)
        elif page == "password":
            account.password_page()
        else:
            module.ROUTES[page]()
    except api.ApiError as e:
        st.error(str(e))


main()