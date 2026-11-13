#!/usr/bin/env python3
"""Convert a saved Overpass API response into the site GeoJSON behind the Core2 street lines.

Offline: reads one JSON file and writes one GeoJSON file. It makes no network request and
opens no device. Fetching the response is a separate, deliberate step; the query used for
Manresa Island is recorded in pit/server/map/MANRESA-MAP.md.

The output has the same shape as pit/server/map/sono-map.geojson: features whose `kind` is
road, building, water, coastline, rail or pier. Names are kept for roads only; no address
data is copied. Map data (c) OpenStreetMap contributors, ODbL 1.0.
"""
import argparse
import json
from pathlib import Path

# Drivable ways only. Footways, paths, steps and cycleways would clutter a 320x240 map.
ROADS = {'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
         'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'unclassified',
         'residential', 'living_street', 'service', 'track'}
RAILS = {'rail', 'light_rail', 'subway', 'tram', 'narrow_gauge'}
PIERS = {'pier', 'breakwater', 'groyne'}
ORDER = ('water', 'coastline', 'pier', 'building', 'road', 'rail')


def classify(tags):
    """Return (kind, class) for an OSM way's tags, or None when the way is not drawn."""
    if tags.get('highway') in ROADS:
        return 'road', tags['highway']
    if tags.get('railway') in RAILS:
        return 'rail', ''
    if tags.get('natural') == 'coastline':
        return 'coastline', ''
    if tags.get('natural') == 'water':
        return 'water', ''
    if tags.get('man_made') in PIERS:
        return 'pier', ''
    if tags.get('building') not in (None, 'no'):
        return 'building', ''
    return None


def convert(doc, *, source, description):
    features = []
    for element in doc.get('elements', []):
        if element.get('type') != 'way':
            continue
        found = classify(element.get('tags', {}))
        points = [[round(float(p['lon']), 7), round(float(p['lat']), 7)]
                  for p in element.get('geometry', []) if p]
        if not found or len(points) < 2:
            continue
        kind, klass = found
        closed = len(points) >= 4 and points[0] == points[-1]
        area = closed and kind in ('building', 'water', 'pier')
        properties = {'kind': kind, 'class': klass, 'osm_way_id': str(element['id'])}
        if kind == 'road':
            properties['name'] = str(element.get('tags', {}).get('name', ''))
        features.append({
            'type': 'Feature', 'properties': properties,
            'geometry': {'type': 'Polygon', 'coordinates': [points]} if area
            else {'type': 'LineString', 'coordinates': points}})
    features.sort(key=lambda f: (ORDER.index(f['properties']['kind']), int(f['properties']['osm_way_id'])))
    return {'type': 'FeatureCollection', 'attribution': '© OpenStreetMap contributors',
            'license': 'https://opendatacommons.org/licenses/odbl/1-0/', 'source': source,
            'description': description, 'features': features}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--overpass', type=Path, required=True, help='saved Overpass JSON (out tags geom)')
    parser.add_argument('--out', type=Path, required=True, help='GeoJSON file to write')
    parser.add_argument('--source', required=True, help='where the response came from (service, bounding box)')
    parser.add_argument('--description', required=True, help='one line: place, date, what is included')
    args = parser.parse_args()
    doc = json.loads(args.overpass.read_text())
    result = convert(doc, source=args.source, description=args.description)
    args.out.write_text(json.dumps(result, separators=(',', ':'), ensure_ascii=False) + '\n')
    counts = {}
    for feature in result['features']:
        counts[feature['properties']['kind']] = counts.get(feature['properties']['kind'], 0) + 1
    print(json.dumps({'out': str(args.out), 'features': counts, 'no_network': True, 'no_device_opened': True}))


if __name__ == '__main__':
    main()
