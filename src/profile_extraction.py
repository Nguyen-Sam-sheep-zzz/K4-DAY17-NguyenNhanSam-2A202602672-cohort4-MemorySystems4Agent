"""Conservative Vietnamese profile rules for offline mode; not a general parser."""
from __future__ import annotations

import re

SUBJECT = r"(?:mình|tôi|tớ|em)"
MODIFIERS = r"(?:(?:hiện tại|hiện|vẫn|đang|đã|giờ)\s+)*"
STOP = r"[,.;!?]|\s+(?:và|chứ|nhưng|để|vài|mỗi|trong|từ|cho|dù|không|nữa|nhé)\b"


def _value(text: str) -> str:
    value = re.split(STOP, text, maxsplit=1, flags=re.I)[0]
    return value.strip(" :\t\n")[:160]


def _matches(pattern: str, text: str):
    # A greedy tail would swallow a later correction in the same sentence.
    pattern = pattern.replace("(.+)", rf"(.+?)(?={STOP}|$)")
    for match in re.finditer(pattern, text, re.I):
        value = _value(match.group(1))
        if value and not re.search(r"\b(?:gì|ai|đâu|hay)\b", value, re.I):
            yield value


def _positive_feature(pattern: str, text: str):
    for match in re.finditer(pattern, text, re.I):
        prefix = text[:match.start()]
        if not re.search(r"\b(?:không|đừng|tránh|chẳng|chưa)\s+(?:\w+\s+){0,4}$", prefix, re.I):
            return match
    return None


def extract_profile_updates(message: str) -> dict[str, str]:
    """Extract explicit self-reports; latest positive assertion wins per field."""
    facts: dict[str, str] = {}
    text = re.sub(r'"[^"\n]*"|“[^”\n]*”', "", message)
    for sentence in re.split(r"(?<=[.!?;])\s+|\n+", text):
        sentence = sentence.strip()
        if not sentence or "?" in sentence:
            continue
        if re.match(r"(?:nhắc|tóm tắt|(?:bạn|hãy).*(?:nhắc|nhớ lại))\b", sentence, re.I):
            continue
        if re.search(r"\b(?:nhắc lại|nhớ lại|còn nhớ|tóm tắt)\b", sentence, re.I):
            continue
        if re.search(r"\b(?:không|chưa|nhỉ|thế nào)\s*[.!]*$", sentence, re.I):
            continue
        if re.match(r"(?:nếu|giả sử)\b", sentence, re.I):
            continue
        if re.search(r"\b(?:đùa|giả định)\b", sentence, re.I):
            continue
        if re.match(rf"(?:bạn|đồng nghiệp|sếp|anh|chị)\s+(?:{SUBJECT}|ấy|của)\b", sentence, re.I):
            continue
        reported = re.match(r"(?P<speaker>(?:[\w-]+\s+){1,4})(?:nói|bảo|kể|muốn|thích)\b", sentence, re.I)
        profile_label = re.match(r"(?:đồ uống|thức uống|món ăn|style|phong cách|nghề(?: nghiệp)?)\b", sentence, re.I)
        if reported and not profile_label and not re.search(rf"\b{SUBJECT}\b", reported.group("speaker"), re.I):
            continue
        if re.search(rf"\b(?:nói|bảo|kể|cho biết)\s+(?:rằng\s+)?{SUBJECT}\b", sentence, re.I) and not re.match(
            rf"{SUBJECT}\s+(?:nói|bảo|kể)\b", sentence, re.I
        ):
            continue
        temporary_location = re.search(
            r"\b(?:hôm nay|hôm qua|tuần trước|hai ngày|vài ngày|\d+\s+ngày|để họp|đi họp|du lịch|công tác|ghé thăm)\b",
            sentence, re.I,
        ) and not re.search(r"\b(?:chuyển\s+(?:đến|vào|sang)|sinh sống|cư trú|vài tháng|nhiều tháng)\b", sentence, re.I)
        patterns = {
            "name": rf"{SUBJECT}\s+tên(?:\s+là)?\s+(.+)",
            "location": rf"(?:{SUBJECT}\s+{MODIFIERS}(?:(?:sống|sinh sống|cư trú)\s+(?:ở|tại)|ở|chuyển\s+(?:vào|đến|tới|sang))|hiện(?:\s+tại)?\s+ở)\s+(.+)",
            "favorite_drink": rf"(?:đồ uống|thức uống)\s+yêu thích(?:\s+của\s+{SUBJECT})?\s+là\s+(.+)",
            "favorite_food": rf"món ăn\s+yêu thích(?:\s+của\s+{SUBJECT})?\s+là\s+(.+)",
            "pet": rf"{SUBJECT}\s+nuôi\s+(?:(?:một bé|một con|một)\s+)?(.+)",
        }
        for key, pattern in patterns.items():
            if key == "location" and temporary_location:
                continue
            for value in _matches(pattern, sentence):
                facts[key] = value
        # Working in a city for months is stable enough; today's cafe is not.
        if re.search(r"\b(?:vài tháng|nhiều tháng|chuyển nơi ở)\b", sentence, re.I):
            for value in _matches(rf"{SUBJECT}\s+{MODIFIERS}làm việc\s+(?:ở|tại)\s+(.+)", sentence):
                facts["location"] = value
        for value in _matches(r"nơi ở\s+(?:đã\s+)?(?:cập nhật|đổi)\s+từ\s+.+?\s+sang\s+(.+)", sentence):
            facts["location"] = value
        profession_pattern = (
            rf"(?:{SUBJECT}\s+{MODIFIERS}làm(?:\s+nghề)?"
            rf"|và\s+(?:đang|hiện)\s+làm"
            rf"|nghề(?: nghiệp)?(?:(?:\s+(?:hiện tại|thì|vẫn|của mình)))*\s+là"
            rf"|giờ\s+(?:{SUBJECT}\s+)?chuyển\s+sang)\s+(.+)"
        )
        for value in _matches(profession_pattern, sentence):
            if re.search(r"\b(?:engineer|developer|manager|analyst|designer|scientist|architect)\b", value, re.I) or re.match(
                r"(?:kỹ sư|giáo viên|bác sĩ|sinh viên|kế toán|lập trình viên|nhân viên)\b", value, re.I
            ):
                facts["profession"] = value
        likes = re.finditer(
            rf"{SUBJECT}\s+(?:vẫn\s+)?(?:thích|(?:đang\s+)?quan tâm(?:\s+nhiều)?(?:\s+(?:đến|tới))?)\s+(.+?)(?=[.;!?]|\s+(?:nhưng|chứ|không)\b|,\s+(?:giờ\s+)?{SUBJECT}\b|$)",
            sentence, re.I,
        )
        for preference in likes:
            positive = preference.group(1)
            interests = [label for label in ("Python", "AI", "MLOps", "RAG")
                         if re.search(rf"\b{label}\b", positive, re.I)]
            if interests:
                facts["interests"] = ", ".join(interests)
        own_style = re.search(
            rf"{SUBJECT}[^.!?]*\b(?:muốn|thích)|hãy\s+(?:trả lời|giải thích)|^style.*giữ",
            sentence, re.I,
        )
        if own_style and re.search(r"(?:trả lời|câu trả lời|style)", sentence, re.I) and re.search(
            r"(?:muốn|thích|hãy|style.*giữ)", sentence, re.I
        ):
            style_text = re.split(r"hãy", sentence, maxsplit=1, flags=re.I)[-1]
            parts = []
            if _positive_feature(r"\b(?:ngắn|gọn)\b", style_text):
                parts.append("ngắn gọn")
            elif _positive_feature(r"\b(?:chi tiết|dài)\b", style_text):
                parts.append("chi tiết")
            bullets = _positive_feature(r"(\d+)\s+bullet", style_text)
            if bullets:
                parts.append(f"{bullets.group(1)} bullet")
            elif _positive_feature(r"\bbullet\b", style_text):
                parts.append("có bullet")
            if _positive_feature(r"ví dụ", style_text):
                parts.append("có ví dụ thực chiến" if "thực chiến" in style_text.casefold() else "có ví dụ thực tế")
            if _positive_feature(r"trade-off", style_text):
                parts.append("so sánh trade-off")
            if parts:
                facts["response_style"] = "; ".join(parts)
    return facts
