#!/usr/bin/env python3
"""
fightodds_scraper.py — Scrapes opening odds from fightodds.io (leftmost book = BetOnline).

SETUP:
    python -m pip install playwright
    python -m playwright install chromium

RUN:
    python fightodds_scraper.py

OUTPUT:
    odds_data.json  →  then run: python merge_odds.py
"""

import json, re, asyncio
from playwright.async_api import async_playwright

BASE       = "https://fightodds.io"
EVENTS_URL = f"{BASE}/recent-mma-events/ufc"
OUT        = "odds_data.json"

def parse_american(text):
    t = text.strip().replace("\u2212", "-").replace(",", "")
    if not t or t in ("-", "—", "N/A", ""):
        return None
    if t in ("EVEN", "PK", "pk"):
        return 100
    m = re.match(r'^([+-]\d{2,5})$', t)
    if m:
        v = int(m.group(1))
        return v if abs(v) >= 100 else None
    return None

async def wait_for_odds_table(page, timeout=15000):
    """Wait until at least one fighter link appears in a table row."""
    try:
        await page.wait_for_selector(
            "tbody tr a[href*='/fighters/']",
            timeout=timeout
        )
        return True
    except:
        return False

async def scrape_event_odds(page, base_url, event_name):
    """
    Navigate to /odds sub-page. 
    Parse using the exact structure confirmed from HTML dump:
      - tbody rows, one per fighter
      - col 0: <a href="/fighters/..."> = fighter name
      - col 1 button span: first (leftmost = BetOnline) odds value
    """
    url = base_url.rstrip("/") + "/odds"
    try:
        await page.goto(url, wait_until="networkidle", timeout=25000)
    except Exception as e:
        print(f"    Load error: {e}")
        return []

    # Wait for React to render the table
    rendered = await wait_for_odds_table(page, timeout=12000)
    if not rendered:
        # Try one more time with a longer wait
        await page.wait_for_timeout(3000)
        rendered = await wait_for_odds_table(page, timeout=8000)
        if not rendered:
            print(f"    Table never rendered, skipping")
            return []

    # Extra buffer for all rows to paint
    await page.wait_for_timeout(800)

    # Use JS to extract data directly from the DOM — much more reliable than
    # querying row by row with Python async calls
    result = await page.evaluate("""
        () => {
            const rows = Array.from(document.querySelectorAll('tbody tr'));
            const out = [];
            for (const row of rows) {
                const cells = Array.from(row.querySelectorAll('td'));
                if (cells.length < 2) continue;

                // Fighter name: first <a href="/fighters/..."> in col 0
                const link = cells[0].querySelector('a[href*="/fighters/"]');
                if (!link) continue;
                const name = link.innerText.trim();
                if (!name || name.length < 2) continue;

                // First odds column (col 1): get the span text inside the button
                // It may be a <span> inside a <button> or just text
                let oddsText = '';
                const btn = cells[1].querySelector('button');
                if (btn) {
                    // The odds value is in a <span> inside the button label
                    const spans = btn.querySelectorAll('span');
                    for (const sp of spans) {
                        const t = sp.innerText.trim();
                        if (/^[+-]?\d{3,5}$/.test(t)) {
                            oddsText = t;
                            break;
                        }
                    }
                    if (!oddsText) oddsText = btn.innerText.trim().split('\\n')[0];
                } else {
                    oddsText = cells[1].innerText.trim().split('\\n')[0];
                }

                out.push({ name, oddsText });
            }
            return out;
        }
    """)

    if not result:
        print(f"    JS extraction returned 0 rows")
        return []

    print(f"    {len(result)} fighter rows extracted")

    # Parse odds and pair into fights
    fighter_odds = []
    for row in result:
        v = parse_american(row['oddsText'])
        fighter_odds.append((row['name'], v))
        if not fighter_odds or len(fighter_odds) <= 2:
            s = f"+{v}" if v and v > 0 else str(v)
            # (just for first couple, printed below)

    fights = []
    for i in range(0, len(fighter_odds) - 1, 2):
        f1, o1 = fighter_odds[i]
        f2, o2 = fighter_odds[i + 1]
        s1 = f"+{o1}" if o1 and o1 > 0 else str(o1)
        s2 = f"+{o2}" if o2 and o2 > 0 else str(o2)
        print(f"    {f1} ({s1}) vs {f2} ({s2})")
        fights.append({
            "fighter1": f1, "fighter2": f2,
            "odds1": o1, "odds2": o2,
            "event": event_name
        })

    return fights


async def scroll_until_stable(page, max_rounds=120):
    """Scroll until /mma-events/ link count stops growing."""
    stable = 0
    prev = 0
    for _ in range(max_rounds):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(600)
        cur = len(await page.query_selector_all("a[href*='/mma-events/']"))
        if cur == prev:
            stable += 1
            if stable >= 5:   # 5 stable rounds = done
                break
        else:
            stable = 0
        prev = cur
    return prev


async def scrape():
    all_results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124"
        )
        page = await ctx.new_page()

        # ── Load events list + scroll all the way down ──────────────────────
        print(f"Loading: {EVENTS_URL}")
        await page.goto(EVENTS_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2500)

        print("Scrolling to load ALL events (may take ~90 sec)...")
        total = await scroll_until_stable(page, max_rounds=150)
        print(f"Scroll done — {total} raw /mma-events/ links seen")

        # Unique base event URLs: exactly /mma-events/<id>/<slug>
        event_urls = await page.evaluate("""
            () => [...new Set(
                Array.from(document.querySelectorAll('a[href*="/mma-events/"]'))
                    .map(a => a.href)
            )].filter(h => {
                try {
                    const parts = new URL(h).pathname.split('/').filter(Boolean);
                    return parts.length === 3 && parts[0] === 'mma-events';
                } catch(e) { return false; }
            })
        """)
        print(f"Found {len(event_urls)} unique UFC events\n")

        if not event_urls:
            print("ERROR: 0 events found.")
            await browser.close()
            return

        # ── Scrape each event ────────────────────────────────────────────────
        for i, url in enumerate(event_urls):
            slug = url.rstrip("/").split("/")[-1]
            name = slug.replace("-", " ").title()
            print(f"[{i+1}/{len(event_urls)}] {name}")
            fights = await scrape_event_odds(page, url, name)
            all_results.extend(fights)
            # Small polite pause between events
            await page.wait_for_timeout(150)

        await browser.close()

    # Save
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    with_odds = [r for r in all_results if r["odds1"] is not None or r["odds2"] is not None]
    print(f"\n{'='*55}")
    print(f"Scraped {len(event_urls)} events")
    print(f"{len(all_results)} fights total, {len(with_odds)} with odds")
    print(f"Saved → {OUT}")
    print(f"Next  → python merge_odds.py")
    print(f"{'='*55}")

if __name__ == "__main__":
    asyncio.run(scrape())
