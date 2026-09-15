# bdcdata

Work with FCC **Broadband Data Collection** (BDC) data in pandas.

The FCC publishes the National Broadband Map as thousands of individual ZIP
files, behind an authenticated API with a 10-calls-per-minute limit. Finding
the right file, downloading it, unzipping it, and reading it with the right
column types is most of the work of any BDC analysis. `bdcdata` does that part
so you can get to the analysis.

```python
import bdcdata

bdcdata.set_credentials(username="you@example.com", token="...")

df = bdcdata.availability.fixed(state="WA", technology="fiber")
```

## Start here

| Page | What's in it |
|---|---|
| [Quickstart](quickstart.md) | Install, authenticate, and pull your first dataset |
| [Credentials](credentials.md) | Getting a token and the four ways to supply it |
| [Availability](availability.md) | Who reports service where |
| [Challenges](challenges.md) | Disputes against the Fabric and against availability |
| [Funding](funding.md) | Programs, projects, and unserved/unfunded locations |
| [Migrating from 1.x](migrating-from-v1.md) | What changed and why |

## How it's organized

Three data modules, one per FCC data product, plus two support modules:

```
bdcdata.availability   fixed(), served_unserved(), mobile(), summaries
bdcdata.challenges     fabric(), fixed(), mobile(), verification(), audit()
bdcdata.funding        programs(), projects(), unserved_unfunded(), ...

bdcdata.catalog        what the FCC currently publishes
bdcdata.lookups        state and technology reference tables
```

Every data function takes `state` and `release` the same way and returns a
pandas DataFrame. There is nothing to construct and no object model to learn —
you call a function and get a table back.

## Things worth knowing up front

**You can write identifiers however you think of them.** `state="WA"`,
`state="Washington"`, and `state=53` all work. So do `technology="fiber"`,
`technology="fttp"`, and `technology=50`. When you get one wrong, the error
tells you what the valid values are.

**`release="latest"` is the default**, and it resolves against what the FCC
publishes today rather than a date frozen into the source code.

**ID columns are strings.** `location_id`, `block_geoid`, `frn`, and the H3
cell IDs come back as text, not numbers, so leading zeros and full precision
survive. This matters: `frn` `0032176356` is not the number 32,176,356, and a
13-digit `location_id` does not fit in a 32-bit integer.

**Nothing happens when you import.** No network call, no config file read, no
logging setup. Credentials are resolved on your first real request.

**Downloads are not cached unless you ask.** Turn it on with
`bdcdata.set_cache(True)` — worth doing in a notebook, where you will run the
same cell more than once.

## Getting help

- `help(bdcdata.availability.fixed)` works, and every function has a real
  docstring with examples.
- `bdcdata.lookups.states()` and `bdcdata.lookups.technologies()` show you the
  valid codes as DataFrames.
- `bdcdata.catalog.availability_files()` shows what exists before you download
  anything.

## Source specifications

The column layouts and endpoints here are transcribed from the FCC's published
specifications:

- BDC Public Data API Specifications, rev 1.7 (2026-06-08)
- Specifications for Data Downloads from the National Broadband Map,
  rev 2.4.3 (2026-08-11)
- Specifications for Data Downloads from the Broadband Funding Map,
  rev 6.0 (2026-03-16)
