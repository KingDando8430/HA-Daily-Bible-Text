"""Sensor platform for Daily Bible Text."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DATE,
    ATTR_ENTRIES_COUNT,
    ATTR_EPUB_YEAR,
    ATTR_LANGUAGE,
    ATTR_SOURCE_EPUB,
    ATTR_VERSE_REFERENCE,
    CONF_SHOW_VERSE_REF,
    DOMAIN,
)
from .coordinator import BibleTextCoordinator
from .epub_parser import extract_verse_reference, strip_verse_reference

_LOGGER = logging.getLogger(__name__)

_NAMES = {
    "scripture":   {"de": "Tagestext",        "en": "Scripture",        "es": "Texto bíblico"},
    "commentary":  {"de": "Kommentar",         "en": "Comment",          "es": "Comentario"},
    "bible_verse": {"de": "Bibelvers",         "en": "Bible Verse",      "es": "Versículo bíblico"},
    "yeartext":    {"de": "Jahrestext",        "en": "Yeartext",         "es": "Texto del año"},
}


def _sensor_name(key: str, lang: str) -> str:
    return _NAMES[key].get(lang, _NAMES[key]["en"])


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BibleTextCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        BibleScriptureSensor(coordinator, entry),
        BibleVerseSensor(coordinator, entry),
        BibleCommentarySensor(coordinator, entry),
        BibleYeartextSensor(coordinator, entry),
    ])


class _BibleBase(CoordinatorEntity, SensorEntity):
    """Base class – entities grouped as a Service, not a Device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BibleTextCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def _data(self) -> dict:
        return self.coordinator.data or {}

    @property
    def _lang(self) -> str:
        return self._data.get("language", "de")


class BibleScriptureSensor(_BibleBase):
    """Daily scripture sensor — always enabled."""

    _attr_icon = "mdi:book-open-variant"

    def __init__(self, coordinator: BibleTextCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_scripture"

    @property
    def name(self) -> str:
        return _sensor_name("scripture", self._lang)

    @property
    def native_value(self) -> str | None:
        verse = self._data.get("verse", "")
        if not verse:
            return None
        if not self._entry.data.get(CONF_SHOW_VERSE_REF, True):
            verse = strip_verse_reference(verse)
        return verse

    @property
    def extra_state_attributes(self) -> dict:
        verse = self._data.get("verse", "")
        return {
            ATTR_DATE: self._data.get("date_key"),
            ATTR_LANGUAGE: self._lang,
            ATTR_SOURCE_EPUB: self._data.get("source_epub"),
            ATTR_ENTRIES_COUNT: self._data.get("entries_count"),
            ATTR_EPUB_YEAR: self._data.get("epub_year"),
            ATTR_VERSE_REFERENCE: extract_verse_reference(verse),
        }


class BibleVerseSensor(_BibleBase):
    """Bible reference only, e.g. 'Ps. 96:7' — always enabled."""

    _attr_icon = "mdi:bookmark-outline"

    def __init__(self, coordinator: BibleTextCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_bible_verse"

    @property
    def name(self) -> str:
        return _sensor_name("bible_verse", self._lang)

    @property
    def native_value(self) -> str | None:
        return extract_verse_reference(self._data.get("verse", ""))

    @property
    def extra_state_attributes(self) -> dict:
        return {
            ATTR_DATE: self._data.get("date_key"),
            ATTR_LANGUAGE: self._lang,
        }


class BibleCommentarySensor(_BibleBase):
    """Daily commentary — generated always, disabled in registry by default."""

    _attr_icon = "mdi:text-box-outline"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: BibleTextCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_commentary"

    @property
    def name(self) -> str:
        return _sensor_name("commentary", self._lang)

    @property
    def native_value(self) -> str | None:
        commentary = self._data.get("commentary", "")
        if not commentary:
            return None
        return commentary[:255] if len(commentary) > 255 else commentary

    @property
    def extra_state_attributes(self) -> dict:
        return {
            ATTR_DATE: self._data.get("date_key"),
            ATTR_LANGUAGE: self._lang,
            ATTR_SOURCE_EPUB: self._data.get("source_epub"),
            ATTR_ENTRIES_COUNT: self._data.get("entries_count"),
            "commentary_full": self._data.get("commentary", ""),
        }


class BibleYeartextSensor(_BibleBase):
    """Annual year text — generated always, disabled in registry by default."""

    _attr_icon = "mdi:calendar-star"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: BibleTextCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_yeartext"

    @property
    def name(self) -> str:
        return _sensor_name("yeartext", self._lang)

    @property
    def native_value(self) -> str | None:
        yt = self._data.get("yeartext", "")
        if not yt:
            return None
        return yt[:255] if len(yt) > 255 else yt

    @property
    def extra_state_attributes(self) -> dict:
        yt = self._data.get("yeartext", "")
        return {
            ATTR_EPUB_YEAR: self._data.get("epub_year"),
            ATTR_LANGUAGE: self._lang,
            ATTR_VERSE_REFERENCE: extract_verse_reference(yt),
            "yeartext_full": yt,
        }
