# Energy Brief: daily sustainability news to your phone

Every morning at about 7:45am Eastern, a GitHub Action runs `digest.py`. It:

1. Pulls ~18 feeds: Canary Media, Utility Dive, Inside Climate News, Renewable Energy World,
   EIA, Grist, Trellis, Electrek, edie, Carbon Brief, pv magazine, CleanTechnica, and Google News
   searches for solar, energy prices, net zero/emissions, storage and grid, efficiency, and
   sustainable development.
2. Tags each story by topic (Solar, Wind, Storage & Grid, Energy Prices, Carbon & Net Zero,
   Efficiency, Sustainable Development, Policy, Clean Tech) and skips ones already sent.
3. Sends you the top 6 headlines plus a daily book, podcast or documentary pick and a link to the hub page.
4. Saves the stories to `feed.json`, which the hub page shows with search and topic filters.

Hub page: https://dbarlow2004-hub.github.io/endiatx.github.io-workspace/sustainability/

## Study app: track, take notes, flashcards & quizzes

`learn.html` ("🧠 My Library & Study" on the hub) is a Goodreads-plus-Quizlet for everything on the hub:

- **Library:** mark each book, podcast, documentary or YouTube channel as *Want to*, *Reading/Listening/Watching* or *Done*, and rate it 1-5 stars.
  Add your own items (podcast episodes, articles, courses). Tap **＋ Save** on any headline to add it to the library.
- **Notes:** each item has a notes box, a summary with key takeaways, and links to find summaries, transcripts, audiobooks or where to watch.
- **Flashcards:** marking something *Done* unlocks its deck (8 cards per book, 5-6 per podcast or film, plus a 30-card Key Concepts starter deck).
  Reviews use spaced repetition: Again / Hard / Good / Easy schedules the next review just before you'd forget.
- **Quiz & Lightning round:** multiple-choice questions with an explanation after each answer. Answer streaks multiply XP; missed questions return to your flashcard reviews.
- **Game layer:** XP, levels from "Curious" to "Thought Leader", a daily goal ring, a day streak and 13 badges.
- **AI summaries & cards (optional):** paste your notes or a transcript and Claude writes a summary, takeaways and 8-12 new flashcards.
  This needs your own Anthropic API key (console.anthropic.com), entered under Home → Settings. The key is stored only in your browser and each request costs a few cents.

Progress is saved in your browser on that device. Use **Export / Import backup** under Settings to move it to another device.

## Turn on delivery (pick one or more)

Add these under **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**.

### Option A: push notification (free, 2 minutes, recommended)
1. Install the **ntfy** app (iOS / Android).
2. Make up a hard-to-guess topic name, e.g. `energy-brief-x7k29q`, and subscribe to it in the app.
3. Add secret `NTFY_TOPIC` = that topic name.

### Option B: real SMS text (Twilio, about 1¢ per message)
1. Create a Twilio account and buy a toll-free number (US carriers require toll-free
   verification before delivery; submit it in the Twilio console. It's free and takes a few days).
2. Add secrets: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM` (your Twilio number,
   e.g. `+18885551234`), `SMS_TO` (your cell, e.g. `+15555551234`).

Note: the free "email-to-text" carrier addresses (`@vtext.com`, `@txt.att.net`, `@tmomail.net`)
no longer work reliably, because AT&T and T-Mobile have shut theirs down and Verizon is phasing its address out.

### Option C: email digest (full list with links)
1. In your Google account, create an **App password** (requires 2-step verification).
2. Add secrets: `SMTP_USER` (your Gmail address), `SMTP_PASSWORD` (the app password), `EMAIL_TO`.

## Run it now
GitHub → **Actions → Sustainability news digest → Run workflow**.
The daily schedule only runs from the repo's default branch, so merge this branch first.

## Customize
- **Topics / keywords:** edit `TOPICS` in `digest.py`.
- **Sources:** edit `FEEDS` in `digest.py` (any RSS URL, or `gnews('your search')`).
- **Time:** edit the `cron` line in `.github/workflows/sustainability-digest.yml` (UTC).
- **Headlines per text:** `MAX_ITEMS` in the workflow.
- **Books, podcasts, documentaries, companies, glossary:** `resources.json`.

Test locally without sending anything: `python3 sustainability/digest.py --dry-run`
