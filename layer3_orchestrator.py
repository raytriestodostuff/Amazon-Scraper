"""
LAYER 3: Orchestrator & Main Scraper Logic
- Coordinates HTTP client and parser
- Manages workflow: search -> products -> enrichment
- Handles parallel processing and output generation
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from urllib.parse import quote_plus
from typing import List, Dict, Optional

from layer1_http_client import HTTPClient
from layer2_parser import ProductParser

logger = logging.getLogger(__name__)


class AmazonScraper:
    """Main orchestrator for Amazon product scraping"""

    # Country configurations
    COUNTRY_CONFIG = {
        'uk': {'domain': 'amazon.co.uk', 'currency': 'GBP', 'code': 'gb'},
        'es': {'domain': 'amazon.es', 'currency': 'EUR', 'code': 'es'},
        'de': {'domain': 'amazon.de', 'currency': 'EUR', 'code': 'de'},
        'fr': {'domain': 'amazon.fr', 'currency': 'EUR', 'code': 'fr'},
        'it': {'domain': 'amazon.it', 'currency': 'EUR', 'code': 'it'}
    }

    def __init__(self, config_path: str = "config.json"):
        """
        Initialize scraper from config file

        Args:
            config_path: Path to JSON configuration file
        """
        # Load configuration
        with open(config_path) as f:
            self.config = json.load(f)

        # Extract settings
        self.keywords = self.config['keywords']
        self.max_concurrent = self.config['settings']['max_concurrent']
        self.max_products = self.config['settings'].get('max_products_to_scrape', 10)

        # Country setup
        country = self.config['settings'].get('country', 'uk')
        country_info = self.COUNTRY_CONFIG.get(country, self.COUNTRY_CONFIG['uk'])
        self.country = country
        self.domain = country_info['domain']
        self.currency = country_info['currency']
        self.country_code = country_info['code']

        # Output directory (organized by country)
        base_output_dir = Path(self.config['settings']['output_dir'])
        self.output_dir = base_output_dir / country
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize layers
        semaphore = asyncio.Semaphore(self.max_concurrent)
        self.http_client = HTTPClient(
            scraperapi_key=self.config['api_keys']['scraperapi'],
            firecrawl_key=self.config['api_keys']['firecrawl'],
            country_code=self.country_code,
            semaphore=semaphore
        )
        self.parser = ProductParser(domain=self.domain, currency=self.currency)

        logger.info(f"✓ Initialized Amazon {country.upper()} Scraper")
        logger.info(f"  Domain: {self.domain}")
        logger.info(f"  Concurrency: {self.max_concurrent}")
        logger.info(f"  Output: {self.output_dir}")

    async def scrape_keyword(self, keyword: str) -> Dict:
        """
        Scrape products for a single keyword

        Args:
            keyword: Search keyword (in English)

        Returns:
            Dictionary with keyword results and metadata
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"KEYWORD: {keyword}")
        logger.info(f"{'='*70}")

        search_url = f"https://www.{self.domain}/s?k={quote_plus(keyword)}"

        try:
            # Step 1: Fetch search results page
            html = await self.http_client.fetch_with_firecrawl(search_url)
            if not html:
                raise Exception("Failed to fetch search page")

            # Step 2: Parse search results
            products = self.parser.parse_search_results(html)
            logger.info(f"  Extracted {len(products)} products from search")

            # Step 3: Scrape individual product pages (parallel)
            if products:
                logger.info(f"  Enriching product data (max: {self.max_products})...")
                product_tasks = [
                    self._enrich_product(product)
                    for product in products[:self.max_products]
                ]
                enriched_products = await asyncio.gather(*product_tasks)
                products = [p for p in enriched_products if p is not None]

            # Step 4: Build output
            result = {
                'keyword': keyword,
                'country': self.country,
                'domain': self.domain,
                'currency': self.currency,
                'search_url': search_url,
                'scrape_date': datetime.now().isoformat(),
                'status': 'success',
                'total_products': len(products),
                'products': products
            }

            logger.info(f"✓ SUCCESS: {len(products)} products")
            return result

        except Exception as e:
            logger.error(f"✗ FAILED: {e}")
            return {
                'keyword': keyword,
                'country': self.country,
                'search_url': search_url,
                'scrape_date': datetime.now().isoformat(),
                'status': 'failed',
                'error': str(e),
                'products': []
            }

    async def _enrich_product(self, product: Dict) -> Optional[Dict]:
        """
        Enrich product with data from individual product page

        Args:
            product: Basic product dict from search results

        Returns:
            Enriched product dict with BSR and images
        """
        if not product.get('url'):
            return product

        try:
            logger.info(f"    Enriching: {product['asin']}")

            # Fetch product page
            html = await self.http_client.fetch_with_firecrawl(product['url'])
            if not html:
                logger.warning(f"    ⚠ Failed to fetch {product['asin']}")
                # Return with main image only
                product['images'] = [product['main_image']] if product.get('main_image') else []
                product.pop('main_image', None)
                return product

            # Parse product page
            bsr_rank, bsr_category, images = self.parser.parse_product_page(html)

            # Update product with enriched data
            if bsr_rank:
                product['bsr_rank'] = bsr_rank
            if bsr_category:
                product['bsr_category'] = bsr_category

            # Use product page images (more complete)
            product['images'] = images if images else ([product['main_image']] if product.get('main_image') else [])
            product.pop('main_image', None)

            logger.info(f"    ✓ {product['asin']}: BSR={bsr_rank}, Images={len(product.get('images', []))}")
            return product

        except Exception as e:
            logger.error(f"    ✗ Error enriching {product.get('asin')}: {e}")
            # Return basic product on error
            product['images'] = [product['main_image']] if product.get('main_image') else []
            product.pop('main_image', None)
            return product

    async def scrape_all(self) -> List[Dict]:
        """
        Scrape all keywords from configuration

        Returns:
            List of results for all keywords
        """
        logger.info(f"\n{'*'*70}")
        logger.info(f"STARTING SCRAPE: {len(self.keywords)} keywords")
        logger.info(f"{'*'*70}\n")

        # Scrape all keywords in parallel
        tasks = [self.scrape_keyword(kw) for kw in self.keywords]
        results = await asyncio.gather(*tasks)

        # Save results
        self._save_results(results)

        # Summary
        successful = sum(1 for r in results if r['status'] == 'success')
        total_products = sum(r.get('total_products', 0) for r in results)

        logger.info(f"\n{'='*70}")
        logger.info(f"COMPLETE: {successful}/{len(results)} keywords | {total_products} products")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"{'='*70}\n")

        return results

    def _save_results(self, results: List[Dict]):
        """
        Save results to JSON files (organized by country)

        Saves:
        1. Individual keyword files: output/{country}/{keyword}_{timestamp}.json
        2. Consolidated file: output/{country}/all_keywords_{timestamp}.json
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

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
        logger.info(f"  Consolidated: {consolidated_file}")


def main():
    """Entry point for scraper"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Run scraper
    scraper = AmazonScraper("config.json")
    results = asyncio.run(scraper.scrape_all())

    print("\nDone! Check output/ folder")


if __name__ == '__main__':
    main()
