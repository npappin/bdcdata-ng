# Migrating from 1.x

**2.0 is a rewrite.** The API changed, and code written against 1.x will not
run unchanged. This page covers what moved and why.

## The short version

```python
# 1.x
import bdcdata  # made a network call on this line

df = bdcdata.availability.fixed(states="53", technology="50", release="2024-06-30", cache=True)

# 2.0
import bdcdata  # does nothing

bdcdata.set_credentials(username="you@example.com", token="...")
bdcdata.set_cache(True)
df = bdcdata.availability.fixed(state="WA", technology="fiber")
```

The submodule layout is unchanged — `bdcdata.availability.fixed()` is still
`bdcdata.availability.fixed()`.

## Argument changes

| 1.x | 2.0 | Notes |
|---|---|---|
| `states=` | `state=` | Singular; still accepts a list |
| `states="53"` | `state="WA"` | FIPS codes still work; so do names |
| `technology="50"` | `technology="fiber"` | Codes still work; so do names and groups |
| `release="2024-06-30"` | `release="latest"` | Explicit dates still work |
| `cache=True` | `cache=True` or `set_cache(True)` | Now settable globally |

Everything 1.x accepted, 2.0 still accepts. The difference is that 2.0 accepts
a lot more:

```python
bdcdata.availability.fixed(state="53", technology="50")  # 1.x style
bdcdata.availability.fixed(state="WA", technology="fiber")  # equivalent
bdcdata.availability.fixed(state="Washington", technology="fttp")  # also equivalent
bdcdata.availability.fixed(state=53, technology=50)  # also equivalent
```

## Credentials must be supplied explicitly

1.x called `load_dotenv()` at import and read `BDC_API_KEY` and `BDC_USERNAME`
into module-level globals. 2.0 never reads anything at import.

If you relied on a `.env` file, add one line:

```python
import bdcdata

bdcdata.load_dotenv()
```

Environment variables still work with no code change at all — the variable
names (`BDC_USERNAME`, `BDC_API_KEY`) are unchanged.

### Why

The metadata endpoint 1.x called at import now requires authentication. That
made `import bdcdata` fail outright on any machine without credentials —
including CI runners, test collection, and documentation builds. An import that
can fail because of a network condition is an import you cannot rely on.

## Logging no longer hijacks your application

1.x ran `logging.basicConfig()` at import, attached a `StreamHandler` to the
root logger, set the level to `DEBUG`, and opened `bdc.log` in the working
directory for append. Any program that imported bdcdata inherited all of that.

2.0 attaches a `NullHandler` to the `bdcdata` logger and nothing else. To see
log output, ask for it:

```python
import logging

logging.basicConfig(level=logging.INFO)
```

No `bdc.log` file is created.

## Two dtype bugs are fixed

These changed the values you get back, so check any code that depends on them.

**`business_residental_code` → `business_residential_code`.** 1.x misspelled
the column in its dtype hints (missing the second `i`), so the hint silently
never applied and the column fell back to inferred typing.

**`location_id` is now a string.** 1.x typed it `UInt32`, whose maximum is
4,294,967,295. The FCC specification defines `location_id` as `String{13}`, and
a 13-digit ID does not fit. If you were casting it back to compare against
other sources, you can stop:

```python
# 1.x workaround, no longer needed
df["location_id"] = df["location_id"].astype(str)
```

The same applies to `block_geoid`, `frn`, and the H3 cell IDs — all strings
now, with leading zeros intact.

## The cache moved

1.x wrote to `./cache/{filename}.zip` relative to the working directory,
whenever `cache=True` was passed.

2.0 writes to `./bdc_cache/` with a `.bdccache` suffix, is off by default, and
is configured globally:

```python
bdcdata.set_cache(True)  # ./bdc_cache
bdcdata.set_cache(True, path="~/bdc-data")  # anywhere you like
bdcdata.cache_info()
bdcdata.clear_cache()  # only deletes bdcdata's own files
```

Cache entries are keyed by request URL rather than by filename, so two requests
that differ only in a query parameter no longer collide. **Your 1.x `./cache`
directory is not reused** — delete it when you're done migrating.

## Errors are specific now

1.x raised bare `Exception` for every failure. 2.0 raises typed exceptions you
can catch:

```python
import bdcdata

try:
    df = bdcdata.availability.fixed(state="WA", technology="fiber")
except bdcdata.BdcAuthError:
    ...  # token rejected
except bdcdata.BdcUnprocessableError:
    ...  # no file for that combination
except bdcdata.BdcRateLimitError:
    ...  # over 10 calls/minute
except bdcdata.BdcError:
    ...  # catches all of the above
```

Validation errors now fire *before* any network request, so a typo costs you
nothing:

```python
bdcdata.availability.fixed(state="Washingtn", technology="fiber")
# ValueError raised immediately -- no request made
```

## What's new

**Challenge and funding data actually work.** In 1.x, `challenge.py` and
`funding.py` were five-line import stubs with no functions. The download path
was hardcoded to `downloadFile/availability/{file_id}`, so challenge files were
unreachable even in principle.

```python
bdcdata.challenges.fabric(state="WA")
bdcdata.challenges.fixed(state="WA", status="resolved")
bdcdata.funding.unserved_unfunded(state="WA")
```

**Mobile availability.** 1.x had a commented-out block for it. 2.0 reads the
GIS attribute table without requiring geopandas:

```python
bdcdata.availability.mobile(state="WA", technology="5g")  # needs bdcdata[mobile]
```

**Served/unserved**, added in the August 2026 specification revision:

```python
bdcdata.availability.served_unserved(state="WA")
```

**A browsable catalog:**

```python
bdcdata.catalog.releases()
bdcdata.catalog.availability_files(release="latest")
bdcdata.catalog.challenge_files(release="latest")
```

**Reference tables:**

```python
bdcdata.lookups.states()
bdcdata.lookups.technologies("fixed")
bdcdata.lookups.challenge_categories()
```

## What's gone

**`fabric.py`.** 1.x had a `process()` that printed a message and returned
`True`, and a `load()` that read a CSV path nothing ever wrote. Neither did
anything. Fabric data is licensed and reaches users through a different channel
than the public downloads, so it is out of scope for 2.0 rather than present
and non-functional.

**`bdcdata.echo()`** and the `main()` entry point, which were scaffolding.

**Module-level `apiKey`, `username`, `session`, and `metadata` globals.**
Use `set_credentials()` and `bdcdata.catalog.releases()` instead.

## Other changes worth knowing

**The API host moved.** 2.0 talks to `https://bdc.fcc.gov`, which is what the
current FCC specification documents. 1.x used `broadbandmap.fcc.gov`, which
still answers today but is no longer the documented host. Override with
`bdcdata.set_base_url()` if you need to.

**Rate limiting is built in.** 1.x used `requests-ratelimiter`. 2.0 has its own
shared limiter at the documented 10 calls per minute, plus retry with backoff
that honors `Retry-After`. `requests-ratelimiter` is no longer a dependency.

**Multi-state pulls got faster.** 1.x concatenated inside its download loop,
which is quadratic. 2.0 accumulates and concatenates once.

**`release` and `state_fips` columns are added** to downloaded data. The FCC's
files don't always carry their own vintage or state, so pulling several at once
in 1.x gave you a frame you couldn't take apart again.
