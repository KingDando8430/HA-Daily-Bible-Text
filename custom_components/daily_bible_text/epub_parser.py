"""
EPUB Parser for Daily Bible Text.

Three verse styles handled:
  DE:  text (Ref)          <em>text (</em><a>Ref</a><em>)</em>
  ES:  text (Ref).         <em>text (</em><a>Ref</a><em>).</em>
  EN:  text\u200b—Ref.     <em>text\u200b—</em><a>Ref</a><em>.</em>

All are normalised to:  text (Ref)
"""
from __future__ import annotations

import hashlib
import logging
import re
import zipfile
from html.parser import HTMLParser
from typing import Optional

from .const import (
    MONTHS_DE, MONTHS_EN, MONTHS_EN_SHORT, MONTHS_ES,
    WEEKDAYS_DE, WEEKDAYS_EN, WEEKDAYS_ES,
)

_LOGGER = logging.getLogger(__name__)

MONTH_MAP_DE = {m: i + 1 for i, m in enumerate(MONTHS_DE)}
MONTH_MAP_EN = {m: i + 1 for i, m in enumerate(MONTHS_EN)}
MONTH_MAP_EN_SHORT = {m: i + 1 for i, m in enumerate(MONTHS_EN_SHORT)}
MONTH_MAP_ES = {m: i + 1 for i, m in enumerate(MONTHS_ES)}
_ALL_WEEKDAYS = set(WEEKDAYS_DE + WEEKDAYS_EN + WEEKDAYS_ES)
_PUB_REF_RE = re.compile(r"^[a-z]+\d{2}\.\d{2}$", re.IGNORECASE)

# EN-style: zero-width space + em-dash before the reference
# Matches: "...Lord.\u200b— Rom. 6:23 ."  OR  "...Lord.— Rom. 6:23 ."
_EN_DASH_VERSE_RE = re.compile(
    r"^(.*?)\s*[\u200b\u200c]*[—\u2014]\s*(.+?)\s*\.\s*$", re.DOTALL
)
# ES-style: trailing " ." after closing paren:  "text (Ref) ."
_TRAILING_DOT_RE = re.compile(r"\)\s+\.\s*$")


# ── HTML element extractor ────────────────────────────────────────────────────

class _ElementParser(HTMLParser):
    _SKIP = {"script", "style", "head", "noscript"}
    _BLOCK = {
        "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
        "li", "section", "article", "header", "footer",
        "span", "title", "td", "th",
    }

    def __init__(self):
        super().__init__()
        self.elements = []
        self._stack = [("root", set())]
        self._buf = []
        self._skip = 0

    def _flush(self):
        raw = "".join(self._buf).replace("\xa0", " ")
        text = re.sub(r"\s+", " ", raw).strip()
        self._buf = []
        if text and self._stack:
            tag, cls = self._stack[-1]
            self.elements.append((tag, cls, text))

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t in self._SKIP:
            self._skip += 1
            return
        if self._skip:
            return
        if t in self._BLOCK:
            self._flush()
        cls = set((dict(attrs).get("class") or "").lower().split())
        self._stack.append((t, cls))

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in self._SKIP:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        self._flush()
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i][0] == t:
                self._stack.pop(i)
                break

    def handle_data(self, data):
        if not self._skip:
            self._buf.append(data)

    def done(self):
        self._flush()
        return self.elements


def _parse_elements(html: str):
    p = _ElementParser()
    try:
        p.feed(html)
    except Exception:
        pass
    return p.done()


def _html_to_text(html: str) -> str:
    els = _parse_elements(html)
    lines = [t for _, _, t in els]
    result, prev = [], None
    for ln in lines:
        if ln != prev:
            result.append(ln)
        prev = ln
    return "\n".join(result)


# ── Date parsing ──────────────────────────────────────────────────────────────

def _strip_weekday(s: str) -> str:
    lower = s.lower()
    for wd in _ALL_WEEKDAYS:
        if lower.startswith(wd):
            return s[len(wd):].lstrip(",. \t\xa0")
    return s


def try_parse_date(raw: str) -> Optional[tuple]:
    """Return (month, day) int tuple or None."""
    s = _strip_weekday(raw.strip())
    # German: "1. Januar"
    for name, num in MONTH_MAP_DE.items():
        m = re.fullmatch(rf"(\d{{1,2}})\s*\.\s*{re.escape(name)}", s, re.IGNORECASE)
        if m:
            day = int(m.group(1))
            if 1 <= day <= 31:
                return num, day
    # English: "January 10"
    for name, num in MONTH_MAP_EN.items():
        m = re.fullmatch(rf"{re.escape(name)}\s+(\d{{1,2}})", s, re.IGNORECASE)
        if m:
            day = int(m.group(1))
            if 1 <= day <= 31:
                return num, day
    # English short: "Jan. 10"
    for name, num in MONTH_MAP_EN_SHORT.items():
        m = re.fullmatch(rf"{re.escape(name)}\.?\s+(\d{{1,2}})", s, re.IGNORECASE)
        if m:
            day = int(m.group(1))
            if 1 <= day <= 31:
                return num, day
    # Spanish: "10 de enero"
    for name, num in MONTH_MAP_ES.items():
        m = re.fullmatch(rf"(\d{{1,2}})\s+de\s+{re.escape(name)}", s, re.IGNORECASE)
        if m:
            day = int(m.group(1))
            if 1 <= day <= 31:
                return num, day
    return None


# ── Verse normalisation ───────────────────────────────────────────────────────

def _normalise_verse(raw: str) -> str:
    """
    Normalise all verse formats to  "text (Ref)" :

    EN:  "text\u200b— Rom. 6:23 ."  →  "text (Rom. 6:23)"
    ES:  "text (Ref) ."              →  "text (Ref)"
    DE:  "text (Ref)"                →  unchanged
    """
    # Step 1 – basic whitespace / paren spacing
    v = re.sub(r"\s*\(\s*", " (", raw)
    v = re.sub(r"\s*\)\s*", ") ", v).strip()
    v = re.sub(r"\s+", " ", v).strip()
    v = re.sub(r"\s+\)", ")", v)

    # Step 2 – EN pattern: "text\u200b—Ref." → "text (Ref)"
    m = _EN_DASH_VERSE_RE.match(v)
    if m:
        text_part = m.group(1).strip().rstrip(".")
        ref_part = m.group(2).strip()
        if re.search(r"\d", ref_part):          # must contain a digit to be a ref
            return f"{text_part} ({ref_part})"

    # Step 3 – ES/others: strip trailing " ."  from  "text (Ref) ."
    v = _TRAILING_DOT_RE.sub(")", v).strip()

    return v


# ── Verse reference extraction ────────────────────────────────────────────────

def extract_verse_reference(text: str) -> Optional[str]:
    """
    Extract Bible reference from the last (…) of a normalised verse.
    Returns e.g. "Ps. 96:7", "Rom. 6:23", "Matthew 5:3", or None.
    """
    if not text:
        return None
    # After normalisation all languages use (Ref) at the end
    m = re.search(r"\(([^()]+)\)\s*$", text)
    if m:
        candidate = m.group(1).strip()
        if re.search(r"\d", candidate):
            return candidate
    return None


def strip_verse_reference(text: str) -> str:
    """Remove the trailing (Reference) from a verse string."""
    return re.sub(r"\s*\([^()]+\)\s*$", "", text).strip()


# ── Commentary paragraph detector ────────────────────────────────────────────

def _is_commentary_p(tag: str, classes: set) -> bool:
    if tag != "p":
        return False
    excluded = {"extscrpcitetxt", "qu", "fn"}
    if classes & excluded:
        return False
    if "sb" in classes:
        return True
    return False


# ── Single-file parser ────────────────────────────────────────────────────────

def _parse_single_file_entry(html: str) -> Optional[dict]:
    """Parse one XHTML file → {"date_key", "verse", "commentary"} or None."""
    elements = _parse_elements(html)

    # 1. Find date
    date_key = None
    date_idx = -1
    for i, (tag, _, text) in enumerate(elements):
        if tag in ("title", "h2", "h3", "h1"):
            parsed = try_parse_date(text)
            if parsed:
                date_key = f"{parsed[0]:02d}-{parsed[1]:02d}"
                date_idx = i
                break
    if date_key is None:
        return None

    # 2. Collect verse elements
    #    DE/ES: <em>text (</em><a>Ref</a><em>)</em>  or  <em>).</em>
    #    EN:    <em>text—</em><a>Ref</a><em>.</em>
    verse_parts = []
    verse_end_idx = date_idx
    in_verse = False

    for i, (tag, _, text) in enumerate(elements[date_idx + 1:], start=date_idx + 1):
        if not in_verse:
            if tag == "em":
                in_verse = True
                verse_parts.append(text)
                verse_end_idx = i
                # DE single-em verse that already contains closing paren
                if re.search(r"\)\s*,?\s*$", text):
                    break
            elif tag in ("p", "div"):
                break
        else:
            if tag == "em":
                verse_parts.append(text)
                verse_end_idx = i
                # DE/ES closing em:  ")"  or  ")."  or  "),"
                stripped = text.strip()
                if re.fullmatch(r"\)\s*[.,]?\s*", stripped):
                    break
                # EN closing em is just "." – we stop here too
                if stripped == ".":
                    break
                # Verse text that already ends with )
                if re.search(r"\)\s*$", text) and not text.strip().endswith("("):
                    break
            elif tag == "a":
                verse_parts.append(text)
            elif tag in ("p", "div"):
                break
            else:
                verse_parts.append(text)

    raw_verse = " ".join(verse_parts)
    verse = _normalise_verse(raw_verse)

    # 3. Extract commentary
    commentary_parts = []
    for tag, classes, text in elements[verse_end_idx + 1:]:
        if tag == "em" and _PUB_REF_RE.match(text.strip()):
            break
        if text.strip() == "^" and tag in ("a", "strong", "span"):
            break
        if tag == "strong" and text.strip().startswith("^"):
            break
        if _is_commentary_p(tag, classes):
            clean = text.strip().lstrip(").").strip()
            if len(clean) > 5:
                commentary_parts.append(text)

    commentary = re.sub(r"\s+", " ", " ".join(commentary_parts)).strip()

    return {"date_key": date_key, "verse": verse, "commentary": commentary}


def _try_file_per_day(zf: zipfile.ZipFile, files: list) -> dict:
    entries = {}
    for fp in files:
        try:
            raw = zf.read(fp).decode("utf-8", errors="replace")
        except Exception:
            continue
        r = _parse_single_file_entry(raw)
        if r and r["verse"] and r["date_key"] not in entries:
            entries[r["date_key"]] = {"verse": r["verse"], "commentary": r["commentary"]}
    _LOGGER.debug("File-per-day: %d entries", len(entries))
    return entries


# ── Text-segment fallback ─────────────────────────────────────────────────────

def _process_day_lines(lines: list) -> dict:
    non_empty = [ln for ln in lines if ln.strip()]
    if not non_empty:
        return {"verse": "", "commentary": ""}
    verse_lines, commentary_lines = [], []
    verse_done = False
    for line in non_empty:
        if verse_done:
            commentary_lines.append(line)
        else:
            verse_lines.append(line)
            if extract_verse_reference(line) or len(verse_lines) >= 3:
                verse_done = True
    return {
        "verse": " ".join(verse_lines).strip(),
        "commentary": "\n\n".join(commentary_lines).strip(),
    }


def _try_text_segment(text: str) -> dict:
    entries = {}
    current_key = None
    current_lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        parsed = try_parse_date(line)
        if parsed:
            if current_key and current_lines:
                entries[current_key] = _process_day_lines(current_lines)
            current_key = f"{parsed[0]:02d}-{parsed[1]:02d}"
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)
    if current_key and current_lines:
        entries[current_key] = _process_day_lines(current_lines)
    return entries


# ── OPF spine ─────────────────────────────────────────────────────────────────

def _get_spine_files(zf: zipfile.ZipFile) -> list:
    opf_raw = None
    opf_base = ""
    for name in zf.namelist():
        if name.endswith(".opf"):
            opf_raw = zf.read(name).decode("utf-8", errors="replace")
            parts = name.split("/")
            opf_base = "/".join(parts[:-1]) + "/" if len(parts) > 1 else ""
            break
    if not opf_raw:
        return []
    manifest = {}
    for m in re.finditer(
        r"<item\b[^>]*\bid=['\"]([^'\"]+)['\"][^>]*\bhref=['\"]([^'\"]+)['\"]", opf_raw, re.I
    ):
        manifest[m.group(1)] = m.group(2)
    for m in re.finditer(
        r"<item\b[^>]*\bhref=['\"]([^'\"]+)['\"][^>]*\bid=['\"]([^'\"]+)['\"]", opf_raw, re.I
    ):
        manifest[m.group(2)] = m.group(1)
    spine_ids = re.findall(r"<itemref\b[^>]*\bidref=['\"]([^'\"]+)['\"]", opf_raw)
    nameset = set(zf.namelist())
    result = []
    for sid in spine_ids:
        href = manifest.get(sid, "").split("#")[0]
        if not href:
            continue
        full = re.sub(r"/+", "/", (href if href.startswith("/") else opf_base + href)).lstrip("/")
        if full in nameset:
            result.append(full)
    return result


# ── Yeartext extraction ────────────────────────────────────────────────────────

_YEARTEXT_KEYWORDS = (
    "jahrestext",
    "yeartext",
    "texto del año",
    "texto del ano",
    "texto del año:",
)
# Strip these prefixes from the yeartext value (with optional colon/space after)
_YEARTEXT_PREFIX_RE = re.compile(
    r"^(jahrestext|yeartext|texto del a[nñ]o)\s*[:\s]*", re.IGNORECASE
)
# EN em-dash at end of yeartext text: "...need."\u200b—"  →  strip it
_YEARTEXT_DASH_RE = re.compile(r'\s*[\u200b\u200c]*[—\u2014]\s*$')


def _extract_yeartext_from_elements(elements: list) -> Optional[str]:
    """
    Extract yeartext from a parsed XHTML element list.
    Handles DE, EN, ES styles – always returns "text (Ref)" format.
    """
    for i, (tag, cls, text) in enumerate(elements):
        lower = text.lower()
        if not any(kw in lower for kw in _YEARTEXT_KEYWORDS):
            continue

        # Strip keyword prefix + any surrounding quotes (all quote styles incl. ASCII ")
        text_clean = _YEARTEXT_PREFIX_RE.sub("", text)
        text_clean = re.sub(r'[\u201e\u201c\u201d\u00ab\u00bb"\'„]', "", text_clean)
        # Strip trailing em-dash (EN style) or opening paren (DE/ES style)
        text_clean = _YEARTEXT_DASH_RE.sub("", text_clean)
        text_clean = re.sub(r"\s*\(\s*$", "", text_clean).strip()
        # Strip any trailing colon/punctuation
        text_clean = re.sub(r"\s*[:,.]\s*$", "", text_clean).strip()

        # Find the Bible reference from the nearest <a> tag after this element
        ref: Optional[str] = None
        for j in range(i + 1, min(i + 8, len(elements))):
            t2, _, tx2 = elements[j]
            tx2s = tx2.strip()
            if t2 == "a" and re.search(r"\d", tx2s):
                ref = tx2s
                break

        if text_clean:
            if ref:
                return f"{text_clean} ({ref})"
            return text_clean

    return None


def extract_yeartext(epub_path: str) -> Optional[str]:
    """Search all non-daily XHTML files for the yeartext."""
    try:
        with zipfile.ZipFile(epub_path) as zf:
            for name in zf.namelist():
                if not name.lower().endswith((".xhtml", ".html", ".htm")):
                    continue
                if "split" in name.lower():
                    continue            # skip daily split files
                try:
                    raw = zf.read(name).decode("utf-8", errors="replace")
                    if not any(kw in raw.lower() for kw in _YEARTEXT_KEYWORDS):
                        continue
                    result = _extract_yeartext_from_elements(_parse_elements(raw))
                    if result:
                        return result
                except Exception:
                    continue
    except Exception:
        pass
    return None


# ── Metadata ──────────────────────────────────────────────────────────────────

def read_epub_metadata(epub_path: str) -> dict:
    """Return {year, language, title, yeartext}."""
    result: dict = {"year": None, "language": None, "title": "", "yeartext": None}
    try:
        with zipfile.ZipFile(epub_path) as zf:
            for name in zf.namelist():
                if name.endswith(".opf"):
                    raw = zf.read(name).decode("utf-8", errors="replace")
                    tm = re.search(r"<dc:title[^>]*>([^<]+)</dc:title>", raw, re.I)
                    if tm:
                        result["title"] = tm.group(1).strip()
                    ym = re.search(r"\b(20\d\d)\b", result["title"])
                    if ym:
                        result["year"] = int(ym.group(1))
                    lm = re.search(r"<dc:language[^>]*>([^<]+)</dc:language>", raw, re.I)
                    if lm:
                        lang = lm.group(1).lower()
                        if lang.startswith("de"):
                            result["language"] = "de"
                        elif lang.startswith("en"):
                            result["language"] = "en"
                        elif lang.startswith("es"):
                            result["language"] = "es"
                        else:
                            result["language"] = lang[:2]  # best-effort for other langs
                    break
    except Exception:
        pass
    result["yeartext"] = extract_yeartext(epub_path)
    return result


def detect_language_from_text(text: str) -> str:
    lower = text.lower()
    de = sum(1 for m in MONTHS_DE if m in lower)
    en = sum(1 for m in MONTHS_EN if m in lower)
    es = sum(1 for m in MONTHS_ES if m in lower)
    if de >= en and de >= es:
        return "de"
    if en >= es:
        return "en"
    return "es"


# ── Hash ──────────────────────────────────────────────────────────────────────

def compute_file_hash(filepath: str) -> str:
    h = hashlib.md5()
    with open(filepath, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Main parse ────────────────────────────────────────────────────────────────

def parse_epub(epub_path: str, language: str = "auto") -> tuple:
    """Return (entries dict, detected_language str)."""
    detected_lang = language if language != "auto" else None

    if detected_lang is None:
        meta = read_epub_metadata(epub_path)
        detected_lang = meta.get("language")

    try:
        with zipfile.ZipFile(epub_path) as zf:
            spine_files = _get_spine_files(zf)
            if not spine_files:
                spine_files = sorted(
                    n for n in zf.namelist()
                    if n.lower().endswith((".xhtml", ".html", ".htm"))
                )

            def _is_daily(name: str) -> bool:
                base = name.lower().split("/")[-1]
                return not any(
                    x in base
                    for x in ("cover", "toc", "nav", "ncx", "extracted", "css", "pagenav")
                )

            daily_files = [f for f in spine_files if _is_daily(f)]
            entries = _try_file_per_day(zf, daily_files)

            if len(entries) < 100:
                _LOGGER.info("File-per-day: %d entries → trying text-segment", len(entries))
                texts = []
                for fp in daily_files:
                    try:
                        raw = zf.read(fp).decode("utf-8", errors="replace")
                        texts.append(_html_to_text(raw))
                    except Exception:
                        pass
                fallback = _try_text_segment("\n".join(texts))
                if len(fallback) > len(entries):
                    entries = fallback

            if detected_lang is None:
                sample = ""
                if daily_files:
                    try:
                        sample = _html_to_text(
                            zf.read(daily_files[0]).decode("utf-8", errors="replace")
                        )
                    except Exception:
                        pass
                detected_lang = detect_language_from_text(sample)

    except zipfile.BadZipFile as exc:
        raise ValueError(f"Invalid EPUB: {epub_path}") from exc

    _LOGGER.info("Parsed %s → %d entries, lang=%s", epub_path, len(entries), detected_lang)
    if len(entries) < 300:
        _LOGGER.warning("Only %d daily entries found (expected ~365).", len(entries))
    return entries, detected_lang or "de"
