import pytest
from crawl4ai import BrowserConfig


def test_browser_config_init_extra_args():
    """
    Regression test to ensure BrowserConfig accepts 'extra_args'
    and does not regress to expecting 'args' or failing on valid config.
    """
    try:
        config = BrowserConfig(headless=True, verbose=True, extra_args=["--no-sandbox"])
        assert config.extra_args == ["--no-sandbox"]
    except TypeError as e:
        pytest.fail(
            f"BrowserConfig raised TypeError, possibly due to invalid arguments: {e}"
        )
    except Exception as e:
        pytest.fail(f"BrowserConfig init failed with unexpected error: {e}")
