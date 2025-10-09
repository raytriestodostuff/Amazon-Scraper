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

class AmazonUKScraper:
    def __init__(self, output_dir="data", headless=False):
        self.output_dir = output_dir
        self.images_dir = os.path.join(output_dir, "product_images")  # Separate images folder
        os.makedirs(self.images_dir, exist_ok=True)
        
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--incognito")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        
        chrome_profile_dir = tempfile.mkdtemp(prefix="chrome_scraper_")
        chrome_options.add_argument(f"--user-data-dir={chrome_profile_dir}")
        
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
    def scrape_keyword(self, keyword, max_products=10):
        print(f"\n{'='*60}")
        print(f"Scraping keyword: {keyword}")
        print(f"{'='*60}")
        
        search_url = f"https://www.amazon.co.uk/s?k={quote_plus(keyword)}"
        products = []
        
        try:
            self.driver.get(search_url)
            print("  Waiting for page to load...")
            time.sleep(random.uniform(5, 7))
            
            if "captcha" in self.driver.page_source.lower():
                print("  CAPTCHA detected! Please solve it manually...")
                input("  Press Enter after solving CAPTCHA...")
            
            try:
                product_elements = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
                )
            except TimeoutException:
                print("  Timeout waiting for products")
                return []
            
            print(f"  Found {len(product_elements)} total products")
            
            organic_count = 0
            
            for elem in product_elements:
                if organic_count >= max_products:
                    break
                
                try:
                    sponsored = elem.find_element(By.XPATH, ".//span[contains(text(), 'Sponsored')]")
                    print(f"  Skipping sponsored")
                    continue
                except NoSuchElementException:
                    pass
                
                try:
                    product_data = self.extract_product_data(elem, keyword, organic_count + 1)
                    if product_data:
                        products.append(product_data)
                        organic_count += 1
                        title = product_data.get("title", "")[:60] if product_data.get("title") else "No title"
                        price = f"£{product_data.get('price')}" if product_data.get("price") else "No price"
                        print(f"  Product {organic_count}: {title}... | {price}")
                except Exception as e:
                    print(f"  Error: {str(e)}")
                    continue
            
            print(f"\nScraped {len(products)} products")
            
        except Exception as e:
            print(f"Error: {str(e)}")
        
        return products
    
    def extract_product_data(self, elem, keyword, position):
        product = {
            "position": position,
            "keyword": keyword,
            "scrape_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        asin = elem.get_attribute("data-asin")
        if not asin:
            return None
        product["asin"] = asin
        
        # Extract title
        title = None
        title_selectors = ["h2 a span", "h2 span", "h2 a"]
        
        for selector in title_selectors:
            try:
                title_elem = elem.find_element(By.CSS_SELECTOR, selector)
                title = title_elem.text.strip()
                if title and len(title) > 10:
                    break
            except NoSuchElementException:
                continue
        
        product["title"] = title or ""
        
        # Extract price
        price = None
        debug = position <= 3
        
        if debug:
            print(f"\n    DEBUG Product {position}:")
            try:
                full_text = elem.text
                print(f"    Text snippet: {full_text[:250]}")
                pounds = re.findall(r"£[\d,]+\.?\d*", full_text)
                print(f"    Pound symbols found: {pounds}")
            except:
                pass
        
        # Try standard price structure
        try:
            price_whole = elem.find_element(By.CSS_SELECTOR, "span.a-price-whole")
            price_fraction = elem.find_element(By.CSS_SELECTOR, "span.a-price-fraction")
            whole = price_whole.text.strip().replace(",", "").replace(".", "")
            fraction = price_fraction.text.strip()
            price = float(f"{whole}.{fraction}")
            if debug:
                print(f"    Found via standard: £{price}")
        except:
            if debug:
                print(f"    Standard method failed")
        
        # Try offscreen prices
        if price is None:
            try:
                offscreens = elem.find_elements(By.CSS_SELECTOR, "span.a-offscreen")
                if debug:
                    print(f"    Offscreen elements: {len(offscreens)}")
                for off in offscreens:
                    text = off.text.strip()
                    if debug:
                        print(f"    Offscreen: '{text}'")
                    match = re.search(r"[\d,]+\.?\d*", text.replace("£", "").replace(",", ""))
                    if match:
                        try:
                            price = float(match.group(0))
                            if 0.01 <= price <= 9999:
                                if debug:
                                    print(f"    Found via offscreen: £{price}")
                                break
                        except:
                            pass
            except:
                if debug:
                    print(f"    Offscreen method failed")
        
        # Try all price-related elements
        if price is None:
            try:
                price_elems = elem.find_elements(By.CSS_SELECTOR, "[class*='price']")
                if debug:
                    print(f"    Price elements: {len(price_elems)}")
                for idx, pe in enumerate(price_elems):
                    text = pe.text.strip()
                    if debug and idx < 5:
                        print(f"    Price elem {idx}: '{text}'")
                    if text:
                        match = re.search(r"[\d,]+\.?\d*", text.replace("£", "").replace(",", ""))
                        if match:
                            try:
                                price = float(match.group(0))
                                if 0.01 <= price <= 9999:
                                    if debug:
                                        print(f"    Found via price elem: £{price}")
                                    break
                            except:
                                pass
            except:
                if debug:
                    print(f"    Price elem method failed")
        
        # Search all text
        if price is None:
            try:
                all_text = elem.text
                matches = re.findall(r"£([\d,]+\.?\d{0,2})", all_text)
                if debug:
                    print(f"    Text search found: {matches}")
                for m in matches:
                    try:
                        price = float(m.replace(",", ""))
                        if 0.01 <= price <= 9999:
                            if debug:
                                print(f"    Found via text search: £{price}")
                            break
                    except:
                        pass
            except:
                if debug:
                    print(f"    Text search failed")
        
        if debug and price is None:
            print(f"    NO PRICE FOUND")
        
        product["price"] = price
        
        # Extract rating
        rating = None
        try:
            rating_elem = elem.find_element(By.CSS_SELECTOR, "span.a-icon-alt")
            text = rating_elem.get_attribute("textContent")
            match = re.search(r"(\d+\.?\d*)", text)
            if match:
                rating = float(match.group(1))
        except:
            pass
        
        product["rating"] = rating
        
        # Extract review count
        review_count = 0
        try:
            links = elem.find_elements(By.CSS_SELECTOR, "a[href*='#customerReviews']")
            for link in links:
                aria = link.get_attribute("aria-label")
                if aria:
                    match = re.search(r"([\d,]+)", aria)
                    if match:
                        review_count = int(match.group(1).replace(",", ""))
                        break
        except:
            pass
        
        product["review_count"] = review_count
        
        # Extract badges (Amazon's Choice, Best Seller, etc.)
        badges = self.extract_badges(elem, debug=(position <= 3))
        product["badges"] = badges
        if badges and position <= 3:
            print(f"    Badges: {', '.join(badges)}")
        
        # Extract product URL
        product_url = None
        try:
            link = elem.find_element(By.CSS_SELECTOR, "h2 a")
            href = link.get_attribute("href")
            if href:
                # Clean the URL - Amazon URLs can be messy
                if href.startswith("http"):
                    product_url = href.split("?")[0] if "?" in href else href
                else:
                    # Relative URL, make it absolute
                    product_url = "https://www.amazon.co.uk" + href
                
                if debug:
                    print(f"    Product URL: {product_url}")
        except Exception as e:
            if debug:
                print(f"    URL extraction failed (h2 a): {str(e)}")
            
            # Fallback: Try to find any link with the ASIN
            try:
                all_links = elem.find_elements(By.TAG_NAME, "a")
                for link in all_links:
                    href = link.get_attribute("href")
                    if href and asin in href and "/dp/" in href:
                        product_url = "https://www.amazon.co.uk/dp/" + asin
                        if debug:
                            print(f"    Product URL (fallback): {product_url}")
                        break
            except Exception as e2:
                if debug:
                    print(f"    URL fallback also failed: {str(e2)}")
        
        # Final fallback: construct URL from ASIN
        if not product_url and asin:
            product_url = f"https://www.amazon.co.uk/dp/{asin}"
            if debug:
                print(f"    Product URL (constructed): {product_url}")
        
        product["url"] = product_url
        
        # Extract ALL product images (thumbnail + additional images from product page)
        image_data = self.download_all_images(product_url, keyword, asin, elem)
        product["image_folder"] = image_data["folder"]
        product["image_count"] = image_data["count"]
        product["thumbnail_path"] = image_data["thumbnail"]
        
        return product
    
    def extract_badges(self, elem, debug=False):
        """
        Extract all badges from a product element.
        Common badges: Amazon's Choice, Best Seller, Climate Pledge Friendly, etc.
        """
        badges = []
        
        try:
            # Method 1: Look for badge labels (most common)
            badge_elements = elem.find_elements(By.CSS_SELECTOR, "span.a-badge-label")
            for badge_elem in badge_elements:
                badge_text = badge_elem.text.strip()
                if badge_text:
                    badges.append(badge_text)
                    if debug:
                        print(f"    Found badge (a-badge-label): {badge_text}")
            
            # Method 2: Look for specific badge classes
            badge_selectors = [
                "span[class*='badge']",
                "div[class*='badge']",
                "span.a-badge-text",
                "span.a-color-secondary.a-text-bold"
            ]
            
            for selector in badge_selectors:
                try:
                    elements = elem.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        text = el.text.strip()
                        # Filter for known badge patterns
                        if text and any(keyword in text.lower() for keyword in [
                            "amazon's choice", "amazons choice", 
                            "best seller", "bestseller",
                            "climate pledge", 
                            "limited time deal",
                            "prime",
                            "small business"
                        ]):
                            if text not in badges:  # Avoid duplicates
                                badges.append(text)
                                if debug:
                                    print(f"    Found badge ({selector}): {text}")
                except:
                    continue
            
            # Method 3: Search in all span elements for specific patterns
            try:
                all_spans = elem.find_elements(By.TAG_NAME, "span")
                for span in all_spans:
                    text = span.text.strip()
                    # Look for specific badge patterns in the text
                    if text and len(text) < 50:  # Badges are usually short
                        lower_text = text.lower()
                        if any(pattern in lower_text for pattern in [
                            "amazon's choice", "amazons choice",
                            "best seller", "bestseller", "#1 best seller",
                            "climate pledge friendly",
                            "limited time deal",
                            "small business"
                        ]):
                            # Clean up the text
                            clean_text = text.replace("\n", " ").strip()
                            if clean_text not in badges:
                                badges.append(clean_text)
                                if debug:
                                    print(f"    Found badge (span text): {clean_text}")
            except:
                pass
            
            # Method 4: Check for "Amazon's Choice" specifically with its keyword
            try:
                # Amazon's Choice often includes the keyword it's for
                choice_elem = elem.find_elements(By.XPATH, ".//*[contains(text(), \"Amazon's Choice\") or contains(text(), 'Amazons Choice')]")
                for ce in choice_elem:
                    text = ce.text.strip()
                    if text and text not in badges:
                        badges.append(text)
                        if debug:
                            print(f"    Found badge (XPath): {text}")
            except:
                pass
            
        except Exception as e:
            if debug:
                print(f"    Badge extraction error: {str(e)}")
        
        # Clean up badges: remove duplicates and empty strings
        badges = list(dict.fromkeys([b for b in badges if b]))  # Remove duplicates while preserving order
        
        if debug and badges:
            print(f"    Final badges: {badges}")
        
        return badges
    
    def download_all_images(self, product_url, keyword, asin, search_elem):
        """Download thumbnail AND all product page images"""
        import requests
        
        result = {
            "folder": None,
            "count": 0,
            "thumbnail": None
        }
        
        # Create organized folder structure: keyword/ASIN/
        keyword_clean = keyword.replace(" ", "_").replace("/", "-")
        product_folder = os.path.join(self.images_dir, keyword_clean, asin)
        os.makedirs(product_folder, exist_ok=True)
        result["folder"] = product_folder
        
        # 1. Download thumbnail from search results
        thumbnail_url = None
        try:
            img = search_elem.find_element(By.CSS_SELECTOR, "img.s-image")
            img_url = img.get_attribute("src")
            if img_url:
                thumbnail_url = img_url  # Save for deduplication
                response = requests.get(img_url, timeout=10)
                response.raise_for_status()
                thumb_path = os.path.join(product_folder, "00_thumbnail.jpg")
                with open(thumb_path, "wb") as f:
                    f.write(response.content)
                result["thumbnail"] = thumb_path
                result["count"] += 1
                print(f"      Thumbnail saved")
        except Exception as e:
            print(f"      Thumbnail failed: {str(e)}")
        
        # 2. Visit product page WITH Selenium (requests gets blocked)
        if product_url:
            try:
                print(f"      Opening product page in new tab...")
                
                # Open in new tab
                self.driver.execute_script("window.open('');")
                self.driver.switch_to.window(self.driver.window_handles[-1])
                
                # Navigate to product page
                self.driver.get(product_url)
                time.sleep(3)  # Wait for images to load
                
                # Get page source
                html = self.driver.page_source
                print(f"      HTML length: {len(html)} characters")
                
                # Save HTML for debugging (first product only)
                if result["count"] == 1:
                    debug_path = os.path.join(product_folder, "debug_page.html")
                    with open(debug_path, "w", encoding="utf-8") as f:
                        f.write(html)
                    print(f"      Saved HTML for debugging")
                
                # Find all product images
                image_urls = set()
                
                # ONLY use hiRes from JSON - this is the most reliable and complete
                json_matches = re.findall(r'"hiRes":"(https://[^"]+)"', html)
                print(f"      Found {len(json_matches)} hiRes URLs in JSON")
                
                for match in json_matches:
                    if match and match != "null":
                        image_urls.add(match)
                        print(f"        Added: {match[:80]}...")
                
                print(f"      Total unique image URLs to download: {len(image_urls)}")
                
                # Remove thumbnail URL if it's in the set (avoid duplicates)
                if thumbnail_url:
                    # Check if thumbnail is in image_urls (could be different size)
                    urls_to_remove = set()
                    for img_url in image_urls:
                        # Check if it's the same base image (ignore size variations)
                        if thumbnail_url.split("._")[0] in img_url or img_url.split("._")[0] in thumbnail_url:
                            urls_to_remove.add(img_url)
                    
                    if urls_to_remove:
                        print(f"      Removing {len(urls_to_remove)} duplicate(s) of thumbnail")
                        image_urls -= urls_to_remove
                
                print(f"      Images to download (after dedup): {len(image_urls)}")
                
                # Download images with hash-based deduplication
                import requests
                import hashlib
                
                downloaded = 0
                seen_hashes = set()  # Track image content hashes to avoid duplicates
                
                # Start numbering after thumbnail (which is 00)
                img_number = 1
                for img_url in sorted(image_urls):
                    try:
                        print(f"      Downloading image from: {img_url[:60]}...")
                        response = requests.get(img_url, timeout=15)
                        response.raise_for_status()
                        
                        # Calculate hash of image content
                        img_hash = hashlib.md5(response.content).hexdigest()
                        
                        # Check if we've seen this exact image before
                        if img_hash in seen_hashes:
                            print(f"      ⊗ Duplicate image detected (same content), skipping")
                            continue
                        
                        seen_hashes.add(img_hash)
                        
                        # Save with sequential number
                        img_path = os.path.join(product_folder, f"{img_number:02d}_image.jpg")
                        
                        # Double-check file doesn't exist
                        if os.path.exists(img_path):
                            print(f"      ⊗ File {img_number:02d}_image.jpg already exists, skipping")
                            img_number += 1
                            continue
                        
                        with open(img_path, "wb") as f:
                            f.write(response.content)
                        
                        downloaded += 1
                        result["count"] += 1
                        print(f"      ✓ Saved {img_number:02d}_image.jpg ({len(response.content)} bytes)")
                        img_number += 1
                        
                    except Exception as e:
                        print(f"      ✗ Failed: {str(e)}")
                
                print(f"      Downloaded {downloaded} images from product page")
                
                # Close tab and return to search
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
                
            except Exception as e:
                print(f"      ERROR: {str(e)}")
                # Cleanup
                try:
                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                        self.driver.switch_to.window(self.driver.window_handles[0])
                except:
                    pass
        else:
            print(f"      No product URL")
        
        return result
    
    def download_image(self, img_url, keyword, asin):
        try:
            import requests
            folder = os.path.join(self.images_dir, keyword.replace(" ", "_"))
            os.makedirs(folder, exist_ok=True)
            
            response = requests.get(img_url, timeout=10)
            response.raise_for_status()
            
            path = os.path.join(folder, f"{asin}.jpg")
            with open(path, "wb") as f:
                f.write(response.content)
            
            return path
        except:
            return None
    
    def save_results(self, keyword, products):
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
        
        print(f"Saved: {filepath}")
        return filepath
    
    def run(self, keywords, max_products=10):
        print("\n" + "="*60)
        print("AMAZON UK SCRAPER")
        print("="*60)
        print(f"Keywords: {len(keywords)}")
        print(f"Products per keyword: {max_products}")
        print("="*60)
        
        all_results = {}
        
        try:
            for i, keyword in enumerate(keywords, 1):
                print(f"\n[{i}/{len(keywords)}] {keyword}")
                
                products = self.scrape_keyword(keyword, max_products)
                all_results[keyword] = products
                
                if products:
                    self.save_results(keyword, products)
                    
                    titles = sum(1 for p in products if p.get("title"))
                    prices = sum(1 for p in products if p.get("price"))
                    ratings = sum(1 for p in products if p.get("rating"))
                    reviews = sum(1 for p in products if p.get("review_count", 0) > 0)
                    badges = sum(1 for p in products if p.get("badges"))
                    
                    print(f"\n  Completeness:")
                    print(f"    Titles:  {titles}/{len(products)}")
                    print(f"    Prices:  {prices}/{len(products)}")
                    print(f"    Ratings: {ratings}/{len(products)}")
                    print(f"    Reviews: {reviews}/{len(products)}")
                    print(f"    Badges:  {badges}/{len(products)}")
                
                if i < len(keywords):
                    print(f"\nWaiting 30s...")
                    time.sleep(30)
            
            self.save_consolidated(all_results)
            
        finally:
            self.driver.quit()
            print("\nBrowser closed")
        
        print("\n" + "="*60)
        print("COMPLETE")
        print("="*60)
        
        return all_results
    
    def save_consolidated(self, all_results):
        data = {
            "scrape_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_keywords": len(all_results),
            "keywords": all_results
        }
        
        filename = f"consolidated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\nConsolidated: {filepath}")


if __name__ == "__main__":
    keywords = [
        "barberry supplement",
    ]
    
    # Headless mode - no browser window shown
    scraper = AmazonUKScraper(output_dir="data", headless=True)
    results = scraper.run(keywords, max_products=10)
    
    print("\nSUMMARY:")
    for keyword, products in results.items():
        if products:
            titles = sum(1 for p in products if p.get("title"))
            prices = sum(1 for p in products if p.get("price"))
            badges = sum(1 for p in products if p.get("badges"))
            print(f"  {keyword}: {len(products)} products | {titles} titles | {prices} prices | {badges} badges")
        else:
            print(f"  {keyword}: Failed")