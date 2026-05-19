# Networking Supervision Plan

> **For Hermes:** Use this plan to establish a weekly networking monitoring pipeline connected to the MemRetrievalEnigma Obsidian vault.

**Goal:** Build a persistent system to discover, track, and supervise networking events, congresses, and professional opportunities every week.

**Architecture:** A weekly cron job queries event sources (web search, APIs, RSS feeds), aggregates new findings, and appends structured updates to the MemRetrievalEnigma Obsidian vault. Manual review and action items are managed inside the vault.

**Tech Stack:** Hermes cronjob, web search, Obsidian vault (filesystem markdown), browser tools for deep dives.

---

## Current Context

- Obsidian vault location (iCloud): `/Users/atabaresa/Library/Mobile Documents/iCloud~md~obsidian/Documents/MemRetrievalEnigma`
- Vault initialized with: `Networking Hub.md` (master tracker)
- No automated monitoring exists yet.

---

## Step-by-Step Plan

### Task 1: Finalize Event Sources and Keywords

**Objective:** Define exactly what industries, roles, geographies, and keywords to monitor.

**Files:**
- Modify: `MemRetrievalEnigma/Networking Hub.md`

**Actions:**
1. Ask the user for:
   - Industry / field (e.g., data governance, AI/ML, tech policy)
   - Preferred geographies (e.g., Spain, Europe, global)
   - Event types (congresses, meetups, webinars, hackathons)
   - Communities or platforms they already follow
2. Write the answers into a new note: `MemRetrievalEnigma/Networking Configuration.md`

---

### Task 2: Create Weekly Cron Monitoring Job

**Objective:** Schedule a recurring Hermes cronjob that runs every week to search for upcoming events.

**Actions:**
1. Create cronjob with `cronjob(action="create", ...)`
2. Schedule: every Monday at 09:00 (`0 9 * * 1`)
3. Prompt the cron agent to:
   - Search the web for upcoming events matching the configured keywords
   - Look at major event platforms (Eventbrite, Meetup, LinkedIn Events, congress websites)
   - Compile a short list: event name, date, location, URL, relevance score
   - Append the results to `MemRetrievalEnigma/Networking Weekly Report YYYY-WNN.md`
   - Update `Networking Hub.md` with any high-priority items

---

### Task 3: Build Vault Supervision Structure

**Objective:** Prepare the MemRetrievalEnigma vault to receive and organize cron outputs.

**Files:**
- Create: `MemRetrievalEnigma/Templates/Weekly Report Template.md`
- Create: `MemRetrievalEnigma/People/Contacts.md`
- Create: `MemRetrievalEnigma/Events/Upcoming.md`
- Create: `MemRetrievalEnigma/Events/Archive.md`

**Actions:**
1. Write a markdown template for weekly reports so the cron agent has a consistent format.
2. Ensure all new notes are linked from `Networking Hub.md` via wikilinks.

---

### Task 4: Validate End-to-End Pipeline

**Objective:** Run a one-shot test of the cron logic before leaving it on autopilot.

**Actions:**
1. Trigger the cron script/prompt manually once (`cronjob(action="run")`)
2. Verify:
   - A new weekly report note is created in the vault
   - The report contains actual event data
   - `Networking Hub.md` links are intact
3. Fix any path or formatting issues.

---

### Task 5: Ongoing Supervision & Tuning

**Objective:** Human-in-the-loop review every week.

**Actions:**
1. User reviews the weekly report note in Obsidian.
2. User marks interesting events for follow-up.
3. Every month, review the `Networking Configuration.md` keywords and adjust if needed.
4. If the cron output quality degrades, update the cron prompt or add new data sources.

---

## Risks & Open Questions

- **Vault sync delay:** iCloud Obsidian sync may lag; if so, switch to a local vault path.
- **Search quality:** Generic web search may miss niche congresses; may need site-specific scraping or RSS feeds.
- **Rate limits:** Frequent web searches could hit rate limits; consider caching or slower cadence.
- **User availability:** The user must actually read the weekly notes for the system to work.

---

## Verification Checklist

- [ ] MemRetrievalEnigma vault exists and is visible in Obsidian
- [ ] `Networking Hub.md` opens correctly
- [ ] Weekly cronjob appears in `cronjob(action="list")`
- [ ] One manual run produced a populated weekly report
- [ ] User knows where to find the reports
