"""
ufc_enrich_v2.py
=================
Fixes all remaining missing fields in ufc_fights_enriched.csv:
  1. method          — was using wrong CSS selector, now fixed
  2. event_date      — scrapes from event pages (763 pages, fast)
  3. event_location  — same
  4. country1/2      — Wikipedia fighter pages (has nationality data)

Requirements:
    pip install requests beautifulsoup4 pandas

Usage:
    python ufc_enrich_v2.py

Output:
    ufc_fights_final.csv
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
import json
import os
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
DELAY = 0.5
NATIONALITY_CACHE = "nationality_cache_v2.json"
EVENT_CACHE = "event_cache.json"
CHECKPOINT = "ufc_fights_final_checkpoint.csv"

def load_json(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)

def get(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            return r
        except Exception as e:
            log.warning(f"Attempt {attempt+1} failed: {url} — {e}")
            time.sleep(2 ** attempt)
    return None

# ─────────────────────────────────────────────
# FIX 1: Method — correct selector
# The method value is inside b-fight-details__text-item_first
# as a child <i style="font-style: normal">
# ─────────────────────────────────────────────
def scrape_method(fight_url):
    r = get(fight_url)
    if not r:
        return ""
    soup = BeautifulSoup(r.text, "html.parser")

    # The full text block: "Method: Decision - Unanimous Round: 3 ..."
    text_block = soup.select_one("p.b-fight-details__text")
    if text_block:
        full_text = text_block.get_text(" ", strip=True)
        # Extract method value between "Method:" and "Round:"
        match = re.search(r"Method:\s*(.+?)\s+Round:", full_text)
        if match:
            return match.group(1).strip()

    # Fallback: find the first item and get the non-label child
    first_item = soup.select_one("i.b-fight-details__text-item_first")
    if first_item:
        # Remove the label "Method:" text, get the value
        label = first_item.select_one("i.b-fight-details__label")
        if label:
            label.decompose()
        return first_item.get_text(" ", strip=True).strip()

    return ""

# ─────────────────────────────────────────────
# FIX 2: Event date & location
# Scrape from UFCStats event pages
# ─────────────────────────────────────────────
def scrape_event_info(event_url, event_cache):
    if event_url in event_cache:
        return event_cache[event_url]

    r = get(event_url)
    if not r:
        event_cache[event_url] = {}
        return {}

    soup = BeautifulSoup(r.text, "html.parser")
    info = {}

    for li in soup.select("li.b-list__box-list-item"):
        text = li.get_text(" ", strip=True)
        if text.startswith("Date:"):
            info["event_date"] = text.replace("Date:", "").strip()
        elif text.startswith("Location:"):
            info["event_location"] = text.replace("Location:", "").strip()

    event_cache[event_url] = info
    time.sleep(DELAY)
    return info

# ─────────────────────────────────────────────
# FIX 3: Nationality from Wikipedia
# Search Wikipedia for fighter, extract nationality from intro
# ─────────────────────────────────────────────

# Common nationality keywords to look for in Wikipedia intros
NATIONALITIES = [
    "American", "Brazilian", "Russian", "British", "Canadian", "Australian",
    "Irish", "French", "Dutch", "Swedish", "Polish", "Mexican", "Japanese",
    "Korean", "Chinese", "Nigerian", "Cameroonian", "Georgian", "Kazakh",
    "Kyrgyz", "Czech", "South African", "Ecuadorian", "New Zealand",
    "German", "Spanish", "Italian", "Portuguese", "Romanian", "Ukrainian",
    "Belarusian", "Azerbaijani", "Armenian", "Uzbek", "Tajik", "Mongolian",
    "Thai", "Filipino", "Indonesian", "Senegalese", "Congolese", "Ghanaian",
    "Jamaican", "Trinidad", "Puerto Rican", "Venezuelan", "Colombian",
    "Peruvian", "Argentine", "Chilean", "Bolivian", "Panamanian",
    "Costa Rican", "Nicaraguan", "Honduran", "Guatemalan", "Dominican",
    "Cuban", "Haitian", "Bahamian", "Scottish", "Welsh", "Northern Irish",
    "Israeli", "Iranian", "Turkish", "Lebanese", "Jordanian", "Saudi",
    "Emirati", "Pakistani", "Indian", "Bangladeshi", "Sri Lankan",
    "Nepali", "Afghan", "Serbian", "Croatian", "Bosnian", "Slovenian",
    "Slovak", "Hungarian", "Bulgarian", "Greek", "Finnish", "Norwegian",
    "Danish", "Icelandic", "Swiss", "Austrian", "Belgian", "Luxembourg",
]

def get_nationality_wikipedia(fighter_name, cache):
    if fighter_name in cache:
        return cache[fighter_name]

    # Search Wikipedia
    search_url = f"https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": f"{fighter_name} MMA fighter",
        "format": "json",
        "srlimit": 1,
    }

    try:
        r = requests.get(search_url, params=params, headers=HEADERS, timeout=10)
        data = r.json()
        results = data.get("query", {}).get("search", [])
        if not results:
            cache[fighter_name] = ""
            return ""

        page_title = results[0]["title"]

        # Fetch the page extract
        extract_url = "https://en.wikipedia.org/w/api.php"
        params2 = {
            "action": "query",
            "prop": "extracts",
            "exintro": True,
            "explaintext": True,
            "titles": page_title,
            "format": "json",
        }
        r2 = requests.get(extract_url, params=params2, headers=HEADERS, timeout=10)
        data2 = r2.json()
        pages = data2.get("query", {}).get("pages", {})
        extract = ""
        for page in pages.values():
            extract = page.get("extract", "")
            break

        if not extract:
            cache[fighter_name] = ""
            return ""

        # Find nationality in first 500 chars of intro
        intro = extract[:500]
        for nat in NATIONALITIES:
            if nat.lower() in intro.lower():
                cache[fighter_name] = nat
                time.sleep(DELAY)
                return nat

        # Fallback: try to find "born in X" or "from X"
        cache[fighter_name] = ""
        time.sleep(DELAY)
        return ""

    except Exception as e:
        log.warning(f"Wikipedia lookup failed for {fighter_name}: {e}")
        cache[fighter_name] = ""
        return ""

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    # Load enriched CSV
    df = pd.read_csv("ufc_fights_enriched.csv", dtype=str)
    log.info(f"Loaded {len(df)} fights")

    # Load caches
    nat_cache = load_json(NATIONALITY_CACHE)
    event_cache = load_json(EVENT_CACHE)
    log.info(f"Nationality cache: {len(nat_cache)} entries")
    log.info(f"Event cache: {len(event_cache)} entries")

    # Load checkpoint
    done_methods = set()
    if os.path.exists(CHECKPOINT):
        cp = pd.read_csv(CHECKPOINT, dtype=str)
        done_methods = set(cp[cp["method"].notna() & (cp["method"] != "nan")]["fight_url"].tolist())
        df = cp.copy()
        log.info(f"Checkpoint: {len(done_methods)} fights already have method")

    # ── STEP 1: Get event dates (scrape event pages) ──
    log.info("=== STEP 1: Event dates & locations ===")
    
    # Get all event URLs from the original events list
    events_r = get("http://ufcstats.com/statistics/events/completed?page=all")
    if events_r:
        events_soup = BeautifulSoup(events_r.text, "html.parser")
        event_links = {}
        rows = events_soup.select("tr.b-statistics__table-row")
        for row in rows:
            name_el = row.select_one("td a")
            if name_el:
                name = name_el.get_text(strip=True)
                href = name_el.get("href", "")
                # Get date from same row
                date_el = row.select_one("span.b-statistics__date")
                loc_el = row.select("td")
                date_text = date_el.get_text(strip=True) if date_el else ""
                loc_text = loc_el[1].get_text(strip=True) if len(loc_el) > 1 else ""
                event_links[name] = {"url": href, "date": date_text, "location": loc_text}

        log.info(f"Found {len(event_links)} events from list page")

        # Fill in event dates directly from list page (no extra requests needed!)
        for idx, row in df.iterrows():
            event_name = row.get("event_name", "")
            if event_name in event_links:
                info = event_links[event_name]
                if info.get("date"):
                    df.at[idx, "event_date"] = info["date"]
                if info.get("location"):
                    df.at[idx, "event_location"] = info["location"]

        log.info(f"Event dates filled: {df['event_date'].notna().sum()}")
        time.sleep(DELAY)

    # ── STEP 2: Method ──
    log.info("=== STEP 2: Fight methods ===")
    need_method = df[df["method"].isna() | (df["method"] == "nan")]["fight_url"].tolist()
    log.info(f"Fights needing method: {len(need_method)}")

    for i, fight_url in enumerate(need_method):
        if not fight_url or fight_url == "nan":
            continue
        log.info(f"[{i+1}/{len(need_method)}] Method scrape: {fight_url}")
        method = scrape_method(fight_url)
        if method:
            df.loc[df["fight_url"] == fight_url, "method"] = method
        time.sleep(DELAY)

        if (i + 1) % 100 == 0:
            df.to_csv(CHECKPOINT, index=False)
            log.info(f"Checkpoint saved ({i+1} methods done)")

    log.info(f"Methods filled: {df['method'].notna().sum()}")

    # ── STEP 3: Nationality from Wikipedia ──
    log.info("=== STEP 3: Nationalities from Wikipedia ===")

    # Get unique fighters
    f1s = df[df["country1"].isna() | (df["country1"] == "nan")][["fighter1"]].drop_duplicates()
    f2s = df[df["country2"].isna() | (df["country2"] == "nan")][["fighter2"]].drop_duplicates()
    all_fighters = list(set(f1s["fighter1"].tolist() + f2s["fighter2"].tolist()))
    log.info(f"Unique fighters needing nationality: {len(all_fighters)}")

    for i, fighter in enumerate(all_fighters):
        if not fighter or fighter == "nan":
            continue
        if fighter in nat_cache:
            continue
        log.info(f"[{i+1}/{len(all_fighters)}] Wikipedia: {fighter}")
        nat = get_nationality_wikipedia(fighter, nat_cache)

        if (i + 1) % 100 == 0:
            save_json(NATIONALITY_CACHE, nat_cache)
            log.info(f"Nationality cache saved ({i+1} fighters done)")

    save_json(NATIONALITY_CACHE, nat_cache)

    # Apply nationalities to dataframe
    for idx, row in df.iterrows():
        f1 = row.get("fighter1", "")
        f2 = row.get("fighter2", "")
        if f1 and f1 in nat_cache and nat_cache[f1]:
            df.at[idx, "country1"] = nat_cache[f1]
        if f2 and f2 in nat_cache and nat_cache[f2]:
            df.at[idx, "country2"] = nat_cache[f2]

    # ── FINAL SAVE ──
    df.to_csv("ufc_fights_final.csv", index=False)
    log.info("Saved ufc_fights_final.csv")

    print("\n✅ All done!")
    print(f"   Fights with method:       {df['method'].notna().sum()} / {len(df)}")
    print(f"   Fights with event_date:   {df['event_date'].notna().sum()} / {len(df)}")
    print(f"   Fights with nationality:  {df['country1'].notna().sum()} / {len(df)}")
    print(f"\nTop nationalities:")
    print(df["country1"].value_counts().head(15).to_string())
    print(f"\nMethods breakdown:")
    print(df["method"].value_counts().head(10).to_string())
    print(f"\nWeight classes:")
    print(df["weight_class"].value_counts().head(15).to_string())

if __name__ == "__main__":
    main()
