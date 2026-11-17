class BusinessError(Exception):
    """Lỗi vi phạm quy tắc nghiệp vụ; main.py chuyển thành phản hồi HTTP."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
