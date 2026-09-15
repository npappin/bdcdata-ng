# Funding

Data from the Broadband Funding Map: which programs and projects are paying to
build broadband where, and which locations are still both unserved and
unfunded.

```python
import bdcdata

df = bdcdata.funding.unserved_unfunded(state="WA")
```

## A separate system

The Broadband Funding Map is its own system with its own endpoints, and it has
**no "as of date" concept**. There is no `release=` parameter here — the
catalog lists whatever is currently published:

```python
bdcdata.catalog.funding_files()
```

Files are organized by `category` and `data_type` rather than by vintage:

| Category | What it is |
|---|---|
| `Funding Data` | Raw program and project data submitted by agencies |
| `Unserved-Unfunded` | Locations with neither qualifying service nor a commitment |
| `Funded Locations State` | Locations covered by an enforceable commitment |
| `Funded Locations State Program` | The same, broken out per program |

## `unserved_unfunded()`

The headline dataset for anyone doing BEAD-adjacent work: locations that have
no reported qualifying service *and* no enforceable funding commitment to build
there.

```python
df = bdcdata.funding.unserved_unfunded(state="WA")
```

One row per location, with `location_id`, `block_geoid`, `h3_res8_id`,
`building_type_code`, and the technology/speed buildout columns.

`location_id` and `block_geoid` are strings, so this joins straight to
availability data:

```python
avail = bdcdata.availability.served_unserved(state="WA")
gaps = bdcdata.funding.unserved_unfunded(state="WA")

combined = avail.merge(gaps, on="location_id", how="left", indicator=True)
```

## `programs()` and `projects()`

Program- and project-level detail submitted by funding agencies.

```python
bdcdata.funding.programs(agency="Federal Communications")
bdcdata.funding.projects(program="Rural Digital Opportunity")
```

Both `agency` and `program` are case-insensitive substring matches, so
`agency="fcc"` won't match but `agency="Federal Communications"` will, and
`agency="agriculture"` finds the Department of Agriculture.

**Filter these.** The FCC publishes thousands of funding files; an unfiltered
`programs()` downloads every one. bdcdata warns when you're about to pull more
than 50 files, but it's better to look first:

```python
files = bdcdata.catalog.funding_files(data_type="Program")
files[["agency_name", "program_name"]].drop_duplicates()
```

Program data includes `program_id`, `program_name`, `authorization_date`,
`funding_committed`, and `funding_revised`. Project data includes `project_id`,
`project_name`, `funding_obligated`, `funding_disbursed`, `locations_planned`,
and `locations_supported`.

### Field names changed in 2026

Revision 6.0 of the funding specification (March 2026) renamed most columns for
clarity. If you're following an older tutorial or have existing code, the
mapping is:

| Old | New |
|---|---|
| `fund_ob` | `funding_obligated` |
| `funding_ob` | `funding_committed` |
| `funding_def` | `funding_revised` |
| `loc_sup` | `locations_supported` |
| `loc_plan` | `locations_planned` |
| `build_req` | `buildout_requirement` |

The same revision removed Middle Mile data (attributes, line segments, and
buildout) from the funding map entirely.

## `funded_locations()`

Locations covered by an enforceable commitment.

```python
# One row per funded location
bdcdata.funding.funded_locations(state="WA")

# Per-program breakdown: a location funded twice appears twice
bdcdata.funding.funded_locations(state="WA", by_program=True)
```

Both exports were added in the June 2026 API specification revision. If they
aren't published yet for your state, you get an empty DataFrame and a warning
explaining why.

## `projects_in_geography()`

Funded projects within a single geography.

```python
# What geographies are available
bdcdata.catalog.geographies()

# Projects in Albany County, NY
bdcdata.funding.projects_in_geography("county", "36001")
```

Geography types are `state`, `county`, `cdist` (congressional district),
`place`, `tribal`, and `cbsa`.

This endpoint returns a plain CSV rather than a ZIP — an inconsistency in the
API that bdcdata handles for you.

## Readme files

Some funding programs publish a PDF readme explaining their data.

```python
bdcdata.funding.readmes()
```

```
  program_id      program_name                                ref_id     file_name
0          1   BFM Funding Program   f4a81134-6f4a-4c24-a9b6-7d31af0d0b4a   Readme.pdf
```

```python
path = bdcdata.funding.download_readme("f4a81134-6f4a-4c24-a9b6-7d31af0d0b4a")
# PosixPath('readme_f4a81134-6f4a-4c24-a9b6-7d31af0d0b4a.pdf')

# Or choose where it lands
bdcdata.funding.download_readme(ref_id, dest="docs/program-readmes/")
```

This is the one function that writes a file rather than returning a DataFrame,
since the content is a PDF.
