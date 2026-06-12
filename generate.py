#!/usr/bin/env python3
"""Student Cribs Viewings Dashboard — Daily Generator"""
import os, json, xml.etree.ElementTree as ET, urllib.request, sys
from datetime import date, timedelta
from collections import defaultdict

AUTH = os.environ.get('SC_API_AUTH', '')
if not AUTH:
    print("ERROR: SC_API_AUTH not set", file=sys.stderr)
    sys.exit(1)

BASE = "https://api.student-cribs.com/api/xmls/viewings-booked"

def fetch():
    url = f"{BASE}?auth={AUTH}"
    print(f"  Fetching viewings data...", file=sys.stderr)
    req = urllib.request.Request(url, headers={'User-Agent': 'SC-Dashboard/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            content = r.read()
        root = ET.fromstring(content)
        return root.findall('.//viewing')
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return []

def filter_by_date(viewings, d_from, d_to):
    return [v for v in viewings if d_from.isoformat() <= (v.findtext('viewing_date') or '') <= d_to.isoformat()]

def agg(viewings):
    brand_managers = defaultdict(lambda: {'total': 0, 'booked': 0})
    properties = defaultdict(int)
    booked_props = defaultdict(int)
    months = defaultdict(int)
    total = len(viewings)
    booked_count = 0
    for v in viewings:
        bm = (v.findtext('brand_manager_taking_viewing') or 'Unclaimed').strip()
        brand_managers[bm]['total'] += 1
        d = (v.findtext('viewing_date') or '').strip()
        if d and len(d) >= 7:
            months[d[:7]] += 1
        prop = (v.findtext('viewing_property_address') or '').strip()
        if prop:
            properties[prop] += 1
        booked = (v.findtext('booked_crib') or '').strip().lower() == 'yes'
        if booked:
            booked_count += 1
            brand_managers[bm]['booked'] += 1
            bp = (v.findtext('property_booked') or prop).strip()
            if bp:
                booked_props[bp] += 1
    bm_list = []
    for bm, counts in brand_managers.items():
        rate = round(counts['booked'] / counts['total'] * 100, 1) if counts['total'] > 0 else 0
        bm_list.append({'name': bm, 'total': counts['total'], 'booked': counts['booked'], 'rate': rate})
    bm_list.sort(key=lambda x: -x['total'])
    return {
        'total': total,
        'booked': booked_count,
        'conversion_rate': round(booked_count / total * 100, 1) if total > 0 else 0,
        'brand_managers': bm_list[:25],
        'top_properties': sorted(properties.items(), key=lambda x: -x[1])[:20],
        'top_booked': sorted(booked_props.items(), key=lambda x: -x[1])[:15],
        'by_month': dict(sorted(months.items())[-12:]),
    }

today = date.today()
week_start = today - timedelta(days=7)
month_start = today.replace(day=1)
ytd_start = date(today.year if today.month >= 7 else today.year - 1, 7, 1)

print("Fetching all viewings...", file=sys.stderr)
all_v = fetch()
print(f"  Got {len(all_v)} total", file=sys.stderr)

weekly  = agg(filter_by_date(all_v, week_start, today))
monthly = agg(filter_by_date(all_v, month_start, today))
ytd     = agg(filter_by_date(all_v, ytd_start, today))

def fmt(d): return f"{d.day} {d.strftime('%b %Y')}"

meta = {
    'generated': today.strftime('%d %b %Y'),
    'week': f"{fmt(week_start)} – {fmt(today)}",
    'month': today.strftime('%B %Y'),
    'ytd_label': f"1 Jul {ytd_start.year} – {fmt(today)}",
}

data_js = f"""const WEEKLY = {json.dumps(weekly)};
const MONTHLY = {json.dumps(monthly)};
const YTD = {json.dumps(ytd)};
const META = {json.dumps(meta)};"""

script_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(script_dir, 'template.html'), 'r', encoding='utf-8') as f:
    html = f.read()
html = html.replace('// <!--INJECT_DATA-->', data_js)
with open(os.path.join(script_dir, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(html)
print("Done!", file=sys.stderr)
