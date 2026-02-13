"""Common test fixtures for nautilus-adapter-gmocoin."""
import json
import os
from pathlib import Path

import pytest


CASSETTE_DIR = Path(__file__).parent / "cassettes"


def has_api_keys() -> bool:
    """Check if GMO Coin API keys are available."""
    env_path = os.environ.get("GMOCOIN_ENV_PATH", "")
    if env_path and os.path.exists(env_path):
        return True
    return bool(os.environ.get("GMOCOIN_API_KEY") and os.environ.get("GMOCOIN_API_SECRET"))


def load_api_keys():
    """Load API keys from environment or .env file."""
    api_key = os.environ.get("GMOCOIN_API_KEY", "")
    api_secret = os.environ.get("GMOCOIN_API_SECRET", "")

    if not api_key or not api_secret:
        env_path = os.environ.get("GMOCOIN_ENV_PATH", "")
        if env_path and os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GMOCOIN_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith("GMOCOIN_API_SECRET="):
                        api_secret = line.split("=", 1)[1].strip().strip('"').strip("'")

    return api_key, api_secret


def _check_rust_extension():
    try:
        import _nautilus_gmocoin
        return True
    except ImportError:
        try:
            from nautilus_gmocoin import _nautilus_gmocoin
            return True
        except ImportError:
            return False


def pytest_addoption(parser):
    parser.addoption(
        "--record-cassettes",
        action="store_true",
        default=False,
        help="Record live API responses to cassette fixture files",
    )


# Markers
requires_api_keys = pytest.mark.skipif(
    not has_api_keys(),
    reason="GMOCOIN_API_KEY and GMOCOIN_API_SECRET not set"
)

requires_rust_extension = pytest.mark.skipif(
    not _check_rust_extension(),
    reason="Rust extension not built (run: maturin develop)"
)

integration = pytest.mark.integration


@pytest.fixture
def vcr(request):
    """VCR-style fixture: record live API responses, replay from cassette files.

    Usage in tests:
        def test_something(self, vcr):
            result = vcr(_live(lambda c: c.some_api_py()))
            data = json.loads(result)
            assert ...

    Record cassettes:  pytest -m integration --record-cassettes
    Replay (default):  pytest  (uses committed cassette files)
    """
    record = request.config.getoption("--record-cassettes")

    # Build cassette name from test node: "TestClassName.test_method_name"
    node = request.node
    parent = node.parent
    if parent and parent.name and not parent.name.endswith(".py"):
        cassette_name = f"{parent.name}.{node.name}"
    else:
        cassette_name = node.name
    cassette_path = CASSETTE_DIR / f"{cassette_name}.json"

    def play_or_record(live_fn):
        if cassette_path.exists() and not record:
            # Replay from cassette
            data = json.loads(cassette_path.read_text())
            return json.dumps(data, ensure_ascii=False)
        if not record:
            pytest.skip(
                f"Cassette not found: {cassette_name}.json "
                "(run with --record-cassettes to record)"
            )
        # Record: execute live, save cassette
        result = live_fn()
        data = json.loads(result)
        cassette_path.parent.mkdir(parents=True, exist_ok=True)
        cassette_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        )
        return result

    return play_or_record
