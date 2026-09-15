# Challenges

Disputes filed against the location Fabric and against reported availability,
plus the verification and audit processes the FCC added later.

```python
import bdcdata

df = bdcdata.challenges.fixed(state="WA", status="resolved")
```

## Releases are monthly

Challenge files are snapshots taken on the last day of each month, so the
challenge series has many more releases than the twice-yearly availability
series — and they are at different dates.

`release="latest"` resolves against the right series automatically. You do not
have to track which is which:

```python
bdcdata.catalog.releases("challenge").tail()
```

## The functions

Each maps onto one of the FCC's `category` strings.

```python
bdcdata.challenges.fabric(state="all", status="in_progress", release="latest")
bdcdata.challenges.fixed(state="all", status="in_progress", release="latest")
bdcdata.challenges.mobile(state="all", status="in_progress", release="latest")
bdcdata.challenges.verification(kind="mobile", status="in_progress", ...)
bdcdata.challenges.audit(status="in_progress", ...)
```

| Function | Statuses |
|---|---|
| `fabric()` | `in_progress`, `resolved` |
| `fixed()` | `in_progress`, `resolved`, `cumulative` |
| `mobile()` | `in_progress`, `resolved` |
| `verification(kind=...)` | `in_progress`, `resolved` |
| `audit()` | `in_progress`, `resolved` — mobile only |

`status` accepts some everyday synonyms: `"in progress"`, `"in-progress"`,
`"open"`, and `"pending"` all mean `in_progress`; `"closed"`, `"complete"`, and
`"completed"` all mean `resolved`.

Asking for a status a dataset doesn't have tells you what it does have:

```python
bdcdata.challenges.fabric(state="WA", status="cumulative")
# ValueError: status='cumulative' is not available for fabric challenges.
# Valid: 'in_progress', 'resolved'. See bdcdata.lookups.challenge_categories().
```

## Fabric challenges

Disputes about the location inventory itself — a missing address, a wrong unit
count, a building that isn't broadband serviceable.

```python
df = bdcdata.challenges.fabric(state="WA", status="in_progress")
```

In-progress files carry `challenge_id`, `fabric_vintage`, `category_code`,
`category_code_desc`, `location_id`, and `location_state`. Resolved files add
address fields and the adjudication outcome.

The eight category codes:

| Code | Meaning |
|---|---|
| 1 | Missing Broadband Serviceable Location |
| 2 | Incorrect Location Address |
| 3 | Incorrect Location Unit Count |
| 4 | Incorrect Location Building Type |
| 5 | Location is Not Within Correct Building Footprint |
| 6 | Location is Not Broadband Serviceable |
| 7 | Add Supplemental Address |
| 8 | Remove Secondary Address |

`location_id` is null when `category_code` is 1 or 8 — a challenge adding a
missing location has no ID to point at yet.

## Fixed challenges

Disputes about reported fixed availability — a provider says service is
available at a location and the resident says otherwise.

```python
df = bdcdata.challenges.fixed(state="WA", status="resolved")
```

Columns include `challenge_id`, `location_id`, `location_state`,
`data_vintage`, `frn`, `provider_id`, `technology`, `category_code`, and dates
(`request_date`, `date_received`, `withdraw_date`, `adjudication_date`).

`status="cumulative"` gives running counts by provider rather than individual
records — much smaller, and the right choice for a provider-level summary.

## Mobile challenges, verification, and audit

```python
bdcdata.challenges.mobile(state="WA", status="in_progress")
bdcdata.challenges.verification(kind="mobile", state="WA")
bdcdata.challenges.audit(state="WA")
```

Mobile challenges are keyed by H3 cell (`h3_cell_id`, `h3_resolution`) rather
than location, since mobile coverage is areal.

Verification and audit are distinct processes from challenges — they are the
FCC asking a provider to substantiate reported coverage, not a consumer
disputing it. Those categories were added in the September 2025 API
specification revision.

## Joining to availability

`location_id` is a string in both availability and challenge data, so they join
directly:

```python
avail = bdcdata.availability.fixed(state="WA", technology="fiber")
chal = bdcdata.challenges.fixed(state="WA", status="resolved")

merged = avail.merge(chal, on="location_id", how="left", suffixes=("", "_challenge"))
```

Worth knowing: the FCC's own specification calls `location_id` a `String{13}`
in the availability files and an `Integer` in the challenge files. bdcdata
makes it a string in both, precisely so this join works without a cast.

## When the FCC adds a category

The challenge category list has grown twice since 2023 — six new categories in
2025 alone. If the FCC adds one after this release, `bdcdata.challenges.get()`
reaches it without waiting for a package update:

```python
# See what the API currently offers
bdcdata.catalog.challenge_files(release="latest")["category"].unique()

# Then request it by exact string
bdcdata.challenges.get("Some New Category - In Progress", state="WA")
```

`bdcdata.lookups.challenge_categories()` shows the categories this release
knows about, which is a snapshot rather than the authority.

## Empty results

An empty DataFrame means the FCC published no file for that combination — a
state with no in-progress challenges this month, for instance. bdcdata logs a
warning saying so rather than raising, because "no challenges" is a legitimate
answer to the question.
