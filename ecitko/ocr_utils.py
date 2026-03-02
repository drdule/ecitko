import re


def average_confidence(ocr_data: dict) -> float:
    values = []
    for conf in ocr_data.get("conf", []):
        try:
            parsed = float(conf)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            values.append(parsed)
    return (sum(values) / len(values)) if values else 0.0


def extract_water_meter_value(raw_text: str) -> str:
    compact = re.sub(r"\s+", "", raw_text)
    candidates = re.findall(r"\d{4,12}", compact)
    if candidates:
        return max(candidates, key=len)

    groups = re.findall(r"\d+", raw_text)
    if groups:
        merged = "".join(groups)
        if merged:
            return merged

    return raw_text.strip()


def _normalize_digits(text: str) -> str:
    return "".join(ch for ch in (text or "") if ch.isdigit())


def extract_meter_reading_candidates(text: str) -> list[str]:
    if not text:
        return []

    candidates: list[str] = []

    groups = re.findall(r"\d+", text)
    # Prefer pairs like: 5 digits + 3 digits (black + red)
    for i in range(len(groups) - 1):
        left = groups[i]
        right = groups[i + 1]
        if len(right) == 3 and 4 <= len(left) <= 6:
            candidates.append(f"{left.zfill(5)} {right.zfill(3)}")

    # Single-group fallback: if OCR returns 8 digits, split to 5+3
    for group in groups:
        digits = _normalize_digits(group)
        if len(digits) == 8:
            candidates.append(f"{digits[:5]} {digits[5:]}")
        elif len(digits) == 7:
            candidates.append(f"{digits[:4].zfill(5)} {digits[4:]}".replace(" 0", " "))

    # Sliding-window fallback: if OCR returns a longer digit stream,
    # extract 8-digit windows and format them as 5+3.
    compact = _normalize_digits(text)
    if len(compact) >= 8:
        # Limit windows to keep it bounded
        max_windows = min(40, len(compact) - 7)
        for start in range(max_windows):
            window = compact[start : start + 8]
            candidates.append(f"{window[:5]} {window[5:]}")
    elif 4 <= len(compact) <= 10:
        candidates.append(compact)

    # De-dup while preserving order
    seen = set()
    out: list[str] = []
    for cand in candidates:
        if cand not in seen:
            seen.add(cand)
            out.append(cand)
    return out


def score_reading(candidate: str) -> int:
    if not candidate:
        return 0

    if re.fullmatch(r"\d{5}\s\d{3}", candidate):
        return 200

    digits = _normalize_digits(candidate)
    if len(digits) == 8:
        return 180
    if 6 <= len(digits) <= 10:
        return 120 - (abs(len(digits) - 8) * 10)
    return 0


def pick_best_reading(texts: list[str]) -> str:
    best = ""
    best_score = -1
    for text in texts:
        for cand in extract_meter_reading_candidates(text):
            score = score_reading(cand)
            if score > best_score:
                best = cand
                best_score = score
    # If we didn't find anything plausibly close to a real meter reading, return empty
    return best if best_score >= 110 else ""