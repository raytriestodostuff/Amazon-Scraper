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
        self.images_dir = os.path.join(output_dir, "product_images")
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
        
        # Extract badges from search results (simplified - just badge types)
        badges_full = self.extract_badges(elem, debug=(position <= 3))
        # Simplify to just badge types
        product["badges"] = [b["badge_type"] for b in badges_full]
        
        # Check if has best seller for BSR extraction
        has_best_seller = any(b["badge_type"] == "Best Seller" for b in badges_full)
        
        if badges_full and position <= 3:
            print(f"    Badges found: {len(badges_full)}")
            for badge in badges_full:
                if badge["badge_type"] == "Best Seller":
                    print(f"      - Best Seller badge detected")
                elif badge["badge_type"] == "Amazon's Choice":
                    kw_str = f"for '{badge['keyword']}'" if badge['keyword'] else ""
                    print(f"      - Amazon's Choice {kw_str}")
                else:
                    print(f"      - {badge['badge_type']}")
        
        # Extract product URL
        product_url = None
        try:
            link = elem.find_element(By.CSS_SELECTOR, "h2 a")
            href = link.get_attribute("href")
            if href:
                if href.startswith("http"):
                    product_url = href.split("?")[0] if "?" in href else href
                else:
                    product_url = "https://www.amazon.co.uk" + href
                
                if debug:
                    print(f"    Product URL: {product_url}")
        except Exception as e:
            if debug:
                print(f"    URL extraction failed (h2 a): {str(e)}")
            
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
        
        if not product_url and asin:
            product_url = f"https://www.amazon.co.uk/dp/{asin}"
            if debug:
                print(f"    Product URL (constructed): {product_url}")
        
        product["url"] = product_url
        
        # Extract images AND BSR from product page (combined to avoid visiting page twice)
        # Only extract BSR if product has "Best Seller" badge
        image_and_bsr_data = self.download_all_images_and_extract_bsr(
            product_url, keyword, asin, elem, 
            extract_bsr=has_best_seller,
            debug=(position <= 3)
        )
        product["image_folder"] = image_and_bsr_data["folder"]
        product["image_count"] = image_and_bsr_data["count"]
        product["thumbnail_path"] = image_and_bsr_data["thumbnail"]
        
        # Add BSR data - simplified structure with N/A instead of null
        if image_and_bsr_data["bsr_ranks"]:
            # Get the primary (first) rank
            primary_rank = image_and_bsr_data["bsr_ranks"][0]
            product["bsr_rank"] = primary_rank.get("rank", "N/A")
            product["bsr_category"] = primary_rank.get("category", "N/A")
            # Store all ranks only if there are multiple
            if len(image_and_bsr_data["bsr_ranks"]) > 1:
                product["bsr_all_ranks"] = image_and_bsr_data["bsr_ranks"]
        else:
            product["bsr_rank"] = "N/A"
            product["bsr_category"] = "N/A"
        
        return product
    
    def parse_badge_details(self, badge_text):
        """Parse badge text to extract rank, category, and badge type."""
        details = {
            "raw_text": badge_text,
            "badge_type": None,
            "rank": None,
            "category": None,
            "keyword": None
        }
        
        lower_text = badge_text.lower()
        
        if "amazon's choice" in lower_text or "amazons choice" in lower_text:
            details["badge_type"] = "Amazon's Choice"
            keyword_match = re.search(r'for ["\']([^"\']+)["\']', badge_text, re.IGNORECASE)
            if keyword_match:
                details["keyword"] = keyword_match.group(1)
        
        elif "best seller" in lower_text or "bestseller" in lower_text:
            details["badge_type"] = "Best Seller"
            rank_match = re.search(r'#(\d+)', badge_text)
            if rank_match:
                details["rank"] = int(rank_match.group(1))
            category_match = re.search(r'\bin\s+(.+?)(?:\s*$)', badge_text, re.IGNORECASE)
            if category_match:
                details["category"] = category_match.group(1).strip()
        
        elif "climate pledge" in lower_text:
            details["badge_type"] = "Climate Pledge Friendly"
        
        elif "limited time deal" in lower_text:
            details["badge_type"] = "Limited Time Deal"
        
        elif "small business" in lower_text:
            details["badge_type"] = "Small Business"
        
        else:
            details["badge_type"] = "Other"
        
        return details
    
    def extract_badges(self, elem, debug=False):
        """Extract all badges with detailed parsing for rank and category."""
        badges_raw = []
        
        try:
            badge_elements = elem.find_elements(By.CSS_SELECTOR, "span.a-badge-label")
            for badge_elem in badge_elements:
                badge_text = badge_elem.text.strip()
                if badge_text:
                    badges_raw.append(badge_text)
                    if debug:
                        print(f"    Found badge (a-badge-label): {badge_text}")
            
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
                        if text and any(keyword in text.lower() for keyword in [
                            "amazon's choice", "amazons choice", 
                            "best seller", "bestseller",
                            "climate pledge", 
                            "limited time deal",
                            "prime",
                            "small business"
                        ]):
                            if text not in badges_raw:
                                badges_raw.append(text)
                                if debug:
                                    print(f"    Found badge ({selector}): {text}")
                except:
                    continue
            
            try:
                all_spans = elem.find_elements(By.TAG_NAME, "span")
                for span in all_spans:
                    text = span.text.strip()
                    if text and len(text) < 100:
                        lower_text = text.lower()
                        if any(pattern in lower_text for pattern in [
                            "amazon's choice", "amazons choice",
                            "best seller", "bestseller", "#1 best seller",
                            "climate pledge friendly",
                            "limited time deal",
                            "small business"
                        ]):
                            clean_text = text.replace("\n", " ").strip()
                            if clean_text not in badges_raw:
                                badges_raw.append(clean_text)
                                if debug:
                                    print(f"    Found badge (span text): {clean_text}")
            except:
                pass
            
            try:
                choice_elem = elem.find_elements(By.XPATH, ".//*[contains(text(), \"Amazon's Choice\") or contains(text(), 'Amazons Choice')]")
                for ce in choice_elem:
                    text = ce.text.strip()
                    if text and text not in badges_raw:
                        badges_raw.append(text)
                        if debug:
                            print(f"    Found badge (XPath): {text}")
            except:
                pass
            
        except Exception as e:
            if debug:
                print(f"    Badge extraction error: {str(e)}")
        
        badges_raw = list(dict.fromkeys([b for b in badges_raw if b]))
        
        badges_parsed = []
        for badge_text in badges_raw:
            badge_details = self.parse_badge_details(badge_text)
            badges_parsed.append(badge_details)
        
        return badges_parsed
    
    def extract_bsr_from_page(self, html, asin, debug=False):
        """
        Extract Best Sellers Rank from product page HTML.
        Looks for patterns like:
        - "Best Sellers Rank: 6,163 in Health & Personal Care"
        - "12 in Grocery"
        
        Avoids matching "Top 100" text.
        """
        bsr_ranks = []
        
        # Save HTML snippet for debugging if needed
        if debug:
            # Look for BSR section in HTML
            bsr_section_match = re.search(r'Best Sellers? Rank.{0,500}', html, re.IGNORECASE | re.DOTALL)
            if bsr_section_match:
                print(f"      Found BSR section in HTML:")
                print(f"      {bsr_section_match.group(0)[:300]}...")
            else:
                print(f"      WARNING: No 'Best Sellers Rank' text found in HTML")
                # Check if product details section exists at all
                if "Product details" in html or "Product information" in html:
                    print(f"      (Product details section exists)")
                else:
                    print(f"      (Product details section NOT found)")
        
        try:
           
            patterns = [
                # Pattern 1: "Best Sellers Rank: 6,163 in Category" (no #)
                r'Best Sellers? Rank[:\s]*([0-9,]+)\s+in\s+([^(<\n]+?)(?:\s*\(|$)',
                # Pattern 2: "Best-sellers rank: 6,163 in Category" (with hyphen, no #)
                r'Best-sellers? rank[:\s]*([0-9,]+)\s+in\s+([^(<\n]+?)(?:\s*\(|$)',
                # Pattern 3: More lenient - any rank after "Best" and "Rank"
                r'Best[^:]{0,20}Rank[:\s]*([0-9,]+)\s+in\s+([^(<\n]+?)(?:\s*\(|$)',
            ]
            
            for pattern_idx, pattern in enumerate(patterns):
                matches = re.findall(pattern, html, re.IGNORECASE)
                
                if debug and matches:
                    print(f"      BSR Pattern {pattern_idx+1} found {len(matches)} potential ranks")
                
                for match in matches:
                    rank_str = match[0].replace(',', '')
                    category = match[1].strip()
                    
                    # Smart filtering: Check if "Top" precedes this number to avoid "Top 100" false positives
                    # Only skip if this looks like "Top 100" pattern
                    search_pattern = f'Top\\s+{re.escape(match[0])}\\s+in'
                    if re.search(search_pattern, html, re.IGNORECASE):
                        if debug:
                            print(f"        Skipping 'Top {match[0]}' text (found 'Top' before number)")
                        continue
                    
                    try:
                        rank_num = int(rank_str)
                        if rank_num > 0 and len(category) > 2:
                            # Avoid duplicates
                            if not any(r["rank"] == rank_num and r["category"] == category for r in bsr_ranks):
                                bsr_ranks.append({
                                    "rank": rank_num,
                                    "category": category
                                })
                                if debug:
                                    print(f"        ✓ #{rank_num:,} in {category}")
                    except:
                        pass
            
           
            pattern2 = r'(?:>|\s)([0-9,]+)\s+in\s+([^(<\n]+?)(?:\s*\(|<)'
            matches2 = re.findall(pattern2, html, re.IGNORECASE)
            
            seen_ranks = {(r["rank"], r["category"]) for r in bsr_ranks}
            
            if debug and matches2:
                print(f"      BSR Method 2 found {len(matches2)} potential sub-ranks")
            
            for match in matches2:
                rank_str = match[0].replace(',', '')
                category = match[1].strip()
                
                # Skip "Top 100", "Top 50" etc by checking if preceded by "Top"
                # Look backwards in HTML to see if "Top" appears right before this number
                search_pattern = f'Top\\s+{re.escape(match[0])}\\s+in'
                if re.search(search_pattern, html, re.IGNORECASE):
                    if debug:
                        print(f"        Skipping 'Top {match[0]}' text")
                    continue
                
                # Filter out junk matches
                if len(category) < 3 or len(category) > 100:
                    continue
                    
                # Avoid duplicates
                try:
                    rank_num = int(rank_str)
                    if (rank_num, category) not in seen_ranks and rank_num > 0:
                        # Check if this looks like a real category
                        if any(char.isalpha() for char in category):
                            bsr_ranks.append({
                                "rank": rank_num,
                                "category": category
                            })
                            seen_ranks.add((rank_num, category))
                            if debug:
                                print(f"        ✓ #{rank_num:,} in {category}")
                except:
                    pass
            
            # Limit to top 5 most relevant ranks
            bsr_ranks = bsr_ranks[:5]
            
        except Exception as e:
            if debug:
                print(f"      BSR extraction error: {str(e)}")
        
        return bsr_ranks
    
    def download_all_images_and_extract_bsr(self, product_url, keyword, asin, search_elem, extract_bsr=False, debug=False):
        """Download thumbnail, all product page images, AND extract BSR (only if extract_bsr=True)."""
        import requests
        
        result = {
            "folder": None,
            "count": 0,
            "thumbnail": None,
            "bsr_ranks": []
        }
        
        keyword_clean = keyword.replace(" ", "_").replace("/", "-")
        product_folder = os.path.join(self.images_dir, keyword_clean, asin)
        os.makedirs(product_folder, exist_ok=True)
        result["folder"] = product_folder
        
        thumbnail_url = None
        try:
            img = search_elem.find_element(By.CSS_SELECTOR, "img.s-image")
            img_url = img.get_attribute("src")
            if img_url:
                thumbnail_url = img_url
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
        
        if product_url:
            try:
                print(f"      Opening product page in new tab...")
                
                self.driver.execute_script("window.open('');")
                self.driver.switch_to.window(self.driver.window_handles[-1])
                
                self.driver.get(product_url)
                time.sleep(3)
                
                html = self.driver.page_source
                print(f"      HTML length: {len(html)} characters")
                
                # Extract BSR from product page ONLY if product has Best Seller badge
                if extract_bsr:
                    if debug:
                        print(f"      Extracting BSR (Best Seller badge detected)...")
                    bsr_ranks = self.extract_bsr_from_page(html, asin, debug=debug)
                    result["bsr_ranks"] = bsr_ranks
                    
                    if bsr_ranks:
                        print(f"      Found {len(bsr_ranks)} BSR rank(s)")
                        for bsr in bsr_ranks[:2]:  # Show first 2
                            print(f"        #{bsr['rank']:,} in {bsr['category']}")
                    else:
                        print(f"      No BSR found on product page")
                else:
                    if debug:
                        print(f"      Skipping BSR (no Best Seller badge)")
                
                # Find all product images
                image_urls = set()
                json_matches = re.findall(r'"hiRes":"(https://[^"]+)"', html)
                print(f"      Found {len(json_matches)} hiRes URLs in JSON")
                
                for match in json_matches:
                    if match and match != "null":
                        image_urls.add(match)
                
                if thumbnail_url:
                    urls_to_remove = set()
                    for img_url in image_urls:
                        if thumbnail_url.split("._")[0] in img_url or img_url.split("._")[0] in thumbnail_url:
                            urls_to_remove.add(img_url)
                    
                    if urls_to_remove:
                        print(f"      Removing {len(urls_to_remove)} duplicate(s) of thumbnail")
                        image_urls -= urls_to_remove
                
                print(f"      Images to download: {len(image_urls)}")
                
                import hashlib
                downloaded = 0
                seen_hashes = set()
                img_number = 1
                
                for img_url in sorted(image_urls):
                    try:
                        response = requests.get(img_url, timeout=15)
                        response.raise_for_status()
                        
                        img_hash = hashlib.md5(response.content).hexdigest()
                        
                        if img_hash in seen_hashes:
                            continue
                        
                        seen_hashes.add(img_hash)
                        img_path = os.path.join(product_folder, f"{img_number:02d}_image.jpg")
                        
                        if os.path.exists(img_path):
                            img_number += 1
                            continue
                        
                        with open(img_path, "wb") as f:
                            f.write(response.content)
                        
                        downloaded += 1
                        result["count"] += 1
                        img_number += 1
                        
                    except Exception as e:
                        pass
                
                if downloaded > 0:
                    print(f"      Downloaded {downloaded} images from product page")
                
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
                
            except Exception as e:
                print(f"      ERROR: {str(e)}")
                try:
                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                        self.driver.switch_to.window(self.driver.window_handles[0])
                except:
                    pass
        else:
            print(f"      No product URL")
        
        return result
    
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
                    best_sellers = sum(1 for p in products if "Best Seller" in p.get("badges", []))
                    amazons_choice = sum(1 for p in products if "Amazon's Choice" in p.get("badges", []))
                    bsr_count = sum(1 for p in products if p.get("bsr_rank") != "N/A")
                    
                    print(f"\n  Completeness:")
                    print(f"    Titles:  {titles}/{len(products)}")
                    print(f"    Prices:  {prices}/{len(products)}")
                    print(f"    Ratings: {ratings}/{len(products)}")
                    print(f"    Reviews: {reviews}/{len(products)}")
                    print(f"    Badges:  {badges}/{len(products)}")
                    print(f"    Best Sellers: {best_sellers}/{len(products)}")
                    print(f"    Amazon's Choice: {amazons_choice}/{len(products)}")
                    print(f"    BSR Data: {bsr_count}/{len(products)}")
                
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
        "keyrings",
    ]
    
    scraper = AmazonUKScraper(output_dir="data", headless=True)
    results = scraper.run(keywords, max_products=10)
    
    print("\nSUMMARY:")
    for keyword, products in results.items():
        if products:
            titles = sum(1 for p in products if p.get("title"))
            prices = sum(1 for p in products if p.get("price"))
            bsr_count = sum(1 for p in products if p.get("bsr_rank") != "N/A")
            print(f"  {keyword}: {len(products)} products | {titles} titles | {prices} prices | {bsr_count} with BSR")
        else:
            print(f"  {keyword}: Failed")