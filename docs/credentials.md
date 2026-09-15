# Credentials

## Getting a token

You need a free FCC User Registration account. If you don't have one, the FCC's
instructions are at
<https://help.bdc.fcc.gov/hc/en-us/articles/20044640394395>.

Then:

1. Log in at <https://broadbandmap.fcc.gov/login>
2. Click your username in the top right, then **Manage API Access**
3. Click **Generate**. The first time, you'll accept a terms-of-use dialog
4. Copy the token and save it somewhere safe — the modal is your one good look
   at it

**Your username is the email address on your FCC account.** Not a display name,
not a handle. This is the single most common reason `check_credentials()`
fails.

You can regenerate or revoke the token from the same page at any time, and an
FCC administrator can revoke it too. If yours stops working, check that page
before assuming the problem is in your code.

## Supplying them

bdcdata looks in four places, in this order. The first complete pair wins.

### 1. Directly in the call

```python
bdcdata.availability.fixed(
    state="WA",
    technology="fiber",
    username="you@example.com",
    token="...",
)
```

Useful when you're juggling more than one account. Rarely what you want
otherwise.

### 2. `set_credentials()`

```python
import bdcdata

bdcdata.set_credentials(username="you@example.com", token="...")
```

Applies for the rest of the session. Good for interactive work, but don't
commit it — a token in a notebook is a token in your git history.

### 3. Environment variables

```bash
export BDC_USERNAME=you@example.com
export BDC_API_KEY=your-token
```

The best option for scripts, scheduled jobs, and CI. Nothing secret ends up in
the repository.

### 4. A `.env` file

Put a `.env` in your working directory:

```
BDC_USERNAME=you@example.com
BDC_API_KEY=your-token
```

Then either load it explicitly:

```python
bdcdata.load_dotenv()
```

...or just make a request — bdcdata checks for `.env` in the working directory
as a last resort before giving up.

**Add `.env` to your `.gitignore`.** The FCC token is tied to your personal
registration.

`load_dotenv()` uses [python-dotenv](https://pypi.org/project/python-dotenv/)
when it's installed (`pip install 'bdcdata[dotenv]'`) and otherwise falls back
to a small built-in parser that handles `KEY=value`, `#` comments, quoted
values, and a leading `export`.

## Checking

Verify against the live API — this makes exactly one request:

```python
bdcdata.check_credentials()
# True
```

Check whether credentials can be *found*, without any network call:

```python
bdcdata.have_credentials()
# True
```

`have_credentials()` is the one to use for skipping tests or branching in a
notebook, since it costs nothing and doesn't consume rate limit.

## Nothing is read at import

`import bdcdata` does not read your environment, does not look for a `.env`,
and does not contact the FCC. Credentials are resolved the first time you
actually request data.

This is deliberate, and it's a change from 1.x. It means `import bdcdata`
works on a machine that has never been configured — which matters for CI, for
test collection, for building documentation, and for anyone who just wants to
read `bdcdata.lookups.technologies()` without having an account yet.

## Your token stays out of output

`Credentials` masks the token in its `repr`, so it won't turn up in a
traceback, a notebook cell, or a log line:

```python
>>> from bdcdata.credentials import get_credentials
>>> get_credentials()
Credentials(username='you@example.com', token='***')
```

The token is only ever sent as the `hash_value` request header, which is what
the FCC API expects.

## Troubleshooting

**`BdcCredentialsMissing`** — nothing was found. The message lists every way to
supply credentials and how to generate a token. If only one of the two
variables is set, the message says which one is missing.

**`BdcAuthError`** — the FCC rejected what you sent. In order of likelihood:
the username isn't the account email; the token was regenerated (which
invalidates the old one); the token was revoked; you copied a truncated value.

**`BdcRateLimitError`** — you're over 10 calls per minute. bdcdata paces itself
to stay under that, so seeing this usually means another process is using the
same token at the same time.
