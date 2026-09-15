# Availability

Who reports offering broadband service, and where.

```python
import bdcdata

df = bdcdata.availability.fixed(state="WA", technology="fiber")
```

## `fixed()` — service by location

The core dataset. One row per location, per provider, per technology: what each
provider reports offering at each Broadband Serviceable Location.

```python
bdcdata.availability.fixed(state, technology="all", release="latest")
```

| Column | Type | Notes |
|---|---|---|
| `frn` | string | 10-digit FCC Registration Number, leading zeros kept |
| `provider_id` | int | Join to `provider_list()` |
| `brand_name` | string | The name consumers see |
| `location_id` | string | Fabric location ID — **string**, see below |
| `technology` | int | See `lookups.technologies("fixed")` |
| `max_advertised_download_speed` | int | Mbps |
| `max_advertised_upload_speed` | int | Mbps |
| `low_latency` | bool | ≤100 ms round trip at the 95th percentile |
| `business_residential_code` | string | `B`, `R`, or `X` (both) |
| `state_usps` | string | Two-letter abbreviation |
| `block_geoid` | string | 15-digit census block, leading zeros kept |
| `h3_res8_id` | string | H3 resolution-8 cell |
| `release` | string | Added by bdcdata |
| `state_fips` | string | Added by bdcdata |

`location_id` and `block_geoid` are strings on purpose. A `block_geoid` like
`011010106033002` loses its meaning as a number, and a 13-digit `location_id`
exceeds what a 32-bit integer can hold. Join on them as text.

### Examples

```python
# One state, one technology
bdcdata.availability.fixed(state="WA", technology="fiber")

# Several states
bdcdata.availability.fixed(state=["WA", "OR", "ID"], technology="fiber")

# All wired technologies (copper, cable, fiber)
bdcdata.availability.fixed(state="WA", technology="wired")

# Everything for one state — large
bdcdata.availability.fixed(state="WA", technology="all")

# A past release
bdcdata.availability.fixed(state="WA", technology="fiber", release="2023-12-31")

# Compare two releases in one frame
bdcdata.availability.fixed(state="WA", technology="fiber", release=["2023-12-31", "2024-06-30"])
```

The `release` column is what makes the last one useful:

```python
df.groupby("release")["location_id"].nunique()
```

### Technology groups

Instead of listing codes, you can name a group:

| Group | Codes | Meaning |
|---|---|---|
| `"all"` | every fixed code | |
| `"wired"` | 10, 40, 50 | Copper, cable, fiber — the FCC's own definition |
| `"terrestrial"` | everything but 60, 61 | All non-satellite |
| `"satellite"` | 60, 61 | Geostationary and non-geostationary |
| `"wireless"` | 70, 71, 72 | Fixed wireless |

`"wired"` and `"terrestrial"` match the definitions the FCC uses in the
served/unserved file, so the groupings line up across datasets.

## `served_unserved()` — the 100/20 question

For **every** location in the Fabric — not just those with service — whether
any provider reported at least 100 Mbps down / 20 Mbps up.

```python
df = bdcdata.availability.served_unserved(state="WA")
```

| Column | Type |
|---|---|
| `location_id` | string |
| `block_geoid` | string |
| `h3_res8_id` | string |
| `any_dl100_ul20` | bool |
| `wired_dl100_ul20` | bool |
| `terrestrial_dl100_ul20` | bool |

The three flags are real booleans, so they aggregate directly:

```python
# Unserved locations by census block
unserved = df[~df["any_dl100_ul20"]]
unserved.groupby("block_geoid").size().sort_values(ascending=False)

# Share served, statewide
df["any_dl100_ul20"].mean()
```

This export was added in the August 2026 revision of the download
specification, so it may not exist for older releases. If it doesn't, you get
an empty DataFrame and a warning saying why.

## `mobile()` — mobile coverage by H3 cell

```python
df = bdcdata.availability.mobile(state="WA", technology="5g")
```

Needs `pip install 'bdcdata[mobile]'`.

The FCC publishes these as GIS files (shapefile or GeoPackage), not CSV.
bdcdata reads the **attribute table only** and skips the geometry, so you get
one row per H3 resolution-9 cell without geopandas in your dependency tree.

| Column | Type | Notes |
|---|---|---|
| `technology` | int | 300 = 3G, 400 = 4G LTE, 500 = 5G-NR |
| `mindown` | float | Minimum modeled download, Mbps |
| `minup` | float | Minimum modeled upload, Mbps |
| `environmnt` | int | 0 = outdoor stationary only, 1 = also in-vehicle |
| `h3_res9_id` | string | H3 resolution-9 cell |

`environmnt` is spelled that way in the FCC's files. It's kept as published
rather than silently corrected, so what you see matches the specification.

To map it, join `h3_res9_id` to hexagon geometry with the
[h3](https://pypi.org/project/h3/) package:

```python
import h3

df["boundary"] = df["h3_res9_id"].map(lambda cell: h3.cell_to_boundary(cell))
```

**Mobile technology codes are a separate namespace from fixed ones.** Code `0`
means "Other" for fixed and "Mobile Voice" for mobile. Passing `"fiber"` to
`mobile()` is an error, not a silent empty result.

## Summary tables

Smaller aggregates, when you don't need location-level detail.

```python
# Providers that submitted data — join target for provider_id
bdcdata.availability.provider_list()

# Per-provider totals
bdcdata.availability.provider_summary(kind="fixed")  # location and unit counts
bdcdata.availability.provider_summary(kind="mobile")  # covered area in sq km

# Coverage percentages by geography, across all providers
bdcdata.availability.summary_by_geography(kind="fixed", geography="place")
bdcdata.availability.summary_by_geography(kind="fixed", geography="other")
```

`geography="place"` is census places; `geography="other"` is everything else
(state, county, congressional district, tribal area, CBSA). The FCC split these
into separate exports in June 2024.

## Size

An availability pull can be very large. A single state's fiber file is tens of
megabytes; `state="all", technology="all"` is many gigabytes and will likely
exhaust memory.

bdcdata sums the catalog's `record_count` before downloading and warns you when
a request is about to load millions of rows. To see what you're asking for
first:

```python
files = bdcdata.catalog.availability_files(
    release="latest", category="State", subcategory="Location Coverage"
)
files["record_count"].sum()
```

If you need everything, loop a state at a time and write each to Parquet rather
than holding it all in memory:

```python
for state in bdcdata.lookups.states()["usps"]:
    df = bdcdata.availability.fixed(state=state, technology="fiber")
    df.to_parquet(f"fiber_{state}.parquet")
```

With `bdcdata.set_cache(True)`, a loop like that is resumable — re-running
skips anything already downloaded.
