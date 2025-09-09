import requests
import time
import random
import logging
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional
from django.utils import timezone
from .models import DailySlotData, Store, ScrapingError

logger = logging.getLogger('scraper')

class PachinkoScraper:
    """Enhanced scraping engine for pachinko data"""
    
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://min-repo.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session.headers.update(self.headers)
        
    def scrape_store_data(self, store_id: int, target_date, scraping_session) -> Dict:
        """Scrape data for a single store"""
        result = {
            'success': False,
            'store_id': store_id,
            'records_created': 0,
            'errors': []
        }
        
        try:
            # Get or create Store object
            store, created = Store.objects.get_or_create(
                store_id=store_id,
                defaults={'is_active': True}
            )
            
            # Build URL
            url = f"{self.base_url}/{store_id}/"
            logger.info(f"Scraping store {store_id}: {url}")
            
            # Add random delay to avoid rate limiting
            time.sleep(random.uniform(1, 3))
            
            # Make request
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Debug: Save HTML for inspection
            if logger.isEnabledFor(logging.DEBUG):
                with open(f'debug_store_{store_id}.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                logger.debug(f"Saved HTML to debug_store_{store_id}.html")
            
            # Parse data with multiple strategies
            slot_data_list = self._parse_store_page_enhanced(response.text, store, target_date, url)
            
            if slot_data_list:
                # Add scraping session to each record
                for slot_data in slot_data_list:
                    slot_data.scraping_session = scraping_session
                
                # Bulk create records
                try:
                    DailySlotData.objects.bulk_create(
                        slot_data_list,
                        ignore_conflicts=True,
                        batch_size=1000
                    )
                    result['records_created'] = len(slot_data_list)
                    result['success'] = True
                    logger.info(f"Successfully scraped {len(slot_data_list)} records for store {store_id}")
                    
                    # Update store success
                    store.last_successful_scrape = timezone.now()
                    store.consecutive_failures = 0
                    store.save()
                    
                except Exception as db_error:
                    error_msg = f"Database error: {str(db_error)}"
                    result['errors'].append(error_msg)
                    logger.error(f"Database error for store {store_id}: {error_msg}")
                
            else:
                result['errors'].append("No valid data found on page")
                logger.warning(f"No valid data found for store {store_id}")
                
        except requests.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            result['errors'].append(error_msg)
            logger.error(f"Request error for store {store_id}: {error_msg}")
            self._log_error(scraping_session, store_id, "RequestException", error_msg, url)
            
        except Exception as e:
            error_msg = f"Parsing failed: {str(e)}"
            result['errors'].append(error_msg)
            logger.error(f"Parsing error for store {store_id}: {error_msg}")
            self._log_error(scraping_session, store_id, "ParsingException", error_msg, url)
            
        return result
    
    def _parse_store_page_enhanced(self, html_content: str, store: Store, target_date, url: str) -> List[DailySlotData]:
        """Enhanced parsing with multiple strategies"""
        soup = BeautifulSoup(html_content, 'html.parser')
        slot_data_list = []
        
        # Strategy 1: Look for tables with specific selectors
        strategies = [
            self._parse_table_strategy,
            self._parse_div_strategy,
            self._parse_list_strategy,
            self._parse_json_strategy
        ]
        
        for strategy_func in strategies:
            try:
                result = strategy_func(soup, store, target_date, url)
                if result:
                    logger.info(f"Successfully parsed {len(result)} records using {strategy_func.__name__}")
                    return result
            except Exception as e:
                logger.debug(f"Strategy {strategy_func.__name__} failed: {str(e)}")
                continue
        
        logger.warning(f"All parsing strategies failed for store {store.store_id}")
        return slot_data_list
    
    def _parse_table_strategy(self, soup: BeautifulSoup, store: Store, target_date, url: str) -> List[DailySlotData]:
        """Parse data from HTML tables"""
        slot_data_list = []
        
        # Look for tables with different selectors
        table_selectors = [
            'table.data-table',
            'table#machine-data',
            'table[class*="machine"]',
            'table[class*="data"]',
            'div.machine-list table',
            'table'
        ]
        
        for selector in table_selectors:
            tables = soup.select(selector)
            for table in tables:
                rows = table.find_all('tr')
                if len(rows) < 2:  # Need at least header + 1 data row
                    continue
                    
                logger.debug(f"Processing table with {len(rows)} rows using selector: {selector}")
                
                # Identify data rows (skip obvious headers)
                data_rows = []
                for i, row in enumerate(rows):
                    if not self._is_header_row(row):
                        data_rows.append((i, row))
                
                if not data_rows:
                    continue
                
                # Parse each data row
                for row_index, row in data_rows:
                    try:
                        slot_data = self._parse_machine_row_enhanced(row, store, target_date, url, row_index)
                        if slot_data:
                            slot_data_list.append(slot_data)
                    except Exception as e:
                        logger.debug(f"Failed to parse row {row_index}: {str(e)}")
                        continue
                
                if slot_data_list:
                    return slot_data_list
        
        return slot_data_list
    
    def _parse_div_strategy(self, soup: BeautifulSoup, store: Store, target_date, url: str) -> List[DailySlotData]:
        """Parse data from div elements (alternative layout)"""
        slot_data_list = []
        
        # Look for div-based layouts
        div_selectors = [
            'div.machine-item',
            'div.machine-row',
            'div[class*="machine"]',
            'div[class*="slot"]',
            'div[data-machine]',
        ]
        
        for selector in div_selectors:
            divs = soup.select(selector)
            if divs:
                logger.debug(f"Found {len(divs)} machine divs with selector: {selector}")
                for i, div in enumerate(divs):
                    try:
                        slot_data = self._parse_machine_div(div, store, target_date, url, i)
                        if slot_data:
                            slot_data_list.append(slot_data)
                    except Exception as e:
                        logger.debug(f"Failed to parse div {i}: {str(e)}")
                        continue
                
                if slot_data_list:
                    return slot_data_list
        
        return slot_data_list
    
    def _parse_list_strategy(self, soup: BeautifulSoup, store: Store, target_date, url: str) -> List[DailySlotData]:
        """Parse data from list elements"""
        slot_data_list = []
        
        # Look for list-based layouts
        list_selectors = [
            'ul.machine-list li',
            'ol.machine-list li',
            'ul[class*="machine"] li',
            'li[class*="machine"]',
        ]
        
        for selector in list_selectors:
            items = soup.select(selector)
            if items:
                logger.debug(f"Found {len(items)} machine list items with selector: {selector}")
                for i, item in enumerate(items):
                    try:
                        slot_data = self._parse_machine_list_item(item, store, target_date, url, i)
                        if slot_data:
                            slot_data_list.append(slot_data)
                    except Exception as e:
                        logger.debug(f"Failed to parse list item {i}: {str(e)}")
                        continue
                
                if slot_data_list:
                    return slot_data_list
        
        return slot_data_list
    
    def _parse_json_strategy(self, soup: BeautifulSoup, store: Store, target_date, url: str) -> List[DailySlotData]:
        """Parse data from embedded JSON"""
        slot_data_list = []
        
        # Look for JSON data in script tags
        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string:
                try:
                    import json
                    # Look for JSON-like patterns
                    content = script.string
                    if 'machine' in content.lower() or 'slot' in content.lower():
                        # Try to extract JSON data (implementation depends on actual format)
                        logger.debug("Found potential JSON data in script tag")
                        # Add actual JSON parsing logic here based on site structure
                except Exception as e:
                    continue
        
        return slot_data_list
    
    # In scraper/scraper_engine.py - Update the _parse_machine_row_enhanced method

    def _parse_machine_row_enhanced(self, row, store: Store, target_date, url: str, row_index: int) -> Optional[DailySlotData]:
        """Enhanced machine row parsing for MySQL"""
        cells = row.find_all(['td', 'th'])
        if len(cells) < 2:
            return None
        
        try:
            cell_texts = []
            for cell in cells:
                text = cell.get_text().strip()
                if not text and cell.get('data-value'):
                    text = cell.get('data-value')
                cell_texts.append(text)
            
            non_empty_cells = [text for text in cell_texts if text and text != '-']
            if len(non_empty_cells) < 2:
                return None
            
            # Parse data
            machine_number = None
            credit_diff = None
            game_count = None
            bb_count = None
            rb_count = None
            
            for i, text in enumerate(cell_texts):
                if machine_number is None and re.match(r'^\d+$', text):
                    machine_number = int(text)
                elif re.match(r'^[\d\-\+\.,]+$', text):
                    num_value = self._safe_int(text)
                    if num_value is not None:
                        if credit_diff is None and abs(num_value) > 10:
                            credit_diff = num_value
                        elif game_count is None and num_value > 0:
                            game_count = num_value
                        elif bb_count is None and 0 <= num_value <= 100:
                            bb_count = num_value
                        elif rb_count is None and 0 <= num_value <= 100:
                            rb_count = num_value
            
            if machine_number or (credit_diff is not None) or (game_count is not None):
                # Generate unique ID for MySQL
                unique_id = self._generate_mysql_id(store.store_id, target_date, machine_number or row_index)
                
                payout_rate = None
                if credit_diff is not None and game_count and game_count > 0:
                    payout_rate = round((credit_diff / game_count) * 100, 4)
                
                slot_data = DailySlotData(
                    id=unique_id,  # Use generated ID
                    date=target_date,
                    store_id=store.store_id,  # Use store_id directly
                    machine_number=machine_number,
                    credit_difference=credit_diff,
                    game_count=game_count,
                    bb=bb_count,
                    rb=rb_count,
                    payout_rate=payout_rate,
                    data_url=url
                )
                
                return slot_data
                
        except Exception as e:
            logger.debug(f"Error parsing enhanced machine row {row_index}: {str(e)}")
        
        return None

    def _generate_mysql_id(self, store_id: int, target_date, machine_number: int) -> int:
        """Generate unique ID for MySQL table"""
        import hashlib
        from datetime import datetime
        
        # Create a unique string
        date_str = target_date.strftime('%Y%m%d')
        unique_str = f"{store_id}_{date_str}_{machine_number}_{datetime.now().microsecond}"
        
        # Generate a hash and convert to integer
        hash_obj = hashlib.md5(unique_str.encode())
        # Take first 15 characters of hex to ensure it fits in BIGINT
        hash_hex = hash_obj.hexdigest()[:15]
        unique_id = int(hash_hex, 16)
        
        return unique_id

    def _parse_machine_div(self, div, store: Store, target_date, url: str, index: int) -> Optional[DailySlotData]:
        """Parse machine data from div element"""
        try:
            # Extract text and look for data attributes
            text_content = div.get_text().strip()
            
            # Look for data in attributes
            machine_number = div.get('data-machine-number') or div.get('data-number')
            machine_name = div.get('data-machine-name') or div.get('data-name')
            
            # Parse text content for numeric data
            numbers = re.findall(r'[\d\-\+\.,]+', text_content)
            
            if machine_number:
                machine_number = self._safe_int(machine_number)
            elif numbers:
                machine_number = self._safe_int(numbers[0])
            
            # Create minimal record if we have some data
            if machine_number or text_content:
                slot_data = DailySlotData(
                    date=target_date,
                    store=store,
                    machine_number=machine_number,
                    machine_name=machine_name,
                    data_url=url,
                    raw_data={
                        'div_index': index,
                        'text_content': text_content,
                        'parsed_numbers': numbers,
                        'parsed_at': timezone.now().isoformat(),
                        'parsing_strategy': 'div_based'
                    }
                )
                return slot_data
                
        except Exception as e:
            logger.debug(f"Error parsing machine div {index}: {str(e)}")
        
        return None
    
    def _parse_machine_list_item(self, item, store: Store, target_date, url: str, index: int) -> Optional[DailySlotData]:
        """Parse machine data from list item"""
        # Similar to div parsing but for list items
        return self._parse_machine_div(item, store, target_date, url, index)
    
    def _is_header_row(self, row) -> bool:
        """Enhanced header row detection"""
        cells = row.find_all(['td', 'th'])
        if not cells:
            return False
        
        # Check if it's a th row (table header)
        if row.find_all('th'):
            return True
        
        # Check for common header text patterns
        text = ' '.join(cell.get_text().strip().lower() for cell in cells)
        header_keywords = [
            '台番号', '機種', '差枚', 'ゲーム数', 'bb', 'rb', 
            'machine', 'number', 'game', 'count', 'bonus',
            '番号', '台', '機', 'no', 'name', '名前'
        ]
        
        # If more than 2 header keywords found, likely a header
        keyword_count = sum(1 for keyword in header_keywords if keyword in text)
        
        return keyword_count >= 2
    
    def _safe_int(self, value: str) -> Optional[int]:
        """Enhanced safe integer conversion"""
        if not value:
            return None
        try:
            # Remove common formatting characters
            cleaned = str(value).replace(',', '').replace('枚', '').replace('回', '').replace('円', '').strip()
            
            # Handle negative numbers
            if cleaned.startswith('-'):
                cleaned = cleaned[1:]
                multiplier = -1
            elif cleaned.startswith('+'):
                cleaned = cleaned[1:]
                multiplier = 1
            else:
                multiplier = 1
            
            if cleaned == '-' or cleaned == '' or cleaned == 'null' or cleaned == 'None':
                return None
            
            # Try to convert
            result = int(float(cleaned)) * multiplier
            return result
            
        except (ValueError, TypeError):
            return None
    
    def _log_error(self, session, store_id: int, error_type: str, error_message: str, url: str):
        """Log scraping error to database"""
        try:
            ScrapingError.objects.create(
                session=session,
                store_id=store_id,
                error_type=error_type,
                error_message=error_message,
                url=url
            )
        except Exception as e:
            logger.error(f"Failed to log error to database: {str(e)}")
