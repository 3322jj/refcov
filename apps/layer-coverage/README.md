# Layer coverage app: NYC building footprints, Bayside subset

A RefCov adapter named `layer`, plus the scripts that build its manifest. The data is the Bayside subset of the NYC Building Footprints dataset (Socrata `5zhs-2jue`). The app uses only the Python standard library, apart from importing `refcov.sources` in `adapter.py`.

## What it does

- Splits `bayside.fields.md` into units: one `crs` unit, one `extent` unit, and one `field` unit for each dataset field.
- Each field unit holds the field's text from the NYC data dictionary, copied as written, and statistics computed from the subset: the non-null count, the number of distinct values, the five most frequent values with their counts, and the number of zero values.
- It does not compute areas, draw maps, make charts, filter data, or clean data.

## Files

| File | Purpose |
|---|---|
| `fetch.py` | Downloads the subset from the Socrata API into a file outside the repository. Before writing, it checks the total row count and the count for each `feature_code` against the API. `--check` only reads the counts. |
| `build.py` | Reads a local GeoJSON file and the dictionary URL, and writes `bayside.fields.md`. The text is split by the adapter before it is written. |
| `stats.py` | Counting functions used by `build.py`. |
| `adapter.py` | The RefCov adapter `layer`. Field units are strict. Crs and extent units are strict and key. |
| `cli.py` | `fields` lists the field units. `show <unit-id>` prints one unit. Both only read the manifest. |
| `bayside.fields.md` | The generated manifest. It is committed; the raw data is not. |

## Rebuilding the manifest

```
python apps/layer-coverage/fetch.py --check
python apps/layer-coverage/fetch.py --out <file outside the repository>
python apps/layer-coverage/build.py --geojson <that file>
```

The manifest records the SHA-256 of the GeoJSON file and of the dictionary text, so a change in either input shows up in the file.

## How RefCov uses the manifest

- The workspace config declares `[adapters] layer = "apps/layer-coverage/adapter.py"` and `[sources.layer] files = ["apps/layer-coverage/bayside.fields.md"]`. The adapter path must be relative to the workspace root.
- In strict mode every unit is required. A unit counts as read only when it was read through the RefCov MCP tool. Reading the file directly does not count.
- A requirement that cites a unit, written `[ref:<source>/<unit>]`, fails the citation check in strict mode if that unit was not read.
- The write gate blocks writes to scoped paths until the required units have been read.

## Limits

- Only the Bayside subset: features whose geometry falls in the box used by `within_box(the_geom, 40.770, -73.785, 40.755, -73.765)`. The extract checked on 2026-11-15 has 6018 features.
- Field counts describe this subset only.
- `shape_area` and `shape_length` are shown with the dictionary's warning: they are computed in Web Mercator and do not preserve area. The app does not compute areas from the geometry.
- The adapter file is loaded from the workspace. A workspace outside this repository needs its own copy of `adapter.py` at the same relative path.
