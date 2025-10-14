"""
LAYER 2: HTML Parser & Data Extractor
- Parses HTML using BeautifulSoup
- Extracts structured product data
- Handles multi-language content (EN, ES, DE, FR, IT)
"""

import re
import logging
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ProductParser:
    """Extracts structured product data from Amazon HTML"""

    def __init__(self, domain: str, currency: str):
        self.domain = domain
        self.currency = currency

    def parse_search_results(self, html: str) -> List[Dict]:
        """
        Extract product list from search results page

        Args:
            html: Search results HTML

        Returns:
            List of product dictionaries with basic data
        """
        soup = BeautifulSoup(html, 'html.parser')
        products = []

        # Find all product containers
        product_divs = soup.find_all('div', {'data-component-type': 's-search-result'})
        logger.info(f"  Found {len(product_divs)} product containers")

        position_counter = 0  # Track non-sponsored position

        for idx, div in enumerate(product_divs, 1):
            try:
                # Extract ASIN
                asin = div.get('data-asin', '')
                if not asin or len(asin) != 10 or asin.startswith('000'):
                    continue

                # Skip sponsored products
                if self._is_sponsored(div):
                    continue

                # Increment position for non-sponsored products
                position_counter += 1

                # Extract all basic fields
                title = self._extract_title(div)
                price = self._extract_price(div)
                rating = self._extract_rating(div)
                review_count = self._extract_review_count(div)
                badges = self._extract_badges(div)
                image_url = self._extract_image(div)

                # Build product URL from ASIN
                product_url = f"https://www.{self.domain}/dp/{asin}"

                product = {
                    'asin': asin,
                    'search_position': position_counter,  # Add position (1-indexed)
                    'title': title,
                    'price': price,
                    'currency': self.currency,
                    'rating': rating,
                    'review_count': review_count,
                    'badges': badges,
                    'url': product_url,
                    'main_image': image_url
                }

                products.append(product)

            except Exception as e:
                logger.error(f"  ✗ Error parsing product {idx}: {e}")
                continue

        logger.info(f"  ✓ Extracted {len(products)} valid products")
        return products

    def parse_product_page(self, html: str) -> Tuple[Optional[int], Optional[str], List[str]]:
        """
        Extract detailed data from individual product page

        Args:
            html: Product page HTML

        Returns:
            Tuple of (bsr_rank, bsr_category, images_list)
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Extract BSR (Best Sellers Rank)
        bsr_rank, bsr_category = self._extract_bsr(soup, html)

        # Extract product images
        images = self._extract_product_images(soup)

        return bsr_rank, bsr_category, images

    def _is_sponsored(self, div) -> bool:
        """Check if product is sponsored (multi-language)"""
        sponsored_span = div.find('span', text=re.compile(r'Sponsored|Patrocinado|Gesponsert|Sponsorisé', re.I))
        return sponsored_span is not None

    def _extract_title(self, div) -> str:
        """Extract product title"""
        title_elem = div.find('h2')
        return title_elem.get_text(strip=True) if title_elem else ''

    def _extract_price(self, div) -> Optional[float]:
        """Extract product price"""
        price_whole = div.find('span', class_='a-price-whole')
        price_fraction = div.find('span', class_='a-price-fraction')

        if price_whole and price_fraction:
            try:
                # Handle different decimal separators (UK uses ., EU uses ,)
                whole = price_whole.get_text(strip=True).replace(',', '').replace('.', '')
                fraction = price_fraction.get_text(strip=True)
                price_str = f"{whole}.{fraction}"
                return float(price_str)
            except (ValueError, AttributeError):
                return None
        return None

    def _extract_rating(self, div) -> Optional[float]:
        """Extract product rating (out of 5)"""
        rating_elem = div.find('span', class_='a-icon-alt')
        if rating_elem:
            rating_text = rating_elem.get_text()
            match = re.search(r'([\d.]+)', rating_text)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    return None
        return None

    def _extract_review_count(self, div) -> int:
        """Extract number of reviews (multi-language)"""
        # Method 1: aria-label with ratings count
        review_elem = div.find('span', {'aria-label': re.compile(r'\d+.*rating', re.I)})
        if review_elem:
            review_text = review_elem.get('aria-label', '')
            match = re.search(r'([\d,]+)', review_text)
            if match:
                try:
                    return int(match.group(1).replace(',', '').replace('.', ''))
                except ValueError:
                    pass

        # Method 2: Direct numeric text near rating
        review_spans = div.find_all('span', string=re.compile(r'^\d+(,\d+)*$'))
        for span in review_spans:
            text = span.get_text(strip=True)
            if text and (',' in text or len(text) >= 2):
                try:
                    return int(text.replace(',', '').replace('.', ''))
                except ValueError:
                    continue

        return 0

    def _extract_badges(self, div) -> List[str]:
        """Extract product badges (Best Seller, Amazon's Choice, etc.)"""
        badges = []
        seen_badges = set()

        badge_containers = div.find_all(['span', 'div'], class_=re.compile(r'badge|a-badge', re.I))
        for container in badge_containers:
            badge_text = container.get_text(separator=' ', strip=True)
            # Filter: meaningful length, not duplicate, not substring
            if badge_text and 5 < len(badge_text) < 100:
                if badge_text not in seen_badges and not any(badge_text in s or s in badge_text for s in seen_badges):
                    badges.append(badge_text)
                    seen_badges.add(badge_text)

        return badges

    def _extract_image(self, div) -> str:
        """Extract main product image URL"""
        img_elem = div.find('img', class_='s-image')
        return img_elem.get('src', '') if img_elem else ''

    def _extract_bsr(self, soup, html: str) -> Tuple[Optional[int], Optional[str]]:
        """
        Extract Best Sellers Rank with multi-language support

        Tries 4 methods:
        1. Product details table
        2. Product information section
        3. Detail bullets
        4. Regex patterns (EN, ES, DE, FR, IT)
        """
        bsr_rank = None
        bsr_category = None

        # Method 1: Detail bullets wrapper
        detail_bullets = soup.find('div', id='detailBulletsWrapper_feature_div')
        if detail_bullets:
            bsr_rank, bsr_category = self._extract_bsr_from_element(detail_bullets)
            if bsr_rank:
                return bsr_rank, bsr_category

        # Method 2: Product details section
        prod_info = soup.find('div', id='prodDetails')
        if prod_info:
            bsr_rank, bsr_category = self._extract_bsr_from_element(prod_info)
            if bsr_rank:
                return bsr_rank, bsr_category

        # Method 3: Detail bullets alternative
        detail_bullets_alt = soup.find('div', id='detail-bullets')
        if detail_bullets_alt:
            bsr_rank, bsr_category = self._extract_bsr_from_element(detail_bullets_alt)
            if bsr_rank:
                return bsr_rank, bsr_category

        # Method 4: Multi-language regex patterns
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
            # Italian
            r'Posizione nella classifica[:\s]*</span>\s*(\d+)\s+in\s+.*?>([^<]+)</a>',
            # Generic fallback
            r'#(\d+)\s+in\s+<a[^>]*>([^<]+)</a>'
        ]

        for pattern in bsr_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                try:
                    bsr_rank = int(match.group(1).replace(',', '').replace('.', ''))
                    bsr_category = match.group(2).strip() if len(match.groups()) > 1 else None
                    return bsr_rank, bsr_category
                except (ValueError, IndexError):
                    continue

        return None, None

    def _extract_bsr_from_element(self, element) -> Tuple[Optional[int], Optional[str]]:
        """Extract BSR rank and category from BeautifulSoup element"""
        bsr_text = element.find(string=re.compile(
            r'Best Sellers Rank|Clasificación|Bestseller-Rang|Classement|Posizione',
            re.I
        ))
        if bsr_text:
            parent = bsr_text.find_parent('li') or bsr_text.find_parent('tr')
            if parent:
                full_text = parent.get_text()
                rank_match = re.search(r'#?([\d,\.]+)', full_text)
                if rank_match:
                    try:
                        rank = int(rank_match.group(1).replace(',', '').replace('.', ''))
                        cat_match = re.search(r'(?:in|en)\s+([^(#\n]+)', full_text)
                        category = cat_match.group(1).strip() if cat_match else None
                        return rank, category
                    except ValueError:
                        pass
        return None, None

    def _extract_product_images(self, soup) -> List[str]:
        """Extract main product images (not color variants)"""
        images = []
        img_block = soup.find('div', id='altImages')

        if img_block:
            imgs = img_block.find_all('img')
            for img in imgs[:7]:  # Limit to 7 to avoid color variants
                img_src = img.get('src', '')
                if img_src and 'amazon' in img_src and 'icon' not in img_src.lower():
                    # Convert thumbnail to full size
                    img_src = re.sub(r'\._.*?_\.', '.', img_src)
                    clean_img = img_src.split('?')[0]
                    if clean_img and clean_img not in images:
                        images.append(clean_img)

        return images
