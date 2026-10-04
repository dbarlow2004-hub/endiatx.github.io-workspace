# Energy Brief: daily sustainability news to your phone

Every morning at about 7:45am Eastern, a GitHub Action runs `digest.py`. It:

1. Pulls ~30 feeds from every viewpoint (see "Every side of the issues" below): Canary Media, Utility Dive, Inside Climate News, Renewable Energy World,
   EIA, Grist, Trellis, Electrek, edie, Carbon Brief, pv magazine, CleanTechnica, and Google News
   searches for solar, energy prices, net zero/emissions, storage and grid, efficiency, and
   sustainable development.
2. Tags each story by topic (Solar, Wind, Storage & Grid, Energy Prices, Carbon & Net Zero,
   Efficiency, Sustainable Development, Policy, Clean Tech) and skips ones already sent.
3. Sends you the top 5 headlines, each with a short link straight to the article, plus a daily book, podcast or documentary pick (linked into the study app) and a link to the hub page.
4. Saves the stories to `feed.json`, which the hub page shows with search and topic filters.

Hub page: https://dbarlow2004-hub.github.io/endiatx.github.io-workspace/sustainability/

## Every side of the issues

- **News from every viewpoint.** Each story is tagged:
  - 🌱 Climate press (Canary Media, Grist, Inside Climate News, Carbon Brief...)
  - 📈 Business & markets (Reuters, WSJ, Utility Dive, pv magazine...)
  - 🛢️ Energy industry (Oilprice.com, Rigzone, NGI, POWER)
  - 🗽 Free-market & skeptic (Robert Bryce, Alex Epstein, AEI, Washington Examiner, Fox Business)
  - 🔬 Research & data (EIA, Energy Institute at Haas)
  - ⚖️ All sides (RealClearEnergy)
  The daily text takes turns across viewpoints, so the top 5 never come from one side, and the hub lets you filter by viewpoint.
- **Recommendations from every side.** Books and podcasts carry a viewpoint badge. "Other viewpoints" adds books by Alex Epstein, Robert Bryce, Michael Shellenberger, Bjorn Lomborg, Naomi Klein and Jason Hickel, and podcasts Power Hungry, Decouple and Odd Lots.
- **The big debates** (`debates.json`): 10 contested questions, such as wind and solar pace, nuclear, gas as a bridge, prices, offsets, policy tools, EVs, AI power demand, degrowth and ESG.
  Each has every side's strongest case, who makes it, the evidence they cite and what would settle it. They're on the hub, and the questions form the "Big Debates" deck in the study app.
- **AI notes and cards** always include how other sides see contested claims.

## Career prep (Career tab)

`career.json` holds your career goals and the job you're preparing for:

- **Target companies:** Gensler, Arup and Arcadis. The goal is a big global firm with offices in Los Angeles, San Francisco, New York, Madrid and Paris.
  - **Arcadis:** all five cities.
  - **Arup:** LA, SF, NYC and Madrid; Paris not confirmed.
  - **Gensler:** LA, SF, NYC and Paris; no Madrid.
  - **AECOM:** also has all five, as a backup.

  Each company lists roles to look for and what to emphasize. A "Working in Madrid & Paris" section covers internal transfers, EU work authorization, language, BREEAM, CSRD and the EU Taxonomy, France's RE2020 and Spain's CTE.
- **Open role: Arup Graduate Sustainability Consultant (2027, SF, SAN00013H).**
  - a readiness meter and a month-by-month plan
  - 12 skill areas from the posting, each with what to learn, free resources, a portfolio project and notes
  - credentials: LEED GA, LEED AP BD+C, WELL AP, Fitwel, ENV SP
  - tips for each hiring stage
  - 18 interview questions, with optional Claude feedback on your answers
  - a 40-card "Job prep: Arup" flashcard deck

To prep for another posting, add another entry to `jobs` in `career.json`.

## Podcast transcripts

On any podcast episode in the study app, tap **📝 Get transcript**.

1. The app posts a private request to `<your ntfy topic>-transcribe`.
2. The **Podcast transcripts** workflow (`.github/workflows/podcast-transcripts.yml` + `transcribe.py`) checks every 10 minutes.
3. It uses the show's own published transcript when the feed has one (`<podcast:transcript>`). Otherwise it transcribes the audio with faster-whisper; a 30-minute episode takes about 2-5 minutes.
4. It saves the transcript **encrypted with your topic** in `transcripts/`. The repo is public, but only your app can read the transcripts, and file names are hashed.
5. It sends you a "📝 Transcript ready" notification.

Then tap **🤖 Make notes & cards from transcript**. Claude writes:
- a summary and key points
- numbers worth remembering
- people and companies mentioned
- "How other sides see it"
- 8-12 flashcards

You can also paste a transcript yourself. Requirements: the `NTFY_TOPIC` repo secret must match the topic entered in the app, and making notes needs your Anthropic API key.

## Study app: shelves, reading progress, flashcards & quizzes

`learn.html` ("🧠 My Library & Study" on the hub) works like Ravelry's project tracker, but for books, podcasts, films and articles:

- **Shelves:** 📖 On the go · 🛍️ Bought · 🔖 Want to · ✅ Finished · ✨ Recommended.
  Recommended lists every book, podcast and film from the hub with covers, books ordered beginner → pro.
  Tap **Want**, **Bought** or **Start** right on the tile.
- **Statuses:** Want to, Bought it (books), Reading/Listening/Watching, Paused, Finished, Didn't finish. Pick Print / Ebook / Audiobook per book.
- **Straight to the source:** each item links to Bookshop.org, Amazon, Audible, Spotify audiobooks and your library (WorldCat) for books.
  Podcasts link to Spotify and Apple Podcasts, documentaries to where they're streaming, and YouTube channels to the channel.
  News headlines in the daily text link through `go.html` straight to the article, which is also added to your library as "Reading".
- **Progress & reminders:** log the page you're on (or % for audiobooks). Each item gets a progress bar, a projected finish date and a reading journal.
  Set pages (or minutes) per day and a time, and you get a **phone notification** through the free ntfy app.
  The notification shows today's goal and where you are; tapping it opens the log screen for that book.
  Set it up once under Home → Settings → Phone notifications (you can use the same topic as the news brief).
  Reminders are scheduled up to 3 days ahead (ntfy.sh's limit) and topped up every time you open the app, including by tapping a reminder.
  Logging that day cancels the day's reminder, and pausing or finishing a book stops them.
- **Podcast episodes:** each podcast has its own episode list.
  - **📥 Browse episodes** pulls the show's episodes from Apple Podcasts; **＋ Add by name** works for anything else.
  - Check episodes off as you listen. Each episode gets its own notes, rating, Apple/Spotify links and, with an API key, flashcards made from your notes.
  - Adding an "Episode" from the ＋ Add form lets you file it under one of your podcasts.
- **Checkpoint questions:** book questions unlock page by page as you reach the part where each idea comes up.
  After each logged session you get up to 3 questions on what you've read, with no spoilers. Podcasts, films and channels unlock their cards when finished.
- **Flashcards & quizzes:** spaced-repetition flashcards, 10-question quizzes and a 60-second lightning round with streak multipliers.
  There are 8 cards per book, 5-6 per podcast or film, and a 30-card Key Concepts deck that is open from the start.
- **Game layer:** XP, levels from "Curious" to "Thought Leader", a daily goal ring, a day streak and 14 badges.
- **AI (optional):** with your own Anthropic API key (Home → Settings, stored only in your browser), Claude can:
  - summarize your notes or a pasted transcript into 8-12 flashcards
  - after a reading session, write 3-5 questions on exactly the pages you just read

Progress is saved in your browser on that device. Use **Export / Import backup** under Settings to move it.

## Put it on your home screen

The hub and study app install as one app, "Energy Brief". It has its own icon and works offline.

- **Android (Chrome):** open the study app and tap **📲 Install app** on Home, or Chrome's **⋮ → Install app**.
  Long-press the icon for shortcuts to Today's reading, Study and News.
- **iPhone (Safari):** tap **Share → Add to Home Screen → Add**. If an **Open as Web App** switch appears, turn it **off**.
  iOS keeps a full-screen web app's saved data separate from Safari, and notification taps always open Safari, so leaving it off keeps your progress in one place.

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
- **Headlines per text:** `MAX_ITEMS` in the workflow (5 keeps a text under Twilio's 1,500-character limit).
- **Books, podcasts, documentaries, companies, glossary:** `resources.json`.

Test locally without sending anything: `python3 sustainability/digest.py --dry-run`
