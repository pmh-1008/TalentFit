"""Gọi Gemini. Mọi việc chấm điểm/trích xuất đều đi qua LLM; lỗi (thiếu key, hết quota...) được báo lại cho người dùng."""
import json
import re
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from ..config import settings


class LLMError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


_client = None


def _get_client():
    global _client
    if not settings.GEMINI_API_KEY:
        raise LLMError("Chưa cấu hình GEMINI_API_KEY nên không thể gọi LLM. Hãy khai báo trong file .env.", 503)
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _is_quota(e: Exception) -> bool:
    text = str(e).upper()
    return getattr(e, "code", None) == 429 or "RESOURCE_EXHAUSTED" in text or "QUOTA" in text


def generate_json(prompt: str, system: str | None = None) -> dict:
    client = _get_client()
    config = types.GenerateContentConfig(
        system_instruction=system, response_mime_type="application/json", temperature=0.1
    )
    last_error = None
    for attempt in range(2):
        try:
            resp = client.models.generate_content(model=settings.GEMINI_MODEL, contents=prompt, config=config)
            text = (resp.text or "").strip()
            text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
            data = json.loads(text)
            if not isinstance(data, dict):
                raise ValueError("not an object")
            return data
        except (json.JSONDecodeError, ValueError):
            last_error = LLMError("LLM trả về dữ liệu không đúng định dạng JSON. Vui lòng thử lại.", 502)
        except genai_errors.APIError as e:
            if _is_quota(e):
                raise LLMError("LLM đã vượt hạn mức sử dụng (quota exceeded). Vui lòng thử lại sau.", 429)
            last_error = LLMError(f"Không gọi được LLM: {getattr(e, 'message', None) or e}", 502)
            if getattr(e, "code", 0) not in (500, 503, 504):
                break
        except Exception as e:  # lỗi mạng, timeout...
            if _is_quota(e):
                raise LLMError("LLM đã vượt hạn mức sử dụng (quota exceeded). Vui lòng thử lại sau.", 429)
            last_error = LLMError(f"Không gọi được LLM: {e}", 502)
        time.sleep(1.5)
    raise last_error


# ---------------------------------------------------------------- chấm điểm
SYSTEM = (
    "Bạn là chuyên gia tuyển dụng, đánh giá khách quan và chỉ dựa trên thông tin có trong hồ sơ. "
    "Không suy đoán kỹ năng hay kinh nghiệm không được nêu. Luôn trả về JSON hợp lệ."
)

MATCH_PROMPT = """Given the job description: {jd} and the candidate profile: {profile}.
Score the candidate on each criterion from 0 to 100:
- skill_match: how well the candidate's profile matches the job's stated requirements
- experience_match: how well the candidate's experience matches the job's stated requirements
- education_match: how well the candidate's education matches the job's stated requirements
For each score, provide a brief explanation (2-3 sentences, in Vietnamese, citing concrete evidence from the profile).
Also provide overall_comment: 2-3 sentences in Vietnamese summarising strengths and gaps.

Return ONLY a JSON object of this exact shape:
{"skill_match": int, "experience_match": int, "education_match": int,
 "explanations": {"skill_match": str, "experience_match": str, "education_match": str, "overall_comment": str}}"""

WEIGHTS = {"skill_match": 0.4, "experience_match": 0.4, "education_match": 0.2}


def _score(v) -> float:
    return float(max(0, min(100, round(float(v)))))


def score_candidate(jd: dict, profile: dict) -> dict:
    prompt = MATCH_PROMPT.replace("{jd}", json.dumps(jd, ensure_ascii=False)).replace(
        "{profile}", json.dumps(profile, ensure_ascii=False)
    )
    data = generate_json(prompt, SYSTEM)
    try:
        scores = {k: _score(data[k]) for k in WEIGHTS}
        ex = data.get("explanations") or {}
        explanations = {k: str(ex.get(k, "")) for k in (*WEIGHTS, "overall_comment")}
    except (KeyError, TypeError, ValueError):
        raise LLMError("LLM trả về kết quả chấm điểm thiếu trường bắt buộc. Vui lòng thử lại.", 502)
    # overall_fit = 40% skill + 40% experience + 20% education
    scores["overall_fit"] = round(sum(scores[k] * w for k, w in WEIGHTS.items()), 1)
    return {**scores, "explanations": explanations}


# ---------------------------------------------------------------- CV | JD -> JSON
CV_PROMPT = """Extract the CV text below into JSON. Do not invent information; use "" or [] when missing.
Shape: {"name": str, "email": str, "phone": str, "github": str, "linkedin": str, "summary": str,
 "education": [{"degree": str, "school": str, "year": int|null, "gpa": number|null}],
 "experience": [{"title": str, "company": str, "duration_months": int, "description": str}],
 "skills": [str], "certifications_awards": [{"title": str, "year": int|null}]}
"github" and "linkedin" are profile URLs only if they appear in the CV.
Keep the original language of the content.

CV:
"""

JD_PROMPT = """Extract the job description below into JSON. Do not invent information; use "" when missing.
Shape: {"title": str, "description": str, "location": str, "job_type": str, "salary_range": str,
 "requirements": {"text": str}, "benefits": str}
"description" is a clean summary of responsibilities. Put candidate qualifications in requirements.text
and benefits in benefits. Keep the original language.

Job description:
"""


def parse_cv(text: str) -> dict:
    return generate_json(CV_PROMPT + text[:20000], SYSTEM)


def parse_jd(text: str) -> dict:
    return generate_json(JD_PROMPT + text[:20000], SYSTEM)
