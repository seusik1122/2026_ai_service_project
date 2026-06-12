import re

def clean_text(text: str) -> str:
    """HTML 태그 제거, 공백 정규화"""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def truncate(text: str, max_len: int = 500) -> str:
    return text[:max_len] if len(text) > max_len else text
