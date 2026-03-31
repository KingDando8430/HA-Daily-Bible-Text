"""Config flow for Daily Bible Text – file upload + optional path."""
from __future__ import annotations

import logging
import os
import shutil
import zipfile

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    FileSelector,
    FileSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_EPUB_PATH,
    CONF_LANGUAGE,
    CONF_SHOW_VERSE_REF,
    DOMAIN,
    LANGUAGE_AUTO,
    LANGUAGE_DE,
    LANGUAGE_EN,
    LANGUAGE_ES,
    STORAGE_DIR,
)
from .epub_parser import read_epub_metadata

_LOGGER = logging.getLogger(__name__)

LANGUAGE_OPTIONS = [
    {"value": LANGUAGE_AUTO, "label": "Auto-detect"},
    {"value": LANGUAGE_DE,   "label": "Deutsch"},
    {"value": LANGUAGE_EN,   "label": "English"},
    {"value": LANGUAGE_ES,   "label": "Español"},
]


def _epub_dir(hass) -> str:
    path = hass.config.path(STORAGE_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def _validate_epub(path: str) -> str | None:
    """Return error key or None if valid."""
    if not path.lower().endswith(".epub"):
        return "not_epub"
    if not os.path.isfile(path):
        return "file_not_found"
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
        if not any(n.endswith((".xhtml", ".html", ".opf")) for n in names):
            return "invalid_epub"
    except Exception:
        return "invalid_epub"
    return None


async def _save_upload(hass, upload_id: str) -> str:
    """Save an uploaded file to the storage dir, keeping its original name. Returns dest path."""
    from homeassistant.components.file_upload import process_uploaded_file

    dest_dir = _epub_dir(hass)

    def _copy():
        with process_uploaded_file(hass, upload_id) as tmp_path:
            filename = os.path.basename(str(tmp_path))
            # Keep the original extension; process_uploaded_file uses a temp name,
            # so we just store it as bible_text_<upload_id[:8]>.epub to avoid collisions
            dest = os.path.join(dest_dir, f"bible_text_{upload_id[:8]}.epub")
            shutil.copy2(tmp_path, dest)
            return dest

    return await hass.async_add_executor_job(_copy)


class DailyBibleTextConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Daily Bible Text."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            upload_id = (user_input.get("epub_file") or "").strip()
            manual_path = (user_input.get(CONF_EPUB_PATH) or "").strip()
            resolved_path: str | None = None

            if upload_id:
                try:
                    resolved_path = await _save_upload(self.hass, upload_id)
                except Exception as exc:
                    _LOGGER.error("Upload failed: %s", exc)
                    errors["epub_file"] = "upload_failed"
            elif manual_path:
                err = _validate_epub(manual_path)
                if err:
                    errors[CONF_EPUB_PATH] = err
                else:
                    resolved_path = manual_path
            else:
                errors["base"] = "no_epub_provided"

            if resolved_path and not errors:
                err = await self.hass.async_add_executor_job(_validate_epub, resolved_path)
                if err:
                    errors["epub_file"] = err

            if resolved_path and not errors:
                meta = await self.hass.async_add_executor_job(read_epub_metadata, resolved_path)
                lang = meta.get("language") or user_input.get(CONF_LANGUAGE, LANGUAGE_AUTO)
                year = meta.get("year")

                lang_display = {"de": "Deutsch", "en": "English", "es": "Español"}.get(lang, lang)
                title = " ".join(filter(None, ["Daily Bible Text", str(year) if year else None, lang_display]))

                await self.async_set_unique_id(f"daily_bible_text_{resolved_path}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_EPUB_PATH: resolved_path,
                        CONF_LANGUAGE: user_input.get(CONF_LANGUAGE, LANGUAGE_AUTO),
                        CONF_SHOW_VERSE_REF: user_input.get(CONF_SHOW_VERSE_REF, True),
                    },
                )

        schema = vol.Schema({
            vol.Optional("epub_file"): FileSelector(FileSelectorConfig(accept=".epub")),
            vol.Optional(CONF_EPUB_PATH, default=""): TextSelector(),
            vol.Optional(CONF_LANGUAGE, default=LANGUAGE_AUTO): SelectSelector(
                SelectSelectorConfig(options=LANGUAGE_OPTIONS, mode=SelectSelectorMode.LIST)
            ),
            vol.Optional(CONF_SHOW_VERSE_REF, default=True): BooleanSelector(),
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return DailyBibleTextOptionsFlow(config_entry)


class DailyBibleTextOptionsFlow(config_entries.OptionsFlow):
    """Options flow."""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors: dict[str, str] = {}
        current = self._config_entry.data

        if user_input is not None:
            upload_id = (user_input.get("epub_file") or "").strip()
            manual_path = (user_input.get(CONF_EPUB_PATH) or "").strip()
            resolved_path: str = current.get(CONF_EPUB_PATH, "")

            if upload_id:
                try:
                    resolved_path = await _save_upload(self.hass, upload_id)
                except Exception as exc:
                    _LOGGER.error("Upload failed: %s", exc)
                    errors["epub_file"] = "upload_failed"
            elif manual_path:
                err = _validate_epub(manual_path)
                if err:
                    errors[CONF_EPUB_PATH] = err
                else:
                    resolved_path = manual_path

            if not errors:
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data={
                        **current,
                        CONF_EPUB_PATH: resolved_path,
                        CONF_LANGUAGE: user_input.get(CONF_LANGUAGE, current.get(CONF_LANGUAGE, LANGUAGE_AUTO)),
                        CONF_SHOW_VERSE_REF: user_input.get(CONF_SHOW_VERSE_REF, current.get(CONF_SHOW_VERSE_REF, True)),
                    },
                )
                return self.async_create_entry(title="", data={})

        schema = vol.Schema({
            vol.Optional("epub_file"): FileSelector(FileSelectorConfig(accept=".epub")),
            vol.Optional(CONF_EPUB_PATH, default=current.get(CONF_EPUB_PATH, "")): TextSelector(),
            vol.Optional(CONF_LANGUAGE, default=current.get(CONF_LANGUAGE, LANGUAGE_AUTO)): SelectSelector(
                SelectSelectorConfig(options=LANGUAGE_OPTIONS, mode=SelectSelectorMode.LIST)
            ),
            vol.Optional(CONF_SHOW_VERSE_REF, default=current.get(CONF_SHOW_VERSE_REF, True)): BooleanSelector(),
        })

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
