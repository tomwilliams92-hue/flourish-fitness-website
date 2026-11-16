# Flourish Fitness with Amy: website

One page (`index.html`), no build step.

## Where the classes come from

Amy only has to keep **Bookwhen** up to date. The site does the rest:

- `update_classes.py` reads her public Bookwhen page (bookwhen.com/flourishfitnesswithamy) and writes `data/classes.js`: every class, its day, time, venue, prices, whether it's fully booked, the next dates, and the spaces left over the next two weeks.
- The page builds the class cards, the "Coming up" list, the special-event card and each venue's class list from that file.
- Every 3 hours Tom's iMac runs it (launchd job `com.tw.flourish-classes`, script `~/Tools/flourish-sync/sync.sh`, log `sync.log` beside it) and pushes `data/classes.js` when something has changed, so the live site follows Bookwhen on its own. It pauses while the Mac is off.
- To move it off the Mac: give the GitHub token `workflow` scope and add `update-classes.yml` (kept in the Google Drive copy under `.github/workflows/`) to this repo. GitHub then runs it every 3 hours instead; unload the launchd job afterwards.
- Run it by hand any time: `python3 -I update_classes.py`

A new class added on Bookwhen appears on the site automatically, using the first paragraph of its Bookwhen description. To give it nicer wording and tags, add an entry to `INFO` near the bottom of `index.html`.

Two weekly classes aren't on Bookwhen, so they're typed into `EXTRA` in `index.html`: **Chair Pilates** (Tuesdays 9.30am, just turn up) and **Sensory Steps** (Tuesdays 1.30pm, booked through Babi Actif). If Amy puts either on Bookwhen, the typed one drops out by itself.

If Bookwhen ever changes its page layout, the script stops with an error and the site keeps the last good list. The longer-term fix is Bookwhen's API (Amy would create a read-only API token in Bookwhen's settings).

## Other content

- Google reviews: 5.0 from 21 reviews (checked 16.11.2026). The eight quotes are typed in; update the count in the hero badge and the reviews section when it changes.
- Photos: from Amy's Instagram. `img/amy.jpg` is cropped from her "Hey, I'm Amy" post, with the overlay text removed from her hair.
- Live preview: https://tomwilliams92-hue.github.io/flourish-fitness-website/
- `noindex` is set in the page head while it's a preview. Remove it when the site goes live on its own domain.
