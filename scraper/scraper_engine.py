# scraper/scraper_engine.py
import requests
import time
import random
import logging
import hashlib
import json
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from django.utils import timezone
from urllib.parse import urlparse, parse_qs
from .models import DailySlotData, Store, ScrapingError

from playwright.sync_api import sync_playwright, Response, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger("scraper")


class PachinkoScraper:
    """
    Robust Playwright-driven scraper for min-repo.com store pages.
    - Renders JS
    - Captures JSON/XHR responses
    - Clicks through "tabs" to reveal all tables
    - Dynamically maps headers to fields
    """

    def __init__(self, use_browser: bool = True, headless: bool = True, wait_table_timeout: int = 8_000):
        self.base_url = "https://min-repo.com"
        self.use_browser = use_browser
        self.headless = headless
        self.wait_table_timeout = wait_table_timeout

        # requests fallback
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
            ),
            "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
        })

        # A flexible header -> field mapping (expand as needed)
        self.column_map = {
            "台番号": "machine_number",
            "番号": "machine_number",
            "機種": "machine_name",
            "機種名": "machine_name",
            "差枚": "credit_difference",
            "平均差枚": "credit_difference",
            "総差枚": "credit_difference",
            "出玉": "credit_difference",
            "平均G数": "game_count",
            "ゲーム数": "game_count",
            "回転数": "game_count",
            "BB": "bb",
            "RB": "rb",
            "合成": "synthesis",
            "機械割": "payout_rate",
            "出率": "payout_rate",
            "BB確率": "bb_rate",
            "RB確率": "rb_rate",
            "勝率": "win_rate",
        }

        # Tab keyword heuristics (Japanese + English)
        self.tab_keywords = ["機種", "機種別", "バラエティ", "Variety", "By model", "suffix", "サフィックス", "機種別データ"]

    # -------------------- Helpers --------------------
    def _safe_int(self, value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        try:
            s = str(value).strip()
            # drop leading +, commas, and common suffixes
            s = s.replace(",", "").replace("+", "").replace("枚", "").replace("回", "").replace("円", "")
            if s == "" or s.lower() in ("-", "null", "none"):
                return None
            return int(float(s))
        except Exception:
            return None

    def _safe_float(self, value: Optional[str]) -> Optional[float]:
        if value is None:
            return None
        try:
            s = str(value).strip().replace("%", "").replace(",", "")
            if s == "" or s.lower() in ("-", "null", "none"):
                return None
            return float(s)
        except Exception:
            return None

    def _parse_win_rate(self, text: str):
        """
        Parse '3/5' style to wins,total,percent
        Returns (wins:int or None, total:int or None, pct:float or None)
        """
        if not text:
            return None, None, None
        text = text.strip()
        if "/" in text:
            try:
                parts = text.split("/")
                wins = self._safe_int(parts[0])
                total = self._safe_int(parts[1])
                if wins is not None and total and total > 0:
                    pct = round((wins / total) * 100.0, 2)
                else:
                    pct = None
                return wins, total, pct
            except Exception:
                return None, None, None
        # if already a percentage:
        if "%" in text:
            pct = self._safe_float(text)
            return None, None, pct
        return None, None, None

    def _generate_mysql_id(self, store_id, target_date, unique_key) -> int:
        date_str = target_date.strftime("%Y%m%d")
        raw = f"{store_id}_{date_str}_{unique_key}_{time.time_ns()}"
        return int(hashlib.md5(raw.encode()).hexdigest()[:15], 16)

    def _model_has_field(self, field_name: str) -> bool:
        # Safe check whether your model has a field (so we don't set unknown attributes)
        try:
            return any(f.name == field_name for f in DailySlotData._meta.get_fields())
        except Exception:
            return False

    # -------------------- Page rendering & capture --------------------
    def _render_page_and_capture(self, url: str, max_tab_clicks: int = 6) -> Dict[str, Any]:
        """
        Render page via Playwright, click candidate tab elements, capture:
          - html_fragments: list of HTML snapshots after each tab activation
          - json_payloads: list of parsed JSON from XHR responses
        """
        fragments: List[str] = []
        captured_jsons: List[Any] = []

        if not self.use_browser:
            # fallback to requests
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return {"html_fragments": [resp.text], "json_payloads": []}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless,
                                       args=[
                                           "--no-sandbox",
                                           "--disable-dev-shm-usage",
                                           "--disable-blink-features=AutomationControlled",
                                       ])
            page = browser.new_page()
            page.set_extra_http_headers({"User-Agent": self.session.headers["User-Agent"]})
            response_jsons = []

            def _on_response(response: Response):
                try:
                    ct = response.headers.get("content-type", "")
                    url_r = response.url
                    # heuristic: JSON endpoints or xhr
                    if "application/json" in ct.lower() or url_r.lower().endswith(".json") or "ajax" in url_r.lower() or "api" in url_r.lower():
                        try:
                            text = response.text()
                            # parse small JSON bodies only (avoid giant binary)
                            if text and len(text) < 5_000_000:
                                parsed = json.loads(text)
                                response_jsons.append({"url": url_r, "json": parsed})
                        except Exception:
                            pass
                except Exception:
                    pass

            page.on("response", _on_response)

            try:
                page.goto(url, timeout=60_000)
            except PlaywrightTimeoutError:
                logger.warning("Playwright: initial page.goto timeout, continuing with current DOM.")

            # allow network idle & small wait
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except PlaywrightTimeoutError:
                pass
            page.wait_for_timeout(1_200)

            # initial snapshot
            try:
                fragments.append(page.content())
            except Exception:
                pass

            # Find possible tab-like controls and click them
            candidate_selectors = ["a", "button", "li", "span", "label", "div"]
            clicks_done = 0
            seen_texts = set()

            # gather clickable elements that contain any tab_keywords in their visible text
            clickable_locators = []
            for tag in candidate_selectors:
                elems = page.query_selector_all(tag)
                for el in elems:
                    try:
                        text = (el.inner_text() or "").strip()
                        if not text:
                            continue
                        # reduce noise
                        txt_norm = text.replace("\n", " ").strip()
                        if txt_norm in seen_texts:
                            continue
                        for kw in self.tab_keywords:
                            if kw in txt_norm:
                                clickable_locators.append(el)
                                seen_texts.add(txt_norm)
                                break
                    except Exception:
                        continue
                if len(clickable_locators) >= max_tab_clicks:
                    break

            # Click each candidate and capture snapshot after action
            for el in clickable_locators[:max_tab_clicks]:
                try:
                    # scroll into view and click
                    el.scroll_into_view_if_needed()
                    el.click(force=True, timeout=5_000)
                    # wait for any network activity (XHR) to settle
                    try:
                        page.wait_for_load_state("networkidle", timeout=6_000)
                    except PlaywrightTimeoutError:
                        pass
                    page.wait_for_timeout(800)  # small pause
                    fragments.append(page.content())
                    clicks_done += 1
                except Exception:
                    # ignore click failures
                    continue

            # Also try clicking elements that have 'tab' role or data attributes pointing to table
            # (best-effort; site-specific tuning may be needed)
            # No more clicks; now close
            captured_jsons = response_jsons
            try:
                browser.close()
            except Exception:
                pass

        return {"html_fragments": fragments, "json_payloads": captured_jsons}

    # -------------------- DOM parsing --------------------
    def _extract_from_table_html(self, html: str, store: Store, target_date, page_url: str) -> List[DailySlotData]:
        soup = BeautifulSoup(html, "html.parser")
        results: List[DailySlotData] = []

        # find all table elements
        tables = soup.find_all("table")
        if not tables:
            return results

        for table in tables:
            # collect headers (if any)
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            # If there are no headers, try infer small table by number of columns by the first row
            if not headers:
                first_row = table.find("tr")
                if not first_row:
                    continue
                td_count = len(first_row.find_all("td"))
                # create generic headers if none found (best-effort)
                headers = [f"col_{i}" for i in range(td_count)]

            mapped_headers = [self.column_map.get(h, None) for h in headers]

            # iterate rows (skip header row)
            for tr in table.find_all("tr"):
                tds = tr.find_all("td")
                # skip empty / header-only rows
                if not tds:
                    continue
                # if mismatch in td count and header len, try to proceed with min length
                # get text of each td
                td_texts = [td.get_text(strip=True) for td in tds]
                # skip rows too short
                if len(td_texts) < 1:
                    continue

                data: Dict[str, Any] = {}
                unmapped: Dict[str, str] = {}
                for idx, cell_text in enumerate(td_texts):
                    hdr = headers[idx] if idx < len(headers) else f"col_{idx}"
                    mapped = self.column_map.get(hdr)
                    if not mapped:
                        # maybe header was something like '勝率' but the actual header text is present in some other language
                        unmapped[hdr] = cell_text
                        continue
                    # handle special mapped types
                    if mapped in ("machine_number", "credit_difference", "game_count", "bb", "rb"):
                        data[mapped] = self._safe_int(cell_text)
                    elif mapped in ("payout_rate", "bb_rate", "rb_rate"):
                        data[mapped] = self._safe_float(cell_text)
                    elif mapped == "win_rate":
                        wins, total, pct = self._parse_win_rate(cell_text)
                        # store wins/total in bb/rb if model doesn't have dedicated fields
                        data["bb"] = wins
                        data["rb"] = total
                        data["win_rate"] = pct
                    else:
                        data[mapped] = cell_text

                # Accept row if we have at least machine_number or machine_name or credit_difference (aggregated table)
                if not any(k in data for k in ("machine_number", "machine_name", "credit_difference")):
                    continue

                # try to find machine_id in anchor href inside the row (if present)
                machine_id = None
                try:
                    a = tr.find("a", href=True)
                    if a:
                        parsed = parse_qs(urlparse(a["href"]).query)
                        if "num" in parsed:
                            machine_id = self._safe_int(parsed.get("num")[0])
                except Exception:
                    machine_id = None

                # unique key for ID generation
                unique_key = data.get("machine_number") or data.get("machine_name") or hash("".join(td_texts)) & 0xFFFFFF
                unique_id = self._generate_mysql_id(store.store_id, target_date, unique_key)

                # build kwargs carefully only allowing fields that exist on the model
                kwargs = {
                    "id": unique_id,
                    "date": target_date,
                    "store_id": store.store_id,
                    "machine_id": machine_id,
                    "data_url": page_url
                }

                # whitelisted fields typical in your model
                allowed_fields = [
                    "machine_number",
                    "credit_difference",
                    "game_count",
                    "payout_rate",
                    "bb",
                    "rb",
                    "synthesis",
                    "bb_rate",
                    "rb_rate",
                    "win_rate"
                ]
                for k in allowed_fields:
                    if k in data and self._model_has_field(k):
                        kwargs[k] = data[k]

                # create model instance (unsaved)
                try:
                    slot = DailySlotData(**kwargs)
                    # attach unmapped info if model supports raw_data
                    if unmapped and self._model_has_field("raw_data"):
                        try:
                            setattr(slot, "raw_data", {"unmapped": unmapped, "parsed_at": timezone.now().isoformat()})
                        except Exception:
                            pass
                    results.append(slot)
                except Exception as e:
                    logger.debug(f"Failed to create DailySlotData instance for row: {e}")
                    continue

        return results

    # -------------------- JSON parsing --------------------
    def _extract_from_json_payloads(self, payloads: List[Dict[str, Any]], store: Store, target_date, page_url: str) -> List[DailySlotData]:
        """
        Try to locate arrays of machine data inside JSON responses.
        This is heuristic: we search for list values where items are dicts that contain numeric fields like '差枚', 'g', 'game', 'bb', etc.
        """
        results: List[DailySlotData] = []

        for p in payloads:
            body = p.get("json")
            if not body:
                continue

            # if body itself is list of dicts
            candidates = []
            if isinstance(body, list):
                candidates.append(body)
            elif isinstance(body, dict):
                # find nested lists with dict items
                for k, v in body.items():
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        candidates.append(v)

            for c in candidates:
                for item in c:
                    # best-effort field extraction by key name similarity
                    # normalize keys to lower/strip
                    lk = {str(k).lower(): v for k, v in item.items()}
                    # heuristics
                    machine_number = None
                    credit_difference = None
                    game_count = None
                    bb = None
                    rb = None
                    payout_rate = None
                    machine_id = None

                    # try common keys
                    for key in ("machine_number", "no", "台番号", "number", "num"):
                        if key in lk:
                            machine_number = self._safe_int(lk[key])
                            break
                    for key in ("difference", "差枚", "credit", "差"):
                        if key in lk:
                            credit_difference = self._safe_int(lk[key])
                            break
                    for key in ("game_count", "g", "games", "回転数"):
                        if key in lk:
                            game_count = self._safe_int(lk[key])
                            break
                    for key in ("bb",):
                        if key in lk:
                            bb = self._safe_int(lk[key])
                            break
                    for key in ("rb",):
                        if key in lk:
                            rb = self._safe_int(lk[key])
                            break
                    for key in ("payout_rate", "rate", "出率"):
                        if key in lk:
                            payout_rate = self._safe_float(lk[key])
                            break
                    for key in ("id", "machine_id", "num"):
                        if key in lk:
                            machine_id = self._safe_int(lk[key])
                            break

                    if machine_number is None and credit_difference is None:
                        # skip unlikely entries
                        continue

                    unique_key = machine_number or machine_id or hash(str(item)) & 0xFFFFFF
                    uid = self._generate_mysql_id(store.store_id, target_date, unique_key)

                    kwargs = {
                        "id": uid,
                        "date": target_date,
                        "store_id": store.store_id,
                        "machine_id": machine_id,
                        "data_url": page_url
                    }
                    for k, v in (
                        ("machine_number", machine_number),
                        ("credit_difference", credit_difference),
                        ("game_count", game_count),
                        ("bb", bb),
                        ("rb", rb),
                        ("payout_rate", payout_rate),
                    ):
                        if v is not None and self._model_has_field(k):
                            kwargs[k] = v

                    try:
                        slot = DailySlotData(**kwargs)
                        # attach item raw if model supports raw_data
                        if self._model_has_field("raw_data"):
                            try:
                                setattr(slot, "raw_data", {"source": p.get("url"), "payload_item": item})
                            except Exception:
                                pass
                        results.append(slot)
                    except Exception:
                        continue

        return results

    # -------------------- Orchestration --------------------
    def _parse_store_page_enhanced(self, html_content: str, store: Store, target_date, url: str) -> List[DailySlotData]:
        """
        Main orchestrator: try JSON payloads first (if any found while rendering),
        otherwise parse all table HTML snapshots.
        """
        # If use_browser, perform interactive render to also capture XHR and tabbed snapshots
        if self.use_browser:
            capture = self._render_page_and_capture(url)
            fragments = capture.get("html_fragments", [])
            json_payloads = capture.get("json_payloads", [])
        else:
            # fallback only static HTML
            fragments = [html_content]
            json_payloads = []

        # First try JSON payloads (faster, less error-prone)
        if json_payloads:
            try:
                from itertools import chain
                json_items = self._extract_from_json_payloads(json_payloads, store, target_date, url)
                if json_items:
                    logger.info(f"Extracted {len(json_items)} items from JSON payloads")
                    return json_items
            except Exception:
                logger.debug("JSON extraction failed, will fall back to DOM parsing.")

        # Parse every HTML fragment (snapshots for initial + tabs)
        all_rows: List[DailySlotData] = []
        for frag in fragments:
            try:
                rows = self._extract_from_table_html(frag, store, target_date, url)
                if rows:
                    all_rows.extend(rows)
            except Exception as e:
                logger.debug(f"Failed parsing fragment: {e}")
                continue

        # Deduplicate by unique id
        unique_map = {}
        for r in all_rows:
            try:
                unique_map[getattr(r, "id")] = r
            except Exception:
                pass

        final_rows = list(unique_map.values())
        return final_rows

    # -------------------- Error logging --------------------
    def _log_error(self, session, store_id: int, error_type: str, error_message: str, url: str):
        try:
            ScrapingError.objects.create(
                session=session,
                store_id=store_id,
                error_type=error_type,
                error_message=error_message,
                url=url
            )
        except Exception as e:
            logger.error(f"Failed to log error to database: {e}")

    # Public wrapper (keeps signature similar to your existing code)
    def scrape_store_data(self, store_id: int, target_date, scraping_session) -> Dict:
        """Compatibility wrapper so your management command stays the same."""
        # reuse your previous flow but call the enhanced parser
        result = {
            "success": False,
            "store_id": store_id,
            "records_created": 0,
            "errors": []
        }
        try:
            store, _ = Store.objects.get_or_create(store_id=store_id, defaults={"is_active": True})
            url = f"{self.base_url}/{store_id}/"
            logger.info(f"Scraping store {store_id}: {url}")

            # polite random delay
            time.sleep(random.uniform(0.5, 2.0))

            # initial HTML using requests only (for non-browser mode) - we pass it to enhanced parser which can re-render
            initial_html = None
            try:
                initial_html = self.session.get(url, timeout=30).text
            except Exception:
                initial_html = ""

            rows = self._parse_store_page_enhanced(initial_html, store, target_date, url)

            if rows:
                for slot in rows:
                    try:
                        # attach scraping session if field exists
                        if self._model_has_field("scraping_session"):
                            try:
                                setattr(slot, "scraping_session", scraping_session)
                            except Exception:
                                pass
                    except Exception:
                        pass

                try:
                    DailySlotData.objects.bulk_create(rows, ignore_conflicts=True, batch_size=1000)
                    result["records_created"] = len(rows)
                    result["success"] = True
                    logger.info(f"Successfully scraped {len(rows)} records for store {store_id}")
                except Exception as db_err:
                    error_msg = str(db_err)
                    result["errors"].append(error_msg)
                    logger.error(f"DB error: {error_msg}")
            else:
                result["errors"].append("No valid data found on page")
                logger.warning(f"No valid data found for store {store_id}")
        except Exception as e:
            result["errors"].append(str(e))
            logger.error(f"Scraping failed: {e}")
            try:
                self._log_error(scraping_session, store_id, "ScrapingException", str(e), f"{self.base_url}/{store_id}/")
            except Exception:
                pass
        return result
