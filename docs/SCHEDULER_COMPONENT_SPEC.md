# Scheduler Component — Requirements Spec

## Overview
A unified scheduler UI component that provides both simple and advanced modes for configuring agent run schedules. Must be usable both as a full page (`/scheduler`) and embedded in a drawer from the dashboard.

## Design Language
- Light theme with pastel colors
- Consistent with the rest of the app (MUI components, same border radius, same typography scale)
- Info icons (ⓘ) with helpful tooltips on each section

---

## Components

### 1. Mode Toggle
- Basic Mode (frequency dropdowns)
- Advanced Mode (cron expression input)

### 2. Frequency Dropdowns (Basic Mode)
- Base interval selector: Hourly, Daily, Weekly, Monthly
- **Hourly** → shows "Every X hours" selector (1, 2, 4, 6, 8, 12)
- **Daily** → shows time picker (at what time each day)
- **Weekly** → reveals checkbox grid for days (Mon–Sun) + time picker
- **Monthly** → reveals date selector ("On day 15" or "On the last Friday")
- Dynamic reveal: each selection conditionally shows the next relevant input

**ⓘ Tooltip:** "Select your base frequency. The system will automatically generate the execution rule and pick optimal, low-traffic minutes to balance server load."

### 3. Cron Expression Input (Advanced Mode)
- 5 visually separated input boxes: Minutes | Hours | Day of Month | Month | Day of Week
- Inline validation (red border on invalid characters)
- Placeholder text in each box showing allowed values
- Examples below: "0 */2 * * 1-5" = every 2 hours, Mon-Fri

**ⓘ Tooltip:** "Standard 5-field format: Min Hour DayMonth Month DayWeek. Use asterisks (*) for wildcards, commas for lists, and dashes for ranges."

### 4. Live Human-Readable Translator
- Dynamic text below the cron input
- Updates instantly on every keystroke
- Shows plain English: "At 10:15 AM every day" or "Every 2 hours, Monday through Friday"
- Uses cronstrue or equivalent library
- Green text when valid, red when invalid

**ⓘ Tooltip:** "This translates your technical cron expression into plain language in real-time. Always review this text to double-check your schedule before saving."

### 5. Time Zone Selector
- Searchable dropdown with IANA time zones
- Defaults to browser's local timezone
- Shows UTC offset: "America/New_York (UTC-5)"
- DST awareness note

**ⓘ Tooltip:** "All executions lock to this time zone. If your chosen zone observes Daylight Saving Time (DST), the system automatically shifts the execution hour to keep it accurate to local time."

### 6. Upcoming Executions Preview (Next 5 Runs)
- List showing exact future timestamps
- Calculates from the defined schedule
- Shows relative time too: "in 2 hours", "tomorrow at 9:00 AM"
- Updates live when schedule changes

**ⓘ Tooltip:** "A simulated list of the exact upcoming dates and times this job will trigger. Use this to verify that holidays, weekends, or specific intervals are calculating correctly."

---

## Additional Requirements
- Active hours constraint (start/end hour)
- Dry Run toggle
- Urgent Mode toggle (doubles frequency for 7 days)
- Save & Activate button
- "Run Once Now" shortcut

## Technical Notes
- Use `cronstrue` npm package for human-readable translation
- Use `cron-parser` for next-run calculation
- Timezone list from `Intl.supportedValuesOf('timeZone')` or `moment-timezone`
- Component should be reusable: `<SchedulerBuilder onSave={...} />`
