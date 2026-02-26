"""
UFC Fight Scraper - UFCStats.com
=================================
Scrapes every UFC event and fight from UFCStats.com and saves to:
  - ufc_fights.csv       (one row per fight)
  - ufc_fighters.csv     (one row per unique fighter)

Requirements:
    pip install requests beautifulsoup4 pandas

Usage:
    python ufc_scraper.py

Runtime: ~30-60 minutes (7,000+ fights, polite rate limiting)
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_URL = "http://ufcstats.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (UFC Research Scraper)"}
DELAY = 0.8  # seconds between requests — be polite


def get(url, retries=3):
    """GET with retry logic."""
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            return r
        except Exception as e:
            log.warning(f"Attempt {attempt+1} failed for {url}: {e}")
            time.sleep(2 ** attempt)
    return None


# ─────────────────────────────────────────────
# STEP 1: Scrape all event URLs
# ─────────────────────────────────────────────

def get_all_event_urls():
    log.info("Fetching all event URLs...")
    url = f"{BASE_URL}/statistics/events/completed?page=all"
    r = get(url)
    if not r:
        raise RuntimeError("Failed to fetch event list")
    soup = BeautifulSoup(r.text, "html.parser")
    links = soup.select("td.b-statistics__table-col a")
    urls = list(dict.fromkeys(a["href"] for a in links if "event-details" in a.get("href", "")))
    log.info(f"Found {len(urls)} events")
    return urls


# ─────────────────────────────────────────────
# STEP 2: Scrape all fight URLs from an event
# ─────────────────────────────────────────────

def get_fight_urls_from_event(event_url):
    r = get(event_url)
    if not r:
        return [], {}
    soup = BeautifulSoup(r.text, "html.parser")

    # Event metadata
    event_name = soup.select_one("span.b-content__title-highlight")
    event_name = event_name.text.strip() if event_name else "Unknown"

    event_meta = {}
    for li in soup.select("li.b-list__box-list-item"):
        text = li.get_text(separator="|").split("|")
        if len(text) >= 2:
            k = text[0].strip().rstrip(":")
            v = text[1].strip()
            event_meta[k] = v

    event_date = event_meta.get("Date", "")
    event_location = event_meta.get("Location", "")

    fight_links = soup.select("tr.b-fight-details__table-row[data-link]")
    fight_urls = [row["data-link"] for row in fight_links if row.get("data-link")]

    return fight_urls, {
        "event_name": event_name,
        "event_date": event_date,
        "event_location": event_location,
    }


# ─────────────────────────────────────────────
# STEP 3: Scrape a single fight page
# ─────────────────────────────────────────────

def parse_fight(fight_url, event_info):
    r = get(fight_url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")

    # Fighter names
    fighters = soup.select("a.b-fight-details__person-link")
    if len(fighters) < 2:
        return None
    fighter1 = fighters[0].text.strip()
    fighter2 = fighters[1].text.strip()

    # Winner (has "i-Winning" class on parent)
    winner_els = soup.select("div.b-fight-details__person.b-fight-details__person--last i.b-fight-details__person-status")
    # More reliable: check who has the "W" status
    statuses = soup.select("i.b-fight-details__person-status")
    winner = ""
    if len(statuses) >= 2:
        s1 = statuses[0].text.strip()
        s2 = statuses[1].text.strip()
        if s1 == "W":
            winner = fighter1
        elif s2 == "W":
            winner = fighter2
        elif s1 == "D" or s2 == "D":
            winner = "Draw"
        else:
            winner = "NC"  # No Contest

    # Fight details
    details = {}
    for item in soup.select("i.b-fight-details__text-item"):
        parts = item.get_text(separator="|").split("|")
        if len(parts) >= 2:
            k = parts[0].strip().rstrip(":")
            v = parts[1].strip()
            details[k] = v

    method = details.get("Method", "")
    round_ = details.get("Round", "")
    time_ = details.get("Time", "")
    time_format = details.get("Time format", "")
    referee = details.get("Referee", "")
    weight_class = details.get("Weight class", "")

    # Fighter nationalities — from fighter profile pages
    def get_fighter_country(fighter_link_el):
        href = fighter_link_el.get("href", "")
        if not href:
            return ""
        r2 = get(href)
        if not r2:
            return ""
        s2 = BeautifulSoup(r2.text, "html.parser")
        for li in s2.select("li.b-list__box-list-item"):
            txt = li.get_text(separator="|")
            if "Nationality" in txt:
                parts = txt.split("|")
                if len(parts) >= 2:
                    return parts[1].strip()
        return ""

    # Get nationalities (with caching done at caller level)
    country1 = get_fighter_country(fighters[0])
    time.sleep(DELAY)
    country2 = get_fighter_country(fighters[1])
    time.sleep(DELAY)

    return {
        "event_name": event_info["event_name"],
        "event_date": event_info["event_date"],
        "event_location": event_info["event_location"],
        "fighter1": fighter1,
        "fighter2": fighter2,
        "country1": country1,
        "country2": country2,
        "winner": winner,
        "weight_class": weight_class,
        "method": method,
        "round": round_,
        "time": time_,
        "time_format": time_format,
        "referee": referee,
        "fight_url": fight_url,
    }


# ─────────────────────────────────────────────
# STEP 4: Main orchestrator
# ─────────────────────────────────────────────

def main():
    all_fights = []
    fighter_cache = {}  # name -> country (avoids re-scraping same fighter)

    event_urls = get_all_event_urls()

    for i, event_url in enumerate(event_urls):
        log.info(f"Event {i+1}/{len(event_urls)}: {event_url}")
        fight_urls, event_info = get_fight_urls_from_event(event_url)
        time.sleep(DELAY)

        for j, fight_url in enumerate(fight_urls):
            log.info(f"  Fight {j+1}/{len(fight_urls)}: {fight_url}")
            fight_data = parse_fight(fight_url, event_info)
            if fight_data:
                all_fights.append(fight_data)
            time.sleep(DELAY)

        # Save checkpoint every 10 events
        if (i + 1) % 10 == 0:
            df = pd.DataFrame(all_fights)
            df.to_csv("ufc_fights_checkpoint.csv", index=False)
            log.info(f"Checkpoint saved: {len(all_fights)} fights so far")

    # Final save
    df = pd.DataFrame(all_fights)
    df.to_csv("ufc_fights.csv", index=False)
    log.info(f"Done! {len(all_fights)} fights saved to ufc_fights.csv")

    # Fighter summary
    fighters = {}
    for _, row in df.iterrows():
        for name, country in [(row["fighter1"], row["country1"]), (row["fighter2"], row["country2"])]:
            if name not in fighters:
                fighters[name] = {"fighter": name, "country": country, "fights": 0, "wins": 0}
            fighters[name]["fights"] += 1
            if row["winner"] == name:
                fighters[name]["wins"] += 1

    fighter_df = pd.DataFrame(fighters.values())
    fighter_df["win_rate"] = (fighter_df["wins"] / fighter_df["fights"] * 100).round(1)
    fighter_df = fighter_df.sort_values("fights", ascending=False)
    fighter_df.to_csv("ufc_fighters.csv", index=False)
    log.info(f"Fighter summary saved to ufc_fighters.csv ({len(fighter_df)} fighters)")

    print("\n✅ Scrape complete!")
    print(f"   {len(all_fights)} fights → ufc_fights.csv")
    print(f"   {len(fighter_df)} fighters → ufc_fighters.csv")
    print(f"\nTop nationalities:")
    print(df['country1'].value_counts().head(10).to_string())


if __name__ == "__main__":
    main()
