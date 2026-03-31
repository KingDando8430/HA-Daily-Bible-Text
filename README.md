# Daily Bible Text — Home Assistant Integration

A fully offline Home Assistant custom integration that reads daily Bible verse entries from an EPUB file and exposes them as sensors. Supports German, English, and Spanish Watchtower-style EPUB publications.

## Features

- 📖 **Scripture** (`Tagestext` / `Scripture` / `Texto bíblico`) — today's full text, with optional verse reference toggle
- 📌 **Bible Verse** (`Bibelvers` / `Bible Verse`) — Only the text passage
- 💬 **Commentary** (`Kommentar` / `Comment` / `Comentario`) — full commentary ( [currently broken](#problems) / disabled by default)
- 🗓️ **Yeartext** (`Jahrestext` / `Yeartext` / `Texto del año`) — annual year text (disabled by default)
- 📁 **File upload** directly in the HA UI — no SSH or file access needed
- 🔤 **Auto-naming** — integration title set automatically: `Daily Bible Text <year> <langauge>`
- ⚠️ **Outdated EPUB warning** — a repair notice appears if the EPUB year does not match current year
- 🌍 **Multi-language**: German, English, Spanish (more langauges may work / auto-detected from EPUB metadata)
- 🔄 **Midnight refresh** — sensors update automatically at midnight
- 💾 **Smart caching** — EPUB is only re-parsed when the file changes
- 🌐 **Fully offline** — no internet connection required

## Installation

### Manual
1. Copy the `custom_components/daily_bible_text/` folder to `/config/custom_components/`
2. Restart Home Assistant
3. 
    <a href="https://my.home-assistant.io/redirect/integration/?domain=daily_bible_text" target="_blank" rel="noreferrer noopener"><img src="https://my.home-assistant.io/badges/integration.svg" alt="Open your Home Assistant instance and show an integration." /></a>

### HACS (Currently not available)
Add this repository as a custom integration repository in HACS.

## Setup

During setup you can:
- **Upload** the EPUB file directly via drag & drop in the HA config UI
- **Enter a path** to an EPUB already on your server

The integration title is set automatically from the EPUB metadata.

## Sensors

| Entity ID | DE name | EN name | Default |
|-----------|---------|---------|---------|
| `sensor.daily_bible_text_scripture` | Tagestext | Scripture | ✅ enabled |
| `sensor.daily_bible_text_bible_verse` | Bibelvers | Bible Verse | ✅ enabled |
| `sensor.daily_bible_text_commentary` | Kommentar | Comment | [❌ broken](#problems) |
| `sensor.daily_bible_text_yeartext` | Jahrestext | Yeartext | ❌ disabled |

### Sensor attributes

| Attribute | Description |
|-----------|-------------|
| `date` | Today's `MM-DD` key |
| `language` | Detected language |
| `verse_reference` | Extracted Bible reference |
| `source_epub` | Path to the EPUB |
| `entries_count` | Number of daily entries parsed |
| `epub_year` | Year found in EPUB metadata |
| `commentary_full` | Full commentary text (on Commentary sensor) |
| `yeartext_full` | Full yeartext (on Yeartext sensor) |

## Outdated EPUB warning

When the year in the EPUB does not match the current year, a **repair issue** appears in the Home Assistant notification area. To resolve it, upload the current year's EPUB via **Settings → Integrations → Daily Bible Text → Configure**.

## Folder structure

```
/config/
  custom_components/
    daily_bible_text/     ← integration code
  daily_bible_text/
    bible_text.epub       ← uploaded EPUB (or place yours here manually)
    cache_<id>.json       ← auto-generated parse cache
```

## Problems

The commentary is not supported by Home Assistant due to the 255 character limit per sensor. DO NOT make an issue about it.

---

## ⚠️ Legal Notice & Responsibility

This project is **not affiliated with or endorsed by** `jw.org`.

When downloading EPUB files from jw.org, you must comply with their official terms:

* <a href="https://www.jw.org/en/terms-of-use/" target="_blank">Terms of Use (jw.org)</a>
* <a href="https://www.jw.org/en/privacy-policy/" target="_blank">Privacy Policy (jw.org)</a>

All content obtained from jw.org remains the **intellectual property of its respective owner**.

This integration is **not intended for automated scraping, bulk downloading, or mass distribution** of content from jw.org.

By using this integration, you agree that:

* You are **solely responsible** for how you obtain and use any EPUB files
* You must ensure your usage complies with all applicable laws and the terms of jw.org
* This project does **not host, distribute, or modify** any copyrighted content
* You use this software **entirely at your own risk**

## Disclaimer

* ❗ The author provides this project **“as is”**, without any warranty of any kind
* ❗ **No guarantee** is given for correctness, reliability, functionality, or availability
* ❗ The author assumes **zero responsibility and zero liability** for any direct or indirect damages
* ❗ This also includes: data loss, legal issues, misuse, service interruptions, or any other consequences
* ❗ The author is **not responsible for how users obtain, interpret, or use any content**
* ❗ **All responsibility lies entirely with the user**

## Security Notice

* ⚠️ Only use **trusted EPUB files**
* ⚠️ The author is **not responsible for malicious or modified files**

---

## License

MIT License – see [LICENSE](LICENSE)

---

*Icon: AI-generated image.*
