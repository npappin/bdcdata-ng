# bdcdata

Work with FCC **Broadband Data Collection** (BDC) data in pandas.

`bdcdata` handles the parts of the National Broadband Map that are tedious to
get right — authentication, the 10-calls-per-minute rate limit, finding the
right file among thousands, unzipping it, and applying the column types from
the FCC's published specification — and hands you a DataFrame.

```python
import bdcdata

bdcdata.set_credentials(username="you@example.com", token="...")

df = bdcdata.availability.fixed(state="WA", technology="fiber")
```

You can write `state="WA"`, `state="Washington"`, or `state=53`, and
`technology="fiber"`, `technology="fttp"`, or `technology=50`. They all mean
the same thing.

## Install

```bash
pip install bdcdata
```

Reading the mobile H3 coverage files means opening a shapefile, which needs an
extra:

```bash
pip install 'bdcdata[mobile]'
```

## Credentials

Every BDC endpoint requires an FCC username and API token, including the
metadata endpoints.

1. Log in at <https://broadbandmap.fcc.gov/login> with your FCC User
   Registration account.
2. Click your username in the top right, then **Manage API Access**.
3. Click **Generate**, accept the terms, and copy the token.

Your username is the email address on the account. Then pick whichever of
these suits you:

```python
bdcdata.set_credentials(username="you@example.com", token="...")
```

```bash
export BDC_USERNAME=you@example.com
export BDC_API_KEY=...
```

```python
# .env file in your working directory, with BDC_USERNAME and BDC_API_KEY
bdcdata.load_dotenv()
```

Check them with `bdcdata.check_credentials()`.

## Documentation

See the [`docs/`](docs/) directory.

## Upgrading from 1.x

**2.0 is a rewrite and the API changed.** See
[docs/migrating-from-v1.md](docs/migrating-from-v1.md).

## License

MIT
