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
TalentFit/
├── backend/
│   ├── main.py                # khởi tạo FastAPI, CORS, bắt lỗi LLM và lỗi nghiệp vụ
│   ├── config.py database.py models.py schemas.py security.py deps.py
│   ├── constants.py errors.py # hằng số dùng chung (loại hình công việc), BusinessError
│   ├── serializers.py         # model -> dict trả về cho API
│   ├── migrate.py             # chạy `alembic upgrade head` mỗi lần backend khởi động
│   ├── routers/               # auth, company, candidates, jobs, applications, matching, notifications, ai (mỏng, chỉ gọi service)
│   └── services/
│       ├── llm.py             # gọi Gemini: CV|JD -> JSON, chấm điểm theo tiêu chí
│       ├── matching.py        # chấm điểm song song, cache kết quả theo hash(JD, CV)
│       ├── applications.py    # ứng tuyển, giới hạn lượt, lưu nháp và chốt kết quả
│       ├── job_lifecycle.py   # trạng thái hiển thị, đóng tin hết hạn, xóa tin
│       └── cv.py              # CV chung, CV theo job, CV hiệu lực
├── frontend/
│   ├── app.py                 # điểm vào Streamlit, điều hướng theo vai trò
│   ├── api_client.py helpers.py styles.py
│   ├── static/style.css
│   ├── components/            # cv (biểu mẫu + hiển thị CV), job (biểu mẫu + chi tiết tin)
│   └── views/                 # home, auth_view, candidate, recruiter, account, notifications
├── migrations/                # Alembic: 0001 baseline, 0002 toàn vẹn dữ liệu, 0003 CV, 0004 JD
├── alembic.ini
├── database/schema.sql        # DDL MySQL, sinh bằng `python -m scripts.export_schema`
├── scripts/
│   ├── export_schema.py       # sinh lại database/schema.sql từ models + migration
│   └── seed.py                # sinh dữ liệu mẫu bằng Gemini, thay dữ liệu local
├── requirements.txt
├── .streamlit/config.toml
└── .env.example
```

## Cài đặt và chạy (Windows PowerShell)

Yêu cầu: Python 3.10 trở lên và MySQL 8.0.17 trở lên đã cài, dịch vụ MySQL đang chạy. Mở PowerShell tại thư mục gốc của dự án.

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
Hoặc mở MySQL Workbench, mở file `database/schema.sql` và bấm chạy. Bước này có thể bỏ qua vì backend tự tạo/nâng cấp bảng bằng Alembic khi khởi động, nhưng database `recruitment_ai` vẫn cần tồn tại. `schema.sql` đã đánh dấu phiên bản migration mới nhất nên import xong backend sẽ không chạy lại migration.

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
python -m scripts.seed --replace
```

Giao diện: http://localhost:8501, tài liệu API: http://localhost:8000/docs.

`python -m scripts.seed --replace` gọi Gemini để tạo 3 công ty, 15 công việc và 45 hồ sơ ứng viên, sau đó thay toàn bộ dữ liệu trong các bảng ứng dụng của database local. Dữ liệu chỉ bị xóa sau khi dữ liệu mới được tạo và kiểm tra hợp lệ. Nếu một lần gọi Gemini lỗi (API hoặc dữ liệu không hợp lệ), seed tự thử lại; chỉ khi thất bại 10 lần liên tiếp mới dừng và báo không tạo được dữ liệu. Hồ sơ được thiết kế để hướng tới dải fit cao và trung bình; điểm AI thực tế chỉ được tính khi chạy chức năng chấm điểm trong ứng dụng.

**Migration (Alembic):** khi sửa `backend/models.py`, tạo migration mới rồi sinh lại schema:

```powershell
alembic revision --autogenerate -m "mo ta thay doi"
alembic upgrade head
python -m scripts.export_schema
```

Sau khi cập nhật migration hoặc models, chạy lại `python -m scripts.export_schema` để đồng bộ schema. Ràng buộc JSON cho CV dùng `JSON_SCHEMA_VALID` (MySQL 8.0.17 trở lên); các ràng buộc CHECK (role, status) cần MySQL từ 8.0.16.

**Lỗi thường gặp**

* `Access denied for user 'root'`: sai mật khẩu trong `DATABASE_URL`.
* `Unknown database 'recruitment_ai'`: chưa chạy bước 2.
* `Chưa cấu hình GEMINI_API_KEY`: thêm khóa Gemini vào `.env`.
* `scripts/seed.py only supports a local database`: seed từ chối xóa dữ liệu trên database không phải local.

## Tài khoản mẫu (mật khẩu `123456`)

* Nhà tuyển dụng: `hr01@example.test`, `hr02@example.test`, `hr03@example.test`
* Ứng viên: `cand001@example.test` đến `cand045@example.test` (mỗi nhóm 15 ứng viên thuộc một công ty)

## Quy tắc nghiệp vụ

* JD bắt buộc có chức danh, mô tả công việc và yêu cầu đối với ứng viên.
* CV bắt buộc có ít nhất một kỹ năng; mỗi mục học vấn cần bằng cấp, trường và năm; mỗi kinh nghiệm cần vị trí, công ty và số tháng; chứng chỉ/giải thưởng nếu có cần tên và năm.
* Ứng viên chọn tối đa 5 công việc mỗi lần xếp hạng; ứng tuyển tối đa 20 công việc cùng lúc (đơn chờ duyệt hoặc đã duyệt, chỉ tính các tin còn mở; đơn của tin đã đóng không chiếm lượt).
* `overall_fit = 40% skill_match + 40% experience_match + 20% education_match`. Ba điểm thành phần và lời giải thích do LLM trả về.
* Kết quả chấm điểm được lưu ở bảng `match_results` theo hash nội dung JD và CV, nên cùng một cặp không bị gọi LLM lần hai.
* Thiếu `GEMINI_API_KEY`, hết quota hoặc LLM lỗi: API trả lỗi rõ ràng và giao diện hiển thị lỗi, không có điểm dự phòng.
* Khi nộp đơn, hệ thống lưu bản chụp CV (CV tùy chỉnh theo job nếu có, nếu không dùng CV chung).
* Nhà tuyển dụng chọn duyệt/từ chối cho từng hồ sơ, có thể lưu nháp. Bấm "Lưu & thông báo kết quả" (có bước xác nhận) sẽ từ chối các hồ sơ chưa chọn, gửi thông báo cho mọi ứng viên, đóng tin và không thể mở lại.
* Xóa tin: bị chặn nếu đã có ứng viên được duyệt; nếu không, ứng viên đang chờ duyệt nhận thông báo tin đã bị gỡ.
* `deadline` và `open_date` bắt buộc; khi nâng cấp CSDL cũ, tin thiếu ngày mở lấy ngày tạo, tin thiếu hạn nộp được đặt là ngày mở + 30 ngày.
* Điểm AI cũ không còn dùng tới (JD đã sửa, hoặc quá 3 bản chấm của một ứng viên) được dọn khi chấm điểm mới.
* Yêu cầu công việc chỉ lưu một trường văn bản (`requirements.text`); tin cũ lưu theo trường rời được gộp tự động khi backend khởi động.
* Nội dung CV/JD được bọc trong thẻ và dặn LLM coi là dữ liệu, bỏ qua mọi chỉ dẫn nằm trong đó.
* `APP_ENV=prod` bắt buộc đặt `JWT_SECRET` riêng; CORS chỉ cho các origin trong `CORS_ORIGINS`.

## Mô hình dữ liệu

`companies` 1-n `users` (HR) và `jobs`; `users` (ứng viên) 1-1 `candidate_profiles`, 1-n `custom_cvs`;
`applications` nối `jobs` với ứng viên (kèm `cv_data`, `status`); `match_results` lưu điểm LLM; `notifications` gửi tới `users`.
