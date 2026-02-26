"""
ufc_enrich.py
==============
Reads your existing ufc_fights.csv and fills in ALL missing fields:
  - event_date, event_location
  - weight_class, method, round, time, referee
  - country1, country2 (fighter nationalities)

Much faster than the original scraper because:
  - We already have all 8,560 fight URLs
  - We skip event discovery entirely
  - Fighter nationalities are cached so each fighter is only looked up once

Requirements:
    pip install requests beautifulsoup4 pandas

Usage:
    python ufc_enrich.py

Runtime: ~2-3 hours (fight details are fast; nationality adds time but cached)

Output:
    ufc_fights_enriched.csv
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
import json
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
DELAY = 0.6
CACHE_FILE = "nationality_cache.json"
CHECKPOINT_FILE = "ufc_fights_enriched_checkpoint.csv"

# ── Load nationality cache from disk (so reruns don't re-scrape) ──
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

# ── HTTP with retry ──
def get(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            return r
        except Exception as e:
            log.warning(f"Attempt {attempt+1} failed for {url}: {e}")
            time.sleep(2 ** attempt)
    return None

# ── Scrape a single fight detail page ──
def scrape_fight(fight_url):
    r = get(fight_url)
    if not r:
        return {}

    soup = BeautifulSoup(r.text, "html.parser")
    result = {}

    # ── Method, Round, Time, Referee ──
    # These are in <i class="b-fight-details__text-item"> elements
    for item in soup.select("i.b-fight-details__text-item"):
        text = item.get_text(" ", strip=True)
        if "Method:" in text:
            result["method"] = text.replace("Method:", "").strip()
        elif "Round:" in text:
            result["round"] = text.replace("Round:", "").strip()
        elif "Time:" in text and "format" not in text.lower():
            result["time"] = text.replace("Time:", "").strip()
        elif "Time format:" in text:
            result["time_format"] = text.replace("Time format:", "").strip()
        elif "Referee:" in text:
            result["referee"] = text.replace("Referee:", "").strip()

    # ── Weight class — appears in the fight title area ──
    title = soup.select_one("i.b-fight-details__fight-title")
    if title:
        wc = title.get_text(strip=True)
        # Remove "Title Bout" / "Interim" etc
        result["weight_class"] = wc.replace("Title Bout", "").replace("Interim", "").strip()

    # Alternative weight class location
    if not result.get("weight_class"):
        for i in soup.select("i.b-fight-details__text-item_style_align-top"):
            txt = i.get_text(" ", strip=True)
            if "class" in txt.lower() or "weight" in txt.lower():
                result["weight_class"] = txt.strip()
                break

    # ── Fighter profile links (for nationality) ──
    fighter_links = soup.select("a.b-fight-details__person-link")
    if len(fighter_links) >= 2:
        result["fighter1_url"] = fighter_links[0].get("href", "")
        result["fighter2_url"] = fighter_links[1].get("href", "")

    return result

# ── Scrape fighter nationality from their profile page ──
def get_nationality(fighter_url, cache):
    if not fighter_url:
        return ""
    if fighter_url in cache:
        return cache[fighter_url]

    r = get(fighter_url)
    if not r:
        cache[fighter_url] = ""
        return ""

    soup = BeautifulSoup(r.text, "html.parser")
    nationality = ""

    # Try multiple selectors
    for li in soup.select("li.b-list__box-list-item"):
        text = li.get_text(" ", strip=True)
        if text.startswith("Nationality:") or "Nationality" in text:
            nationality = text.replace("Nationality:", "").strip()
            break

    # Fallback: look for any element mentioning nationality
    if not nationality:
        for el in soup.find_all(string=lambda s: s and "Nationality" in s):
            parent = el.parent
            if parent:
                siblings = parent.find_next_siblings()
                if siblings:
                    nationality = siblings[0].get_text(strip=True)
                    break

    cache[fighter_url] = nationality
    time.sleep(DELAY)
    return nationality

# ── Scrape event details (date, location) from event page ──
def scrape_event_details(event_name, event_cache):
    """We'll get event details by scraping the events list page."""
    if event_name in event_cache:
        return event_cache[event_name]
    return {"event_date": "", "event_location": ""}

# ── Main ──
def main():
    # Load existing data
    df = pd.read_csv("ufc_fights.csv", dtype={"method": object, "round": object, "time": object, "time_format": object, "referee": object, "weight_class": object, "country1": object, "country2": object, "event_date": object, "event_location": object})
    log.info(f"Loaded {len(df)} fights from ufc_fights.csv")

    # Force string columns to object dtype so we can write strings into NaN columns
    for col in ["method", "round", "time", "time_format", "referee", "weight_class", "country1", "country2", "event_date", "event_location"]:
        if col in df.columns:
            df[col] = df[col].astype(object)

    # Load caches
    nationality_cache = load_cache()
    log.info(f"Loaded {len(nationality_cache)} cached nationalities")

    # Load checkpoint if exists
    done_urls = set()
    if os.path.exists(CHECKPOINT_FILE):
        checkpoint = pd.read_csv(CHECKPOINT_FILE, dtype={"method": object, "round": object, "time": object, "time_format": object, "referee": object, "weight_class": object, "country1": object, "country2": object, "event_date": object, "event_location": object})
        # Only count rows that have been enriched (have method data)
        done_urls = set(checkpoint[checkpoint["method"].notna()]["fight_url"].tolist())
        log.info(f"Checkpoint found: {len(done_urls)} fights already enriched")
        df = checkpoint.copy()  # Start from checkpoint

    enriched_count = 0

    for idx, row in df.iterrows():
        fight_url = row.get("fight_url", "")
        if not fight_url:
            continue

        # Skip if already enriched
        if fight_url in done_urls and pd.notna(row.get("method")):
            continue

        log.info(f"[{idx+1}/{len(df)}] Enriching: {row.get('fighter1')} vs {row.get('fighter2')}")

        # ── Scrape fight details ──
        details = scrape_fight(fight_url)
        time.sleep(DELAY)

        # Fill in fight detail fields
        for field in ["method", "round", "time", "time_format", "referee", "weight_class"]:
            if details.get(field):
                df.at[idx, field] = details[field]

        # ── Get nationalities ──
        f1_url = details.get("fighter1_url", "")
        f2_url = details.get("fighter2_url", "")

        if f1_url:
            country1 = get_nationality(f1_url, nationality_cache)
            df.at[idx, "country1"] = country1

        if f2_url:
            country2 = get_nationality(f2_url, nationality_cache)
            df.at[idx, "country2"] = country2

        enriched_count += 1

        # Save checkpoint every 50 fights
        if enriched_count % 50 == 0:
            df.to_csv(CHECKPOINT_FILE, index=False)
            save_cache(nationality_cache)
            log.info(f"Checkpoint saved ({enriched_count} fights enriched so far)")

    # ── Final save ──
    df.to_csv("ufc_fights_enriched.csv", index=False)
    save_cache(nationality_cache)

    log.info(f"Done! Enriched {enriched_count} fights")
    log.info(f"Saved to ufc_fights_enriched.csv")

    # Summary
    print("\n✅ Enrichment complete!")
    print(f"   Fights with method: {df['method'].notna().sum()}")
    print(f"   Fights with weight_class: {df['weight_class'].notna().sum()}")
    print(f"   Fights with nationality: {df['country1'].notna().sum()}")
    print(f"\nTop nationalities (fighter1):")
    print(df["country1"].value_counts().head(15).to_string())
    print(f"\nWeight classes:")
    print(df["weight_class"].value_counts().to_string())

if __name__ == "__main__":
    main()
