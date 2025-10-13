from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import json, time, os, tempfile, random, re, traceback, requests, hashlib
from datetime import datetime
from urllib.parse import quote_plus, urlencode

class AmazonMultiCountryScraper:
    def __init__(self, output_dir="data", headless=False, scraperapi_key=None, country="uk"):
        self.base_output_dir = output_dir
        self.headless = headless
        self.scraperapi_key = scraperapi_key
        self.use_scraperapi = scraperapi_key is not None
        self.country = country.lower()
        
        self.country_config = {
            "uk": {"domain": "amazon.co.uk", "country_code": "gb", "currency": "£", "name": "United Kingdom"},
            "spain": {"domain": "amazon.es", "country_code": "es", "currency": "€", "name": "Spain"},
            "germany": {"domain": "amazon.de", "country_code": "de", "currency": "€", "name": "Germany"},
            "france": {"domain": "amazon.fr", "country_code": "fr", "currency": "€", "name": "France"},
            "italy": {"domain": "amazon.it", "country_code": "it", "currency": "€", "name": "Italy"},
            "usa": {"domain": "amazon.com", "country_code": "us", "currency": "$", "name": "United States"},
        }
        
        if self.country not in self.country_config:
            raise ValueError(f"Unsupported country: {country}")
        
        self.config = self.country_config[self.country]
        self.output_dir = os.path.join(self.base_output_dir, self.country.upper())
        self.images_dir = os.path.join(self.output_dir, "product_images")
        self.error_log_path = os.path.join(self.output_dir, "error_log.txt")
        os.makedirs(self.images_dir, exist_ok=True)
        self.init_driver()
    
    def init_driver(self):
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        for arg in ["--no-sandbox", "--disable-dev-shm-usage", "--incognito", "--disable-extensions", 
                    "--disable-blink-features=AutomationControlled", "--disable-gpu", "--single-process"]:
            chrome_options.add_argument(arg)
        chrome_options.add_argument(f"--user-data-dir={tempfile.mkdtemp(prefix='chrome_')}")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        if self.use_scraperapi:
            print("  [OK] ScraperAPI enabled")
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def check_driver_alive(self):
        try:
            self.driver.current_url
            return True
        except:
            print("  [WARN] Restarting browser...")
            try:
                self.driver.quit()
            except:
                pass
            self.init_driver()
            return False
    
    def log_error(self, error_type, keyword, message, exception=None):
        entry = f"\n{'='*60}\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {error_type}\n"
        entry += f"Keyword: {keyword}\nMessage: {message}\n"
        if exception:
            entry += f"Exception: {str(exception)}\n{traceback.format_exc()}\n"
        with open(self.error_log_path, "a", encoding="utf-8") as f:
            f.write(entry)
        print(f"  [ERROR] {message}")
    
    def get_scraperapi_url(self, url):
        if not self.use_scraperapi:
            return url
        params = {'api_key': self.scraperapi_key, 'url': url, 'render': 'true', 'country_code': self.config['country_code']}
        return f"http://api.scraperapi.com/?{urlencode(params)}"
    
    def extract_title(self, elem):
        # Try to get title from the link's aria-label first (most reliable)
        try:
            # Find the h2 that contains an <a> tag with the s-link-style class
            link = elem.find_element(By.CSS_SELECTOR, "a.s-link-style[href*='/dp/']")
            # Try aria-label which often has the full title
            title = link.get_attribute("aria-label")
            if title and len(title.strip()) > 10:
                return ' '.join(title.strip().split())
        except:
            pass

        # Try the h2 inside the link (this is the actual title h2, not the brand one)
        try:
            link = elem.find_element(By.CSS_SELECTOR, "a.s-link-style h2")
            title = (link.get_attribute("textContent") or
                    link.get_attribute("innerText") or
                    link.text or "").strip()
            title = ' '.join(title.split())
            if len(title) > 10:
                return title
        except:
            pass

        # Try span inside the title link
        try:
            span = elem.find_element(By.CSS_SELECTOR, "a.s-link-style h2 span")
            title = (span.get_attribute("textContent") or
                    span.get_attribute("innerText") or
                    span.text or "").strip()
            title = ' '.join(title.split())
            if len(title) > 10:
                return title
        except:
            pass

        # Legacy selectors for older Amazon layouts
        selectors = [
            "h2 a span.a-text-normal",
            "h2 span.a-text-normal",
            "h2 a.a-link-normal span",
            "h2 a.a-link-normal"
        ]

        for selector in selectors:
            try:
                title_elem = elem.find_element(By.CSS_SELECTOR, selector)
                title = (title_elem.get_attribute("textContent") or
                        title_elem.get_attribute("innerText") or
                        title_elem.text or "").strip()
                title = ' '.join(title.split())
                if len(title) > 10:
                    return title
            except:
                continue

        # Fallback to ASIN
        try:
            asin = elem.get_attribute("data-asin")
            return f"Product {asin}" if asin else "Unknown Product"
        except:
            return "Unknown Product"
    
    def extract_price(self, elem):
        # Method 1: Try whole + fraction (works for UK, US, some EU)
        try:
            whole = elem.find_element(By.CSS_SELECTOR, 'span.a-price-whole').text
            fraction = elem.find_element(By.CSS_SELECTOR, 'span.a-price-fraction').text
            # Clean: remove commas and periods from whole part (EU uses periods as thousands separator)
            whole_clean = whole.replace(',', '').replace('.', '')
            price = float(f"{whole_clean}.{fraction}")
            if 0.01 <= price <= 99999:
                return price
        except:
            pass

        # Method 2: Try offscreen prices (hidden but accurate)
        try:
            for off in elem.find_elements(By.CSS_SELECTOR, "span.a-offscreen"):
                text = off.text.strip()
                # Remove currency symbols
                text_clean = text.replace("£", "").replace("€", "").replace("$", "").strip()
                # Try to extract number (handle both comma and period decimals)
                match = re.search(r"([\d,\.]+)", text_clean)
                if match:
                    price_str = match.group(1)
                    # Spanish uses comma as decimal separator (e.g., "49,00")
                    if ',' in price_str and '.' not in price_str:
                        price = float(price_str.replace(',', '.'))
                    # UK uses period as decimal (e.g., "49.00")
                    else:
                        price = float(price_str.replace(',', ''))
                    if 0.01 <= price <= 99999:
                        return price
        except:
            pass

        return None
    
    def extract_badges(self, elem):
        badges_dict = {}  # Use dict to automatically deduplicate by badge_type
        debug_mode = False  # Set to True to see all badge HTML

        # Look for badge components by CSS class patterns
        badge_selectors = [
            "span[data-component-type*='badge']",
            "div[data-component-type*='badge']",
            "span.rush-component[data-component-type='s-status-badge-component']",
            # Add more specific Best Seller selectors
            "span.a-badge-label-inner.a-text-ellipsis",
            "span.a-badge-text",
            "i.a-icon-addon-badge",
        ]

        if debug_mode:
            print(f"\n  [DEBUG] Badge extraction for ASIN: {elem.get_attribute('data-asin')}")
            print(f"  [DEBUG] Checking {len(badge_selectors)} selectors...")

        for selector in badge_selectors:
            try:
                found_elements = elem.find_elements(By.CSS_SELECTOR, selector)
                if debug_mode and found_elements:
                    print(f"  [DEBUG] Selector '{selector}' found {len(found_elements)} elements")

                for badge_container in found_elements:
                    if debug_mode:
                        print(f"  [DEBUG] Badge HTML: {badge_container.get_attribute('outerHTML')[:200]}")
                        print(f"  [DEBUG] Badge text: {badge_container.text.strip()}")

                    # Get badge type from data attributes first (language-independent)
                    badge_type_attr = badge_container.get_attribute("data-component-props")
                    if badge_type_attr and "badgeType" in badge_type_attr:
                        # Extract badge type from JSON in data attribute
                        try:
                            import json
                            props = json.loads(badge_type_attr)
                            badge_type_raw = props.get("badgeType", "")
                            text = badge_container.text.strip()
                            if badge_type_raw and text:
                                parsed = self.parse_badge_by_type(text, badge_type_raw)
                                badges_dict[parsed["badge_type"]] = parsed
                                if debug_mode:
                                    print(f"  [DEBUG] Parsed badge via JSON: {parsed}")
                                continue
                        except Exception as ex:
                            if debug_mode:
                                print(f"  [DEBUG] JSON parse error: {ex}")
                            pass

                    # Fallback: Extract text from badge
                    text = badge_container.text.strip()
                    if text and len(text) > 2:
                        parsed = self.parse_badge(text)
                        badges_dict[parsed["badge_type"]] = parsed
                        if debug_mode:
                            print(f"  [DEBUG] Parsed badge via text: {parsed}")
            except Exception as ex:
                if debug_mode:
                    print(f"  [DEBUG] Selector '{selector}' error: {ex}")
                continue

        if debug_mode:
            print(f"  [DEBUG] Final badges: {list(badges_dict.values())}\n")

        return list(badges_dict.values())
    
    def parse_badge_by_type(self, text, badge_type_raw):
        """Parse badge using Amazon's internal badge type (language-independent)"""
        badge = {"raw_text": text, "badge_type": "Other", "rank": None, "category": None, "keyword": None}

        badge_type_raw = badge_type_raw.lower()
        if "best-seller" in badge_type_raw or "bestseller" in badge_type_raw:
            badge["badge_type"] = "Best Seller"
        elif "amazon" in badge_type_raw and "choice" in badge_type_raw:
            badge["badge_type"] = "Amazon's Choice"
        elif "climate" in badge_type_raw:
            badge["badge_type"] = "Climate Pledge Friendly"
        elif "deal" in badge_type_raw or "limited" in badge_type_raw:
            badge["badge_type"] = "Limited Time Deal"
        elif "small" in badge_type_raw or "business" in badge_type_raw:
            badge["badge_type"] = "Small Business"
        else:
            badge["badge_type"] = text  # Use actual text if can't categorize

        return badge

    def parse_badge(self, text):
        """Parse badge by text pattern matching (fallback method)"""
        lower = text.lower()
        badge = {"raw_text": text, "badge_type": "Other", "rank": None, "category": None, "keyword": None}

        # Use pattern matching for common keywords across languages
        # Best Seller patterns
        if any(pattern in lower for pattern in ["seller", "vendido", "ventes", "verkauf"]):
            badge["badge_type"] = "Best Seller"
        # Amazon's Choice patterns (including "Opción Amazon")
        elif "amazon" in lower or "opción" in lower or "opcion" in lower or "choice" in lower or "elección" in lower or "wahl" in lower or "choix" in lower or "scelta" in lower:
            badge["badge_type"] = "Amazon's Choice"
        # Climate/environment patterns
        elif "climate" in lower or "clima" in lower or "klima" in lower:
            badge["badge_type"] = "Climate Pledge Friendly"
        # Limited time/deal patterns
        elif any(pattern in lower for pattern in ["limited", "limitado", "limitée", "begrenzt", "limitata", "deal", "oferta", "offre"]):
            badge["badge_type"] = "Limited Time Deal"
        # Small business patterns
        elif any(pattern in lower for pattern in ["small", "pequeña", "petite", "kleines", "piccola", "business", "empresa", "entreprise", "unternehmen", "impresa"]):
            badge["badge_type"] = "Small Business"
        else:
            # If we can't categorize, just use the text as-is
            badge["badge_type"] = text

        return badge
    
    def check_bsr_in_html(self, html):
        """Quick check if BSR keywords exist in HTML"""
        bsr_keywords = [
            "Best Sellers Rank",
            "Clasificación en los másvendidos",
            "Bestseller Rang",
            "Classement des meilleures ventes",
            "Classifica",
        ]
        return any(keyword in html for keyword in bsr_keywords)

    def extract_bsr(self, html):
        """Extract BSR - supports both English and native languages"""
        bsr_ranks = []

        # Multi-language patterns
        patterns = [
            # English: "Best Sellers Rank: #123 in Category"
            r'Best Sellers?\s+Rank[:\s]*#?\s*([0-9,\.]+)\s+in\s+([^(<\n]+?)(?:\s*\(|<|$)',
            # English sub-rankings: "1 in <a>Action Cameras</a>" (within lists/bullets)
            r'>\s*([0-9,\.]+)\s+in\s+<a[^>]*>([^<]+)</a>',
            # Spanish: "nº1 en Category" or "n.º 1 en Category"
            r'n[ºo°\.]*\s*([0-9,\.]+)\s+en\s+<a[^>]*>([^<]+)</a>',
            r'n[ºo°\.]*\s*([0-9,\.]+)\s+en\s+([A-Z][^(<\n]+?)(?:\s*\(|<|$)',
            # German
            r'Nr\.\s*([0-9,\.]+)\s+in\s+([^(<\n]+?)(?:\s*\(|<|$)',
            r'>\s*([0-9,\.]+)\s+in\s+<a[^>]*>([^<]+)</a>',  # German sub-rankings
            # French
            r'n[°o]\s*([0-9,\.]+)\s+(?:dans|en)\s+([^(<\n]+?)(?:\s*\(|<|$)',
            r'>\s*([0-9,\.]+)\s+(?:dans|en)\s+<a[^>]*>([^<]+)</a>',  # French sub-rankings
            # Italian
            r'n[°o]\.\s*([0-9,\.]+)\s+in\s+([^(<\n]+?)(?:\s*\(|<|$)',
        ]

        for pattern in patterns:
            for match in re.findall(pattern, html, re.IGNORECASE):
                rank_str, category_str = match[0], match[1]

                try:
                    # Clean rank (handle both comma and period as separators)
                    rank_str_clean = rank_str.replace(',', '').replace('.', '')
                    rank = int(rank_str_clean)

                    # Clean category - remove HTML tags and extra whitespace
                    category = ' '.join(category_str.strip().split())
                    category = re.sub(r'<[^>]+>', '', category)  # Remove HTML
                    category = re.sub(r'\s+', ' ', category).strip()

                    # Validate and add if not duplicate
                    if (rank > 0 and
                        5 <= len(category) <= 100 and
                        not any(r["rank"] == rank and r["category"] == category for r in bsr_ranks)):
                        bsr_ranks.append({"rank": rank, "category": category})
                except (ValueError, IndexError):
                    continue

        return bsr_ranks[:5]
    
    def check_for_popup(self):
        popup_selectors = ["//span[contains(text(), 'still shopping')]", "//button[contains(text(), 'Continue')]"]
        try:
            for selector in popup_selectors:
                try:
                    popup = self.driver.find_element(By.XPATH, selector)
                    if popup.is_displayed():
                        popup.click()
                        time.sleep(1)
                        return True
                except:
                    continue
        except:
            pass
        return False
    
    def download_images_and_bsr(self, url, keyword, asin, search_elem, extract_bsr=False):
        result = {"folder": None, "count": 0, "thumbnail": None, "bsr_ranks": []}
        folder = os.path.join(self.images_dir, keyword.replace(" ", "_").replace("/", "-"), asin)
        os.makedirs(folder, exist_ok=True)
        result["folder"] = folder
        
        try:
            img_url = search_elem.find_element(By.CSS_SELECTOR, "img.s-image").get_attribute("src")
            if img_url:
                response = requests.get(img_url, timeout=10)
                thumb_path = os.path.join(folder, "00_thumbnail.jpg")
                with open(thumb_path, "wb") as f:
                    f.write(response.content)
                result["thumbnail"] = thumb_path
                result["count"] = 1
        except:
            pass
        
        if url:
            new_tab = False
            try:
                if not self.check_driver_alive():
                    return result
                main_window = self.driver.current_window_handle
                
                # Only add language param when NOT using ScraperAPI (to avoid errors)
                product_url = url
                if self.country not in ['uk', 'usa'] and not self.use_scraperapi:
                    product_url = url + ('&' if '?' in url else '?') + 'language=en_GB'

                self.driver.execute_script("window.open('');")
                new_tab = True
                self.driver.switch_to.window(self.driver.window_handles[-1])

                # Use direct connection for product pages (BSR doesn't render well through ScraperAPI)
                # Only use ScraperAPI for search pages to avoid CAPTCHAs
                self.driver.get(product_url)
                time.sleep(3)
                self.check_for_popup()

                # Aggressively scroll to find BSR section - don't stop until found or page end
                html = self.driver.page_source
                if extract_bsr:
                    # Check if BSR already visible
                    bsr_found = self.check_bsr_in_html(html)

                    if not bsr_found:
                        try:
                            # ONLY try clicking expanders if NOT using ScraperAPI
                            # (clicking can cause navigation errors through ScraperAPI proxy)
                            if not self.use_scraperapi:
                                print(f"    [BSR] Trying to expand product info sections...")
                                try:
                                    current_url = self.driver.current_url
                                    expand_selectors = [
                                        "a[data-action='a-expander-toggle']",
                                        "#productDetails_expanderSummary_feature_div a",
                                        "a.a-expander-header",
                                        "#detailBullets_feature_div a",
                                        # Spanish "Información del producto" section
                                        "//span[contains(text(), 'Información del producto')]",
                                        "//h2[contains(text(), 'Información del producto')]",
                                        # English "Product information" section
                                        "//span[contains(text(), 'Product information')]",
                                        "//h2[contains(text(), 'Product information')]",
                                    ]
                                    for selector in expand_selectors:
                                        try:
                                            # Use XPath for text-based selectors
                                            if selector.startswith("//"):
                                                expand_btn = self.driver.find_element(By.XPATH, selector)
                                            else:
                                                expand_btn = self.driver.find_element(By.CSS_SELECTOR, selector)

                                            if expand_btn.is_displayed():
                                                self.driver.execute_script("arguments[0].click();", expand_btn)
                                                time.sleep(0.5)

                                                # Check if we're still on the product page (not navigated away)
                                                if asin not in self.driver.current_url:
                                                    print(f"    [BSR] Navigation detected, going back...")
                                                    self.driver.back()
                                                    time.sleep(1)
                                                    break
                                        except:
                                            continue

                                    # Check if BSR appeared after expanding
                                    html = self.driver.page_source
                                    bsr_found = self.check_bsr_in_html(html)
                                    if bsr_found:
                                        print(f"    [BSR] Found after expanding sections")
                                except:
                                    pass

                            # If still not found, scroll incrementally (safe for both direct and ScraperAPI)
                            if not bsr_found:
                                scroll_position = 0
                                no_change_count = 0
                                previous_height = self.driver.execute_script("return document.body.scrollHeight")

                                print(f"    [BSR] Scrolling to find BSR section...")

                                while not bsr_found:
                                    # Scroll down by 500 pixels at a time (larger increments for faster scrolling)
                                    scroll_position += 500
                                    self.driver.execute_script(f"window.scrollTo(0, {scroll_position});")
                                    time.sleep(0.8)  # Give more time for lazy-loaded content

                                    # Check if BSR is now visible
                                    html = self.driver.page_source
                                    bsr_found = self.check_bsr_in_html(html)

                                    if bsr_found:
                                        print(f"    [BSR] Found at scroll position {scroll_position}px")
                                        break

                                    # Check if page height has stopped changing (absolute bottom)
                                    current_height = self.driver.execute_script("return document.body.scrollHeight")
                                    if current_height == previous_height:
                                        no_change_count += 1
                                        # If height hasn't changed for 3 consecutive checks, we're at the bottom
                                        if no_change_count >= 3:
                                            print(f"    [BSR] Reached page bottom at {scroll_position}px - BSR not found")
                                            break
                                    else:
                                        no_change_count = 0
                                        previous_height = current_height

                                    # Safety check: if we've scrolled beyond reasonable page height
                                    if scroll_position > current_height + 5000:
                                        print(f"    [BSR] Exceeded page bounds - stopping")
                                        break
                        except Exception as e:
                            print(f"    [BSR] Scroll error: {str(e)[:50]}")
                            pass

                if extract_bsr:
                    result["bsr_ranks"] = self.extract_bsr(html)
                    # Debug: save HTML if BSR not found for troubleshooting
                    if not result["bsr_ranks"]:
                        try:
                            debug_file = f"debug_bsr_{asin}_{self.country}.html"
                            with open(debug_file, "w", encoding="utf-8") as f:
                                f.write(html)
                        except:
                            pass
                
                image_urls = set(m for m in re.findall(r'"hiRes":"(https://[^"]+)"', html) if m != "null")
                seen = set()
                for i, img_url in enumerate(sorted(image_urls), 1):
                    try:
                        r = requests.get(img_url, timeout=15)
                        h = hashlib.md5(r.content).hexdigest()
                        if h not in seen:
                            with open(os.path.join(folder, f"{i:02d}_image.jpg"), "wb") as f:
                                f.write(r.content)
                            seen.add(h)
                            result["count"] += 1
                    except:
                        pass
                self.driver.close()
                self.driver.switch_to.window(main_window)
            except:
                if new_tab:
                    try:
                        while len(self.driver.window_handles) > 1:
                            self.driver.close()
                            self.driver.switch_to.window(self.driver.window_handles[0])
                    except:
                        pass
        return result
    
    def extract_product_data(self, elem, keyword, position):
        asin = elem.get_attribute("data-asin")
        if not asin:
            return None
        
        product = {
            "position": position, "keyword": keyword, "country": self.country,
            "scrape_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "asin": asin, "title": self.extract_title(elem),
            "price": self.extract_price(elem), "currency": self.config['currency']
        }
        
        try:
            rating_text = elem.find_element(By.CSS_SELECTOR, "span.a-icon-alt").get_attribute("textContent")
            product["rating"] = float(re.search(r"(\d+\.?\d*)", rating_text).group(1))
        except:
            product["rating"] = None
        
        try:
            for link in elem.find_elements(By.CSS_SELECTOR, "a[href*='#customerReviews']"):
                aria = link.get_attribute("aria-label")
                if aria:
                    match = re.search(r"([\d,]+)", aria)
                    if match:
                        product["review_count"] = int(match.group(1).replace(",", ""))
                        break
            else:
                product["review_count"] = 0
        except:
            product["review_count"] = 0
        
        badges_full = self.extract_badges(elem)
        product["badges"] = [b["badge_type"] for b in badges_full]
        has_best_seller = any(b["badge_type"] == "Best Seller" for b in badges_full)

        try:
            href = elem.find_element(By.CSS_SELECTOR, "h2 a").get_attribute("href")
            product["url"] = href.split("?")[0] if "?" in href else href
        except:
            product["url"] = f"https://www.{self.config['domain']}/dp/{asin}"

        try:
            # Always try to extract BSR (not just for Best Seller products)
            # Some products have BSR but don't show "Best Seller" badge on search results
            img_bsr = self.download_images_and_bsr(product["url"], keyword, asin, elem, extract_bsr=True)
            product.update({
                "image_folder": img_bsr["folder"], "image_count": img_bsr["count"],
                "thumbnail_path": img_bsr["thumbnail"],
                "bsr_rank": img_bsr["bsr_ranks"][0]["rank"] if img_bsr["bsr_ranks"] else "N/A",
                "bsr_category": img_bsr["bsr_ranks"][0]["category"] if img_bsr["bsr_ranks"] else "N/A"
            })
            if len(img_bsr["bsr_ranks"]) > 1:
                product["bsr_all_ranks"] = img_bsr["bsr_ranks"]
        except Exception as e:
            self.log_error("IMAGE_BSR", keyword, f"Failed ASIN {asin}", e)
            product.update({"image_folder": None, "image_count": 0, "thumbnail_path": None, "bsr_rank": "N/A", "bsr_category": "N/A"})
        
        return product
    
    def scrape_keyword(self, keyword, max_products=10, retry=0):
        if retry > 0:
            print(f"\n[{keyword}] - Retry {retry}/2")
        else:
            print(f"\n[{keyword}]")
        
        if not self.check_driver_alive():
            time.sleep(2)
        
        products = []
        try:
            search_url = f"https://www.{self.config['domain']}/s?k={quote_plus(keyword)}"
            if self.country not in ['uk', 'usa'] and not self.use_scraperapi:
                search_url += '&language=en_GB'
            
            final_url = self.get_scraperapi_url(search_url) if self.use_scraperapi else search_url
            self.driver.get(final_url)
            time.sleep(random.uniform(5, 8) if self.use_scraperapi else random.uniform(5, 7))
            self.check_for_popup()
            
            if "captcha" in self.driver.page_source.lower():
                self.log_error("CAPTCHA", keyword, "CAPTCHA detected")
                print("  [WARN] CAPTCHA")
                if retry < 2:
                    time.sleep(5)
                    return self.scrape_keyword(keyword, max_products, retry + 1)
                return []
            
            timeout = 30 if self.use_scraperapi else 10
            product_elements = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
            )

            # DEBUG: Save search page HTML to analyze badge/sponsored structure
            debug_search_page = False  # Set to True to save HTML
            if debug_search_page:
                try:
                    debug_file = f"debug_search_{keyword.replace(' ', '_')}_{self.country}.html"
                    with open(debug_file, "w", encoding="utf-8") as f:
                        f.write(self.driver.page_source)
                    print(f"  [DEBUG] Saved search page HTML to {debug_file}")
                except:
                    pass

            organic_count = 0
            sponsored_count = 0
            for elem in product_elements:
                if organic_count >= max_products:
                    break

                # Skip sponsored products - check multiple indicators
                is_sponsored = False
                asin = elem.get_attribute("data-asin")
                debug_sponsored = False  # Set to True to debug sponsored detection

                try:
                    # Method 1: Look for "Sponsored" text
                    sponsored_indicators = [
                        ".//span[contains(text(), 'Sponsored')]",
                        ".//span[contains(text(), 'Patrocinado')]",  # Spanish
                        ".//span[contains(text(), 'Sponsorisé')]",    # French
                        ".//span[contains(text(), 'Gesponsert')]",    # German
                        ".//*[@data-component-type='sp-sponsored-result']"
                    ]

                    if debug_sponsored:
                        print(f"\n  [DEBUG] Checking ASIN {asin} for sponsored indicators...")

                    for indicator in sponsored_indicators:
                        try:
                            found_elem = elem.find_element(By.XPATH, indicator)
                            is_sponsored = True
                            if debug_sponsored:
                                print(f"  [DEBUG] SPONSORED detected via: {indicator}")
                                print(f"  [DEBUG] Element text: {found_elem.text[:50]}")
                            break
                        except:
                            continue
                except:
                    pass

                if is_sponsored:
                    sponsored_count += 1
                    if debug_sponsored:
                        print(f"  [DEBUG] Skipping sponsored product {asin}")
                    continue

                try:
                    prod = self.extract_product_data(elem, keyword, organic_count + 1)
                    if prod:
                        products.append(prod)
                        organic_count += 1
                        title = (prod.get("title", "")[:40] or "No title") + "..."
                        price = f"{self.config['currency']}{prod.get('price')}" if prod.get('price') else "N/A"
                        badges_str = f" | Badges: {', '.join(prod.get('badges', []))}" if prod.get('badges') else ""
                        print(f"  [{organic_count}] {title} - {price}{badges_str}")
                except Exception as e:
                    self.log_error("EXTRACT", keyword, f"Product {organic_count + 1}", e)

            # Show summary of sponsored filtering
            if sponsored_count > 0:
                print(f"  [OK] Skipped {sponsored_count} sponsored product(s)")

            if not products:
                self.log_error("NO_PRODUCTS", keyword, "No products")
                print(f"  [ERROR] No products")
        
        except TimeoutException as e:
            self.log_error("TIMEOUT", keyword, "Timeout", e)
            print(f"  [ERROR] Timeout")
            if retry < 2:
                time.sleep(10)
                return self.scrape_keyword(keyword, max_products, retry + 1)
        except Exception as e:
            self.log_error("ERROR", keyword, "Critical", e)
            print(f"  [ERROR] Error")
            if retry < 2:
                time.sleep(10)
                return self.scrape_keyword(keyword, max_products, retry + 1)
        
        return products
    
    def save_results(self, keyword, products):
        data = {"keyword": keyword, "country": self.country, "scrape_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_products": len(products), "products": products}
        filename = f"{keyword.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(os.path.join(self.output_dir, filename), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def run(self, keywords, max_products=10):
        print(f"\n{'='*60}\nAmazon Scraper - {self.config['name'].upper()}\n{'='*60}")
        print(f"Domain: {self.config['domain']} | Location: {self.config['country_code'].upper()}")
        print(f"Keywords: {len(keywords)} | Products: {max_products} | ScraperAPI: {'YES' if self.use_scraperapi else 'NO'}")
        print(f"Output: {self.output_dir}\n")
        
        all_results, failed = {}, []
        try:
            for i, keyword in enumerate(keywords, 1):
                print(f"Progress: {i}/{len(keywords)}")
                try:
                    products = self.scrape_keyword(keyword, max_products)
                    all_results[keyword] = products
                    if products:
                        self.save_results(keyword, products)
                        print(f"  [OK] Saved {len(products)} products")
                    else:
                        failed.append(keyword)
                except Exception as e:
                    failed.append(keyword)
                    self.log_error("KEYWORD_FAIL", keyword, "Complete failure", e)
                
                if i < len(keywords):
                    delay = random.uniform(5, 8) if self.use_scraperapi else 30
                    print(f"  Waiting {delay:.1f}s...\n")
                    time.sleep(delay)
            
            consolidated = {"scrape_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "country": self.country,
                          "domain": self.config['domain'], "total_keywords": len(all_results),
                          "successful_keywords": sum(1 for p in all_results.values() if p), "failed_keywords": failed, "keywords": all_results}
            with open(os.path.join(self.output_dir, f"consolidated_{self.country}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"), "w", encoding="utf-8") as f:
                json.dump(consolidated, f, indent=2, ensure_ascii=False)
        finally:
            self.driver.quit()
        
        print(f"\n{'='*50}\nCOMPLETE - {self.config['name'].upper()}\n{'='*50}")
        print(f"Successful: {len(all_results) - len(failed)}/{len(all_results)}")
        if failed:
            print(f"Failed: {len(failed)}")
        return all_results


def load_config(filepath="config.json"):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Config not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, list):
        config = {"keywords": [str(k).strip() for k in data if k], "max_products": 10, "headless": True, "scraperapi_key": None, "countries": ["uk"]}
    elif isinstance(data, dict):
        if "keywords" not in data:
            raise ValueError("JSON must contain 'keywords'")
        countries = data.get("countries", [])
        if not countries and "country" in data:
            countries = [data["country"]]
        if not countries:
            countries = ["uk"]
        config = {"keywords": [str(k).strip() for k in data.get("keywords", []) if k], "max_products": data.get("max_products", 10),
                 "headless": data.get("headless", True), "scraperapi_key": data.get("scraperapi_key"), "countries": [c.lower() for c in countries]}
    else:
        raise ValueError("Invalid JSON format")
    
    if not config["keywords"]:
        raise ValueError("No keywords found")
    
    print(f"Loaded {len(config['keywords'])} keywords")
    if config.get("scraperapi_key"):
        print("ScraperAPI key detected")
    print(f"Countries: {', '.join([c.upper() for c in config['countries']])}")
    return config


if __name__ == "__main__":
    try:
        config = load_config("config.json")
        all_country_results = {}
        
        for country in config["countries"]:
            print(f"\n\n[START] {country.upper()}...")
            scraper = AmazonMultiCountryScraper(output_dir="data", headless=config["headless"],
                                               scraperapi_key=config.get("scraperapi_key"), country=country)
            results = scraper.run(config["keywords"], max_products=config["max_products"])
            all_country_results[country] = results
            total = sum(len(products) for products in results.values() if products)
            print(f"[OK] {country.upper()}: {total} products")
            if country != config["countries"][-1]:
                print(f"\n[WAIT] 10s...")
                time.sleep(10)
        
        print(f"\n\n{'='*60}\nALL COUNTRIES COMPLETE\n{'='*60}")
        for country, results in all_country_results.items():
            print(f"{country.upper()}: {sum(len(p) for p in results.values() if p)} products")
        print(f"\nResults: data/[COUNTRY]/\n")
        
    except (FileNotFoundError, ValueError) as e:
        print(f"\nError: {e}")
        print('\nCreate config.json:\n{\n  "keywords": ["dji"],\n  "max_products": 5,\n  "scraperapi_key": "YOUR_KEY",\n  "countries": ["uk", "spain"]\n}')
    except Exception as e:
        print(f"\nCritical error: {e}")
        print(f"Check: data/[COUNTRY]/error_log.txt")