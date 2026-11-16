# TalentFit: hệ thống tuyển dụng với AI matching

Đồ án môn Lập trình Python và Cơ sở dữ liệu (MySQL).

| Thành phần | Công nghệ |
|---|---|
| Front-end | Streamlit |
| Back-end | FastAPI + SQLAlchemy 2 |
| CSDL | MySQL 8 (JSON column cho CV và yêu cầu công việc) |
| AI | Gemini (`google-genai`), chấm điểm bằng LLM, không có thuật toán matching thủ công |

## Cấu trúc thư mục

```
recruitment_ai/
├── backend/
│   ├── main.py                # khởi tạo FastAPI, bắt lỗi LLM
│   ├── config.py database.py models.py schemas.py security.py deps.py utils.py
│   ├── routers/               # auth, company, candidates, jobs, applications, matching, notifications, ai
│   └── services/
│       ├── llm.py             # gọi Gemini: CV|JD -> JSON, chấm điểm theo tiêu chí
│       └── matching.py        # chấm điểm song song, cache kết quả theo hash(JD, CV)
├── frontend/
│   ├── app.py                 # điểm vào Streamlit, điều hướng theo vai trò
│   ├── api_client.py styles.py
│   └── views/                 # auth_view, candidate, recruiter, common
├── database/schema.sql        # DDL MySQL (backend cũng tự tạo bảng khi khởi động)
├── .streamlit/config.toml     # theme sáng cho giao diện
├── seed.py                    # sinh dữ liệu mẫu bằng Gemini, thay dữ liệu local
├── requirements.txt
└── .env.example
```

## Cài đặt và chạy (Windows PowerShell)

Yêu cầu: Python 3.10 trở lên và MySQL 8 đã cài, dịch vụ MySQL đang chạy. Mở PowerShell tại thư mục gốc `recruitment_ai`.

**1. Tạo môi trường ảo và cài thư viện**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Nếu PowerShell báo lỗi "running scripts is disabled", chạy lệnh sau một lần rồi kích hoạt lại:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

**2. Tạo database MySQL**

PowerShell không hỗ trợ toán tử `<`, nên dùng lệnh `source`:

```powershell
mysql -u root -p -e "source database/schema.sql"
```

Nếu báo không tìm thấy `mysql`, dùng đường dẫn đầy đủ, ví dụ:
`& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p -e "source database/schema.sql"`.
Hoặc mở MySQL Workbench, mở file `database/schema.sql` và bấm chạy. Bước này có thể bỏ qua vì backend cũng tự tạo bảng khi khởi động, nhưng database `recruitment_ai` vẫn cần tồn tại.

**3. Cấu hình `.env`**

```powershell
Copy-Item .env.example .env
notepad .env
```

Điền `DATABASE_URL` (mật khẩu MySQL của bạn) và `GEMINI_API_KEY`. Nếu mật khẩu có ký tự đặc biệt như `@` hoặc `#`, hãy mã hóa URL (ví dụ `@` thành `%40`).

**4. Chạy hệ thống (mở 3 cửa sổ PowerShell, mỗi cửa sổ đều kích hoạt `.venv` trước)**

```powershell
# Cửa sổ 1: backend
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --port 8000

# Cửa sổ 2: giao diện
.\.venv\Scripts\Activate.ps1
streamlit run frontend/app.py

# Cửa sổ 3: tạo lại dữ liệu mẫu (cần DATABASE_URL local và GEMINI_API_KEY trong .env)
.\.venv\Scripts\Activate.ps1
python seed.py --replace
```

Giao diện: http://localhost:8501, tài liệu API: http://localhost:8000/docs.

`seed.py --replace` gọi Gemini để tạo 3 công ty, 15 công việc và 45 hồ sơ ứng viên, sau đó thay toàn bộ dữ liệu trong các bảng ứng dụng của database local. Dữ liệu chỉ bị xóa sau khi dữ liệu mới được tạo và kiểm tra hợp lệ. Hồ sơ được thiết kế để hướng tới dải fit cao và trung bình; điểm AI thực tế chỉ được tính khi chạy chức năng chấm điểm trong ứng dụng.

**Lỗi thường gặp**

* `Access denied for user 'root'`: sai mật khẩu trong `DATABASE_URL`.
* `Unknown database 'recruitment_ai'`: chưa chạy bước 2.
* `Chưa cấu hình GEMINI_API_KEY`: thêm khóa Gemini vào `.env`.
* `seed.py only supports a local database`: seed từ chối xóa dữ liệu trên database không phải local.

## Tài khoản mẫu (mật khẩu `123456`)

* Nhà tuyển dụng: `hr01@example.test`, `hr02@example.test`, `hr03@example.test`
* Ứng viên: `cand001@example.test` đến `cand045@example.test` (mỗi nhóm 15 ứng viên thuộc một công ty)

## Quy tắc nghiệp vụ

* Ứng viên chọn tối đa 5 công việc mỗi lần xếp hạng; ứng tuyển tối đa 20 công việc cùng lúc (đơn đang chờ duyệt hoặc đã duyệt).
* `overall_fit = 40% skill_match + 40% experience_match + 20% education_match`. Ba điểm thành phần và lời giải thích do LLM trả về.
* Kết quả chấm điểm được lưu ở bảng `match_results` theo hash nội dung JD và CV, nên cùng một cặp không bị gọi LLM lần hai.
* Thiếu `GEMINI_API_KEY`, hết quota hoặc LLM lỗi: API trả lỗi rõ ràng và giao diện hiển thị lỗi, không có điểm dự phòng.
* Khi nộp đơn, hệ thống lưu bản chụp CV (CV tùy chỉnh theo job nếu có, nếu không dùng CV chung).
* Duyệt hồ sơ tự tạo thông báo cho ứng viên; nhà tuyển dụng cũng có thể gửi thông báo tới các ứng viên đã duyệt.

## Mô hình dữ liệu

`companies` 1-n `users` (HR) và `jobs`; `users` (ứng viên) 1-1 `candidate_profiles`, 1-n `custom_cvs`;
`applications` nối `jobs` với ứng viên (kèm `cv_data`, `status`); `match_results` lưu điểm LLM; `notifications` gửi tới `users`.
