"""Diagnostics for Daily Bible Text."""
from __future__ import annotations
import os
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import CONF_EPUB_PATH, DOMAIN
from .coordinator import BibleTextCoordinator


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    coordinator: BibleTextCoordinator = hass.data[DOMAIN][entry.entry_id]
    epub_path = entry.data.get(CONF_EPUB_PATH, "")
    return {
        "epub_path": epub_path,
        "epub_exists": os.path.isfile(epub_path),
        "epub_size_bytes": os.path.getsize(epub_path) if os.path.isfile(epub_path) else 0,
        "epub_year": coordinator.epub_year,
        "language_detected": coordinator.detected_language,
        "entries_count": len(coordinator.verses),
        "yeartext": coordinator.yeartext,
        "cache_exists": os.path.isfile(coordinator._cache_path),
        "today_data": coordinator.data,
    }
