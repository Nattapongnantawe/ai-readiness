"""PDPA: contact details must never reach the web page (FR-SS-05).

Module 1 keeps contact info in jobs.contact (never selected), but some employers also put a phone
number, e-mail or LINE id inside the job title or description. These helpers remove them on the way out.
"""
import re

PHONE = re.compile(r"(?<!\d)(?:\+?66[-\s]?|0)\d{1,2}[-\s.]?\d{3}[-\s.]?\d{3,4}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
LINE = re.compile(r"(?i)(?:line\s*id\s*[:：]?|line\s*[:：]|ไลน์\s*(?:id)?\s*[:：]?)\s*@?[A-Za-z0-9._-]{3,}")
# a bracketed part of the title that holds contact info, e.g. "(ติดต่อคุณสมชาย 08x-xxx-xxxx)"
BRACKET = re.compile(r"\s*[\(\[]([^\)\]]*)[\)\]]")
CONTACT_WORD = re.compile(r"(?i)ติดต่อ|สนใจโทร|โทร\s*[:.]|tel\s*[:.]")

HIDDEN = "[ซ่อนข้อมูลติดต่อ]"


def _has_contact(s: str) -> bool:
    return bool(PHONE.search(s) or EMAIL.search(s) or LINE.search(s) or CONTACT_WORD.search(s))


def clean_title(title: str | None) -> str:
    """Drop contact info from a job title entirely (a title should not show a placeholder)."""
    if not title:
        return title or ""
    t = BRACKET.sub(lambda m: "" if _has_contact(m.group(1)) else m.group(0), title)
    t = LINE.sub("", EMAIL.sub("", PHONE.sub("", t)))
    t = re.sub(r"(?i)\s*(ติดต่อ|สนใจโทร|โทร|tel)\s*[:.]?\s*(คุณ\S*)?\s*$", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" -–:/,|")
    return t or title


def mask_text(text: str | None) -> str | None:
    """Replace contact info inside long text (description, qualification, welfare)."""
    if not text:
        return text
    return LINE.sub(HIDDEN, EMAIL.sub(HIDDEN, PHONE.sub(HIDDEN, text)))
