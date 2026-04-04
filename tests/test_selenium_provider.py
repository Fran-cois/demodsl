"""Tests for demodsl.providers.selenium_browser — SeleniumBrowserProvider."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from demodsl.models import Locator


# ── Fixtures — mock selenium imports ─────────────────────────────────────────


@pytest.fixture(autouse=True)
def _mock_selenium(monkeypatch):
    """Mock selenium so tests don't require a real browser."""
    selenium_mod = MagicMock()
    webdriver_mod = MagicMock()
    chrome_opts = MagicMock()
    chrome_svc = MagicMock()
    by_mod = MagicMock()
    by_mod.By.CSS_SELECTOR = "css selector"
    by_mod.By.XPATH = "xpath"
    by_mod.By.ID = "id"
    by_mod.By.LINK_TEXT = "link text"
    ec_mod = MagicMock()
    wait_mod = MagicMock()

    monkeypatch.setitem(sys.modules, "selenium", selenium_mod)
    monkeypatch.setitem(sys.modules, "selenium.webdriver", webdriver_mod)
    monkeypatch.setitem(sys.modules, "selenium.webdriver.chrome", MagicMock())
    monkeypatch.setitem(sys.modules, "selenium.webdriver.chrome.options", chrome_opts)
    monkeypatch.setitem(sys.modules, "selenium.webdriver.chrome.service", chrome_svc)
    monkeypatch.setitem(sys.modules, "selenium.webdriver.common", MagicMock())
    monkeypatch.setitem(sys.modules, "selenium.webdriver.common.by", by_mod)
    monkeypatch.setitem(sys.modules, "selenium.webdriver.support", MagicMock())
    monkeypatch.setitem(
        sys.modules, "selenium.webdriver.support.expected_conditions", ec_mod
    )
    monkeypatch.setitem(sys.modules, "selenium.webdriver.support.ui", wait_mod)


def _make_provider():
    """Create a SeleniumBrowserProvider with a mock driver."""
    from demodsl.providers.selenium_browser import SeleniumBrowserProvider

    provider = SeleniumBrowserProvider()
    provider._driver = MagicMock()
    provider._viewport = {"width": 3840, "height": 2160}
    return provider


# ── Tests ────────────────────────────────────────────────────────────────────


class TestResolveBy:
    def test_css(self):
        from demodsl.providers.selenium_browser import SeleniumBrowserProvider

        loc = Locator(type="css", value="div.main")
        by, val = SeleniumBrowserProvider._resolve_by(loc)
        assert by == "css selector"
        assert val == "div.main"

    def test_id(self):
        from demodsl.providers.selenium_browser import SeleniumBrowserProvider

        loc = Locator(type="id", value="my-elem")
        by, val = SeleniumBrowserProvider._resolve_by(loc)
        assert by == "id"
        assert val == "my-elem"

    def test_xpath(self):
        from demodsl.providers.selenium_browser import SeleniumBrowserProvider

        loc = Locator(type="xpath", value="//div[@class='x']")
        by, val = SeleniumBrowserProvider._resolve_by(loc)
        assert by == "xpath"
        assert val == "//div[@class='x']"

    def test_text_generates_xpath(self):
        from demodsl.providers.selenium_browser import SeleniumBrowserProvider

        loc = Locator(type="text", value="Click me")
        by, val = SeleniumBrowserProvider._resolve_by(loc)
        assert by == "xpath"
        assert "contains(text()" in val
        assert "Click me" in val

    def test_unsupported_raises(self):
        from demodsl.providers.selenium_browser import SeleniumBrowserProvider

        loc = MagicMock()
        loc.type = "aria"
        loc.value = "label"
        with pytest.raises(ValueError, match="Unsupported locator type"):
            SeleniumBrowserProvider._resolve_by(loc)


class TestEvaluateJs:
    def test_delegates_to_execute_script(self):
        p = _make_provider()
        p._driver.execute_script.return_value = 42
        result = p.evaluate_js("1 + 1")
        p._driver.execute_script.assert_called_once_with("1 + 1")
        assert result == 42


class TestNavigate:
    def test_calls_get_and_waits(self):
        p = _make_provider()
        p.navigate("https://example.com")
        p._driver.get.assert_called_once_with("https://example.com")
        # Should call execute_script for readyState & scroll lock
        assert p._driver.execute_script.call_count >= 1


class TestClick:
    def test_finds_and_clicks(self):
        p = _make_provider()
        mock_elem = MagicMock()
        p._driver.find_element.return_value = mock_elem
        p.click(Locator(type="css", value="button.submit"))
        p._driver.find_element.assert_called_once()
        mock_elem.click.assert_called_once()


class TestTypeText:
    def test_clears_and_types(self):
        p = _make_provider()
        mock_elem = MagicMock()
        p._driver.find_element.return_value = mock_elem
        p.type_text(Locator(type="id", value="input1"), "hello")
        mock_elem.clear.assert_called_once()
        mock_elem.send_keys.assert_called_once_with("hello")


class TestScroll:
    def test_scroll_down(self):
        p = _make_provider()
        p.scroll("down", 500)
        p._driver.execute_script.assert_called_with("window.scrollBy(0, 500)")

    def test_scroll_up(self):
        p = _make_provider()
        p.scroll("up", 300)
        p._driver.execute_script.assert_called_with("window.scrollBy(0, -300)")

    def test_scroll_right_unlocks_horizontal(self):
        p = _make_provider()
        p.scroll("right", 200)
        calls = [c.args[0] for c in p._driver.execute_script.call_args_list]
        assert any("scrollBy(200, 0)" in c for c in calls)


class TestScreenshot:
    def test_screenshot_writes_file(self, tmp_path):
        import base64

        p = _make_provider()
        # Fake a 1-pixel white PNG
        fake_png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100).decode()
        p._driver.execute_cdp_cmd.return_value = {"data": fake_png}
        out = p.screenshot(tmp_path / "shot.png")
        assert out.exists()
        p._driver.execute_cdp_cmd.assert_called_once()


class TestGetElementCenter:
    def test_returns_center(self):
        p = _make_provider()
        mock_elem = MagicMock()
        mock_elem.location = {"x": 100, "y": 200}
        mock_elem.size = {"width": 50, "height": 30}
        p._driver.find_element.return_value = mock_elem
        center = p.get_element_center(Locator(type="css", value="div"))
        assert center == (125.0, 215.0)

    def test_returns_none_on_error(self):
        p = _make_provider()
        p._driver.find_element.side_effect = Exception("not found")
        assert p.get_element_center(Locator(type="css", value="div")) is None


class TestGetElementBbox:
    def test_returns_bbox(self):
        p = _make_provider()
        mock_elem = MagicMock()
        mock_elem.location = {"x": 10, "y": 20}
        mock_elem.size = {"width": 100, "height": 50}
        p._driver.find_element.return_value = mock_elem
        bbox = p.get_element_bbox(Locator(type="css", value="div"))
        assert bbox == {"x": 10.0, "y": 20.0, "width": 100.0, "height": 50.0}


class TestCloseWithoutRecording:
    def test_quits_driver(self):
        p = _make_provider()
        p._recorder = None
        p._recording = False
        result = p.close()
        p._driver.quit.assert_called_once()
        assert result is None


class TestFactoryRegistration:
    def test_selenium_registered(self):
        from demodsl.providers.base import BrowserProviderFactory

        assert BrowserProviderFactory.create("selenium") is not None


class TestProviderModelField:
    def test_default_is_playwright(self):
        from demodsl.models import Scenario

        s = Scenario(name="test", url="https://example.com", steps=[])
        assert s.provider == "playwright"

    def test_selenium_accepted(self):
        from demodsl.models import Scenario

        s = Scenario(
            name="test", url="https://example.com", provider="selenium", steps=[]
        )
        assert s.provider == "selenium"

    def test_invalid_rejected(self):
        from demodsl.models import Scenario

        with pytest.raises(Exception):
            Scenario(
                name="test", url="https://example.com", provider="invalid", steps=[]
            )
