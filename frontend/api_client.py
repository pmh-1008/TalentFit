import json
import os

import requests
import streamlit as st

# Dùng 127.0.0.1 thay vì localhost: trên Windows, localhost thử IPv6 trước nên mỗi lần gọi mất thêm ~1 giây
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

# Một Session dùng chung giữ kết nối mở (keep-alive), không bắt tay TCP lại ở mỗi request
_SESSION = requests.Session()
_SESSION.mount("http://", requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=32))
_SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=32))


class ApiError(Exception):
    pass


class _HttpFail(Exception):
    def __init__(self, status: int, detail):
        self.status, self.detail = status, detail


def _call(method: str, path: str, token: str | None, timeout: int, **kwargs):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        resp = _SESSION.request(method, f"{API_URL}{path}", headers=headers, timeout=timeout, **kwargs)
    except requests.RequestException:
        raise ApiError(f"Không kết nối được máy chủ API ({API_URL}). Hãy kiểm tra backend đã chạy chưa.")
    if not resp.ok:
        try:
            detail = resp.json().get("detail")
        except ValueError:
            detail = None
        raise _HttpFail(resp.status_code, detail)
    return resp.json()


@st.cache_data(ttl=30, show_spinner=False)
def _cached_get(token: str | None, path: str, params_json: str):
    """GET được cache theo từng người dùng. Lỗi không bị cache."""
    return _call("GET", path, token, 60, params=json.loads(params_json) or None)


def request(method: str, path: str, timeout: int = 180, cache: bool = False, **kwargs):
    """cache=True chỉ dành cho GET dữ liệu ít đổi; mọi thao tác ghi (POST/PUT/DELETE) sẽ xóa cache."""
    token = st.session_state.get("token")
    try:
        if cache and method == "GET":
            return _cached_get(token, path, json.dumps(kwargs.get("params") or {}, sort_keys=True, default=str))
        out = _call(method, path, token, timeout, **kwargs)
    except _HttpFail as e:
        if e.status == 401 and token:
            st.session_state.clear()
            st.session_state["flash"] = [("Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.", "warning")]
            st.rerun()
        detail = e.detail
        if isinstance(detail, list):
            detail = "Dữ liệu nhập chưa hợp lệ, vui lòng kiểm tra lại các trường."
        raise ApiError(detail or f"Lỗi máy chủ ({e.status})")
    if method != "GET":
        _cached_get.clear()
    return out


def get(path, **kw):
    return request("GET", path, **kw)


def post(path, **kw):
    return request("POST", path, **kw)


def put(path, **kw):
    return request("PUT", path, **kw)


def delete(path, **kw):
    return request("DELETE", path, **kw)
