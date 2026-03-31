"""Constants for Daily Bible Text integration."""

DOMAIN = "daily_bible_text"
NAME = "Daily Bible Text"

# Config entry keys
CONF_EPUB_PATH = "epub_path"
CONF_LANGUAGE = "language"
CONF_SHOW_VERSE_REF = "show_verse_reference"

# Language options
LANGUAGE_AUTO = "auto"
LANGUAGE_DE = "de"
LANGUAGE_EN = "en"
LANGUAGE_ES = "es"

LANGUAGE_DISPLAY = {
    LANGUAGE_DE: "Deutsch",
    LANGUAGE_EN: "English",
    LANGUAGE_ES: "Español",
    LANGUAGE_AUTO: "Auto",
}

# Storage
STORAGE_DIR = "daily_bible_text"
CACHE_VERSION = 2  # bumped for new schema with yeartext

# Sensor state-attribute names
ATTR_DATE = "date"
ATTR_LANGUAGE = "language"
ATTR_SOURCE_EPUB = "source_epub"
ATTR_VERSE_REFERENCE = "verse_reference"
ATTR_ENTRIES_COUNT = "entries_count"
ATTR_EPUB_YEAR = "epub_year"

# German month names
MONTHS_DE = [
    "januar", "februar", "märz", "april", "mai", "juni",
    "juli", "august", "september", "oktober", "november", "dezember",
]
# English month names
MONTHS_EN = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
MONTHS_EN_SHORT = [
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
]
# Spanish month names
MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

WEEKDAYS_DE = [
    "montag", "dienstag", "mittwoch", "donnerstag",
    "freitag", "samstag", "sonntag",
]
WEEKDAYS_EN = [
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
]
WEEKDAYS_ES = [
    "lunes", "martes", "miércoles", "jueves",
    "viernes", "sábado", "domingo",
]
