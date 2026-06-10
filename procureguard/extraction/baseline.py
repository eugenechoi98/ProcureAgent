"""SROIE OCR + Regex baseline。"""

import re
from datetime import datetime

from procureguard.extraction.schemas import BaselineExtraction, BaselineField, OCRToken, SROIE_FIELDS


class SroieRegexBaseline:
    """基于 OCR token 的可解释字段抽取 baseline。"""

    baseline_name = "ocr-regex-sroie-baseline-v1"
    total_keywords = ("grand total", "total amount", "amount due", "total")
    subtotal_keywords = ("subtotal", "sub total")
    date_patterns = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d %Y",
        "%B %d %Y",
    ]
    amount_pattern = re.compile(r"(?:RM|USD|EUR|GBP|CNY|JPY|[$€£¥])?\s*(\d[\d,]*(?:\.\d+)?)")
    numeric_date_pattern = re.compile(r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b")
    text_date_pattern = re.compile(
        r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4})\b"
    )

    def extract(self, tokens: list[OCRToken]) -> BaselineExtraction:
        """按固定优先级抽取 company、address、date、total。"""

        ordered = [token for token in tokens if token.text.strip()]
        fields = {
            "company": self._extract_company(ordered),
            "address": self._extract_address(ordered),
            "date": self._extract_date(ordered),
            "total": self._extract_total(ordered),
        }
        return BaselineExtraction(baseline_name=self.baseline_name, fields=fields)

    def extract_from_words(self, words: list[str]) -> BaselineExtraction:
        """兼容旧测试的纯文本入口。"""

        tokens = [
            OCRToken(text=word, bbox=(0, idx * 10, 100, idx * 10 + 8), confidence=1.0)
            for idx, word in enumerate(words)
            if word.strip()
        ]
        return self.extract(tokens)

    def _extract_company(self, tokens: list[OCRToken]) -> BaselineField:
        """启发式：取顶部最早出现的非噪声文本作为商户名。"""

        for token in sorted(tokens[:8], key=lambda item: (item.bbox[1], item.bbox[0])):
            text = token.text.strip(" :-")
            lower = text.lower()
            if lower and not self._looks_like_noise(lower):
                return BaselineField(text, 0.55, token.text, "top_first_non_noise")
        return BaselineField(rule_name="top_first_non_noise")

    def _extract_address(self, tokens: list[OCRToken]) -> BaselineField:
        """启发式：在商户名之后找包含地址关键词或较长文本的行。"""

        address_words = ("street", "st", "road", "rd", "jalan", "jln", "ave", "avenue", "suite", "floor")
        candidates = tokens[1:8]
        for token in candidates:
            text = token.text.strip()
            lower = text.lower()
            if any(word in lower for word in address_words):
                return BaselineField(text, 0.50, token.text, "address_keyword_after_company")
        for token in candidates:
            text = token.text.strip()
            if len(text) >= 12 and not self._looks_like_noise(text.lower()):
                return BaselineField(text, 0.35, token.text, "long_line_after_company")
        return BaselineField(rule_name="address_keyword_after_company")

    def _extract_date(self, tokens: list[OCRToken]) -> BaselineField:
        """支持常见数字日期和英文月份日期。"""

        for token in tokens:
            for pattern in (self.numeric_date_pattern, self.text_date_pattern):
                match = pattern.search(token.text)
                if not match:
                    continue
                normalized = normalize_date(match.group(1))
                if normalized:
                    return BaselineField(normalized, 0.80, match.group(1), "date_regex_normalized")
        return BaselineField(rule_name="date_regex_normalized")

    def _extract_total(self, tokens: list[OCRToken]) -> BaselineField:
        """优先匹配 GRAND TOTAL / TOTAL，显式跳过 subtotal。"""

        best: tuple[int, BaselineField] | None = None
        for idx, token in enumerate(tokens):
            lower = token.text.lower()
            if any(keyword in lower for keyword in self.subtotal_keywords):
                continue
            keyword_rank = self._total_keyword_rank(lower)
            if keyword_rank is None:
                continue
            value = self._amount_from_text(token.text)
            matched_text = token.text
            if value is None and idx + 1 < len(tokens):
                value = self._amount_from_text(tokens[idx + 1].text)
                matched_text = f"{token.text} {tokens[idx + 1].text}"
            if value is None:
                continue
            field = BaselineField(value, 0.85 - keyword_rank * 0.05, matched_text, "total_keyword_amount")
            if best is None or keyword_rank < best[0]:
                best = (keyword_rank, field)
        if best:
            return best[1]

        return BaselineField(rule_name="total_keyword_amount")

    def _total_keyword_rank(self, lower: str) -> int | None:
        for rank, keyword in enumerate(self.total_keywords):
            if keyword in lower:
                return rank
        return None

    def _amount_from_text(self, text: str) -> str | None:
        matches = self.amount_pattern.findall(text.replace(",", ""))
        if not matches:
            return None
        return normalize_amount(matches[-1])

    def _looks_like_noise(self, lower: str) -> bool:
        return (
            lower in {"invoice", "receipt", "tax invoice", "cash receipt"}
            or any(keyword in lower for keyword in self.total_keywords)
            or any(keyword in lower for keyword in self.subtotal_keywords)
            or self.numeric_date_pattern.search(lower) is not None
            or self.amount_pattern.fullmatch(lower) is not None
        )


def normalize_amount(value: object) -> str:
    """金额标准化为两位小数字符串。"""

    if value is None:
        return ""
    text = str(value).strip().replace(",", "")
    text = re.sub(r"^(RM|USD|EUR|GBP|CNY|JPY|[$€£¥])\s*", "", text, flags=re.IGNORECASE)
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return ""
    return f"{float(match.group(0)):.2f}"


def normalize_date(value: object) -> str:
    """日期标准化为 YYYY-MM-DD。"""

    if value is None:
        return ""
    text = str(value).strip().replace(",", "")
    if not text:
        return ""
    for fmt in SroieRegexBaseline.date_patterns:
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.year < 100:
                parsed = parsed.replace(year=parsed.year + 2000)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def empty_baseline_fields() -> dict[str, BaselineField]:
    """生成四个 SROIE 字段的空结果。"""

    return {field_name: BaselineField() for field_name in SROIE_FIELDS}


RegexInvoiceExtractor = SroieRegexBaseline
