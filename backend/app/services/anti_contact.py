"""Block contact details before a chat is paid for: letters, replies and profile texts.

Catches phones (also spelled out in words), @handles, links, domains, e-mails and
mentions of messengers / social networks in RU, IT and EN, including simple
obfuscation: letters split by spaces, Cyrillic look-alikes inside Latin words,
digits in place of letters.
"""

from __future__ import annotations

import re

_PHONE_RE = re.compile(r"(?:\+|00)?\d[\d\s\-().]{7,}\d")
PHONE_MIN_DIGITS = 9
_USERNAME_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{4,}")
_URL_RE = re.compile(
    r"(?:https?://|www\.|t\.me/|telegram\.me/|wa\.me/)[^\s]+",
    re.IGNORECASE,
)
_DOT_DOMAIN_RE = re.compile(
    r"\b[a-z0-9][a-z0-9\-]*(?:\.|\s\.\s)(?:com|ru|it|org|net|io|me|co|info|eu)\b",
    re.IGNORECASE,
)
_SPELLED_DOT_RE = re.compile(r"\b(?:dot|точка|punto)\s*(?:com|ru|it|net|org|me)\b")
# Handle-like token: anna_petrova, anna.petrova_90
_UNDERSCORE_HANDLE_RE = re.compile(r"(?<![\w@])[a-z0-9]+(?:[._][a-z0-9]+)*_[a-z0-9_.]+")
# anna1990 — only suspicious next to a "soft" keyword such as telegram / ник
_DIGIT_HANDLE_RE = re.compile(r"(?<![\w@])[a-z][a-z._]{2,}\d{2,}\b")

# Always a contact channel, whatever the context.
_LATIN_KEYWORDS_RE = re.compile(
    r"instagram|\binsta(?:gr|gramm?)?\b|\binst\b"
    r"|whats\s?app?|\bwatsapp?\b|\bwhatsap\b|\bwapp\b"
    r"|\bviber\b|\bfacebook\b|\bfb\b|\bsnapchat\b|\btik\s?tok\b|\bskype\b|\bwechat\b"
    r"|\bvk\b|vkontakte|\bsignal\s+app\b"
    r"|\be-?mail\b|\bgmail\b|\bhotmail\b|\byahoo\b|\bicloud\b"
    r"|\bmy\s+number\b|\bphone\s+number\b|\bil\s+mio\s+numero\b|\bnumero\s+di\s+(?:telefono|cellulare)\b"
    r"|\bscrivimi\s+su\b|\bwrite\s+me\s+on\b"
)
_CYRILLIC_KEYWORDS_RE = re.compile(
    r"\bинста(?:грамм?\w*)?\b|\bинст[уеы]\b|\bинстой\b"
    r"|\bв[оа]тс[ао]пп?\w*|\bв[оа]цап\w*|\bв[аи]й?бер\w*"
    r"|\bтелег[аеуи]\b|\bтелегой\b|\bтг\b"
    r"|\bвк\b|\bвконтакт\w*|\bфейсбук\w*|\bфб\b|\bскайп\w*|\bтик\s?ток\w*|\bсн[эеа]пчат\w*"
    r"|\b[иеэ]?мейл\w*|\bпочт[аеуы]\s+gmail|\bгугл\s?почт\w*|\bпиши(?:те)?\s+(?:мне\s+)?на\s+почту\b"
    r"|\bмой\s+номер\b|\bномер\s+телефона\b|\bмой\s+телефон\b|\bнапиши\s+мне\s+в\b"
)
# Mentioned alone this is fine ("нашёл тебя в телеграм-канале", "l'ho visto al tg"), next to a handle it is not.
_SOFT_KEYWORDS_RE = re.compile(r"telegra|телеграм|\btg\b|\bник\b|\bnick\b|\bnickname\b|\busername\b")

_NUMBER_WORD_RE = re.compile(
    r"^(?:ноль|нуль|один|одна|два|две|три|четыре|пять|шесть|семь|восемь|девять|десять"
    r"|\w+надцать|двадцать|тридцать|сорок|пятьдесят|шестьдесят|семьдесят|восемьдесят|девяносто"
    r"|сто|двести|триста|четыреста|пятьсот|шестьсот|семьсот|восемьсот|девятьсот"
    r"|zero|uno|due|tre|quattro|cinque|sei|sette|otto|nove|dieci|venti|trenta|quaranta"
    r"|cinquanta|sessanta|settanta|ottanta|novanta|cento"
    r"|one|two|three|four|five|six|seven|eight|nine|ten|\d+)$"
)
SPELLED_PHONE_MIN_TOKENS = 6

# Single characters split by spaces/dots/dashes: "w h a t s a p p", "и-н-с-т-а".
_SPLIT_LETTERS_RE = re.compile(r"(?<!\w)(?:\w[\s.\-_*·]){3,}\w(?!\w)")
_HOMOGLYPHS = str.maketrans(
    {
        "а": "a", "е": "e", "ё": "e", "о": "o", "р": "p", "с": "c", "у": "y",
        "х": "x", "к": "k", "м": "m", "т": "t", "і": "i", "ї": "i", "в": "b",
        "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "@": "a", "$": "s",
    }
)


def _collapse_split_letters(text: str) -> str:
    return _SPLIT_LETTERS_RE.sub(lambda m: re.sub(r"[\s.\-_*·]", "", m.group(0)), text)


def _has_phone(text: str) -> bool:
    return any(len(re.sub(r"\D", "", m.group(0))) >= PHONE_MIN_DIGITS for m in _PHONE_RE.finditer(text))


def _has_spelled_phone(text: str) -> bool:
    run = 0
    for token in re.findall(r"[a-zа-я]+|\d+", text):
        run = run + 1 if _NUMBER_WORD_RE.match(token) else 0
        if run >= SPELLED_PHONE_MIN_TOKENS:
            return True
    return False


def contains_contact_info(text: str) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    if _URL_RE.search(value) or _USERNAME_RE.search(value) or _has_phone(value):
        return True

    lowered = _collapse_split_letters(value.lower().replace("ё", "е"))
    latinized = lowered.translate(_HOMOGLYPHS)
    if _DOT_DOMAIN_RE.search(lowered) or _SPELLED_DOT_RE.search(lowered):
        return True
    if _CYRILLIC_KEYWORDS_RE.search(lowered):
        return True
    if _LATIN_KEYWORDS_RE.search(lowered) or _LATIN_KEYWORDS_RE.search(latinized):
        return True
    if _UNDERSCORE_HANDLE_RE.search(lowered):
        return True
    if _SOFT_KEYWORDS_RE.search(lowered) and _DIGIT_HANDLE_RE.search(lowered):
        return True
    return _has_spelled_phone(lowered)
