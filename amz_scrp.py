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
from urllib.parse import quote_plus
import random
import re
import traceback
import requests
import hashlib

class AmazonUKScraper:
    def __init__(self, output_dir="data", headless=False):
        self.output_dir = output_dir
        self.images_dir = os.path.join(output_dir, "product_images")
        self.error_log_path = os.path.join(output_dir, "error_log.txt")
        os.makedirs(self.images_dir, exist_ok=True)
        self.headless = headless
        self.init_driver()
    
    def init_driver(self):
        """Initialize or reinitialize the Chrome driver"""
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
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def check_driver_alive(self):
        """Check if driver session is still alive, restart if needed"""
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
        """Log errors to file with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f"\n{'='*60}\n[{timestamp}] {error_type}\nKeyword: {keyword}\nMessage: {message}\n"
        if exception:
            entry += f"Exception: {str(exception)}\nTraceback:\n{traceback.format_exc()}\n"
        entry += f"{'='*60}\n"
        
        with open(self.error_log_path, "a", encoding="utf-8") as f:
            f.write(entry)
        print(f"  ❌ ERROR: {message}")
    
    def extract_title(self, elem):
        """Extract complete product title using multiple fallback methods"""
        title_selectors = ["h2 a span", "h2 span.a-text-normal", "h2 a.a-link-normal span", "h2 span", 
                          "h2 a", "h2", "[data-cy='title-recipe'] h2", "div.s-title-instructions-style h2"]
        
        for selector in title_selectors:
            try:
                title_elem = elem.find_element(By.CSS_SELECTOR, selector)
                title = title_elem.get_attribute("textContent") or title_elem.get_attribute("innerText") or title_elem.text
                if title and len(title.strip()) > 5:
                    return title.strip()
            except NoSuchElementException:
                continue
        
        # Try aria-label and title attributes
        for attr in ["aria-label", "title"]:
            try:
                h2_link = elem.find_element(By.CSS_SELECTOR, "h2 a")
                attr_value = h2_link.get_attribute(attr)
                if attr_value and len(attr_value.strip()) > 5:
                    return attr_value.strip()
            except:
                continue
        
        # Search all links for title-like text
        try:
            for link in elem.find_elements(By.CSS_SELECTOR, "a"):
                link_text = link.get_attribute("textContent") or link.text
                if link_text and len(link_text.strip()) > 10:
                    if not any(char in link_text for char in ['£', '$', '⭐', '★']):
                        return link_text.strip()
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
        """Extract price using multiple fallback methods"""
        methods = [
            lambda: float(f"{elem.find_element(By.CSS_SELECTOR, 'span.a-price-whole').text.strip().replace(',', '').replace('.', '')}.{elem.find_element(By.CSS_SELECTOR, 'span.a-price-fraction').text.strip()}"),
            lambda: next((float(re.search(r"[\d,]+\.?\d*", off.text.replace("£", "").replace(",", "")).group(0)) 
                         for off in elem.find_elements(By.CSS_SELECTOR, "span.a-offscreen") 
                         if re.search(r"[\d,]+\.?\d*", off.text.replace("£", "").replace(",", "")) and 0.01 <= float(re.search(r"[\d,]+\.?\d*", off.text.replace("£", "").replace(",", "")).group(0)) <= 9999), None),
            lambda: next((float(re.search(r"[\d,]+\.?\d*", pe.text.replace("£", "").replace(",", "")).group(0))
                         for pe in elem.find_elements(By.CSS_SELECTOR, "[class*='price']")
                         if pe.text and re.search(r"[\d,]+\.?\d*", pe.text.replace("£", "").replace(",", "")) and 0.01 <= float(re.search(r"[\d,]+\.?\d*", pe.text.replace("£", "").replace(",", "")).group(0)) <= 9999), None),
            lambda: next((float(m.replace(",", "")) for m in re.findall(r"£([\d,]+\.?\d{0,2})", elem.text) if 0.01 <= float(m.replace(",", "")) <= 9999), None)
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
        """Extract and parse badges"""
        badges = []
        for selector in ["span.a-badge-label", "span[class*='badge']", "div[class*='badge']", "span.a-badge-text"]:
            try:
                for badge_elem in elem.find_elements(By.CSS_SELECTOR, selector):
                    text = badge_elem.text.strip()
                    if text and any(kw in text.lower() for kw in ["amazon's choice", "best seller", "climate pledge", "limited time", "small business"]):
                        if text not in [b["raw_text"] for b in badges]:
                            badges.append(self.parse_badge(text))
            except:
                continue
        return badges
    
    def parse_badge(self, text):
        """Parse badge text into structured data"""
        lower = text.lower()
        badge = {"raw_text": text, "badge_type": "Other", "rank": None, "category": None, "keyword": None}
        
        if "amazon's choice" in lower:
            badge["badge_type"] = "Amazon's Choice"
            match = re.search(r'for ["\']([^"\']+)["\']', text, re.IGNORECASE)
            if match:
                badge["keyword"] = match.group(1)
        elif "best seller" in lower:
            badge["badge_type"] = "Best Seller"
            rank_match = re.search(r'#(\d+)', text)
            if rank_match:
                badge["rank"] = int(rank_match.group(1))
        elif "climate pledge" in lower:
            badge["badge_type"] = "Climate Pledge Friendly"
        elif "limited time" in lower:
            badge["badge_type"] = "Limited Time Deal"
        elif "small business" in lower:
            badge["badge_type"] = "Small Business"
        
        return badge
    
    def extract_bsr(self, html):
        """Extract Best Sellers Rank from HTML"""
        bsr_ranks = []
        patterns = [
            r'Best Sellers? Rank[:\s]*([0-9,]+)\s+in\s+([^(<\n]+?)(?:\s*\(|$)',
            r'Best-sellers? rank[:\s]*([0-9,]+)\s+in\s+([^(<\n]+?)(?:\s*\(|$)',
            r'(?:>|\s)([0-9,]+)\s+in\s+([^(<\n]+?)(?:\s*\(|<)'
        ]
        
        for pattern in patterns:
            for match in re.findall(pattern, html, re.IGNORECASE):
                if re.search(f'Top\\s+{re.escape(match[0])}\\s+in', html, re.IGNORECASE):
                    continue
                try:
                    rank = int(match[0].replace(',', ''))
                    category = match[1].strip()
                    if rank > 0 and 2 < len(category) < 100 and not any(r["rank"] == rank and r["category"] == category for r in bsr_ranks):
                        bsr_ranks.append({"rank": rank, "category": category})
                except:
                    continue
        return bsr_ranks[:5]
    
    def check_for_popup(self):
        """Check for and close Amazon pop-ups"""
        popup_selectors = ["//span[contains(text(), 'still shopping')]", "//button[contains(text(), 'Continue')]",
                          "//input[@value='Continue shopping']", "//div[@role='dialog']//button"]
        try:
            for selector in popup_selectors:
                try:
                    popup = self.driver.find_element(By.XPATH, selector)
                    if popup.is_displayed():
                        print("      ⚠️  Pop-up detected - closing...")
                        popup.click()
                        time.sleep(1)
                        return True
                except:
                    continue
        except:
            pass
        return False
    
    def download_images_and_bsr(self, url, keyword, asin, search_elem, extract_bsr=False):
        """Download images and optionally extract BSR from product page"""
        result = {"folder": None, "count": 0, "thumbnail": None, "bsr_ranks": []}
        folder = os.path.join(self.images_dir, keyword.replace(" ", "_").replace("/", "-"), asin)
        os.makedirs(folder, exist_ok=True)
        result["folder"] = folder
        
        # Download thumbnail from search results
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
        
        # Visit product page for high-res images and BSR
        if url:
            new_tab_opened = False
            try:
                if not self.check_driver_alive():
                    return result
                
                main_window = self.driver.current_window_handle
                self.driver.execute_script("window.open('');")
                new_tab_opened = True
                self.driver.switch_to.window(self.driver.window_handles[-1])
                self.driver.get(url)
                time.sleep(3)
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
        """Extract all data from a single product element"""
        asin = elem.get_attribute("data-asin")
        if not asin:
            return None
        
        product = {
            "position": position,
            "keyword": keyword,
            "scrape_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "asin": asin,
            "title": self.extract_title(elem),
            "price": self.extract_price(elem)
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
        badges_full = self.extract_badges(elem)
        product["badges"] = [b["badge_type"] for b in badges_full]
        has_best_seller = any(b["badge_type"] == "Best Seller" for b in badges_full)
        
        # Extract URL
        try:
            href = elem.find_element(By.CSS_SELECTOR, "h2 a").get_attribute("href")
            product["url"] = href.split("?")[0] if "?" in href else href
        except:
            product["url"] = f"https://www.amazon.co.uk/dp/{asin}"
        
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
    
    def scrape_keyword(self, keyword, max_products=10):
        """Scrape products for a single keyword"""
        print(f"\n[{keyword}]")
        
        if not self.check_driver_alive():
            time.sleep(2)
        
        products = []
        try:
            self.driver.get(f"https://www.amazon.co.uk/s?k={quote_plus(keyword)}")
            time.sleep(random.uniform(5, 7))
            self.check_for_popup()
            
            if "captcha" in self.driver.page_source.lower():
                self.log_error("CAPTCHA", keyword, "CAPTCHA detected")
                print("  ⚠️  CAPTCHA detected")
                return []
            
            product_elements = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
            )
            
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
                        price = f"£{product_data.get('price')}" if product_data.get("price") else "N/A"
                        print(f"  [{organic_count}] {title} - {price}")
                except Exception as e:
                    self.log_error("EXTRACTION_ERROR", keyword, f"Failed product {organic_count + 1}", e)
            
            if not products:
                self.log_error("NO_PRODUCTS", keyword, "No products extracted")
                print(f"  ❌ No products found")
            
        except TimeoutException as e:
            self.log_error("TIMEOUT", keyword, "Page timeout", e)
            print(f"  ❌ Timeout")
        except Exception as e:
            self.log_error("CRITICAL_ERROR", keyword, "Critical error", e)
            print(f"  ❌ Error")
        
        return products
    
    def save_results(self, keyword, products):
        """Save results to JSON file"""
        data = {
            "keyword": keyword,
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
        print(f"\nAmazon UK Scraper")
        print(f"Keywords: {len(keywords)} | Products per keyword: {max_products}")
        print(f"Mode: {'Headless' if self.headless else 'Visible'} | Error log: {self.error_log_path}\n")
        
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
                    print(f"  Waiting 30s...\n")
                    time.sleep(30)
            
            consolidated = {
                "scrape_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_keywords": len(all_results),
                "successful_keywords": sum(1 for p in all_results.values() if p),
                "failed_keywords": failed_keywords,
                "keywords": all_results
            }
            
            filepath = os.path.join(self.output_dir, f"consolidated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(consolidated, f, indent=2, ensure_ascii=False)
            
        finally:
            self.driver.quit()
        
        print(f"\n{'='*50}")
        print(f"COMPLETE")
        print(f"{'='*50}")
        print(f"Successful: {len(all_results) - len(failed_keywords)}/{len(all_results)}")
        if failed_keywords:
            print(f"Failed: {len(failed_keywords)}")
            print(f"Check: {self.error_log_path}")
        
        return all_results


def load_config(filepath="config.json"):
    """Load configuration from JSON file"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Config file not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, list):
        config = {"keywords": [str(k).strip() for k in data if k], "max_products": 10, "headless": True}
    elif isinstance(data, dict):
        if "keywords" not in data:
            raise ValueError("JSON must contain 'keywords' array")
        config = {
            "keywords": [str(k).strip() for k in data.get("keywords", []) if k],
            "max_products": data.get("max_products", 10),
            "headless": data.get("headless", True)
        }
    else:
        raise ValueError("JSON must be an array or object")
    
    if not config["keywords"]:
        raise ValueError("No keywords found in config")
    
    print(f"Loaded {len(config['keywords'])} keywords from {filepath}")
    return config


if __name__ == "__main__":
    try:
        config = load_config("config.json")
        scraper = AmazonUKScraper(output_dir="data", headless=config["headless"])
        results = scraper.run(config["keywords"], max_products=config["max_products"])
        
        total_products = sum(len(products) for products in results.values() if products)
        print(f"\nTotal products scraped: {total_products}")
        print(f"Results saved in: data/\n")
        
    except (FileNotFoundError, ValueError) as e:
        print(f"\nError: {e}")
        print("\nCreate 'config.json' with:")
        print('{\n  "keywords": ["keyrings", "wireless mouse"],\n  "max_products": 10\n}\n')
    except Exception as e:
        print(f"\nCritical error: {str(e)}")
        print(f"Check error log: data/error_log.txt\n")