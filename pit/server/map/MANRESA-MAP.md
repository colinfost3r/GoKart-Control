# Manresa Island street outlines

`manresa-map.geojson` is an OpenStreetMap extract for Manresa Island and the neighbourhood
north of it, fetched on 2026-11-13. It holds drivable roads, building outlines, the coastline,
piers and breakwaters: 45 roads, 401 buildings, 12 coastline ways and 13 pier or breakwater
ways. Road names are kept; there is no address data. It has the same shape as
`sono-map.geojson` ([notes](SONO-MAP.md)), with one extra `kind`, `pier`.

Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), available
under the [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/). The
derivative geometry is included here under that license. Keep attribution visible wherever
it is displayed; the Core2 shows it on its startup screen.

## What uses it

Only the Core2's built-in street lines so far: `tools/m5/export_site_maps.py` cuts a 1.5 km
square around 41.0748, -73.4101 into `firmware/m5-core2/site_lines.inc`
([Core2 map notes](../../../firmware/m5-core2/COURSE_MAP.md)). The pit map, the Pi kart
screens and the host's course package do not read this file.

## What it does not show

The inside of the former power-plant site is thinly mapped: three service roads, under 30
building and tank outlines, and the shoreline. There is no course, pit location or surveyed
obstacle in it, and outlines can be out of date. It is context for a driver's map, not a
survey.

## Rebuilding

The fetch is a deliberate manual step; nothing in the repository contacts a map service. The
query sent to `https://overpass-api.de/api/interpreter` was:

```text
[out:json][timeout:90][bbox:41.0655,-73.4215,41.0840,-73.3985];
(
  way[highway];
  way[building];
  relation[building];
  way[natural=coastline];
  way[natural=water];
  relation[natural=water];
  way[railway];
  way[man_made~"^(pier|breakwater|groyne)$"];
);
out tags geom;
```

Save the response, then convert it and regenerate the Core2 tables, both offline:

```sh
python3 tools/m5/osm_site_geojson.py --overpass /path/to/overpass.json \
  --out pit/server/map/manresa-map.geojson \
  --source 'https://overpass-api.de/api/interpreter, bbox 41.0655,-73.4215,41.0840,-73.3985; query in MANRESA-MAP.md' \
  --description 'OSM extract from YYYY-MM-DD for Manresa Island, Norwalk: drivable roads, building outlines, coastline, piers and breakwaters. No address data.'
python3 tools/m5/export_site_maps.py
```

The converter keeps ways only. The one building relation in the area (a house) is dropped,
as are footways, paths and anything that is not a road, building, shoreline, water, rail or
pier.
