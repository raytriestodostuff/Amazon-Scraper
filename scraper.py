"""
Amazon UK Scraper with ScraperAPI + Firecrawl
- Extracts complete product data: ASIN, title, price, reviews, BSR, badges, images
- Parallel keyword scraping
- Structured JSON output ready for GPT-5 Nano
"""

import asyncio
import aiohttp
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import logging
from urllib.parse import quote_plus, urlencode
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AmazonUKScraper:
    """Complete scraper for Amazon UK products"""

    def __init__(self, config_path: str = "config.json"):
        """Initialize scraper from config file"""
        with open(config_path) as f:
            self.config = json.load(f)

        self.scraperapi_key = self.config['api_keys']['scraperapi']
        self.firecrawl_key = self.config['api_keys']['firecrawl']
        self.max_concurrent = self.config['settings']['max_concurrent']

        # Create country-specific output directory
        base_output_dir = Path(self.config['settings']['output_dir'])
        country = self.config['settings'].get('country', 'uk')
        self.output_dir = base_output_dir / country
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Country-specific settings
        country = self.config['settings'].get('country', 'uk')
        country_config = {
            'uk': {'domain': 'amazon.co.uk', 'currency': 'GBP', 'code': 'gb'},
            'es': {'domain': 'amazon.es', 'currency': 'EUR', 'code': 'es'},
            'de': {'domain': 'amazon.de', 'currency': 'EUR', 'code': 'de'},
            'fr': {'domain': 'amazon.fr', 'currency': 'EUR', 'code': 'fr'},
            'it': {'domain': 'amazon.it', 'currency': 'EUR', 'code': 'it'}
        }

        config = country_config.get(country, country_config['uk'])
        self.domain = config['domain']
        self.currency = config['currency']
        self.country_code = config['code']
        self.semaphore = asyncio.Semaphore(self.max_concurrent)

        logger.info(f"✓ Initialized Amazon {country.upper()} Scraper")
        logger.info(f"  Domain: {self.domain}")
        logger.info(f"  Parallel workers: {self.max_concurrent}")

    def build_scraperapi_url(self, amazon_url: str) -> str:
        """Build ScraperAPI URL that wraps Amazon URL"""
        params = {
            'api_key': self.scraperapi_key,
            'url': amazon_url,
            'render': 'true',
            'country_code': self.country_code
        }
        return f"http://api.scraperapi.com/?{urlencode(params)}"

    async def fetch_with_firecrawl_and_scraperapi(self, url: str) -> str:
        """Fetch page via Firecrawl scrape endpoint using ScraperAPI-wrapped URL"""
        if not self.firecrawl_key:
            return ''

        # Wrap the Amazon URL with ScraperAPI
        scraperapi_url = self.build_scraperapi_url(url)

        firecrawl_url = "https://api.firecrawl.dev/v1/scrape"
        headers = {
            'Authorization': f'Bearer {self.firecrawl_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'url': scraperapi_url,
            'formats': ['html']
        }

        async with self.semaphore:
            for attempt in range(3):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            firecrawl_url,
                            headers=headers,
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=90)
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                html = data.get('data', {}).get('html', '')
                                logger.info(f"  + Firecrawl + ScraperAPI: {len(html)} chars")
                                return html
                            else:
                                logger.warning(f"  ! Firecrawl {response.status}")
                except Exception as e:
                    logger.warning(f"  ! Attempt {attempt + 1}: {str(e)[:50]}")
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)

        return ''

    def extract_products_from_html(self, html: str) -> List[Dict]:
        """Extract structured product data from search results HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        products = []

        # Find all product containers
        product_divs = soup.find_all('div', {'data-component-type': 's-search-result'})
        logger.info(f"  Found {len(product_divs)} product containers")

        for idx, div in enumerate(product_divs[:50], 1):  # Top 50 products
            try:
                # ASIN
                asin = div.get('data-asin', '')
                if not asin or len(asin) != 10:
                    continue

                # Skip if starts with 000 (usually invalid)
                if asin.startswith('000'):
                    continue

                # Check if sponsored - skip sponsored products entirely
                sponsored_span = div.find('span', text=re.compile(r'Sponsored|Patrocinado', re.I))
                is_sponsored = sponsored_span is not None

                if is_sponsored:
                    continue  # Skip sponsored products

                # Title
                title_elem = div.find('h2')
                title = title_elem.get_text(strip=True) if title_elem else ''

                # Price
                price = None
                price_whole = div.find('span', class_='a-price-whole')
                price_fraction = div.find('span', class_='a-price-fraction')
                if price_whole and price_fraction:
                    try:
                        price_str = price_whole.get_text(strip=True).replace(',', '').replace('.', '')
                        price_str += '.' + price_fraction.get_text(strip=True)
                        price = float(price_str)
                    except:
                        pass

                # Rating
                rating = None
                rating_elem = div.find('span', class_='a-icon-alt')
                if rating_elem:
                    rating_text = rating_elem.get_text()
                    match = re.search(r'([\d.]+)', rating_text)
                    if match:
                        rating = float(match.group(1))

                # Review count - try multiple methods
                review_count = 0

                # Method 1: Look for aria-label with ratings count
                review_elem = div.find('span', {'aria-label': re.compile(r'\d+.*rating', re.I)})
                if review_elem:
                    review_text = review_elem.get('aria-label', '')
                    match = re.search(r'([\d,]+)', review_text)
                    if match:
                        review_count = int(match.group(1).replace(',', ''))

                # Method 2: Look for direct text near rating
                if review_count == 0:
                    review_spans = div.find_all('span', string=re.compile(r'^\d+(,\d+)*$'))
                    for span in review_spans:
                        text = span.get_text(strip=True)
                        if text and ',' in text or len(text) >= 2:
                            try:
                                review_count = int(text.replace(',', ''))
                                break
                            except:
                                pass

                # Badges (including Best Seller, Amazon's Choice, etc.)
                badges = []
                seen_badges = set()

                # Look for badge containers (avoid nested elements causing duplicates)
                badge_containers = div.find_all(['span', 'div'], class_=re.compile(r'badge|a-badge', re.I))
                for container in badge_containers:
                    badge_text = container.get_text(separator=' ', strip=True)
                    # Only keep meaningful badges (not too short, not too long, not duplicates)
                    if badge_text and 5 < len(badge_text) < 100:
                        if badge_text not in seen_badges and not any(badge_text in s or s in badge_text for s in seen_badges):
                            badges.append(badge_text)
                            seen_badges.add(badge_text)

                # BSR (Best Sellers Rank) - extract from badges or text
                bsr_rank = None
                bsr_category = None
                bsr_text = div.find('span', text=re.compile(r'#\d+.*in', re.I))
                if bsr_text:
                    bsr_full = bsr_text.get_text(strip=True)
                    # Extract rank number
                    rank_match = re.search(r'#([\d,]+)', bsr_full)
                    if rank_match:
                        bsr_rank = int(rank_match.group(1).replace(',', ''))
                    # Extract category
                    cat_match = re.search(r'in\s+(.+?)(?:\(|$)', bsr_full)
                    if cat_match:
                        bsr_category = cat_match.group(1).strip()

                # Product URL - always construct from ASIN for consistency
                product_url = f"https://www.{self.domain}/dp/{asin}" if asin else ''

                # Main image
                img_elem = div.find('img', class_='s-image')
                image_url = img_elem.get('src', '') if img_elem else ''

                # Store only the main image (variants have different ASINs)
                product_images = [image_url] if image_url else []

                # Availability
                availability = None
                avail_elem = div.find('span', {'aria-label': re.compile(r'Available|In stock|Out of stock', re.I)})
                if avail_elem:
                    availability = avail_elem.get_text(strip=True)

                # Build product dict (will be enriched with BSR and images from product page)
                product = {
                    'asin': asin,
                    'title': title,
                    'price': price,
                    'currency': self.currency,
                    'rating': rating,
                    'review_count': review_count,
                    'badges': badges,
                    'url': product_url,
                    'all_images': product_images  # Temp, will be replaced by product page images
                }

                products.append(product)

            except Exception as e:
                logger.error(f"  ✗ Error extracting product {idx}: {e}")
                continue

        logger.info(f"  ✓ Extracted {len(products)} products")
        return products

    async def scrape_keyword(self, keyword: str) -> Dict:
        """Scrape complete product data for a keyword"""
        logger.info(f"\n{'='*70}")
        logger.info(f"KEYWORD: {keyword}")
        logger.info(f"{'='*70}")

        search_url = f"https://www.{self.domain}/s?k={quote_plus(keyword)}"

        try:
            # Fetch search page via Firecrawl using ScraperAPI
            html = await self.fetch_with_firecrawl_and_scraperapi(search_url)

            if not html:
                raise Exception("Failed to fetch search page")

            # Extract structured product data from search results
            products = self.extract_products_from_html(html)

            logger.info(f"  Found {len(products)} products on search page")

            # Scrape individual product pages in parallel
            max_products = self.config['settings'].get('max_products_to_scrape', 50)
            if products:
                logger.info(f"  Scraping individual product pages (max: {max_products})...")
                product_tasks = [
                    self.scrape_product_page(product)
                    for product in products[:max_products]
                ]
                enriched_products = await asyncio.gather(*product_tasks)

                # Replace basic products with enriched data
                products = [p for p in enriched_products if p is not None]

            # Build output
            output = {
                'keyword': keyword,
                'country': self.config['settings'].get('country', 'uk'),
                'domain': self.domain,
                'currency': self.currency,
                'search_url': search_url,
                'scrape_date': datetime.now().isoformat(),
                'status': 'success',
                'total_products': len(products),
                'products': products
            }

            logger.info(f"✓ SUCCESS: {len(products)} products")
            return output

        except Exception as e:
            logger.error(f"✗ FAILED: {e}")
            return {
                'keyword': keyword,
                'search_url': search_url,
                'scrape_date': datetime.now().isoformat(),
                'status': 'failed',
                'error': str(e)
            }

    async def scrape_product_page(self, product: Dict) -> Optional[Dict]:
        """Scrape individual product page for additional details (BSR, etc.)"""
        if not product.get('url'):
            return product

        try:
            logger.info(f"    Scraping: {product['asin']}")

            # Fetch product page via Firecrawl with ScraperAPI
            html = await self.fetch_with_firecrawl_and_scraperapi(product['url'])

            if not html:
                logger.warning(f"    ⚠ Failed to fetch {product['asin']}")
                return product

            soup = BeautifulSoup(html, 'html.parser')

            # Extract BSR from product page - try multiple methods
            bsr_rank = None
            bsr_category = None

            # Method 1: Look in product details table
            detail_bullets = soup.find('div', id='detailBulletsWrapper_feature_div')
            if detail_bullets:
                bsr_text = detail_bullets.find('span', string=re.compile(r'Best Sellers Rank', re.I))
                if bsr_text:
                    parent = bsr_text.find_parent('li') or bsr_text.find_parent('tr')
                    if parent:
                        full_text = parent.get_text()
                        rank_match = re.search(r'#([\d,]+)', full_text)
                        if rank_match:
                            bsr_rank = int(rank_match.group(1).replace(',', ''))
                        cat_match = re.search(r'in\s+([^(#\n]+)', full_text)
                        if cat_match:
                            bsr_category = cat_match.group(1).strip()

            # Method 2: Look in product information section
            if not bsr_rank:
                prod_info = soup.find('div', id='prodDetails')
                if prod_info:
                    bsr_text = prod_info.find(string=re.compile(r'Best Sellers Rank', re.I))
                    if bsr_text:
                        parent = bsr_text.find_parent('tr') or bsr_text.find_parent('li')
                        if parent:
                            full_text = parent.get_text()
                            rank_match = re.search(r'#([\d,]+)', full_text)
                            if rank_match:
                                bsr_rank = int(rank_match.group(1).replace(',', ''))
                            cat_match = re.search(r'in\s+([^(#\n]+)', full_text)
                            if cat_match:
                                bsr_category = cat_match.group(1).strip()

            # Method 3: Look in detail_bullets (alternative structure)
            if not bsr_rank:
                detail_bullets_alt = soup.find('div', id='detail-bullets')
                if detail_bullets_alt:
                    bsr_li = detail_bullets_alt.find('li', string=re.compile(r'Best Sellers Rank', re.I))
                    if not bsr_li:
                        # Try finding via contains
                        for li in detail_bullets_alt.find_all('li'):
                            if 'Best Sellers Rank' in li.get_text():
                                bsr_li = li
                                break
                    if bsr_li:
                        full_text = bsr_li.get_text()
                        rank_match = re.search(r'#([\d,]+)', full_text)
                        if rank_match:
                            bsr_rank = int(rank_match.group(1).replace(',', ''))
                        cat_match = re.search(r'in\s+([^(#\n]+)', full_text)
                        if cat_match:
                            bsr_category = cat_match.group(1).strip()

            # Method 4: Search entire HTML for BSR pattern (multi-language support)
            if not bsr_rank:
                # Multi-language BSR patterns
                bsr_patterns = [
                    # English
                    r'Best Sellers Rank[:\s]*</span>\s*(\d+)\s+in\s+.*?>([^<]+)</a>',
                    r'Best Sellers Rank[:\s]+#?(\d+)\s+in\s+([^(<\n]+)',
                    # Spanish
                    r'Clasificación en los más vendidos[:\s]*</span>\s*(\d+)\s+en\s+.*?>([^<]+)</a>',
                    r'Clasificación[:\s]*</span>\s*nº\.?\s*(\d+)\s+en\s+.*?>([^<]+)</a>',
                    r'nº\.?\s*(\d+)\s+en\s+<a[^>]*>([^<]+)</a>',
                    # German
                    r'Bestseller-Rang[:\s]*</span>\s*Nr\.\s*(\d+)\s+in\s+.*?>([^<]+)</a>',
                    # French
                    r'Classement des meilleures ventes[:\s]*</span>\s*(\d+)\s+en\s+.*?>([^<]+)</a>',
                    # Generic
                    r'#(\d+)\s+in\s+<a[^>]*>([^<]+)</a>'
                ]
                for pattern in bsr_patterns:
                    match = re.search(pattern, html, re.IGNORECASE)
                    if match:
                        bsr_rank = int(match.group(1).replace(',', '').replace('.', ''))
                        bsr_category = match.group(2).strip() if len(match.groups()) > 1 else None
                        break

            # Extract main product images (not variants)
            additional_images = []
            img_block = soup.find('div', id='altImages')
            if img_block:
                imgs = img_block.find_all('img')
                for img in imgs[:7]:  # Limit to first 7 images to avoid variants
                    img_src = img.get('src', '')
                    if img_src and 'amazon' in img_src and 'icon' not in img_src.lower():
                        # Convert thumbnail to full size
                        img_src = re.sub(r'\._.*?_\.', '.', img_src)
                        clean_img = img_src.split('?')[0]
                        if clean_img not in additional_images:
                            additional_images.append(clean_img)

            # Update product with enriched data
            if bsr_rank:
                product['bsr_rank'] = bsr_rank
            if bsr_category:
                product['bsr_category'] = bsr_category
            # Replace with product page images (more complete than search page)
            if additional_images:
                product['images'] = additional_images
            else:
                product['images'] = product.get('all_images', [])
            # Remove old field
            product.pop('all_images', None)
            product.pop('main_image', None)

            logger.info(f"    ✓ {product['asin']}: BSR={bsr_rank}, Images={len(product.get('images', []))}")
            return product

        except Exception as e:
            logger.error(f"    ✗ Error scraping {product.get('asin')}: {e}")
            return product

    async def scrape_all(self) -> List[Dict]:
        """Scrape all keywords from config"""
        keywords = self.config['keywords']
        logger.info(f"\n{'*'*70}")
        logger.info(f"STARTING SCRAPE: {len(keywords)} keywords")
        logger.info(f"{'*'*70}\n")

        tasks = [self.scrape_keyword(kw) for kw in keywords]
        results = await asyncio.gather(*tasks)

        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        country = self.config['settings'].get('country', 'uk')

        # Save individual keyword files
        for result in results:
            if result['status'] == 'success':
                keyword = result['keyword'].replace(' ', '_').replace('/', '_')
                keyword_file = self.output_dir / f"{keyword}_{timestamp}.json"
                with open(keyword_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                logger.info(f"  Saved: {keyword_file}")

        # Save consolidated file
        consolidated_file = self.output_dir / f"all_keywords_{timestamp}.json"
        with open(consolidated_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        successful = sum(1 for r in results if r['status'] == 'success')
        total_products = sum(r.get('total_products', 0) for r in results if r['status'] == 'success')

        logger.info(f"\n{'='*70}")
        logger.info(f"COMPLETE: {successful}/{len(results)} keywords | {total_products} products")
        logger.info(f"Consolidated: {consolidated_file}")
        logger.info(f"{'='*70}\n")

        return results


def main():
    """Run scraper"""
    scraper = AmazonUKScraper("config.json")
    results = asyncio.run(scraper.scrape_all())
    print("\n✓ Done! Check output/ folder")


if __name__ == '__main__':
    main()
