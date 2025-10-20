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

    def parse_product_page(self, html: str) -> Tuple[Optional[int], Optional[str], List[Dict[str, any]], List[str]]:
        """
        Extract detailed data from individual product page

        Args:
            html: Product page HTML

        Returns:
            Tuple of (bsr_rank, bsr_category, bsr_subcategories, images_list)
            - bsr_rank: Primary BSR rank (first subcategory)
            - bsr_category: Primary BSR category (first subcategory)
            - bsr_subcategories: List of ALL subcategory dicts with rank and category
            - images_list: List of all product image URLs
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Extract BSR (Best Sellers Rank) - now returns primary + all subcategories
        bsr_rank, bsr_category, bsr_subcategories = self._extract_bsr(soup, html)

        # Extract product images
        images = self._extract_product_images(soup)

        return bsr_rank, bsr_category, bsr_subcategories, images

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
        """Extract product rating (out of 5) - handles both period and comma decimal separators"""
        rating_elem = div.find('span', class_='a-icon-alt')
        if rating_elem:
            rating_text = rating_elem.get_text()
            # Match ratings with either period or comma as decimal separator
            # Examples: "4.3 out of 5", "4,3 von 5 Sternen", "4.3 de 5 estrellas"
            match = re.search(r'([\d]+[.,][\d]+)', rating_text)
            if match:
                try:
                    # Replace comma with period for float conversion
                    rating_str = match.group(1).replace(',', '.')
                    return float(rating_str)
                except ValueError:
                    return None
        return None

    def _extract_review_count(self, div) -> int:
        """
        Extract number of reviews (multi-language)

        UK/US format: <a aria-label="12,581 ratings"><span>12,581</span></a>
        US alt format: <a aria-label="3,032 ratings"><span>(3K)</span></a>
        German format: <a aria-label="320 Bewertungen">(320)</a>
        """
        # Method 1: Look for US/UK aria-label with "ratings" (exact format: "X ratings")
        # Example: aria-label="3,032 ratings" (US specific - has full count in aria-label)
        # This is checked FIRST for US market products
        # Pattern must match ONLY "X ratings", NOT "X out of 5 stars, rating details"
        review_link = div.find('a', {'aria-label': re.compile(r'^[\d,\.]+\s+ratings?$', re.I)})
        if review_link:
            aria_text = review_link.get('aria-label', '')
            # Extract first number from aria-label
            match = re.search(r'([\d,\.]+)', aria_text)
            if match:
                try:
                    count_str = match.group(1).replace(',', '').replace('.', '')
                    count = int(count_str)
                    # Sanity check: review counts are typically between 1 and 1,000,000
                    if 1 <= count < 1000000:
                        return count
                except ValueError:
                    pass

        # Method 2: Look for <span> inside reviews link with class s-underline-text
        # This is the PRIMARY method for UK markets (actual number visible)
        reviews_block = div.find('div', {'data-cy': 'reviews-block'})
        if reviews_block:
            # Find the ratings link span
            rating_span = reviews_block.find('span', class_='s-underline-text')
            if rating_span:
                text = rating_span.get_text(strip=True)
                # Match numbers like: 12,581 or 1.234 or 320
                match = re.search(r'^([\d,\.]+)$', text)
                if match:
                    try:
                        count_str = match.group(1).replace(',', '').replace('.', '')
                        count = int(count_str)
                        # Sanity check: review counts are typically between 1 and 1,000,000
                        if 1 <= count < 1000000:
                            return count
                    except ValueError:
                        pass

        # Method 3: Look for German-style aria-label with "Bewertungen"
        # Example: aria-label="320 Bewertungen"
        review_link_de = div.find('a', {'aria-label': re.compile(r'\d+.*Bewertungen', re.I)})
        if review_link_de:
            aria_text = review_link_de.get('aria-label', '')
            # Extract first number from aria-label
            match = re.search(r'([\d,\.]+)', aria_text)
            if match:
                try:
                    count_str = match.group(1).replace(',', '').replace('.', '')
                    count = int(count_str)
                    if 1 <= count < 1000000:
                        return count
                except ValueError:
                    pass

        # Method 3: Look for text in parentheses like "(320)" near ratings
        # This appears in some German formats
        review_spans = div.find_all('span', class_=re.compile(r'puis-normal-weight-text|a-size-mini'))
        for span in review_spans:
            text = span.get_text(strip=True)
            # Match parentheses with number: (320), (1,234), (1.234)
            match = re.search(r'^\(([\d,\.]+)\)$', text)
            if match:
                try:
                    count_str = match.group(1).replace(',', '').replace('.', '')
                    count = int(count_str)
                    if 1 <= count < 1000000:
                        return count
                except ValueError:
                    continue

        # Method 4: Fallback - any number in parentheses in reviews block
        if reviews_block:
            text = reviews_block.get_text()
            match = re.search(r'\(([\d,\.]+)\)', text)
            if match:
                try:
                    count_str = match.group(1).replace(',', '').replace('.', '')
                    count = int(count_str)
                    if 1 <= count < 1000000:
                        return count
                except ValueError:
                    pass

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

    def _extract_bsr(self, soup, html: str) -> Tuple[Optional[int], Optional[str], List[Dict[str, any]]]:
        """
        Extract Best Sellers Rank with enhanced multi-language support

        Returns primary BSR (first subcategory) + list of ALL subcategories

        Tries 7 methods (enhanced for DE/IT):
        1-6. Multiple product details sections
        7. Enhanced regex patterns (EN, ES, DE, FR, IT)
        """
        bsr_rank = None
        bsr_category = None
        bsr_subcategories = []

        # Method 1: Detail bullets wrapper
        detail_bullets = soup.find('div', id='detailBulletsWrapper_feature_div')
        if detail_bullets:
            bsr_rank, bsr_category, bsr_subcategories = self._extract_bsr_from_element(detail_bullets)
            if bsr_rank:
                logger.debug(f"  BSR found via detailBulletsWrapper: {bsr_rank} ({len(bsr_subcategories)} subcategories)")
                return bsr_rank, bsr_category, bsr_subcategories

        # Method 2: Product details section
        prod_info = soup.find('div', id='prodDetails')
        if prod_info:
            bsr_rank, bsr_category, bsr_subcategories = self._extract_bsr_from_element(prod_info)
            if bsr_rank:
                logger.debug(f"  BSR found via prodDetails: {bsr_rank} ({len(bsr_subcategories)} subcategories)")
                return bsr_rank, bsr_category, bsr_subcategories

        # Method 3: Detail bullets alternative
        detail_bullets_alt = soup.find('div', id='detail-bullets')
        if detail_bullets_alt:
            bsr_rank, bsr_category, bsr_subcategories = self._extract_bsr_from_element(detail_bullets_alt)
            if bsr_rank:
                logger.debug(f"  BSR found via detail-bullets: {bsr_rank} ({len(bsr_subcategories)} subcategories)")
                return bsr_rank, bsr_category, bsr_subcategories

        # Method 4: Product details feature div (common on DE/IT)
        product_details_feature = soup.find('div', id='productDetails_feature_div')
        if product_details_feature:
            bsr_rank, bsr_category, bsr_subcategories = self._extract_bsr_from_element(product_details_feature)
            if bsr_rank:
                logger.debug(f"  BSR found via productDetails_feature_div: {bsr_rank} ({len(bsr_subcategories)} subcategories)")
                return bsr_rank, bsr_category, bsr_subcategories

        # Method 5: Detail bullets feature div (alternative on DE/IT)
        detail_bullets_feature = soup.find('div', id='detailBullets_feature_div')
        if detail_bullets_feature:
            bsr_rank, bsr_category, bsr_subcategories = self._extract_bsr_from_element(detail_bullets_feature)
            if bsr_rank:
                logger.debug(f"  BSR found via detailBullets_feature_div: {bsr_rank} ({len(bsr_subcategories)} subcategories)")
                return bsr_rank, bsr_category, bsr_subcategories

        # Method 6: Product facts section (sometimes used on EU markets)
        product_facts = soup.find('div', class_=re.compile(r'product-facts|prodDetTable', re.I))
        if product_facts:
            bsr_rank, bsr_category, bsr_subcategories = self._extract_bsr_from_element(product_facts)
            if bsr_rank:
                logger.debug(f"  BSR found via product-facts: {bsr_rank} ({len(bsr_subcategories)} subcategories)")
                return bsr_rank, bsr_category, bsr_subcategories

        # Method 7: Multi-language regex patterns (Enhanced for DE/IT)
        logger.debug("  BSR not found in HTML sections, trying regex patterns...")
        bsr_patterns = [
            # English
            r'Best Sellers Rank[:\s]*</span>\s*#?([\d,]+)\s+in\s+.*?>([^<]+)</a>',
            r'Best Sellers Rank[:\s]+#?([\d,]+)\s+in\s+([^(<\n]+)',
            r'Best Sellers Rank.*?#?([\d,]+).*?in\s+([^(<\n]+)',

            # Spanish
            r'Clasificación en los más vendidos[:\s]*</span>\s*n?º?\.?\s*([\d.]+)\s+en\s+.*?>([^<]+)</a>',
            r'Clasificación[:\s]*</span>\s*nº?\.?\s*([\d.]+)\s+en\s+.*?>([^<]+)</a>',
            r'nº?\.?\s*([\d.]+)\s+en\s+<a[^>]*>([^<]+)</a>',

            # German (Enhanced with multiple variations)
            r'Bestseller-Rang[:\s]*</span>\s*Nr\.\s*([\d.]+)\s+in\s+.*?>([^<]+)</a>',
            r'Bestseller-Rang[:\s]*Nr\.\s*([\d.]+)\s+in\s+([^(<\n]+)',
            r'Bestseller-Rang.*?Nr\.\s*([\d.]+).*?in\s+([^(<\n]+)',
            r'Nr\.\s*([\d.]+)\s+in\s+<a[^>]*>([^<]+)</a>',
            r'Bestseller[:\s-]*Rang[:\s]*#?([\d.]+)\s+in\s+([^(<\n]+)',

            # French
            r'Classement des meilleures ventes[:\s]*</span>\s*n?º?\.?\s*([\d.]+)\s+en\s+.*?>([^<]+)</a>',
            r'Classement[:\s]*n?º?\.?\s*([\d.]+)\s+en\s+([^(<\n]+)',

            # Italian (Enhanced with multiple variations including "n. " format)
            r'Posizione nella classifica Bestseller.*?n\.\s+([\d.,]+)',  # Full format: n. 146,922
            r'Posizione nella classifica[:\s]*</span>\s*n?\.?\s*([\d.,]+)\s+in\s+.*?>([^<]+)</a>',
            r'Posizione nella classifica[:\s]*n\.\s+([\d.,]+)\s+(?:in|nei)\s+([^(<\n]+)',  # n. with space
            r'Posizione.*?classifica.*?n\.\s+([\d.,]+).*?(?:in|nei)\s+([^(<\n]+)',  # Flexible
            r'n\.\s+([\d.,]+)\s+(?:in|nei)\s+<a[^>]*>([^<]+)</a>',  # n. with space in link
            r'Classifica[:\s]*#?([\d.,]+)\s+in\s+([^(<\n]+)',
            r'Posizione[:\s]+n\.\s+([\d.,]+)',  # Simplified Italian with space
            r'classifica[:\s]*n\.\s+([\d.,]+)\s+in',  # Lowercase with space

            # Generic fallbacks
            r'#([\d.,]+)\s+in\s+<a[^>]*>([^<]+)</a>',
            r'(?:Rank|Rang|Posizione)[:\s]*#?([\d.,]+)'
        ]

        for idx, pattern in enumerate(bsr_patterns, 1):
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                try:
                    bsr_rank = int(match.group(1).replace(',', '').replace('.', ''))
                    bsr_category = match.group(2).strip() if len(match.groups()) > 1 else None
                    bsr_subcategories = [{"rank": bsr_rank, "category": bsr_category}]  # Single category from regex
                    logger.debug(f"  BSR found via regex pattern #{idx}: {bsr_rank}")
                    return bsr_rank, bsr_category, bsr_subcategories
                except (ValueError, IndexError):
                    continue

        logger.debug("  BSR extraction failed - no patterns matched")
        return None, None, []

    def _extract_bsr_from_element(self, element) -> Tuple[Optional[int], Optional[str], List[Dict[str, any]]]:
        """
        Extract BSR rank and category from BeautifulSoup element (Enhanced for DE/IT)
        Returns primary BSR (first subcategory) + ALL subcategories

        Example BSR HTML structure (German):
        <ul>
          <li>Nr. 20.178 in Drogerie & Körperpflege (Siehe Top 100...)</li>  ← main category (skip)
          <li>Nr. 35 in Pränatale Vitamine</li>  ← first subcategory (primary!)
          <li>Nr. 5 in Another Category</li>  ← second subcategory
        </ul>

        → Returns: (35, "Pränatale Vitamine", [{rank:35, category:"Pränatale Vitamine"}, {rank:5, category:"Another Category"}])
        """
        # Search for BSR text in multiple languages
        bsr_text = element.find(string=re.compile(
            r'Best Sellers? Rank|Clasificación|Bestseller-?Rang|Classement|Posizione.*classifica.*Bestseller|Posizione.*classifica',
            re.I
        ))
        if bsr_text:
            # Find parent and look for <ul> containing all BSR entries
            parent = bsr_text.find_parent('li') or bsr_text.find_parent('tr') or bsr_text.find_parent('div')
            if parent:
                # Look for <ul> list containing individual BSR entries
                ul_list = parent.find('ul', class_=re.compile(r'a-unordered-list|a-nostyle'))

                if ul_list:
                    # Process each <li> separately
                    li_items = ul_list.find_all('li')
                    subcategories = []

                    # Detect format by checking if parent text contains main category rank
                    # US format: Main rank in parent text, <ul> contains ONLY subcategories
                    # EU/UK format: <ul> contains main category (index 0) + subcategories (index 1+)
                    parent_text = parent.get_text()
                    # Check if parent text BEFORE the <ul> contains the main rank
                    # We need to get text ONLY from parent, not from the ul children
                    parent_text_only = parent.get_text(strip=True)
                    ul_text = ul_list.get_text(strip=True) if ul_list else ''
                    parent_text_without_ul = parent_text_only.replace(ul_text, '').strip()

                    # US format has main rank in parent text (before the <ul>)
                    has_main_rank_in_parent = bool(re.search(r'(?:Best Sellers Rank|Bestseller-Rang)[:\s]*#?([\d,\.]+)\s+in\s+', parent_text_without_ul, re.I))

                    # Extract ALL subcategories
                    for idx, li in enumerate(li_items):
                        li_text = li.get_text()

                        # EU/UK format: ALWAYS skip first item (index 0) - it's the main category
                        # US format: All items in <ul> are subcategories (has_main_rank_in_parent=True)
                        if not has_main_rank_in_parent and idx == 0:
                            continue

                        # Extract rank and category
                        match = re.search(r'(?:Nr\.|n\.|#|nº|º)?\.?\s*([\d,\.]+)\s+(?:in|en|dans|nei)\s+(.+?)(?:\(|$)', li_text, re.I)

                        if match:
                            try:
                                rank_str = match.group(1).replace(',', '').replace('.', '')
                                rank_num = int(rank_str)

                                # Clean category
                                category_clean = match.group(2).strip()
                                category_clean = re.sub(r'\s+', ' ', category_clean)
                                category_clean = re.sub(r'(?:Siehe|See|Ver|Vedi) Top.*', '', category_clean, flags=re.I).strip()

                                # Skip if category is empty after cleaning
                                if not category_clean:
                                    continue

                                # Add to subcategories list
                                subcategories.append({"rank": rank_num, "category": category_clean})
                            except (ValueError, IndexError):
                                continue

                    # Return primary (first subcategory) + all subcategories
                    if subcategories:
                        return subcategories[0]["rank"], subcategories[0]["category"], subcategories

                else:
                    # Fallback: Old method for non-<ul> structure
                    full_text = parent.get_text()
                    rank_category_pattern = r'(?:Nr\.|n\.|#|nº|º)?\.?\s*([\d,\.]+)\s+(?:in|en|dans|nei)\s+([^(#\n]+?)(?:\(|$|#|\d)'
                    matches = re.findall(rank_category_pattern, full_text, re.I)

                    subcategories = []
                    for idx, (rank_str, category_str) in enumerate(matches):
                        # Skip main category (index 0)
                        if idx == 0:
                            continue

                        try:
                            rank_num = int(rank_str.replace(',', '').replace('.', ''))

                            category_clean = category_str.strip()
                            category_clean = re.sub(r'\s+', ' ', category_clean)
                            category_clean = re.sub(r'(?:Siehe|See|Ver) Top.*', '', category_clean, flags=re.I).strip()

                            if category_clean and len(category_clean) >= 3:
                                subcategories.append({"rank": rank_num, "category": category_clean})
                        except (ValueError, IndexError):
                            continue

                    # Return primary (first subcategory) + all subcategories
                    if subcategories:
                        return subcategories[0]["rank"], subcategories[0]["category"], subcategories

        return None, None, []

    def _extract_product_images(self, soup) -> List[str]:
        """
        Extract ALL main product images including those hidden behind +3 overlay

        IMPORTANT: Only extract images from the MAIN product image gallery,
        not from customer reviews, related products, or other sections
        """
        import json
        import html as html_lib

        images = []
        seen_image_ids = set()

        # Method 1: Look for main product image with data-a-dynamic-image in imageBlock or imgTagWrapperDiv
        # This is the MAIN product image that shows in the gallery
        main_image_containers = [
            soup.find('div', id='imageBlock'),
            soup.find('div', id='imgTagWrapperDiv'),
            soup.find('div', id='main-image-container'),
            soup.find('div', class_='imgTagWrapper')
        ]

        for container in main_image_containers:
            if container:
                # Find img with data-a-dynamic-image WITHIN this specific container only
                main_img = container.find('img', {'data-a-dynamic-image': True})
                if main_img:
                    try:
                        json_data = main_img.get('data-a-dynamic-image', '')
                        json_data = html_lib.unescape(json_data)
                        image_dict = json.loads(json_data)

                        # Extract all image URLs from main image JSON
                        for img_url in image_dict.keys():
                            match = re.search(r'/images/I/([A-Za-z0-9+_-]+)\.', img_url)
                            if match:
                                img_id = match.group(1)
                                if img_id not in seen_image_ids:
                                    clean_url = re.sub(r'\._.*?_\.', '.', img_url)
                                    clean_url = re.sub(r'_[A-Z]{2}\d+_\.', '.', clean_url)
                                    clean_url = clean_url.split('?')[0]

                                    if clean_url and 'amazon' in clean_url and 'icon' not in clean_url.lower():
                                        images.append(clean_url)
                                        seen_image_ids.add(img_id)
                    except (json.JSONDecodeError, ValueError, AttributeError):
                        pass
                    break  # Found main image, stop looking

        # Method 2: Extract from altImages thumbnail gallery (contains ALL product images)
        img_block = soup.find('div', id='altImages')
        if img_block:
            imgs = img_block.find_all('img')

            for img in imgs:
                img_src = img.get('src', '')

                # Skip icons and invalid images
                if not img_src or 'amazon' not in img_src or 'icon' in img_src.lower():
                    continue

                # Skip video thumbnails
                parent_li = img.find_parent('li')
                if parent_li:
                    parent_classes = ' '.join(parent_li.get('class', []))
                    # Skip color variant swatches and video thumbnails
                    if 'swatch' in parent_classes.lower() or 'variant' in parent_classes.lower() or 'video' in parent_classes.lower():
                        continue

                # Extract image ID to check if we already have it
                match = re.search(r'/images/I/([A-Za-z0-9+_-]+)\.', img_src)
                if match:
                    img_id = match.group(1)
                    if img_id in seen_image_ids:
                        continue
                    seen_image_ids.add(img_id)

                # Convert thumbnail to full size
                img_src = re.sub(r'\._.*?_\.', '.', img_src)
                clean_img = img_src.split('?')[0]

                # Add if unique and valid
                if clean_img and clean_img not in images and len(clean_img) > 10:
                    images.append(clean_img)

        return images
