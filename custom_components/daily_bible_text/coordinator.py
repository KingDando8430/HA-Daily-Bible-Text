"""DataUpdateCoordinator for Daily Bible Text."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_EPUB_PATH,
    CONF_LANGUAGE,
    DOMAIN,
    STORAGE_DIR,
    CACHE_VERSION,
)
from .epub_parser import compute_file_hash, parse_epub, read_epub_metadata

_LOGGER = logging.getLogger(__name__)


def _build_entry_title(year: Optional[int], lang: Optional[str]) -> str:
    lang_display = {"de": "Deutsch", "en": "English", "es": "Español"}.get(lang or "", lang or "")
    parts = ["Daily Bible Text"]
    if year:
        parts.append(str(year))
    if lang_display:
        parts.append(lang_display)
    return " ".join(parts)


class BibleTextCoordinator(DataUpdateCoordinator):
    """Coordinator that loads the daily Bible text from an EPUB file."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self._entry = entry
        self._epub_path: str = entry.data[CONF_EPUB_PATH]
        self._language: str = entry.data.get(CONF_LANGUAGE, "auto")
        self._verses: dict[str, dict] = {}
        self._detected_language: str = "de"
        self._epub_year: Optional[int] = None
        self._yeartext: Optional[str] = None
        self._unsub_midnight: Optional[Any] = None

        cache_dir = hass.config.path(STORAGE_DIR)
        os.makedirs(cache_dir, exist_ok=True)
        safe_id = entry.entry_id.replace("-", "_")
        self._cache_path = os.path.join(cache_dir, f"cache_{safe_id}.json")

    async def async_setup(self) -> None:
        await self.async_config_entry_first_refresh()
        self._unsub_midnight = async_track_time_change(
            self.hass, self._midnight_refresh, hour=0, minute=0, second=5,
        )

    async def async_shutdown(self) -> None:
        if self._unsub_midnight:
            self._unsub_midnight()
            self._unsub_midnight = None

    @callback
    def _midnight_refresh(self, _now=None) -> None:
        self.hass.async_create_task(self.async_refresh())

    async def _async_update_data(self) -> dict:
        epub_path = self._epub_path
        if not os.path.isfile(epub_path):
            raise UpdateFailed(f"EPUB not found: {epub_path}")

        current_hash = await self.hass.async_add_executor_job(compute_file_hash, epub_path)
        verses = await self._load_cache(current_hash)

        if verses is None:
            meta = await self.hass.async_add_executor_job(read_epub_metadata, epub_path)
            self._epub_year = meta.get("year")
            self._yeartext = meta.get("yeartext")
            detected_lang = meta.get("language")

            verses, lang = await self.hass.async_add_executor_job(parse_epub, epub_path, self._language)
            if detected_lang:
                lang = detected_lang
            self._detected_language = lang

            if not verses:
                raise UpdateFailed("No daily entries found in EPUB. Please check the file and reconfigure.")
            await self._save_cache(current_hash, lang, verses)
        else:
            _LOGGER.debug("Loaded %d entries from cache", len(verses))

        self._verses = verses

        # Year validation
        current_year = datetime.now().year
        issue_id = f"outdated_epub_{self._entry.entry_id}"
        if self._epub_year and self._epub_year != current_year:
            ir.async_create_issue(
                self.hass, DOMAIN, issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="outdated_epub",
                translation_placeholders={
                    "epub_year": str(self._epub_year),
                    "current_year": str(current_year),
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

        today_key = datetime.now().strftime("%m-%d")
        entry_data = verses.get(today_key)
        if entry_data is None:
            available = sorted(verses.keys())
            if available:
                entry_data = verses[available[-1]]
                _LOGGER.warning("No entry for %s, using fallback", today_key)
            else:
                raise UpdateFailed("No daily entries found in EPUB.")

        desired_title = _build_entry_title(self._epub_year, self._detected_language)
        if self._entry.title != desired_title:
            self.hass.config_entries.async_update_entry(self._entry, title=desired_title)

        return {
            "date_key": today_key,
            "verse": entry_data.get("verse", ""),
            "commentary": entry_data.get("commentary", ""),
            "language": self._detected_language,
            "epub_year": self._epub_year,
            "yeartext": self._yeartext or "",
            "entries_count": len(verses),
            "source_epub": epub_path,
        }

    async def _load_cache(self, current_hash: str) -> Optional[dict]:
        def _read():
            if not os.path.isfile(self._cache_path):
                return None
            try:
                with open(self._cache_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if data.get("version") == CACHE_VERSION and data.get("epub_hash") == current_hash:
                    self._detected_language = data.get("language", "de")
                    self._epub_year = data.get("epub_year")
                    self._yeartext = data.get("yeartext")
                    return data.get("verses", {})
            except Exception as exc:
                _LOGGER.debug("Cache read error: %s", exc)
            return None
        return await self.hass.async_add_executor_job(_read)

    async def _save_cache(self, epub_hash: str, lang: str, verses: dict) -> None:
        def _write():
            try:
                with open(self._cache_path, "w", encoding="utf-8") as fh:
                    json.dump({
                        "version": CACHE_VERSION,
                        "epub_hash": epub_hash,
                        "language": lang,
                        "epub_year": self._epub_year,
                        "yeartext": self._yeartext,
                        "verses": verses,
                    }, fh, ensure_ascii=False, indent=2)
            except Exception as exc:
                _LOGGER.warning("Cache write error: %s", exc)
        await self.hass.async_add_executor_job(_write)

    @property
    def detected_language(self) -> str:
        return self._detected_language

    @property
    def epub_year(self) -> Optional[int]:
        return self._epub_year

    @property
    def yeartext(self) -> Optional[str]:
        return self._yeartext

    @property
    def verses(self) -> dict:
        return self._verses
