# Tampa Bay mechanic shops lead scraper.
# Uses DuckDuckGo + pattern extraction to build a CSV of locally-owned auto repair shops.
# Output: Desktop/tampa_mechanics.csv
import re
import csv
import time
import sys
from pathlib import Path

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

OUTPUT = Path("C:/Users/Ryan/Desktop/tampa_mechanics.csv")

SEARCHES = [
    # Tampa proper
    "auto repair shop Tampa FL locally owned independent phone address",
    "mechanic shop Tampa FL phone number address small business",
    "auto mechanic Tampa FL independently owned phone",
    "brake transmission oil change shop Tampa FL phone address",
    "car repair garage Tampa FL locally owned phone number address site:yelp.com",
    # St. Pete / Clearwater
    "auto repair St Petersburg FL locally owned phone address",
    "mechanic shop St Pete FL phone number address",
    "auto repair Clearwater FL locally owned phone number",
    "mechanic shop Clearwater FL phone address",
    # North/East
    "auto repair New Port Richey FL phone address locally owned",
    "mechanic shop Wesley Chapel FL phone address",
    "auto repair Zephyrhills FL phone number address",
    "mechanic shop Land O Lakes FL phone address",
    "auto repair Lutz FL phone number locally owned",
    "mechanic shop Odessa FL phone number address",
    # South/East
    "auto repair Brandon FL phone address locally owned",
    "mechanic shop Riverview FL phone number address",
    "auto repair Ruskin FL phone address",
    "mechanic shop Sun City Center FL phone address",
    "auto repair Apollo Beach FL phone number",
    # Pinellas south
    "auto repair Largo FL phone number locally owned",
    "mechanic shop Seminole FL phone address",
    "auto repair Pinellas Park FL phone number",
    "mechanic shop Tarpon Springs FL phone address",
    "auto repair Dunedin FL phone number",
    "mechanic shop Safety Harbor FL phone address",
    "auto repair Oldsmar FL phone number",
    # Sarasota/Manatee
    "auto repair Bradenton FL phone address locally owned",
    "mechanic shop Sarasota FL phone number address",
    "auto repair Palmetto FL phone address",
    "mechanic shop Ellenton FL phone number",
    # More targeted
    "independent auto shop Tampa FL phone 813",
    "oil change brake repair Tampa FL 813 phone",
    "transmission shop Tampa FL phone address",
    "foreign domestic car repair Tampa FL phone locally owned",
    "auto service center St Petersburg FL 727 phone address",
    "car mechanic service Tampa Bay area phone address small business",
    "auto body repair Tampa FL phone independently owned",
    "diesel repair shop Tampa FL phone address",
]

# Phone number pattern
PHONE_RE = re.compile(r'\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}')
# Address patterns (look for FL zip codes)
ADDR_RE  = re.compile(r'\d+[^,]{5,50},\s*(?:FL|Florida)\s+\d{5}', re.IGNORECASE)
ADDR_RE2 = re.compile(r'\d+\s+[A-Z][^,\n]{5,50}(?:Ave|Blvd|Dr|Rd|St|Ln|Way|Ct|Pkwy)[^,\n]{0,40}', re.IGNORECASE)

def clean(s):
    return re.sub(r'\s+', ' ', s).strip()

def extract_city(text):
    cities = [
        'Tampa','St. Petersburg','St Petersburg','Clearwater','Brandon','Riverview',
        'New Port Richey','Wesley Chapel','Largo','Pinellas Park','Tarpon Springs',
        'Dunedin','Safety Harbor','Seminole','Oldsmar','Odessa','Lutz','Land O Lakes',
        'Zephyrhills','Bradenton','Sarasota','Palmetto','Ellenton','Apollo Beach',
        'Ruskin','Sun City Center','Plant City','Temple Terrace','Valrico',
    ]
    for c in cities:
        if c.lower() in text.lower():
            return c
    return ''

seen_phones = set()
seen_titles = set()
shops = []

print(f"Starting scraper — targeting {len(SEARCHES)} searches...")
print(f"Output: {OUTPUT}")
print()

for i, query in enumerate(SEARCHES):
    try:
        results = list(DDGS().text(query, max_results=15))
        found = 0
        for r in results:
            title = clean(r.get('title', ''))
            body  = clean(r.get('body', ''))
            href  = r.get('href', '')

            # Skip big chains and irrelevant results
            skip_keywords = [
                'jiffy lube','midas','pep boys','firestone','goodyear','meineke','maaco',
                'valvoline','monro','sears auto','walmart auto','costco auto','ntb',
                'advanced auto','autozone','o\'reilly','carmax','dealership','dealer',
                'seo','marketing','agency','insurance','school','college','course',
                'indeed.com','linkedin.com','facebook.com','twitter.com','instagram',
                'glassdoor','ziprecruiter','reddit.com',
            ]
            combined = (title + ' ' + body + ' ' + href).lower()
            if any(kw in combined for kw in skip_keywords):
                continue

            phones = PHONE_RE.findall(body)
            if not phones:
                phones = PHONE_RE.findall(title)
            phone = phones[0] if phones else ''

            # Normalize phone
            norm_phone = re.sub(r'\D', '', phone)

            # Skip if duplicate phone
            if norm_phone and norm_phone in seen_phones:
                continue

            # Extract address
            addr_match = ADDR_RE.search(body) or ADDR_RE2.search(body)
            address = clean(addr_match.group(0)) if addr_match else ''

            city = extract_city(body + ' ' + title + ' ' + address)

            # Skip if no phone AND no address
            if not phone and not address:
                continue

            # Normalize title for dedup
            norm_title = re.sub(r'[^a-z0-9]', '', title.lower())[:30]
            if norm_title in seen_titles:
                continue

            if norm_phone:
                seen_phones.add(norm_phone)
            seen_titles.add(norm_title)

            shops.append({
                'Business Name': title,
                'Phone':         phone,
                'Address':       address,
                'City':          city,
                'State':         'FL',
                'Website':       href,
                'Type':          'Auto Repair / Mechanic',
                'Source':        'DuckDuckGo',
            })
            found += 1

        print(f"[{i+1:2d}/{len(SEARCHES)}] {found:2d} new  |  total: {len(shops):3d}  |  {query[:60]}")
        time.sleep(0.4)

    except Exception as e:
        print(f"[{i+1:2d}/{len(SEARCHES)}] ERROR: {e}")
        time.sleep(1.0)

# Write CSV
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
fieldnames = ['Business Name', 'Phone', 'Address', 'City', 'State', 'Website', 'Type', 'Source']
with open(OUTPUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(shops)

print()
print(f"Done! {len(shops)} shops saved to {OUTPUT}")
