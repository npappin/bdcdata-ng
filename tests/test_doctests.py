"""Run the executable examples in docstrings.

The normalizer docstrings carry real, runnable examples -- they are the first
thing someone sees from `help(bdcdata.availability.fixed)` and from the docs.
Running them here means a change in behavior breaks the build rather than
quietly making the documentation wrong.

Docstrings that would need network access mark their examples
``# doctest: +SKIP``.
"""

from __future__ import annotations

import doctest

import pytest

from bdcdata import _normalize, _schemas, lookups


@pytest.mark.parametrize("module", [_normalize, _schemas, lookups])
def test_docstring_examples(module):
    results = doctest.testmod(module, verbose=False, report=True)

    assert results.failed == 0, f"{results.failed} doctest(s) failed in {module.__name__}"
