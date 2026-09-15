# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [2.0.0] — unreleased

A ground-up rewrite. The submodule layout (`bdcdata.availability.fixed()`) is
unchanged, but arguments, credential handling, and return types all changed.
See [docs/migrating-from-v1.md](docs/migrating-from-v1.md).

### Added

- **Challenge data.** `challenges.fabric()`, `challenges.fixed()`,
  `challenges.mobile()`, `challenges.verification()`, `challenges.audit()`, and
  `challenges.get()` for categories added after this release. These were
  import-only stubs in 1.x.
- **Funding data.** `funding.programs()`, `funding.projects()`,
  `funding.unserved_unfunded()`, `funding.funded_locations()`,
  `funding.projects_in_geography()`, `funding.readmes()`, and
  `funding.download_readme()`. Also stubs in 1.x.
- **Mobile availability.** `availability.mobile()` reads the H3 coverage
  attribute table without requiring geopandas, via the optional
  `bdcdata[mobile]` extra.
- **Served/unserved.** `availability.served_unserved()`, covering the export
  added in the 2026-08-11 specification revision.
- **Summary tables.** `availability.provider_list()`,
  `availability.provider_summary()`, and
  `availability.summary_by_geography()`.
- **A browsable catalog.** `bdcdata.catalog` wraps `listAsOfDates`,
  `listAvailabilityData`, `listChallengeData`, `listFundingData`,
  `listReadmeFiles`, and `listGeographyData`.
- **Reference tables.** `bdcdata.lookups.states()`,
  `lookups.technologies()`, and `lookups.challenge_categories()`.
- **Friendly identifiers.** `state=` accepts FIPS codes, USPS abbreviations,
  and full names; `technology=` accepts codes, slugs, descriptions, aliases
  (`"dsl"`, `"fttp"`, `"lte"`), and groups (`"wired"`, `"satellite"`,
  `"terrestrial"`, `"wireless"`).
- **Typed exceptions.** `BdcError` and its subclasses, replacing bare
  `Exception`. Every message says what to do next.
- **Credential helpers.** `set_credentials()`, `load_dotenv()`,
  `have_credentials()`, `check_credentials()`.
- **Cache controls.** `set_cache()`, `cache_info()`, `clear_cache()`.
- Type hints throughout, with a `py.typed` marker.

### Changed

- **`import bdcdata` has no side effects.** No network call, no `.env` read, no
  logging configuration. Credentials resolve on first request.
- **Logging no longer hijacks the root logger.** A `NullHandler` on the
  `bdcdata` logger, nothing more. No `basicConfig()`, no `StreamHandler`, no
  `bdc.log` file.
- **Base URL is now `https://bdc.fcc.gov`**, matching the current FCC
  specification. Override with `set_base_url()`.
- **`states=` is now `state=`** (singular), and accepts far more spellings.
- **`release` defaults to `"latest"`** instead of a hardcoded date, and
  resolves separately for availability and challenge data.
- **Identifier columns are strings**: `location_id`, `block_geoid`, `frn`,
  `h3_res8_id`, `h3_res9_id`, `state_fips`.
- **Cache is off by default**, lives in `./bdc_cache`, is keyed by request URL
  rather than filename, and is configured globally via `set_cache()`.
- **`release` and `state_fips` columns are added** to downloaded frames, so
  multi-state and multi-release pulls stay separable.
- Validation happens before any network request.
- Multi-file downloads concatenate once instead of inside the loop.

### Fixed

- **`business_residential_code` dtype hint.** 1.x misspelled it
  (`business_residental_code`), so the hint silently never applied.
- **`location_id` overflow.** 1.x typed it `UInt32` (max 4,294,967,295) while
  the FCC specification defines it as `String{13}`. Now a string.
- **Challenge downloads were unreachable.** 1.x hardcoded `availability` as the
  `data_type` path segment, so no challenge file could be fetched.
- **Archive member selection.** 1.x read `zip.filelist[0]` blindly; sidecar
  entries (`__MACOSX`, readmes) are now skipped and CSVs preferred.

### Removed

- **`fabric` module.** Its two functions did nothing — one printed a message,
  the other read a path nothing wrote. Fabric is licensed data on a different
  access path, so it is out of scope rather than present and broken.
- `bdcdata.echo()` and the `main()` entry point.
- Module-level `apiKey`, `username`, `session`, and `metadata` globals.
- The `requests-ratelimiter` dependency, replaced by a built-in limiter that
  also handles retries and `Retry-After`.

### Dependencies

- Core: `requests`, `pandas>=2`, `pyarrow`.
- Optional: `bdcdata[mobile]` (pyogrio), `bdcdata[dotenv]` (python-dotenv),
  `bdcdata[progress]` (tqdm).
- Requires Python 3.10+.

---

## [1.x]

See the [pre-2.0 history](https://github.com/npappin/bdcdata/commits/main).
Supported fixed availability by state and technology; challenge, funding, and
fabric modules were stubs.
