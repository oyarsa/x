Great — I’d bake in **default duration = 1 hour**.

Here’s a detailed product specification for the Python TUI.

## 1. Purpose

A local-first Python terminal UI that lets you:

1. capture **selected text** or an **image** from the clipboard on macOS, or pass a file
   path,
2. extract appointment details with a **vision-capable LLM**,
3. review and edit the extracted fields,
4. choose a target Google Calendar from the user’s available calendars,
5. configure reminders,
6. create the event in Google Calendar.

The integration should use:

* the **OpenAI Responses API** for text/image-to-structured-data extraction, which is
  the recommended API for new OpenAI projects and supports image inputs plus structured
  JSON outputs, and
* the **Google Calendar API** to list calendars and create events. ([OpenAI
  Developers][1])

## 2. Non-goals

Out of scope for v1:

* recurring events,
* attendee invites,
* conferencing links,
* OCR-only fallback engines,
* automatic address geocoding,
* fuzzy deduplication against existing events,
* direct parsing of PDFs or emails.

## 3. Primary use cases

### A. Screenshot flow

User copies a screenshot like the hospital appointment image, opens the TUI, and
confirms a prefilled event.

### B. Selected text flow

User copies text such as:

> General Nephrology @ Croydon University Hospital
> Tuesday 23 June 2026 2:00pm

The TUI parses it into a structured draft event.

### C. File input flow

User runs the app with an image or text file path and reviews the extracted appointment
before saving. If the path is `-`, the app reads from standard input.

## 4. Core requirements

### 4.1 Inputs

The app must support:

* clipboard text,
* clipboard image,
* explicit image or text file path,
* optional pasted freeform text inside the TUI.

### 4.2 Extraction

The app must send either:

* text directly, or
* image input

to an LLM through the **Responses API**, and require a **structured JSON** response
conforming to a schema defined by the app. OpenAI’s Structured Outputs feature is
designed for this exact "must match my JSON schema" workflow. ([OpenAI Developers][2])

### 4.3 Review-before-create

The app must **never** create a calendar event immediately from model output.
It must always show an editable confirmation screen first.

### 4.4 Calendar discovery

The app must fetch the user’s available calendars using `calendarList.list`, which
returns the calendars on the user’s calendar list. ([Google for Developers][3])

### 4.5 Calendar defaulting

Calendar choice behavior:

1. if `default_reminder_method` is defined and a calendar with this name exists,
   preselect it;
2. otherwise prefer the user’s **primary** calendar;
3. otherwise select the first writable calendar returned.

Google Calendar’s API supports listing calendars and also recognizes `"primary"` as the
primary calendar identifier. ([Google for Developers][3])

### 4.6 Reminder UI

The TUI must expose reminder presets:

* 10 min
* 30 min
* 1 hour
* 4 hours
* 1 day

The user can select multiple reminders.

The remainder method is always **popup**.

Google Calendar reminder overrides support `popup` and `email`, and event-specific
reminder overrides require `useDefault=false`. The API allows a maximum of **5**
override reminders. ([Google for Developers][4])

### 4.7 Duration rule

If no end time or duration is inferable:

* default event duration = **1 hour**

## 5. User flow

### 5.1 Startup

On launch, the app shows a compact menu:

* Capture from clipboard
* Load image from file
* Paste text manually
* Settings
* Quit

### 5.2 Capture phase

If "Capture from clipboard":

* if clipboard has image, prefer image
* else if clipboard has text, use text
* else show "No usable clipboard content found"

### 5.3 Extraction phase

The app sends content to the model with a prompt instructing it to:

* extract a single appointment/event,
* normalize ambiguous date/time fields,
* preserve source wording where useful,
* return only schema-compliant JSON,
* mark uncertainty explicitly.

### 5.4 Review phase

Display a form with editable fields:

* Title
* Date
* Start time
* End time
* Duration
* Location
* Notes
* Calendar
* Reminder method
* Reminder presets
* Confidence / warnings

Keyboard actions:

* Tab / Shift-Tab move between fields
* Space toggles reminder presets
* j/k and up/down arrow select next/previous item
* Enter confirms
* Esc cancels or goes back
* `e` toggles raw extracted JSON/debug pane
* `r` re-run extraction
* `s` save event

### 5.5 Create phase

On save:

* validate required fields,
* call `events.insert`,
* show success screen with created event summary.

Google Calendar’s `events.insert` is the standard API method for creating an event.
([Google for Developers][5])

## 6. Extraction contract

The model output must conform to a schema like this:

```json
{
  "title": "string",
  "date": "YYYY-MM-DD | null",
  "start_time": "HH:MM | null",
  "end_time": "HH:MM | null",
  "duration_minutes": "integer | null",
  "location": "string | null",
  "notes": "string | null",
  "source_summary": "string | null",
  "confidence": "high | medium | low",
  "warnings": ["string"],
  "detected_timezone": "string | null"
}
```

### Schema rules

* `title` should be concise and human-usable.
* `date` is required before save.
* `start_time` is required before save.
* if `end_time` is null and `duration_minutes` is null, app sets 60 minutes.
* `warnings` must include ambiguity such as:
  * "date inferred from weekday + date text"
  * "location may contain department code"
  * "no explicit end time found"

Because this app depends on reliable structured output rather than freeform prose,
schema-constrained model responses should be treated as mandatory. ([OpenAI
Developers][6])

## 7. Prompting behavior

### 7.1 System/developer intent

The extraction prompt should tell the model:

* You are extracting exactly one calendar event.
* Prefer precision over creativity.
* Do not invent missing data.
* If uncertain, leave the field null and add a warning.
* Preserve institutional names faithfully.
* Separate title from location where possible.
* Return only valid JSON matching the schema.

### 7.2 Heuristics the model should follow

* "General Nephrology @ Croydon University Hospital-RJ6"
  should typically become:
  * title: `General Nephrology`
  * location: `Croydon University Hospital-RJ6`
* If only one time is present, treat it as start time.
* If "Booked appointment" or something uninformative like this appears, ignore it as a
  generic header unless there is no better title.
* If weekday and numeric date disagree, warn rather than silently correcting.

## 8. Calendar selection behavior

When calendars are fetched:

* show name,
* show whether primary,
* allow fuzzy filter.

Selection logic:

1. exact name match on name in `default_calendar_name` if defined
2. fallback to primary
3. fallback to first selectable calendar

The UI should remember the last chosen calendar locally for convenience, but still
recalculate suggestions from the fresh calendar list on startup.

## 9. Reminder model

### 9.1 Default state

* method: `popup`
* selected reminders:

  * 30 min
  * 1 hour

### 9.2 Available presets

* 10 min = 10
* 30 min = 30
* 1 hour = 60
* 4 hours = 240
* 1 day = 1440

These all fit Google Calendar’s reminder override rules. The API documents valid reminder minutes and the supported methods. ([Google for Developers][7])

### 9.3 Modes

* `default`: use calendar defaults, ignore explicit preset list
* `popup`: explicit popup overrides
* `email`: explicit email overrides

### 9.4 Validation

* max 5 reminders selected
* no duplicate reminder minutes
* if explicit reminders selected, set `useDefault=false`

## 10. Validation rules before save

The event cannot be created until:

* title is non-empty
* date is present
* start time is present
* calendar is selected

On save:

* if end time missing, compute from duration or default 1 hour
* if location missing, allow save
* if confidence is low, show a final confirmation prompt

## 11. Error handling

### 11.1 Extraction errors

Show a recoverable error state for:

* no clipboard content
* unsupported image format
* API timeout
* malformed model JSON
* extraction with missing date/time

User actions:

* retry
* edit fields manually
* cancel

### 11.2 Google auth/API errors

Show explicit messages for:

* not signed in
* OAuth token expired
* no writable calendar found
* event creation failed

### 11.3 Partial extraction

If the model returns title/location but no date/time:

* populate what is known,
* focus the cursor on date,
* show warnings.

## 12. Authentication and credentials

### 12.1 OpenAI

Use API key from environment or config file.

### 12.2 Google Calendar

Use installed-app OAuth for a desktop app.
Persist tokens locally in the user config directory.

Minimum scopes for v1:

* read calendar list
* create events

## 13. Privacy and data handling

User-facing privacy expectations:

* clipboard/file content is sent to the configured LLM provider for extraction,
* calendar metadata and event creation go to Google,
* no local history is stored unless explicitly enabled,
* debug logs must redact tokens and auth secrets.

Optional config:

* `save_last_extraction=false`
* `debug_json=false`

## 14. Suggested TUI structure

### Screens

1. Home
2. Loading / extracting
3. Review form
4. Calendar picker
5. Reminder picker
6. Success
7. Error modal

### Layout on review screen

Left pane:

* extracted fields form

Right pane:

* source preview

  * OCR’d/image summary or pasted text
* warnings
* raw JSON toggle

Bottom action row:

* Back
* Re-extract
* Save

## 15. Configuration

Local config file should support:

```toml
default_calendar_name = "<default>"
default_duration_minutes = 60
default_reminder_method = "popup"
default_reminder_minutes = [10, 30]
timezone = "<default>"
model = "vision-default"
store_tokens_securely = true
show_debug_json = false
```

`init` subcommand create the configuration file with the defaults, then prompts the user
to change them. Timezone is inferred from the OS. The default calendar name defaults for
the user Calendar's default.

## 16. Suggested internal modules

This is still spec, not implementation, but the design should separate:

* `input_capture`
* `extractor`
* `schema`
* `calendar_provider`
* `reminders`
* `ui`
* `config`
* `logging`

That keeps the LLM extraction layer swappable without rewriting the TUI.

## 17. Acceptance criteria

The app is successful if:

1. A user can copy the hospital appointment screenshot, launch the app, and reach a
   populated review form.
2. The default calendar is `Compromissos` when present.
3. Reminder presets are visible and editable.
4. If no end time exists, the event defaults to 1 hour.
5. The user can correct any extracted field before saving.
6. The event is created in the selected Google Calendar with the selected reminder
   behavior. Google Calendar supports both calendar listing and event creation through
   the documented endpoints above. ([Google for Developers][3])

## 18. Recommended v1 decisions

These are the choices I’d lock in now:

* **Extraction backend:** OpenAI Responses API with image/text input and
  schema-constrained JSON output. ([OpenAI Developers][1])
* **Always require confirmation before save**
* **Default calendar name:** `Compromissos`
* **Fallback duration:** 60 minutes
* **Default reminder method:** `popup`
* **Default reminders:** 10 min + 30 min
* **Manual edit always available**
* **No recurring events in v1**

[1]: https://developers.openai.com/api/docs/guides/migrate-to-responses/?utm_source=chatgpt.com "Migrate to the Responses API"
[2]: https://developers.openai.com/api/reference/resources/responses/methods/create/?utm_source=chatgpt.com "Create a model response | OpenAI API Reference"
[3]: https://developers.google.com/workspace/calendar/api/v3/reference/calendarList/list?utm_source=chatgpt.com "CalendarList: list | Google Calendar"
[4]: https://developers.google.com/workspace/calendar/api/concepts/reminders?utm_source=chatgpt.com "Reminders & notifications | Google Calendar"
[5]: https://developers.google.com/workspace/calendar/api/v3/reference/events/insert?utm_source=chatgpt.com "Events: insert | Google Calendar"
[6]: https://developers.openai.com/api/docs/guides/structured-outputs/?utm_source=chatgpt.com "Structured model outputs | OpenAI API"
[7]: https://developers.google.com/workspace/calendar/api/v3/reference/events/instances?utm_source=chatgpt.com "Events: instances | Google Calendar"
