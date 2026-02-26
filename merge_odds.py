#!/usr/bin/env python3
"""
merge_odds.py  —  Fast version using token-based blocking + rapidfuzz.
Runs in ~30 seconds instead of hours.

RUN: python merge_odds.py
OUTPUT: ufc_fights_with_odds.csv  →  send to Claude to rebuild dashboard
"""

import json, re, sys
import pandas as pd

# Try rapidfuzz first (much faster), fall back to difflib
try:
    from rapidfuzz import fuzz, process
    RAPID = True
    print("Using rapidfuzz (fast mode)")
except ImportError:
    print("Installing rapidfuzz for fast matching...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "rapidfuzz", "-q"])
    from rapidfuzz import fuzz, process
    RAPID = True

def norm(name):
    """Normalise fighter name for matching."""
    n = str(name).lower().strip()
    n = re.sub(r'[^a-z\s]', '', n)
    n = re.sub(r'\s+', ' ', n)
    return n.strip()

print("Loading odds_data.json...")
with open("odds_data.json", encoding="utf-8") as f:
    odds = json.load(f)
print(f"  {len(odds)} odds entries")

print("Loading ufc_fights_final.csv...")
df = pd.read_csv("ufc_fights_final.csv", dtype=str)
print(f"  {len(df)} fights")

# Build a lookup: normalised_name -> list of odds entries
# Key = first token of fighter name (blocks comparisons by ~20x)
from collections import defaultdict

odds_by_token = defaultdict(list)
for entry in odds:
    for key in ['fighter1', 'fighter2']:
        n = norm(entry.get(key, ''))
        if n:
            token = n.split()[0] if n.split() else n
            odds_by_token[token].append(entry)

# Also build flat list of all normalised fighter1 names for rapidfuzz
odds_f1 = [norm(e.get('fighter1','')) for e in odds]
odds_f2 = [norm(e.get('fighter2','')) for e in odds]

def find_match(f1, f2, threshold=80):
    """Find best matching odds entry using token blocking + rapidfuzz."""
    nf1, nf2 = norm(f1), norm(f2)
    tok1 = nf1.split()[0] if nf1.split() else ''
    tok2 = nf2.split()[0] if nf2.split() else ''
    
    # Get candidates where either fighter's first token matches
    candidates = set()
    for tok in [tok1, tok2]:
        for i, entry in enumerate(odds):
            e1 = norm(entry.get('fighter1',''))
            e2 = norm(entry.get('fighter2',''))
            et1 = e1.split()[0] if e1.split() else ''
            et2 = e2.split()[0] if e2.split() else ''
            if tok and (tok == et1 or tok == et2):
                candidates.add(i)
    
    if not candidates:
        # Fallback: try partial last name match
        last1 = nf1.split()[-1] if nf1.split() else ''
        last2 = nf2.split()[-1] if nf2.split() else ''
        for i, entry in enumerate(odds):
            e1 = norm(entry.get('fighter1',''))
            e2 = norm(entry.get('fighter2',''))
            if last1 and (last1 in e1 or last1 in e2):
                candidates.add(i)
            if last2 and (last2 in e1 or last2 in e2):
                candidates.add(i)

    best_score = 0
    best_entry = None
    flipped = False

    for i in candidates:
        entry = odds[i]
        e1 = norm(entry.get('fighter1',''))
        e2 = norm(entry.get('fighter2',''))
        
        s_fwd = (fuzz.token_sort_ratio(nf1, e1) + fuzz.token_sort_ratio(nf2, e2)) / 2
        s_rev = (fuzz.token_sort_ratio(nf1, e2) + fuzz.token_sort_ratio(nf2, e1)) / 2
        s = max(s_fwd, s_rev)
        
        if s > best_score:
            best_score = s
            best_entry = entry
            flipped = s_rev > s_fwd

    if best_score >= threshold and best_entry:
        if flipped:
            return best_entry.get('odds2'), best_entry.get('odds1'), best_score
        return best_entry.get('odds1'), best_entry.get('odds2'), best_score
    
    return None, None, 0

# Precompute token index for speed
print("Building token index...")
token_index = defaultdict(set)
for i, entry in enumerate(odds):
    for key in ['fighter1', 'fighter2']:
        n = norm(entry.get(key, ''))
        for tok in n.split()[:2]:  # index first 2 tokens
            if tok:
                token_index[tok].add(i)

def find_match_fast(f1, f2, threshold=80):
    nf1, nf2 = norm(f1), norm(f2)
    
    # Get candidate indices via token index
    candidates = set()
    for n in [nf1, nf2]:
        for tok in n.split()[:2]:
            candidates |= token_index.get(tok, set())
    
    if not candidates:
        return None, None, 0

    best_score = 0
    best_entry = None
    flipped = False

    for i in candidates:
        entry = odds[i]
        e1 = norm(entry.get('fighter1',''))
        e2 = norm(entry.get('fighter2',''))
        s_fwd = (fuzz.token_sort_ratio(nf1, e1) + fuzz.token_sort_ratio(nf2, e2)) / 2
        s_rev = (fuzz.token_sort_ratio(nf1, e2) + fuzz.token_sort_ratio(nf2, e1)) / 2
        s = max(s_fwd, s_rev)
        if s > best_score:
            best_score = s
            best_entry = entry
            flipped = s_rev > s_fwd

    if best_score >= threshold and best_entry:
        if flipped:
            return best_entry.get('odds2'), best_entry.get('odds1'), best_score
        return best_entry.get('odds1'), best_entry.get('odds2'), best_score
    return None, None, 0

# Run matching
print("Matching fights to odds...")
df["odds1"] = None
df["odds2"] = None
matched = 0

for idx, row in df.iterrows():
    o1, o2, score = find_match_fast(str(row["fighter1"]), str(row["fighter2"]))
    if o1 is not None or o2 is not None:
        df.at[idx, "odds1"] = o1
        df.at[idx, "odds2"] = o2
        matched += 1
    if (idx+1) % 500 == 0:
        print(f"  {idx+1}/{len(df)} processed, {matched} matched so far...")

df.to_csv("ufc_fights_with_odds.csv", index=False)
pct = round(matched/len(df)*100)
print(f"\nMatched {matched}/{len(df)} fights ({pct}%)")
print("Saved: ufc_fights_with_odds.csv")
print("Send me this file → I'll rebuild the dashboard with odds!")
