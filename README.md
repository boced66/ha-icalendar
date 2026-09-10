# 📅 iCalendar API integration for Home Assistant

Turn your Home Assistant calendars into a proper iCalendar (`.ics`) feed you can subscribe to from pretty much any calendar app — Apple Calendar, Google Calendar, Outlook, you name it.

> Fork of [chris-y/ha-icalendar](https://github.com/chris-y/ha-icalendar) with a configurable history/future time window. 🕰️

## 🚀 Installation

### HACS (recommended)
1. [Install HACS](https://hacs.xyz/docs/setup/download) if you haven't already.
2. Click the button below — it'll open HACS and add this repo for you ✨

   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=boced66&repository=ha-icalendar&category=integration)
3. Hit **Download**.
4. Restart Home Assistant. ♻️

### Manual install
Copy the `custom_components/icalendar` folder into your Home Assistant `config/custom_components/icalendar` folder, then restart.

## 🛠️ Setup

1. Go to **Settings > Devices & Services > Integrations**.
2. Click **Add integration**, search for **iCalendar API**.
3. Pick **Include selected calendars** or **Exclude selected calendars**.
4. Select which `calendar.*` entities you want in (or out).

Each config entry gives you one combined URL for all matching calendars. Include mode needs at least one calendar selected. Exclude mode with nothing selected exports everything, and automatically picks up any calendar you add later. Old single-calendar feeds keep working exactly as before, as include selections.

## 🔗 URL format

Every feed is tied to its config entry:

```
/api/ics/<entry_id>/<secret>.ics
```

The trailing `.ics` matters for some subscribers (Google Calendar in particular) that decide how to treat a URL partly from its extension — without it, an app may silently accept the subscription and never actually show any events. Feeds created before this `.ics` suffix was added keep working at their original URL too (without the extension), so nothing breaks for existing subscriptions — but if you're seeing an empty calendar in an app you just added, re-copying the URL from the integration's reconfigure/options screen is the first thing to try.

Both the local and external URL (if configured in Home Assistant) are shown in the integration's reconfigure/options screen, so you don't have to build them by hand. You can also rotate the secret from there if a URL ever leaks. 🔐

## ⏳ How much history and future do I get?

By default, your feed includes **4 weeks in the past** and **52 weeks in the future** — but you're not stuck with that! Right from setup, reconfigure, or options, you can dial in:

- **Past events (weeks)** — how far back to reach, from 0 (no past events at all) up to 520 weeks (10 years).
- **Future events (weeks)** — how far ahead to look, from 1 up to 520 weeks.

Want a full year of history for a "look back" view? Set it to 52. Just need next month's agenda and nothing else? Future = 4 is plenty. It's your call. 🎛️

## 🏷️ Naming your feed

By default, a feed shows up in apps like Google Calendar as either the source calendar's own name (single-calendar feed) or plain "iCalendar API" (combined feed) — not always the most useful label when you're juggling a few subscriptions. Set **Feed name** from setup, reconfigure, or options to give it something more recognizable, like "🏠 Family" or "🎉 Kids activities". It also renames the integration entry in Home Assistant, so the two stay in sync. Leave it empty any time to fall back to the default naming. ✏️

## 🎨 Calendar colors

If a feed resolves to a single calendar, its color comes straight from that calendar entity's Home Assistant UI settings — set it there and it'll show up in the feed. Combined feeds (multiple calendars in one URL) skip calendar-level color, since there's no single color that would make sense.

CSS3 color names come through as `COLOR`; hex colors use the `X-APPLE-CALENDAR-COLOR` extension (support for this varies by client).

## 🍏 Apple Calendar locations

Apple Calendar's fancy location field wants coordinates, but Home Assistant's `calendar.get_events` normally only gives you a plain address. Configure an **Address lookup URL** in the feed settings (a Nominatim-compatible search endpoint, e.g. your own `https://geocoder.example/search`) and addresses like `199 Clarence Street, Riccarton` get resolved automatically. Leave it empty to disable this — it's entirely optional. Including city and country in addresses helps avoid ambiguous matches.

Resolved events keep their original `LOCATION` and also gain standard `GEO` plus Apple's `X-APPLE-STRUCTURED-LOCATION` (address, title, and a 100 m radius), which supported clients use for maps and directions. Apple Calendar's actual display of this hasn't been verified in the real app, so your mileage may vary.

A few practical notes:
- 📤 Location text is sent to whichever provider you configure — pick one that fits your privacy comfort level.
- ⏱️ Lookups happen on subscription refresh: at most one new request every 15 seconds across all feeds, 3-second timeout. Unresolved addresses just try again on the next refresh; cached ones show up instantly.
- 💾 Successful lookups are cached 90 days across restarts; misses/ambiguous results for 7 days. Provider errors back off for a minute. A location that never resolves stays as plain text — it never blocks the feed from loading.
- 🗃️ The shared cache holds up to 2,000 lookups, keyed by provider + address. Switching providers starts a fresh cache; disabling lookup just stops adding the extra metadata.

**Using the public Nominatim service?** Please read the [usage policy](https://operations.osmfoundation.org/policies/nominatim/) first — no confidential/personal data, attribution required, and a hard limit of 4 requests/minute with no distributed bulk use. This integration's rate limiter only applies per Home Assistant instance, so it can't enforce policy across multiple installs — for anything beyond light personal use, run your own or a suitably licensed hosted instance. OpenStreetMap geocoding data is © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), under the ODbL.

## ⚙️ Configuration parameters

- **Setup**
  - `feed_name`: optional custom name for the feed, shown in apps like Google Calendar or Apple Calendar. Leave empty to use the default name (the source calendar's name for a single-calendar feed, or "iCalendar API" for a combined feed).
  - `selection_mode`: `include` or `exclude`.
  - `calendar_entity_ids`: calendars to include or exclude.
  - `history_weeks`: how far back to include past events, in weeks. Default `4` (~a month). `0` excludes past events entirely.
  - `future_weeks`: how far ahead to include upcoming events, in weeks. Default `52` (~a year).
- **Reconfigure**
  - `feed_name`: change the displayed name without changing the URL. Also updates the integration entry's title in Home Assistant.
  - `selection_mode` / `calendar_entity_ids`: change the selection without changing the URL.
  - `history_weeks` / `future_weeks`: change the exported time window without changing the URL.
  - `secret`: optional new secret (min. 20 ASCII letters/digits/underscores/hyphens). Leave blank to keep the current one.
- **Options**
  - Same as reconfigure, plus viewing the current feed URLs — all without leaving the integration page.

## 🧩 Installation parameters

- Set Home Assistant's `internal_url` and/or `external_url` so the UI can show you full, ready-to-copy feed URLs.
- Calendar selection needs entities to already be registered; startup doesn't wait around for source calendars to appear.

## ✅ Supported functionality

- Secure iCalendar feed endpoint: `GET /api/ics/<config_entry_id>/<secret>.ics` (also reachable without the `.ics` suffix, for feeds created before it was added).
- Exports events from every matching Home Assistant calendar entity.
- Emits calendar-level `COLOR` from Home Assistant's calendar UI color settings, when available.

## 🔄 Data update behavior

- On startup, previously saved events are restored instantly — no waiting on source calendars.
- Feed requests fetch every source calendar concurrently via `calendar.get_events`, 15-second timeout per source.
- Successful fetches (even empty ones) get saved per entry/source. If a source is missing, unavailable, failing, or timed out, its last saved snapshot is used instead — which can go stale if a source stays broken for a while.
- If a selected source has never successfully synced, the whole feed returns `503` rather than silently dropping events (so subscribers don't mistake "not fetched yet" for "deleted"). Other feed entries aren't affected.
- Exclude mode keeps previously cached sources around during startup, even before their entities show up. To drop a source for good, exclude it explicitly — or just delete the config entry to wipe its saved events.
- The exported time window defaults to 4 weeks back / 52 weeks ahead, and is fully configurable per feed (up to 520 weeks either way) from setup, reconfigure, or options. 🕰️

## 💡 Use cases

- Subscribe to your Home Assistant calendars from any external app that speaks ICS.
- Share a read-only view of your calendars with someone else, using a per-entry secret URL.

## 🧪 Example

```
https://home.example.com/api/ics/01ABCDEF1234567890/your_long_secret.ics
```

## ⚠️ Known limitations

- Feed security is secret-in-URL based — treat these URLs like passwords.
- Event IDs stay stable for unchanged occurrences, scoped to their source calendar. Without a source UID, identity is derived from summary + start time, so editing either changes the ID. Genuinely identical events from the same source can't be told apart.
- Calendar data is read live at request time, so response speed depends on how fast your calendar backend answers.

## 🩺 Troubleshooting

| Response | What it means |
|---|---|
| `401 Unauthorized` | The secret in the URL doesn't match the config entry's secret. |
| `403 Forbidden` | Malformed path/secret, or a non-calendar entity was referenced. |
| `404 Not Found` | That entry ID doesn't exist. |
| `503 Service Unavailable` | The entry is unloaded, or a source has no cached results yet. (An empty calendar still returns a valid `200` feed.) |

If the UI isn't showing you full feed URLs, double-check `internal_url` / `external_url` under Home Assistant's network settings.

## 🗑️ Removal instructions

1. Go to **Settings > Devices & Services > Integrations**.
2. Open **iCalendar API**.
3. Delete the config entry.
4. Don't forget to update or remove any ICS subscriptions that pointed at that entry's URL!

## 🔒 Security notes

- Secret checks use constant-time comparison, to avoid timing attacks.
- iCalendar output escapes reserved characters and folds long lines for better parser safety and compatibility.

## 🧑‍💻 Development tests

```bash
python -m pip install -r requirements-test.txt
python -m pytest
```

Tests run against small Home Assistant boundary doubles plus the real pinned ICS library — handy for fast iteration, but no substitute for testing against a real running Home Assistant instance. 🏡
