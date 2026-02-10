"""Common test fixtures for nautilus-adapter-gmocoin."""
import os
import pytest


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


# Markers
requires_api_keys = pytest.mark.skipif(
    not has_api_keys(),
    reason="GMOCOIN_API_KEY and GMOCOIN_API_SECRET not set"
)

requires_rust_extension = pytest.mark.skipif(
    not _check_rust_extension(),
    reason="Rust extension not built (run: maturin develop)"
)
