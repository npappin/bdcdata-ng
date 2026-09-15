"""Importing bdcdata must do nothing.

This is the regression that defines the 2.0 rewrite. In 1.x, ``__init__.py``
called ``load_dotenv()``, built an HTTP session, requested ``listAsOfDates``,
ran ``logging.basicConfig()``, attached a ``StreamHandler`` to the root logger,
and opened ``bdc.log`` for append -- all at import.

Since that endpoint now returns 401 without credentials, an import-time request
means ``import bdcdata`` fails on any machine that has not been configured,
including CI and documentation builds.

These run in subprocesses so each is a genuine cold import.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


def run_python(code: str, cwd: Path, env_extra: dict[str, str] | None = None) -> str:
    """Run *code* in a clean subprocess and return stdout."""
    import os

    env = dict(os.environ)
    # No credentials of any kind.
    env.pop("BDC_USERNAME", None)
    env.pop("BDC_API_KEY", None)
    env.update(env_extra or {})

    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        timeout=120,
    )
    if result.returncode != 0:
        pytest.fail(f"Subprocess failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return result.stdout


class TestNoNetworkAtImport:
    def test_import_succeeds_with_sockets_disabled(self, tmp_path):
        """The strongest form: make connecting impossible, then import.

        Patches ``connect`` rather than the ``socket`` class itself -- ``ssl``
        subclasses ``socket``, so replacing the class breaks the standard
        library before bdcdata is even reached.
        """
        output = run_python(
            """
            import socket

            def no_network(*args, **kwargs):
                raise RuntimeError("bdcdata opened a connection at import time")

            socket.socket.connect = no_network
            socket.socket.connect_ex = no_network
            socket.create_connection = no_network

            import bdcdata

            print("IMPORTED", bdcdata.__version__)
            """,
            cwd=tmp_path,
        )
        assert "IMPORTED" in output

    def test_import_succeeds_with_no_credentials(self, tmp_path):
        output = run_python(
            """
            import bdcdata
            print("HAVE_CREDENTIALS", bdcdata.have_credentials())
            """,
            cwd=tmp_path,
        )
        assert "HAVE_CREDENTIALS False" in output

    def test_submodules_import_without_network(self, tmp_path):
        """Accessing a submodule must not trigger a request either."""
        output = run_python(
            """
            import socket

            def no_network(*args, **kwargs):
                raise RuntimeError("bdcdata opened a connection at import time")

            socket.socket.connect = no_network
            socket.create_connection = no_network

            import bdcdata
            names = [
                bdcdata.availability.fixed,
                bdcdata.availability.mobile,
                bdcdata.challenges.fabric,
                bdcdata.funding.unserved_unfunded,
                bdcdata.catalog.releases,
                bdcdata.lookups.states,
            ]
            print("SUBMODULES", len(names))
            """,
            cwd=tmp_path,
        )
        assert "SUBMODULES 6" in output


class TestNoLoggingSideEffects:
    def test_root_logger_is_untouched(self, tmp_path):
        output = run_python(
            """
            import logging
            before = len(logging.getLogger().handlers)
            before_level = logging.getLogger().level

            import bdcdata

            after = len(logging.getLogger().handlers)
            after_level = logging.getLogger().level
            print("ROOT_HANDLERS", before, after)
            print("ROOT_LEVEL", before_level, after_level)
            """,
            cwd=tmp_path,
        )
        before, after = output.split("ROOT_HANDLERS ")[1].split("\n")[0].split()
        assert before == after, "bdcdata added a handler to the root logger"

        before_level, after_level = output.split("ROOT_LEVEL ")[1].split("\n")[0].split()
        assert before_level == after_level, "bdcdata changed the root logger level"

    def test_only_a_null_handler_is_attached(self, tmp_path):
        output = run_python(
            """
            import logging
            import bdcdata

            handlers = logging.getLogger("bdcdata").handlers
            print("HANDLERS", [type(h).__name__ for h in handlers])
            """,
            cwd=tmp_path,
        )
        assert "HANDLERS ['NullHandler']" in output

    def test_no_log_file_is_created(self, tmp_path):
        # v1 wrote bdc.log into the working directory on import.
        run_python("import bdcdata", cwd=tmp_path)

        assert list(tmp_path.iterdir()) == [], f"import created files: {list(tmp_path.iterdir())}"


class TestNoFilesystemSideEffects:
    def test_dotenv_is_not_read_automatically_at_import(self, tmp_path):
        (tmp_path / ".env").write_text(
            "BDC_USERNAME=leaked@example.com\nBDC_API_KEY=leaked-token\n"
        )

        output = run_python(
            """
            import os
            import bdcdata
            print("ENV_USER", os.environ.get("BDC_USERNAME"))
            """,
            cwd=tmp_path,
        )
        # Importing must not populate the environment. v1 called load_dotenv()
        # at import; here it happens only on an explicit call or first request.
        assert "ENV_USER None" in output

    def test_explicit_load_dotenv_does_read_it(self, tmp_path):
        (tmp_path / ".env").write_text("BDC_USERNAME=you@example.com\nBDC_API_KEY=a-token\n")

        output = run_python(
            """
            import bdcdata
            bdcdata.load_dotenv()
            print("HAVE_CREDENTIALS", bdcdata.have_credentials())
            """,
            cwd=tmp_path,
        )
        assert "HAVE_CREDENTIALS True" in output

    def test_no_cache_directory_is_created_at_import(self, tmp_path):
        run_python("import bdcdata", cwd=tmp_path)

        assert not (tmp_path / "bdc_cache").exists()


class TestImportCost:
    def test_pandas_is_not_imported_eagerly(self, tmp_path):
        """Keep ``import bdcdata`` snappy.

        pandas is a heavy import; the data functions pull it in on first use.
        """
        output = run_python(
            """
            import sys
            import bdcdata
            print("PANDAS_LOADED", "pandas" in sys.modules)
            """,
            cwd=tmp_path,
        )
        assert "PANDAS_LOADED False" in output
