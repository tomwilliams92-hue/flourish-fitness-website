"""Pull Amy's classes from her public Bookwhen page into data/classes.js.

The website reads data/classes.js, so the class cards and the "Coming up" list
always match Bookwhen. A GitHub Action runs this every 3 hours; you can also run
it by hand:  python3 -I update_classes.py

It only rewrites data/classes.js when something has changed. If Bookwhen can't
be read, it stops with an error and leaves the last good file in place.
Standard library only.
"""
import html
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ACCOUNT = 'flourishfitnesswithamy'
BASE = f'https://bookwhen.com/{ACCOUNT}'
OUT = Path(__file__).parent / 'data' / 'classes.js'
UA = 'Mozilla/5.0 (compatible; FlourishFitnessWebsite/1.0)'
DAYS = 'Monday Tuesday Wednesday Thursday Friday Saturday Sunday'.split()
DAY_RE = re.compile(r'\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b', re.I)


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'en-GB'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')


def text(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', html.unescape(s)).strip()


def no_emoji(s):
    s = re.sub(r'[\U0001F000-\U0001FAFF☀-➿️‍⭐⬆↔-↪]', '', s)
    return re.sub(r'[ \t]+', ' ', s).strip()


def clean_title(raw):
    """'Women’s HIIT - Monday 6.30pm' -> 'Women’s HIIT'."""
    t = no_emoji(html.unescape(raw))
    t = re.split(r'\s+-\s+(?=(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\b)', t, flags=re.I)[0]
    return t.replace('Women’s', "Women's").strip(' -')


def key_of(title):
    return re.sub(r'[^a-z0-9+]+', ' ', title.lower()).strip()


def to_24h(t):
    """'6:30pm' -> '18:30'."""
    m = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', t.strip().lower())
    h, mins, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    h = h % 12 + (12 if ap == 'pm' else 0)
    return f'{h:02d}:{mins:02d}'


_pages = {}


def event_page(code):
    if code not in _pages:
        _pages[code] = get(f'{BASE}/e/{code}')
        time.sleep(1)  # be polite to Bookwhen
    return _pages[code]


MONTHS = {m: i + 1 for i, m in enumerate('jan feb mar apr may jun jul aug sep oct nov dec'.split())}


def course_dates(code):
    """Remaining dates of a block booking: [('2026-11-20', '10:15'), ...]."""
    ul = re.search(r'<ul class="datetimes">(.*?)</ul>', event_page(code), re.S)
    out = []
    for li in re.findall(r'<li>(.*?)</li>', ul.group(1) if ul else '', re.S):
        if 'past_event' in li:
            continue
        m = re.search(r"(\d{1,2}) ([A-Za-z]{3}) '(\d{2}).*?([0-9:]+\s*[ap]m)", text(li))
        if m:
            d, mon, yy, tm = m.groups()
            out.append((f'20{yy}-{MONTHS[mon.lower()]:02d}-{int(d):02d}', to_24h(tm)))
    return out


def schedule():
    """Every upcoming session on the public schedule page, with block bookings expanded."""
    page = get(BASE)
    rows = re.findall(r'<tr data-hook="agenda_list_item"[^>]*?data-event="(ev-[a-z0-9]+-(\d{8})\d{6})"(.*?)</tr>', page, re.S)
    out = []
    for code, ymd, body in rows:
        name = re.search(r'<td class="summary">\s*<button[^>]*>(.*?)</button>', body, re.S)
        if not name:
            continue
        raw = text(name.group(1))
        base = {'code': code, 'raw': raw, 'title': clean_title(raw), 'soldOut': 'sold_out' in body}
        tm = re.search(r'class="time_span">\s*([0-9:]+\s*[ap]m)', body)
        if tm:
            out.append({**base, 'date': f'{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}', 'start': to_24h(tm.group(1))})
        elif 'Course:' in body:  # a block listed once: one session per remaining date
            out += [{**base, 'date': d, 'start': t} for d, t in course_dates(code)]
    seen, uniq = set(), []
    for s in sorted(out, key=lambda s: (s['date'], s['start'])):
        if (s['title'], s['date'], s['start']) not in seen:
            seen.add((s['title'], s['date'], s['start']))
            uniq.append(s)
    return uniq


def event(code):
    """Details from one event page (its schema.org JSON-LD)."""
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', event_page(code), re.S)
    d = json.loads(m.group(1))
    loc = d.get('location') or {}
    loc = loc if isinstance(loc, dict) else {'name': str(loc)}
    addr = loc.get('address') or {}
    addr = addr if isinstance(addr, dict) else {'streetAddress': str(addr)}
    tix = tickets(code)
    price = lambda ts: min((t['price'] for t in ts if t['price'] is not None), default=None)
    desc = no_emoji(html.unescape(html.unescape(d.get('description') or '')))
    # skip lines that only repeat the day, time or place; keep the first real description
    paras = [re.sub(r'^Description:\s*', '', p.strip()) for p in re.split(r'\n\s*\n', desc)]
    paras = [re.sub(r'^[^a-z\n]+\n', '', p).strip() for p in paras]  # drop an ALL-CAPS heading line
    paras = [p for p in paras if len(p) > 50 and not re.search(r'\d[:.]\d\d|\d\s*[ap]m\b|Location:|^Starting\b', p, re.I)]
    s, e = d.get('startDate', ''), d.get('endDate', '')
    end = e[11:16] if len(e) >= 16 else ''
    return {
        'end': end,
        'venue': html.unescape(loc.get('name') or ''),
        'street': html.unescape(addr.get('streetAddress') or ''),
        'town': html.unescape(addr.get('addressLocality') or ''),
        'postcode': addr.get('postalCode') or '',
        'payg': price([t for t in tix if not t['course']]),
        'block': price([t for t in tix if t['course']]),
        'description': paras[:1],
        'startIso': s,
    }


def tickets(code):
    """Ticket rows on an event page: price, block or single, spaces left."""
    out = []
    for block in event_page(code).split('<tr class="ticket">')[1:]:
        block = block.split('</tr>')[0]
        p = re.search(r'currency_symbol">[^<]*</span>\s*([0-9.,]+)', block)
        a = re.search(r'data-attrs="([^"]*)"', block)
        attrs = json.loads(html.unescape(a.group(1))) if a else {}
        out.append({
            'price': float(p.group(1).replace(',', '')) if p else (0.0 if 'Free' in block else None),
            'course': 'Course ticket' in block,
            'spaces': attrs.get('available_spaces'),
            'soldOut': bool(attrs.get('sold_out')),
        })
    return out


def spaces_left(code):
    """Spaces left for one dated session (the single-class ticket if there is one)."""
    tix = tickets(code)
    single = [t for t in tix if not t['course']] or tix
    vals = [t['spaces'] for t in single if isinstance(t['spaces'], int)]
    return min(vals) if vals else None


def build():
    sessions = schedule()
    assert sessions, 'No sessions found on the Bookwhen schedule page (has the page layout changed?)'
    classes, seen = [], {}
    for s in sessions:
        k = key_of(s['title'])
        s['key'] = k
        if k in seen:
            continue
        info = event(s['code'])
        # the event page knows the true start; work out the class length from it
        start_dt = info.pop('startIso')
        if start_dt[11:16] and info['end']:
            sh, sm = map(int, start_dt[11:16].split(':'))
            eh, em = map(int, info['end'].split(':'))
            mins = (eh * 60 + em) - (sh * 60 + sm)
        else:
            mins = 0
        wd = datetime.strptime(s['date'], '%Y-%m-%d').weekday()
        c = {
            'key': k, 'title': s['title'],
            'oneOff': not DAY_RE.search(s['raw']),
            'weekday': DAYS[wd], 'start': s['start'], 'minutes': mins,
            'url': f"{BASE}/e/{s['code']}", **info,
        }
        c['blockOnly'] = c['payg'] is None and c['block'] is not None
        c['free'] = (c['payg'] == 0) or (c['payg'] is None and c['block'] == 0)
        seen[k] = c
        classes.append(c)
    for c in classes:
        mine = [s for s in sessions if s['key'] == c['key']]
        c['soldOutAll'] = all(s['soldOut'] for s in mine)
    # spaces left, for the next two weeks only (one page per date, so keep the load on Bookwhen small)
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    soon = datetime.fromtimestamp(time.time() + 14 * 86400, timezone.utc).strftime('%Y-%m-%d')
    for s in sessions:
        s['spaces'] = None
        if not s['soldOut'] and today <= s['date'] <= soon and s['code'].endswith(s['date'].replace('-', '') + s['start'].replace(':', '') + '00'):
            s['spaces'] = spaces_left(s['code'])
    order = {d: i for i, d in enumerate(DAYS)}
    classes.sort(key=lambda c: (c['oneOff'], order[c['weekday']], c['start']))
    keep = ('key', 'title', 'date', 'start', 'soldOut', 'spaces', 'code')
    sessions = [{k: s[k] for k in keep} for s in sessions]
    for s in sessions:
        s['url'] = f"{BASE}/e/{s.pop('code')}"
    return {'source': BASE, 'classes': classes, 'sessions': sessions}


def main():
    try:
        data = build()
    except Exception as e:  # keep the last good file; the Action shows the failure
        print(f'Could not update from Bookwhen: {e}', file=sys.stderr)
        return 1
    old = None
    if OUT.exists():
        m = re.search(r'=\s*(\{.*\});\s*$', OUT.read_text(), re.S)
        old = json.loads(m.group(1)) if m else None
        if old:
            old.pop('checked', None)
    if old == data:
        print('No change on Bookwhen.')
        return 0
    data['checked'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text('/* Made by update_classes.py from Bookwhen. Do not edit by hand. */\n'
                   'window.FLOURISH_CLASSES = ' + json.dumps(data, ensure_ascii=False, indent=1) + ';\n')
    print(f"Updated: {len(data['classes'])} classes, {len(data['sessions'])} upcoming sessions.")
    return 0


if __name__ == '__main__':
    assert clean_title('Women’s HIIT - Monday 6.30pm') == "Women's HIIT"
    assert clean_title('MumFit Lift+ - Fridays 11.15am') == 'MumFit Lift+'
    assert clean_title('Disco Pilates & Prosecco (or Nosecco)🪩') == 'Disco Pilates & Prosecco (or Nosecco)'
    assert to_24h('6:30pm') == '18:30' and to_24h('10:15am') == '10:15' and to_24h('12:05pm') == '12:05'
    sys.exit(main())
