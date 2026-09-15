# Quickstart

This page takes you from nothing to a DataFrame. It assumes you can run Python
and install a package, and nothing else.

## 1. Install

```bash
pip install bdcdata
```

If you want the mobile coverage data, which the FCC ships as GIS files, also
install the `mobile` extra:

```bash
pip install 'bdcdata[mobile]'
```

## 2. Get a token

Every BDC endpoint needs a username and an API token — even the ones that just
list what is available. You need a free FCC User Registration account first.

1. Log in at <https://broadbandmap.fcc.gov/login>
2. Click your username in the top right, then **Manage API Access**
3. Click **Generate**, accept the terms, and copy the token

Your **username is the email address** on the FCC account, not a display name.
This trips people up.

## 3. Tell bdcdata about it

The simplest way, good for trying things out:

```python
import bdcdata

bdcdata.set_credentials(username="you@example.com", token="paste-token-here")
```

Check it worked:

```python
bdcdata.check_credentials()
# True
```

For real work, keep the token out of your code — see
[Credentials](credentials.md) for environment variables and `.env` files.

## 4. See what's published

```python
bdcdata.catalog.releases()
```

```
      data_type  as_of_date
0  availability  2022-12-31
1  availability  2023-06-30
2  availability  2023-12-31
3  availability  2024-06-30
4     challenge  2025-01-31
5     challenge  2025-02-28
```

Availability data comes out twice a year. Challenge data comes out monthly, so
the two series are at different dates — `release="latest"` knows the difference
and picks the right one for whatever you are asking for.

## 5. Pull some data

```python
df = bdcdata.availability.fixed(state="WA", technology="fiber")
df.head()
```

```
          frn  provider_id    brand_name     location_id  technology  ...
0  0032176356       999100  Acme Telecom      1357135307          50
1  0000000123       999200  Beta Broadband   1357135308          50
```

That call did a fair amount for you: resolved `"latest"` to the current
release, translated `"WA"` to FIPS `53` and `"fiber"` to technology code `50`,
found the matching file in a catalog of thousands, downloaded and unzipped it,
and applied the column types from the FCC specification.

## 6. Turn on caching

If you are in a notebook and will run that cell again, do this first:

```python
bdcdata.set_cache(True)
```

Downloads then go to `./bdc_cache` and re-running is instant. Without it, every
run re-downloads, and the FCC's 10-calls-per-minute limit makes that slow.

```python
bdcdata.cache_info()
# {'enabled': True, 'path': '/home/you/project/bdc_cache', 'files': 1, 'bytes': 48317293}

bdcdata.clear_cache()  # when you want the space back
```

`clear_cache()` only deletes files bdcdata wrote, so it is safe even if you
point the cache somewhere with other things in it.

## Common next steps

**Several states at once:**

```python
df = bdcdata.availability.fixed(state=["WA", "OR", "ID"], technology="fiber")
```

**A technology group instead of one technology:**

```python
df = bdcdata.availability.fixed(state="WA", technology="wired")  # copper + cable + fiber
```

**Who is served and who isn't:**

```python
df = bdcdata.availability.served_unserved(state="WA")
df["any_dl100_ul20"].value_counts()
```

**A specific past release:**

```python
df = bdcdata.availability.fixed(state="WA", technology="fiber", release="2023-12-31")
```

## When something goes wrong

Errors are meant to tell you the fix. A few you might hit:

**Misspelled state or technology** — the error lists valid values and suggests
a correction:

```python
bdcdata.availability.fixed(state="Washingtn", technology="fiber")
# ValueError: 'Washingtn' is not a state, territory, or FIPS code.
# Did you mean 'washington'? See bdcdata.lookups.states() for the full list.
```

**Mixing up fixed and mobile technologies** — these are separate code sets:

```python
bdcdata.availability.fixed(state="WA", technology="5g")
# ValueError: '5g' is not a fixed technology.
#   Valid fixed codes: 0, 10, 40, 50, 60, 61, 70, 71, 72
#   Valid fixed names: 'other', 'copper', 'cable', 'fiber', ...
```

**A release that doesn't exist** — the error lists the ones that do:

```python
bdcdata.availability.fixed(state="WA", technology="fiber", release="2025-06-30")
# ValueError: No release published for '2025-06-30'.
#   Published releases: 2022-12-31, 2023-06-30, 2023-12-31, 2024-06-30
```

**An empty DataFrame** is not an error — it means the FCC publishes no file for
that combination. Check `bdcdata.catalog.availability_files()` to see what does
exist.

## Seeing what it's doing

Large pulls can take a while. To watch progress:

```python
import logging

logging.basicConfig(level=logging.INFO)
```

bdcdata never configures logging itself, so this is entirely under your
control. You can also pass `progress=True` to any data function for a progress
bar, with `pip install 'bdcdata[progress]'`.
