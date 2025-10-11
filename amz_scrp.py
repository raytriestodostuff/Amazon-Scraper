from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import json
import time
import os
import tempfile
from datetime import datetime
from urllib.parse import quote_plus, urlencode
import random
import re
import traceback
import requests
import hashlib

class AmazonMultiCountryScraper:
    def __init__(self, output_dir="data", headless=False, scraperapi_key=None, country="uk"):
        self.base_output_dir = output_dir
        self.headless = headless
        self.scraperapi_key = scraperapi_key
        self.use_scraperapi = scraperapi_key is not None
        self.country = country.lower()
        
        # Country configurations
        self.country_config = {
            "uk": {"domain": "amazon.co.uk", "country_code": "gb", "currency": "£", "name": "United Kingdom"},
            "spain": {"domain": "amazon.es", "country_code": "es", "currency": "€", "name": "Spain"},
            "germany": {"domain": "amazon.de", "country_code": "de", "currency": "€", "name": "Germany"},
            "france": {"domain": "amazon.fr", "country_code": "fr", "currency": "€", "name": "France"},
            "italy": {"domain": "amazon.it", "country_code": "it", "currency": "€", "name": "Italy"},
            "usa": {"domain": "amazon.com", "country_code": "us", "currency": "$", "name": "United States"},
        }
        
        if self.country not in self.country_config:
            raise ValueError(f"Unsupported country: {country}. Supported: {list(self.country_config.keys())}")
        
        self.config = self.country_config[self.country]
        
        # Create country-specific folders
        self.output_dir = os.path.join(self.base_output_dir, self.country.upper())
        self.images_dir = os.path.join(self.output_dir, "product_images")
        self.error_log_path = os.path.join(self.output_dir, "error_log.txt")
        os.makedirs(self.images_dir, exist_ok=True)
        
        self.init_driver()
    
    def init_driver(self):
        """Initialize Chrome driver"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        
        for arg in ["--no-sandbox", "--disable-dev-shm-usage", "--incognito", "--disable-extensions", 
                    "--disable-blink-features=AutomationControlled", "--disable-gpu", 
                    "--disable-software-rasterizer", "--single-process"]:
            chrome_options.add_argument(arg)
        
        chrome_options.add_argument(f"--user-data-dir={tempfile.mkdtemp(prefix='chrome_scraper_')}")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        if self.use_scraperapi:
            print("  ✓ ScraperAPI enabled (URL method)")
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def check_driver_alive(self):
        """Check if driver session is alive, restart if needed"""
        try:
            self.driver.current_url
            return True
        except:
            print("  ⚠️  Browser session lost - restarting...")
            try:
                self.driver.quit()
            except:
                pass
            self.init_driver()
            return False
    
    def log_error(self, error_type, keyword, message, exception=None):
        """Log errors to file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f"\n{'='*60}\n[{timestamp}] {error_type}\nKeyword: {keyword}\nMessage: {message}\n"
        if exception:
            entry += f"Exception: {str(exception)}\nTraceback:\n{traceback.format_exc()}\n"
        entry += f"{'='*60}\n"
        
        with open(self.error_log_path, "a", encoding="utf-8") as f:
            f.write(entry)
        print(f"  ❌ ERROR: {message}")
    
    def get_scraperapi_url(self, url):
        """Convert URL to ScraperAPI URL"""
        if not self.use_scraperapi:
            return url
        
        params = {
            'api_key': self.scraperapi_key,
            'url': url,
            'render': 'true',
            'country_code': self.config['country_code']
        }
        scraperapi_url = f"http://api.scraperapi.com/?{urlencode(params)}"
        return scraperapi_url
    
    def extract_title(self, elem):
        """Extract complete product title with multiple fallback methods"""
        # Method 1: Try comprehensive list of selectors
        title_selectors = [
            "h2 a span",
            "h2 span.a-text-normal",
            "h2 a.a-link-normal span.a-text-normal",
            "h2 a.a-link-normal span",
            "h2 span",
            "h2 a",
            "h2",
            "span.a-size-base-plus",
            "span.a-size-medium",
        ]
        
        for selector in title_selectors:
            try:
                elements = elem.find_elements(By.CSS_SELECTOR, selector)
                for title_elem in elements:
                    # Try multiple methods to get text
                    title = (title_elem.get_attribute("textContent") or 
                            title_elem.get_attribute("innerText") or 
                            title_elem.text or "").strip()
                    
                    # Valid title should be longer than 10 chars and not contain only numbers
                    if title and len(title) > 10 and not title.replace(',', '').replace('.', '').isdigit():
                        return title
            except:
                continue
        
        # Method 2: Try aria-label attribute on h2 link
        try:
            h2_link = elem.find_element(By.CSS_SELECTOR, "h2 a")
            aria_label = h2_link.get_attribute("aria-label")
            if aria_label and len(aria_label.strip()) > 10:
                return aria_label.strip()
        except:
            pass
        
        # Method 3: Try title attribute
        try:
            h2_link = elem.find_element(By.CSS_SELECTOR, "h2 a")
            title_attr = h2_link.get_attribute("title")
            if title_attr and len(title_attr.strip()) > 10:
                return title_attr.strip()
        except:
            pass
        
        # Method 4: Scan all links in the product card
        try:
            all_links = elem.find_elements(By.TAG_NAME, "a")
            for link in all_links:
                link_text = (link.get_attribute("textContent") or 
                            link.get_attribute("innerText") or 
                            link.text or "").strip()
                
                # Check if this looks like a product title
                if (link_text and 
                    len(link_text) > 20 and 
                    len(link_text.split()) >= 4 and
                    not any(char in link_text for char in ['£', '$', '€', '⭐', '★']) and
                    not link_text.replace(',', '').replace('.', '').isdigit()):
                    return link_text
        except:
            pass
        
        # Method 5: Get all text and find the longest meaningful line
        try:
            all_text = elem.get_attribute("textContent") or elem.text or ""
            if all_text:
                lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                # Find longest line that looks like a title
                candidates = []
                for line in lines:
                    if (len(line) > 20 and 
                        len(line.split()) >= 4 and
                        not any(char in line for char in ['£', '$', '€', '⭐', '★']) and
                        not line.replace(',', '').replace('.', '').isdigit()):
                        candidates.append(line)
                
                if candidates:
                    # Return the longest candidate
                    return max(candidates, key=len)
        except:
            pass
        
        # Last resort: use ASIN
        try:
            asin = elem.get_attribute("data-asin")
            if asin:
                return f"Product {asin}"
        except:
            pass
        
        return "Unknown Product"
    
    def extract_price(self, elem):
        """Extract price"""
        methods = [
            lambda: float(f"{elem.find_element(By.CSS_SELECTOR, 'span.a-price-whole').text.strip().replace(',', '').replace('.', '')}.{elem.find_element(By.CSS_SELECTOR, 'span.a-price-fraction').text.strip()}"),
            lambda: next((float(re.search(r"[\d,]+\.?\d*", off.text.replace("£", "").replace("€", "").replace("$", "").replace(",", "")).group(0)) 
                         for off in elem.find_elements(By.CSS_SELECTOR, "span.a-offscreen") 
                         if re.search(r"[\d,]+\.?\d*", off.text.replace("£", "").replace("€", "").replace("$", "").replace(",", "")) and 0.01 <= float(re.search(r"[\d,]+\.?\d*", off.text.replace("£", "").replace("€", "").replace("$", "").replace(",", "")).group(0)) <= 99999), None),
        ]
        
        for method in methods:
            try:
                price = method()
                if price:
                    return price
            except:
                continue
        return None
    
    def extract_badges(self, elem):
        """Extract badges"""
        badges = []
        for selector in ["span.a-badge-label", "span[class*='badge']"]:
            try:
                for badge_elem in elem.find_elements(By.CSS_SELECTOR, selector):
                    text = badge_elem.text.strip()
                    if text and any(kw in text.lower() for kw in ["amazon's choice", "best seller", "climate pledge"]):
                        if text not in badges:
                            badges.append(text)
            except:
                continue
        return badges
    
    def extract_bsr(self, html):
        """Extract Best Sellers Rank"""
        bsr_ranks = []
        patterns = [
            r'Best Sellers? Rank[:\s]*([0-9,]+)\s+in\s+([^(<\n]+?)(?:\s*\(|$)',
            r'Best-sellers? rank[:\s]*([0-9,]+)\s+in\s+([^(<\n]+?)(?:\s*\(|$)',
        ]
        
        for pattern in patterns:
            for match in re.findall(pattern, html, re.IGNORECASE):
                try:
                    rank = int(match[0].replace(',', ''))
                    category = match[1].strip()
                    if rank > 0 and 2 < len(category) < 100:
                        bsr_ranks.append({"rank": rank, "category": category})
                except:
                    continue
        return bsr_ranks[:5]
    
    def check_for_popup(self):
        """Check for and close Amazon pop-ups"""
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
        """Download images and BSR from product page"""
        result = {"folder": None, "count": 0, "thumbnail": None, "bsr_ranks": []}
        folder = os.path.join(self.images_dir, keyword.replace(" ", "_").replace("/", "-"), asin)
        os.makedirs(folder, exist_ok=True)
        result["folder"] = folder
        
        # Download thumbnail
        try:
            img = search_elem.find_element(By.CSS_SELECTOR, "img.s-image")
            img_url = img.get_attribute("src")
            if img_url:
                response = requests.get(img_url, timeout=10)
                response.raise_for_status()
                thumb_path = os.path.join(folder, "00_thumbnail.jpg")
                with open(thumb_path, "wb") as f:
                    f.write(response.content)
                result["thumbnail"] = thumb_path
                result["count"] = 1
        except:
            pass
        
        # Visit product page
        if url:
            new_tab_opened = False
            try:
                if not self.check_driver_alive():
                    return result
                
                main_window = self.driver.current_window_handle
                final_url = self.get_scraperapi_url(url) if self.use_scraperapi else url
                
                self.driver.execute_script("window.open('');")
                new_tab_opened = True
                self.driver.switch_to.window(self.driver.window_handles[-1])
                self.driver.get(final_url)
                
                wait_time = 6 if self.use_scraperapi else 3
                time.sleep(wait_time)
                self.check_for_popup()
                
                html = self.driver.page_source
                
                if extract_bsr:
                    result["bsr_ranks"] = self.extract_bsr(html)
                
                image_urls = set(match for match in re.findall(r'"hiRes":"(https://[^"]+)"', html) if match != "null")
                seen_hashes = set()
                
                for i, img_url in enumerate(sorted(image_urls), 1):
                    try:
                        response = requests.get(img_url, timeout=15)
                        img_hash = hashlib.md5(response.content).hexdigest()
                        if img_hash not in seen_hashes:
                            with open(os.path.join(folder, f"{i:02d}_image.jpg"), "wb") as f:
                                f.write(response.content)
                            seen_hashes.add(img_hash)
                            result["count"] += 1
                    except:
                        continue
                
                self.driver.close()
                self.driver.switch_to.window(main_window)
                
            except Exception:
                if new_tab_opened:
                    try:
                        while len(self.driver.window_handles) > 1:
                            self.driver.close()
                            self.driver.switch_to.window(self.driver.window_handles[0])
                    except:
                        pass
        
        return result
    
    def extract_product_data(self, elem, keyword, position):
        """Extract all product data"""
        asin = elem.get_attribute("data-asin")
        if not asin:
            return None
        
        product = {
            "position": position,
            "keyword": keyword,
            "country": self.country,
            "scrape_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "asin": asin,
            "title": self.extract_title(elem),
            "price": self.extract_price(elem),
            "currency": self.config['currency']
        }
        
        # Extract rating
        try:
            rating_text = elem.find_element(By.CSS_SELECTOR, "span.a-icon-alt").get_attribute("textContent")
            product["rating"] = float(re.search(r"(\d+\.?\d*)", rating_text).group(1))
        except:
            product["rating"] = None
        
        # Extract review count
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
        
        # Extract badges
        product["badges"] = self.extract_badges(elem)
        has_best_seller = any("best seller" in b.lower() for b in product["badges"])
        
        # Extract URL
        try:
            href = elem.find_element(By.CSS_SELECTOR, "h2 a").get_attribute("href")
            product["url"] = href.split("?")[0] if "?" in href else href
        except:
            product["url"] = f"https://www.{self.config['domain']}/dp/{asin}"
        
        # Download images and BSR
        try:
            img_bsr = self.download_images_and_bsr(product["url"], keyword, asin, elem, has_best_seller)
            product["image_folder"] = img_bsr["folder"]
            product["image_count"] = img_bsr["count"]
            product["thumbnail_path"] = img_bsr["thumbnail"]
            
            if img_bsr["bsr_ranks"]:
                product["bsr_rank"] = img_bsr["bsr_ranks"][0]["rank"]
                product["bsr_category"] = img_bsr["bsr_ranks"][0]["category"]
                if len(img_bsr["bsr_ranks"]) > 1:
                    product["bsr_all_ranks"] = img_bsr["bsr_ranks"]
            else:
                product["bsr_rank"] = "N/A"
                product["bsr_category"] = "N/A"
        except Exception as e:
            self.log_error("IMAGE_BSR_ERROR", keyword, f"Failed for ASIN {asin}", e)
            product.update({"image_folder": None, "image_count": 0, "thumbnail_path": None, 
                          "bsr_rank": "N/A", "bsr_category": "N/A"})
        
        return product
    
    def scrape_keyword(self, keyword, max_products=10, retry_attempt=0):
        """Scrape products for a keyword with retry logic"""
        max_retries = 2
        
        if retry_attempt > 0:
            print(f"\n[{keyword}] - Retry {retry_attempt}/{max_retries}")
        else:
            print(f"\n[{keyword}]")
        
        if not self.check_driver_alive():
            time.sleep(2)
        
        products = []
        try:
            search_url = f"https://www.{self.config['domain']}/s?k={quote_plus(keyword)}"
            
            if self.use_scraperapi:
                final_url = self.get_scraperapi_url(search_url)
            else:
                final_url = search_url
            
            self.driver.get(final_url)
            
            wait_time = random.uniform(5, 8) if self.use_scraperapi else random.uniform(5, 7)
            time.sleep(wait_time)
            
            self.check_for_popup()
            
            if "captcha" in self.driver.page_source.lower():
                self.log_error("CAPTCHA", keyword, "CAPTCHA detected")
                print("  ⚠️  CAPTCHA detected")
                if retry_attempt < max_retries:
                    print(f"  🔄 Retrying due to CAPTCHA...")
                    time.sleep(5)
                    return self.scrape_keyword(keyword, max_products, retry_attempt + 1)
                return []
            
            timeout = 30 if self.use_scraperapi else 10
            
            try:
                product_elements = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
                )
            except TimeoutException:
                print("  ⚠️  Trying alternative selector...")
                try:
                    product_elements = WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-asin]:not([data-asin=''])")
                    ))
                except TimeoutException:
                    if retry_attempt < max_retries:
                        print(f"  🔄 Timeout - retrying in 10 seconds...")
                        time.sleep(10)
                        return self.scrape_keyword(keyword, max_products, retry_attempt + 1)
                    raise
            
            organic_count = 0
            for elem in product_elements:
                if organic_count >= max_products:
                    break
                
                try:
                    elem.find_element(By.XPATH, ".//span[contains(text(), 'Sponsored')]")
                    continue
                except NoSuchElementException:
                    pass
                
                try:
                    product_data = self.extract_product_data(elem, keyword, organic_count + 1)
                    if product_data:
                        products.append(product_data)
                        organic_count += 1
                        title = (product_data.get("title", "")[:40] or "No title") + "..."
                        price_val = product_data.get('price')
                        price = f"{self.config['currency']}{price_val}" if price_val else "N/A"
                        print(f"  [{organic_count}] {title} - {price}")
                except Exception as e:
                    self.log_error("EXTRACTION_ERROR", keyword, f"Failed product {organic_count + 1}", e)
            
            if not products:
                self.log_error("NO_PRODUCTS", keyword, "No products extracted")
                print(f"  ❌ No products found")
            
        except TimeoutException as e:
            self.log_error("TIMEOUT", keyword, "Page timeout", e)
            print(f"  ❌ Timeout")
            if retry_attempt < max_retries:
                print(f"  🔄 Retrying in 10 seconds...")
                time.sleep(10)
                return self.scrape_keyword(keyword, max_products, retry_attempt + 1)
        except Exception as e:
            self.log_error("CRITICAL_ERROR", keyword, "Critical error", e)
            print(f"  ❌ Error")
            if retry_attempt < max_retries:
                print(f"  🔄 Retrying in 10 seconds...")
                time.sleep(10)
                return self.scrape_keyword(keyword, max_products, retry_attempt + 1)
        
        return products
    
    def save_results(self, keyword, products):
        """Save results to JSON"""
        data = {
            "keyword": keyword,
            "country": self.country,
            "scrape_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_products": len(products),
            "products": products
        }
        
        filename = f"{keyword.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def run(self, keywords, max_products=10):
        """Run scraper for all keywords"""
        print(f"\n{'='*60}")
        print(f"Amazon Scraper - {self.config['name'].upper()}")
        print(f"{'='*60}")
        print(f"Domain: {self.config['domain']} | Location: {self.config['country_code'].upper()}")
        print(f"Keywords: {len(keywords)} | Products per keyword: {max_products}")
        print(f"Mode: {'Headless' if self.headless else 'Visible'} | ScraperAPI: {'Enabled ✓' if self.use_scraperapi else 'Disabled'}")
        print(f"Auto-retry: Enabled (up to 3 attempts per keyword)")
        print(f"Output folder: {self.output_dir}\n")
        
        all_results = {}
        failed_keywords = []
        
        try:
            for i, keyword in enumerate(keywords, 1):
                print(f"Progress: {i}/{len(keywords)}")
                
                try:
                    products = self.scrape_keyword(keyword, max_products)
                    all_results[keyword] = products
                    
                    if products:
                        self.save_results(keyword, products)
                        print(f"  ✓ Saved {len(products)} products")
                    else:
                        failed_keywords.append(keyword)
                except Exception as e:
                    failed_keywords.append(keyword)
                    self.log_error("KEYWORD_FAILURE", keyword, "Complete failure", e)
                    print(f"  ❌ Failed")
                
                if i < len(keywords):
                    delay = random.uniform(5, 8) if self.use_scraperapi else 30
                    print(f"  Waiting {delay:.1f}s...\n")
                    time.sleep(delay)
            
            consolidated = {
                "scrape_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "country": self.country,
                "domain": self.config['domain'],
                "total_keywords": len(all_results),
                "successful_keywords": sum(1 for p in all_results.values() if p),
                "failed_keywords": failed_keywords,
                "keywords": all_results
            }
            
            filepath = os.path.join(self.output_dir, f"consolidated_{self.country}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(consolidated, f, indent=2, ensure_ascii=False)
            
        finally:
            self.driver.quit()
        
        print(f"\n{'='*50}")
        print(f"COMPLETE - {self.config['name'].upper()}")
        print(f"{'='*50}")
        print(f"Successful: {len(all_results) - len(failed_keywords)}/{len(all_results)}")
        if failed_keywords:
            print(f"Failed: {len(failed_keywords)}")
        
        return all_results


def load_config(filepath="config.json"):
    """Load configuration from JSON"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Config file not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, list):
        config = {
            "keywords": [str(k).strip() for k in data if k], 
            "max_products": 10, 
            "headless": True, 
            "scraperapi_key": None,
            "countries": ["uk"]
        }
    elif isinstance(data, dict):
        if "keywords" not in data:
            raise ValueError("JSON must contain 'keywords' array")
        
        countries = data.get("countries", [])
        if not countries and "country" in data:
            countries = [data["country"]]
        if not countries:
            countries = ["uk"]
        
        config = {
            "keywords": [str(k).strip() for k in data.get("keywords", []) if k],
            "max_products": data.get("max_products", 10),
            "headless": data.get("headless", True),
            "scraperapi_key": data.get("scraperapi_key", None),
            "countries": [c.lower() for c in countries]
        }
    else:
        raise ValueError("JSON must be an array or object")
    
    if not config["keywords"]:
        raise ValueError("No keywords found in config")
    
    print(f"Loaded {len(config['keywords'])} keywords from {filepath}")
    if config.get("scraperapi_key"):
        print("✓ ScraperAPI key detected")
    print(f"✓ Target countries: {', '.join([c.upper() for c in config['countries']])}")
    return config


if __name__ == "__main__":
    try:
        config = load_config("config.json")
        
        all_country_results = {}
        
        for country in config["countries"]:
            print(f"\n\n🌍 Starting scrape for {country.upper()}...")
            
            scraper = AmazonMultiCountryScraper(
                output_dir="data", 
                headless=config["headless"],
                scraperapi_key=config.get("scraperapi_key"),
                country=country
            )
            
            results = scraper.run(config["keywords"], max_products=config["max_products"])
            all_country_results[country] = results
            
            total_products = sum(len(products) for products in results.values() if products)
            print(f"✓ {country.upper()}: {total_products} products scraped")
            
            if country != config["countries"][-1]:
                print(f"\n⏳ Waiting 10 seconds before next country...")
                time.sleep(10)
        
        print(f"\n\n{'='*60}")
        print(f"ALL COUNTRIES COMPLETE")
        print(f"{'='*60}")
        for country, results in all_country_results.items():
            total = sum(len(products) for products in results.values() if products)
            print(f"{country.upper()}: {total} products")
        print(f"\nResults saved in: data/[COUNTRY]/\n")
        
    except (FileNotFoundError, ValueError) as e:
        print(f"\nError: {e}")
        print("\nCreate 'config.json' with:")
        print('{\n  "keywords": ["dji", "muji"],\n  "max_products": 5,\n  "scraperapi_key": "YOUR_API_KEY",\n  "countries": ["uk", "spain", "germany"]\n}\n')
    except Exception as e:
        print(f"\nCritical error: {str(e)}")
        print(f"Check error logs in: data/[COUNTRY]/error_log.txt\n")