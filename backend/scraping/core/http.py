"""HTTP robuste pour le scraping (retry, headers, repli Selenium)."""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def build_session(*, retries: int = 3) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers.update(DEFAULT_HEADERS)
    return session


def fetch_html(
    url: str,
    *,
    timeout: int = 20,
    headers: dict | None = None,
    session: requests.Session | None = None,
) -> str:
    sess = session or build_session()
    hdrs = {**sess.headers, **(headers or {})}
    resp = sess.get(url, timeout=timeout, headers=hdrs)
    resp.raise_for_status()
    return resp.text


def fetch_soup(
    url: str,
    *,
    timeout: int = 20,
    headers: dict | None = None,
    use_selenium_on_forbidden: bool = False,
) -> BeautifulSoup:
    try:
        html = fetch_html(url, timeout=timeout, headers=headers)
        return BeautifulSoup(html, "html.parser")
    except requests.HTTPError as e:
        if use_selenium_on_forbidden and e.response is not None and e.response.status_code == 403:
            logging.warning("HTTP 403 sur %s — repli Selenium", url)
            html = _fetch_with_selenium(url)
            return BeautifulSoup(html, "html.parser")
        raise


def _fetch_with_selenium(url: str) -> str:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service as ChromeService
    from webdriver_manager.chrome import ChromeDriverManager

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={DEFAULT_HEADERS['User-Agent']}")

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options,
    )
    try:
        driver.set_page_load_timeout(30)
        driver.get(url)
        time.sleep(2)
        return driver.page_source
    finally:
        driver.quit()


def fetch_legisocial(template: str, *, timeout: int = 15) -> requests.Response:
    """Essaie l'année courante puis N-1."""
    from core.year_utils import fetch_years_fallback

    last_exc: Optional[Exception] = None
    for y in fetch_years_fallback():
        url = template.format(year=y)
        try:
            resp = requests.get(
                url, timeout=timeout, headers=DEFAULT_HEADERS
            )
            if resp.status_code == 200:
                return resp
        except requests.RequestException as e:
            last_exc = e
            continue
    raise RuntimeError(
        f"URL LegiSocial inaccessible: {template} — {last_exc}"
    )
