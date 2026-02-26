import json

# ── Load (3) HTML and build fighter -> nationality map ──────────────────────
print("Loading (3) HTML...")
with open(r'C:\Users\edcha\Downloads\ufc_dashboard (3).html', encoding='utf-8-sig') as f:
    html3 = f.read()

idx = html3.find('const FIGHTS_DATA = [')
start = html3.index('[', idx)
end = html3.index('\n', start)
json_str = html3[start:end].rstrip(';').rstrip()
fights3 = json.loads(json_str)
print(f"  (3) fights: {len(fights3)}")

# Build best nationality map from (3) - use non-empty values
nat_map = {}
for f in fights3:
    if f.get('fighter1') and f.get('country1', '').strip():
        nat_map[f['fighter1']] = f['country1'].strip()
    if f.get('fighter2') and f.get('country2', '').strip():
        nat_map[f['fighter2']] = f['country2'].strip()

print(f"  Nationality map from (3): {len(nat_map)} fighters")

# ── Load current JSON ────────────────────────────────────────────────────────
print("\nLoading ufc_fights.json...")
with open('ufc_fights.json', encoding='utf-8-sig') as f:
    fights = json.load(f)
print(f"  Current fights: {len(fights)}")

before_c1 = sum(1 for f in fights if not f.get('country1', '').strip())
before_c2 = sum(1 for f in fights if not f.get('country2', '').strip())
print(f"  Missing country1: {before_c1}, country2: {before_c2}")

# ── Enrich: fill in missing nationalities ───────────────────────────────────
filled_c1 = 0
filled_c2 = 0
for f in fights:
    if not f.get('country1', '').strip() and f.get('fighter1') and f['fighter1'] in nat_map:
        f['country1'] = nat_map[f['fighter1']]
        filled_c1 += 1
    if not f.get('country2', '').strip() and f.get('fighter2') and f['fighter2'] in nat_map:
        f['country2'] = nat_map[f['fighter2']]
        filled_c2 += 1

after_c1 = sum(1 for f in fights if not f.get('country1', '').strip())
after_c2 = sum(1 for f in fights if not f.get('country2', '').strip())
print(f"\nFilled country1: {filled_c1}, country2: {filled_c2}")
print(f"Still missing country1: {after_c1}, country2: {after_c2}")

# ── Save enriched JSON ───────────────────────────────────────────────────────
with open('ufc_fights.json', 'w', encoding='utf-8') as f:
    json.dump(fights, f, ensure_ascii=False, separators=(',', ':'))

print(f"\nSaved ufc_fights.json ({len(fights)} fights)")

# Verify a few fighters
for name in ['Sean Strickland', 'Israel Adesanya', 'Jon Jones', 'Michel Pereira', 'Serghei Spivac']:
    nat = nat_map.get(name, 'NOT IN MAP')
    in_json = next((f.get('country1') or f.get('country2') for f in fights 
                    if f.get('fighter1') == name or f.get('fighter2') == name), 'NOT FOUND')
    print(f"  {name}: map={nat}, json={in_json}")
