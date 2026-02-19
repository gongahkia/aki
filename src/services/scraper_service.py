"""Scraper service for Singapore case law from public sources.

Sources:
  - CommonLII  (http://www.commonlii.org/sg/) - free SG case law archive
  - Judiciary SG (https://www.judiciary.gov.sg/judgments) - official judgments
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

COMMONLII_BASE = "http://www.commonlii.org"
JUDICIARY_BASE = "https://www.judiciary.gov.sg"

COURTS: Dict[str, str] = {
    "SGCA": "Court of Appeal",
    "SGHC": "High Court",
    "SGDC": "District Court",
    "SGMC": "Magistrate's Court",
}

# tort-related keywords for case filtering
_TORT_KWS = [
    "negligence",
    "duty of care",
    "breach of duty",
    "standard of care",
    "causation",
    "but-for",
    "material contribution",
    "remoteness",
    "foreseeability",
    "battery",
    "assault",
    "false imprisonment",
    "trespass to land",
    "trespass to person",
    "private nuisance",
    "nuisance",
    "defamation",
    "libel",
    "slander",
    "vicarious liability",
    "strict liability",
    "rylands v fletcher",
    "occupiers liability",
    "product liability",
    "nervous shock",
    "psychiatric harm",
    "economic loss",
    "pure economic loss",
    "contributory negligence",
    "volenti",
    "res ipsa loquitur",
    "tortious",
    "unlawful interference",
    "harassment",
    "employer's liability",
]

# topic → keywords for inference
_TOPIC_MAP: Dict[str, List[str]] = {
    "negligence": ["negligence", "duty of care", "breach of duty", "res ipsa loquitur"],
    "duty_of_care": ["duty of care", "neighbour principle", "proximity", "caparo"],
    "causation": ["causation", "but-for", "but for", "material contribution"],
    "remoteness": ["remoteness", "foreseeability", "too remote", "wagon mound"],
    "battery": ["battery", "intentional contact", "unlawful force"],
    "assault": ["assault", "apprehension", "immediate unlawful force"],
    "false_imprisonment": [
        "false imprisonment",
        "unlawful detention",
        "restraint of liberty",
    ],
    "defamation": ["defamation", "libel", "slander", "reputation", "defamatory"],
    "private_nuisance": ["nuisance", "unreasonable interference", "enjoyment of land"],
    "trespass_to_land": ["trespass to land", "unlawful entry", "direct interference"],
    "vicarious_liability": [
        "vicarious liability",
        "employer liability",
        "course of employment",
    ],
    "strict_liability": ["strict liability", "rylands v fletcher", "non-natural use"],
    "occupiers_liability": [
        "occupiers liability",
        "premises",
        "visitor",
        "trespasser",
        "occupier",
    ],
    "product_liability": [
        "product liability",
        "defective product",
        "manufacturer",
        "consumer protection",
    ],
    "contributory_negligence": [
        "contributory negligence",
        "claimant's own fault",
        "apportionment",
    ],
    "economic_loss": ["economic loss", "pure economic loss", "financial loss"],
    "psychiatric_harm": [
        "psychiatric harm",
        "nervous shock",
        "mental injury",
        "ptsd",
        "primary victim",
    ],
    "employers_liability": [
        "employer",
        "workplace safety",
        "safe system of work",
        "safe place of work",
    ],
    "harassment": ["harassment", "course of conduct", "alarm or distress"],
}

_HEADERS = {
    "User-Agent": (
        "Jikai/2.0 Legal Research Tool (educational; Singapore tort law; "
        "https://github.com/gongahkia/jikai)"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-SG,en;q=0.9",
}

_REQUEST_DELAY = 1.5  # seconds between requests (polite crawling)


def _require_bs4():
    try:
        from bs4 import BeautifulSoup  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "beautifulsoup4 is required for scraping. "
            "Run: pip install beautifulsoup4 lxml"
        ) from e


def _infer_topics(text: str) -> List[str]:
    """Infer tort topics from case text based on keyword presence."""
    text_lower = text.lower()
    topics = [t for t, kws in _TOPIC_MAP.items() if any(kw in text_lower for kw in kws)]
    return topics or ["negligence"]


def _is_tort_case(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in _TORT_KWS)


def _clean_case_text(raw: str) -> str:
    """Strip boilerplate, excess whitespace from scraped case text."""
    # collapse blank lines
    text = re.sub(r"\n{3,}", "\n\n", raw)
    # strip leading/trailing whitespace per line
    lines = [ln.rstrip() for ln in text.splitlines()]
    return "\n".join(lines).strip()


def _entry_from_case(title: str, text: str, meta: Dict) -> Dict:
    now = datetime.utcnow().isoformat()
    return {
        "text": text,
        "topic": _infer_topics(text),
        "metadata": {**meta, "title": title, "jurisdiction": "Singapore"},
        "created_at": now,
        "updated_at": now,
    }


class CommonLIIScraper:
    """Async scraper for Singapore case law from CommonLII."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _client_get(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=_HEADERS,
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_case_urls(self, court: str, year: int) -> List[str]:
        """Return list of case page URLs for a given court and year."""
        _require_bs4()
        from bs4 import BeautifulSoup

        index_url = f"{COMMONLII_BASE}/sg/cases/{court}/{year}/"
        client = await self._client_get()
        try:
            resp = await client.get(index_url)
            resp.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning("CommonLII index fetch failed %s: %s", index_url, e)
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        pattern = re.compile(rf"/sg/cases/{court}/{year}/\d+\.html$")
        urls = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if pattern.search(href):
                full = href if href.startswith("http") else COMMONLII_BASE + href
                if full not in urls:
                    urls.append(full)
        return urls

    async def fetch_case(self, url: str) -> Optional[Tuple[str, str]]:
        """Fetch a single case page. Returns (title, cleaned_text) or None."""
        _require_bs4()
        from bs4 import BeautifulSoup

        client = await self._client_get()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning("Case fetch failed %s: %s", url, e)
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        # title: prefer <title> or first <h1>
        title_el = soup.find("title") or soup.find("h1")
        title = title_el.get_text(" ", strip=True) if title_el else url.split("/")[-1]
        title = re.sub(r"\s+", " ", title).strip()
        # body text: try common CommonLII content wrappers
        body = (
            soup.find("div", class_="body-text")
            or soup.find("div", id="content")
            or soup.find("div", id="main-content")
            or soup.find("div", class_="judgement")
            or soup.find("body")
        )
        if not body:
            return None
        # remove nav/footer/script/style noise
        for tag in body.find_all(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        raw_text = body.get_text(separator="\n", strip=True)
        return title, _clean_case_text(raw_text)

    async def scrape(
        self,
        courts: List[str],
        years: List[int],
        max_cases: int = 50,
        tort_only: bool = True,
        progress_cb=None,
    ) -> List[Dict]:
        """Scrape SG case law from CommonLII.

        Args:
            courts: list of court codes, e.g. ["SGHC", "SGCA"]
            years: list of years to scrape
            max_cases: cap on total cases returned
            tort_only: if True, filter to tort-related cases only
            progress_cb: optional callable(fetched, total_urls) for progress reporting
        Returns:
            list of corpus-ready dicts
        """
        results: List[Dict] = []
        all_urls: List[Tuple[str, str, int]] = []  # (url, court, year)
        # collect URLs first
        for court in courts:
            for year in years:
                urls = await self.fetch_case_urls(court, year)
                for u in urls:
                    all_urls.append((u, court, year))
                await asyncio.sleep(_REQUEST_DELAY)

        total = len(all_urls)
        for i, (url, court, year) in enumerate(all_urls):
            if len(results) >= max_cases:
                break
            result = await self.fetch_case(url)
            if progress_cb:
                progress_cb(i + 1, total)
            if result is None:
                await asyncio.sleep(_REQUEST_DELAY)
                continue
            title, text = result
            if tort_only and not _is_tort_case(text):
                await asyncio.sleep(_REQUEST_DELAY)
                continue
            entry = _entry_from_case(
                title,
                text,
                {
                    "source": "commonlii",
                    "source_url": url,
                    "court": COURTS.get(court, court),
                    "year": year,
                },
            )
            results.append(entry)
            logger.info("Scraped: %s (%d topics)", title[:60], len(entry["topic"]))
            await asyncio.sleep(_REQUEST_DELAY)

        return results


class JudiciarySGScraper:
    """Scraper for judiciary.gov.sg judgment search.

    Note: judiciary.gov.sg uses a server-rendered search. This scraper
    targets the keyword search endpoint. May break if the site changes.
    """

    _SEARCH_URL = "https://www.judiciary.gov.sg/judgments/search"

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _client_get(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=_HEADERS,
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search_judgments(
        self, keywords: str, page: int = 1
    ) -> List[Tuple[str, str]]:
        """Search judiciary.gov.sg. Returns list of (title, url) pairs."""
        _require_bs4()
        from bs4 import BeautifulSoup

        client = await self._client_get()
        params = {"q": keywords, "page": str(page)}
        try:
            resp = await client.get(self._SEARCH_URL, params=params)
            resp.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning("Judiciary search failed: %s", e)
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        results: List[Tuple[str, str]] = []
        # judgment links typically have /judgments/ in href
        for a in soup.find_all("a", href=re.compile(r"/judgments/[^/]+")):
            href = a["href"]
            full = href if href.startswith("http") else JUDICIARY_BASE + href
            title = a.get_text(" ", strip=True)
            if title and full not in [u for _, u in results]:
                results.append((title, full))
        return results

    async def fetch_judgment(self, url: str) -> Optional[Tuple[str, str]]:
        """Fetch a single judgment page. Returns (title, text) or None."""
        _require_bs4()
        from bs4 import BeautifulSoup

        client = await self._client_get()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning("Judgment fetch failed %s: %s", url, e)
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        title_el = soup.find("h1") or soup.find("title")
        title = title_el.get_text(" ", strip=True) if title_el else url.split("/")[-1]
        content = (
            soup.find("div", class_="judgment-content")
            or soup.find("div", class_="content")
            or soup.find("main")
            or soup.find("body")
        )
        if not content:
            return None
        for tag in content.find_all(["script", "style", "nav", "aside"]):
            tag.decompose()
        return title, _clean_case_text(content.get_text(separator="\n", strip=True))

    async def scrape_tort_judgments(
        self, max_cases: int = 30, progress_cb=None
    ) -> List[Dict]:
        """Scrape tort-related judgments from judiciary.gov.sg."""
        keywords = "negligence tort duty of care"
        all_links: List[Tuple[str, str]] = []
        for page in range(1, 4):  # first 3 pages
            links = await self.search_judgments(keywords, page=page)
            all_links.extend(links)
            if not links:
                break
            await asyncio.sleep(_REQUEST_DELAY)

        results: List[Dict] = []
        for i, (title, url) in enumerate(all_links):
            if len(results) >= max_cases:
                break
            result = await self.fetch_judgment(url)
            if progress_cb:
                progress_cb(i + 1, len(all_links))
            if result is None:
                await asyncio.sleep(_REQUEST_DELAY)
                continue
            _, text = result
            if not _is_tort_case(text):
                await asyncio.sleep(_REQUEST_DELAY)
                continue
            entry = _entry_from_case(
                title,
                text,
                {"source": "judiciary_sg", "source_url": url},
            )
            results.append(entry)
            await asyncio.sleep(_REQUEST_DELAY)
        return results


def save_scraped(
    entries: List[Dict], out_dir: str = "corpus/raw/scraped"
) -> List[Path]:
    """Save scraped entries as individual .txt files in out_dir.

    Returns list of written paths (for the OCR preprocessor to pick up).
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for i, entry in enumerate(entries):
        title_slug = re.sub(
            r"[^\w\-]", "_", entry.get("metadata", {}).get("title", f"case_{i}")
        )[:60]
        path = out / f"{title_slug}.txt"
        # write text file with metadata header for downstream processing
        header = (
            f"# Source: {entry['metadata'].get('source', 'unknown')}\n"
            f"# Court: {entry['metadata'].get('court', 'unknown')}\n"
            f"# Year: {entry['metadata'].get('year', 'unknown')}\n"
            f"# URL: {entry['metadata'].get('source_url', '')}\n"
            f"# Topics: {', '.join(entry.get('topic', []))}\n"
            f"# Jurisdiction: Singapore\n\n"
        )
        path.write_text(header + entry["text"], encoding="utf-8")
        written.append(path)
    return written


def merge_into_corpus(
    entries: List[Dict], corpus_path: str = "corpus/clean/tort/corpus.json"
) -> int:
    """Merge scraped entries into existing corpus JSON. Returns count added."""
    cp = Path(corpus_path)
    existing: List[Dict] = []
    if cp.exists():
        try:
            loaded = json.loads(cp.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing = loaded
            elif isinstance(loaded, dict):
                existing = loaded.get("entries", [])
        except Exception:
            existing = []
    existing_urls = {e.get("metadata", {}).get("source_url", "") for e in existing}
    new_entries = [
        e
        for e in entries
        if e.get("metadata", {}).get("source_url", "") not in existing_urls
    ]
    if not new_entries:
        return 0
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(
        json.dumps(existing + new_entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return len(new_entries)


async def run_scraper(
    source: str,
    courts: Optional[List[str]] = None,
    years: Optional[List[int]] = None,
    max_cases: int = 50,
    tort_only: bool = True,
    progress_cb=None,
) -> List[Dict]:
    """Top-level async entry point for the TUI.

    source: "commonlii" | "judiciary"
    """
    if source == "commonlii":
        cli = CommonLIIScraper()
        try:
            return await cli.scrape(
                courts=courts or ["SGHC", "SGCA"],
                years=years or [datetime.now().year - 1, datetime.now().year - 2],
                max_cases=max_cases,
                tort_only=tort_only,
                progress_cb=progress_cb,
            )
        finally:
            await cli.close()
    elif source == "judiciary":
        jud = JudiciarySGScraper()
        try:
            return await jud.scrape_tort_judgments(
                max_cases=max_cases,
                progress_cb=progress_cb,
            )
        finally:
            await jud.close()
    else:
        raise ValueError(f"Unknown scraper source: {source}")
