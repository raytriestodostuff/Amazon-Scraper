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
from layer4_analyzer import AIAnalyzer

logger = logging.getLogger(__name__)


class AmazonScraper:
    """Main orchestrator for Amazon product scraping"""

    # Country configurations
    COUNTRY_CONFIG = {
        'uk': {'domain': 'amazon.co.uk', 'currency': 'GBP', 'code': 'gb'},
        'us': {'domain': 'amazon.com', 'currency': 'USD', 'code': 'us'},
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

        # ASIN cache for deduplication within a single run
        self.asin_cache = {}  # {asin: {full_product_data, first_keyword}}

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
                    self._enrich_product(product, keyword)
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

    async def _enrich_product(self, product: Dict, current_keyword: str) -> Optional[Dict]:
        """
        Enrich product with data from individual product page
        For duplicates: Still fetches BSR but uses cached data for other fields

        Args:
            product: Basic product dict from search results
            current_keyword: The keyword being processed

        Returns:
            Enriched product dict with BSR and images
        """
        if not product.get('url'):
            return product

        asin = product.get('asin')

        # Check if we've already scraped this ASIN in a previous keyword
        if asin in self.asin_cache:
            cached_data = self.asin_cache[asin]
            logger.info(f"    ⟳ {asin}: DUPLICATE - fetching BSR (first seen in '{cached_data['first_keyword']}')")

            try:
                # BSR Retry Logic for duplicates: Try up to 3 times to get BSR
                max_bsr_retries = 3
                bsr_rank = None
                bsr_category = None

                for attempt in range(1, max_bsr_retries + 1):
                    # Still fetch product page to get BSR (which should be scraped for every keyword)
                    html = await self.http_client.fetch_with_firecrawl(product['url'])
                    if not html:
                        logger.warning(f"    ⚠ Failed to fetch BSR for {asin} (attempt {attempt}/{max_bsr_retries})")
                        if attempt < max_bsr_retries:
                            await asyncio.sleep(2)
                            continue
                    else:
                        # Parse product page for BSR only
                        bsr_rank, bsr_category, bsr_subcategories, _ = self.parser.parse_product_page(html)

                    # Check if BSR was extracted
                    if bsr_rank:
                        logger.info(f"    ✓ {asin}: BSR={bsr_rank} (duplicate, attempt {attempt})")
                        break
                    else:
                        logger.warning(f"    ⚠ No BSR for duplicate {asin} (attempt {attempt}/{max_bsr_retries}) - retrying...")
                        if attempt < max_bsr_retries:
                            await asyncio.sleep(2)
                        else:
                            logger.warning(f"    ⚠ {asin}: BSR not found after {max_bsr_retries} attempts (duplicate)")
                            bsr_category = '[REPEATED]'

                # Return product with repeated markers for non-variable data
                return {
                    'asin': asin,
                    'url': product.get('url'),
                    'search_position': product.get('search_position'),
                    'title': f"[REPEATED - see '{cached_data['first_keyword']}']",
                    'price': '[REPEATED]',
                    'currency': '[REPEATED]',
                    'rating': '[REPEATED]',
                    'review_count': '[REPEATED]',
                    'bsr_subcategories': bsr_subcategories if bsr_subcategories else [],  # Always scraped fresh
                    'badges': product.get('badges', []),  # Varies per keyword
                    'images': '[REPEATED]',
                    'is_duplicate': True,
                    'first_seen_in': cached_data['first_keyword']
                }

            except Exception as e:
                logger.error(f"    ✗ Error fetching BSR for duplicate {asin}: {e}")
                return {
                    'asin': asin,
                    'url': product.get('url'),
                    'search_position': product.get('search_position'),
                    'title': f"[REPEATED - see '{cached_data['first_keyword']}']",
                    'price': '[REPEATED]',
                    'currency': '[REPEATED]',
                    'rating': '[REPEATED]',
                    'review_count': '[REPEATED]',
                    'bsr_subcategories': [],
                    'badges': product.get('badges', []),
                    'images': '[REPEATED]',
                    'is_duplicate': True,
                    'first_seen_in': cached_data['first_keyword']
                }

        try:
            logger.info(f"    Enriching: {asin}")

            # BSR Retry Logic: Try up to 3 times to get BSR
            max_bsr_retries = 3
            bsr_rank = None
            bsr_category = None
            bsr_subcategories = []
            images = []

            for attempt in range(1, max_bsr_retries + 1):
                # Fetch product page
                html = await self.http_client.fetch_with_firecrawl(product['url'])
                if not html:
                    logger.warning(f"    ⚠ Fetch failed for {asin} (attempt {attempt}/{max_bsr_retries})")
                    if attempt < max_bsr_retries:
                        await asyncio.sleep(2)  # Wait before retry
                        continue
                    else:
                        # Return with main image only after all retries fail
                        product['images'] = [product['main_image']] if product.get('main_image') else []
                        product.pop('main_image', None)
                        return product

                # Parse product page
                bsr_rank, bsr_category, bsr_subcategories, images = self.parser.parse_product_page(html)

                # Check if BSR was extracted
                if bsr_rank:
                    logger.info(f"    ✓ {asin}: BSR={bsr_rank}, Images={len(images)} (attempt {attempt})")
                    break  # Success! Exit retry loop
                else:
                    logger.warning(f"    ⚠ No BSR found for {asin} (attempt {attempt}/{max_bsr_retries}) - retrying...")
                    if attempt < max_bsr_retries:
                        await asyncio.sleep(2)  # Wait before retry
                    else:
                        logger.warning(f"    ⚠ {asin}: BSR not found after {max_bsr_retries} attempts")

            # Update product with enriched data (only bsr_subcategories, no redundant fields)
            if bsr_subcategories:
                product['bsr_subcategories'] = bsr_subcategories

            # Use product page images (more complete)
            product['images'] = images if images else ([product['main_image']] if product.get('main_image') else [])
            product.pop('main_image', None)

            # Cache this ASIN for future keyword lookups
            self.asin_cache[asin] = {
                'first_keyword': current_keyword,
                'product_data': product.copy()
            }

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
        Keywords are processed sequentially to enable ASIN deduplication

        Returns:
            List of results for all keywords
        """
        logger.info(f"\n{'*'*70}")
        logger.info(f"STARTING SCRAPE: {len(self.keywords)} keywords")
        logger.info(f"ASIN Deduplication: ENABLED (sequential processing)")
        logger.info(f"{'*'*70}\n")

        # Scrape keywords sequentially to build ASIN cache
        results = []
        for keyword in self.keywords:
            result = await self.scrape_keyword(keyword)
            results.append(result)

        # Save results
        self._save_results(results)

        # Summary with deduplication stats
        successful = sum(1 for r in results if r['status'] == 'success')
        total_products = sum(r.get('total_products', 0) for r in results)
        duplicate_count = sum(
            1 for r in results if r['status'] == 'success'
            for p in r.get('products', [])
            if p.get('is_duplicate', False)
        )

        logger.info(f"\n{'='*70}")
        logger.info(f"COMPLETE: {successful}/{len(results)} keywords | {total_products} products")
        logger.info(f"Unique ASINs: {len(self.asin_cache)}")
        logger.info(f"Duplicate ASINs: {duplicate_count} (BSR still scraped per keyword)")
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


async def run_multi_country(config_path: str = "config.json"):
    """
    Run scraper for multiple countries if 'countries' is specified in config.
    Falls back to single country mode if 'country' is specified instead.

    Args:
        config_path: Path to configuration file

    Returns:
        Dictionary with results per country
    """
    # Load config to check if multi-country
    with open(config_path) as f:
        config = json.load(f)

    # Check for multi-country vs single-country config
    countries = config['settings'].get('countries')
    single_country = config['settings'].get('country')

    if countries and isinstance(countries, list):
        # Multi-country mode
        logger.info(f"\n{'#'*80}")
        logger.info(f"# MULTI-COUNTRY MODE: {len(countries)} countries")
        logger.info(f"{'#'*80}")
        logger.info(f"Countries: {', '.join(c.upper() for c in countries)}")
        logger.info(f"Keywords: {len(config['keywords'])}")
        logger.info(f"Products per keyword: {config['settings'].get('max_products_to_scrape', 10)}")
        logger.info(f"Concurrency: {config['settings'].get('max_concurrent', 2)}")
        logger.info(f"{'#'*80}\n")

        all_results = {}

        for country in countries:
            logger.info(f"\n{'='*80}")
            logger.info(f"COUNTRY: {country.upper()}")
            logger.info(f"{'='*80}\n")

            # Create temporary single-country config
            temp_config = config.copy()
            temp_config['settings'] = config['settings'].copy()
            temp_config['settings']['country'] = country
            temp_config['settings'].pop('countries', None)  # Remove multi-country key

            # Save temp config
            temp_file = f"config_{country}_temp.json"
            with open(temp_file, 'w') as f:
                json.dump(temp_config, f, indent=2)

            try:
                # Run scraper for this country
                scraper = AmazonScraper(temp_file)
                results = await scraper.scrape_all()
                all_results[country] = {
                    'status': 'success',
                    'results': results
                }

                # Cleanup temp file
                Path(temp_file).unlink()

            except Exception as e:
                logger.error(f"✗ {country.upper()} failed: {e}")
                all_results[country] = {
                    'status': 'failed',
                    'error': str(e)
                }
                Path(temp_file).unlink(missing_ok=True)

        # Summary
        logger.info(f"\n{'='*80}")
        logger.info(f"MULTI-COUNTRY SCRAPE COMPLETE")
        logger.info(f"{'='*80}")

        successful_countries = sum(1 for r in all_results.values() if r['status'] == 'success')
        logger.info(f"Countries: {successful_countries}/{len(countries)} successful\n")

        for country, result in all_results.items():
            if result['status'] == 'success':
                products = sum(r.get('total_products', 0) for r in result['results'])
                keywords_success = sum(1 for r in result['results'] if r['status'] == 'success')
                logger.info(f"  {country.upper()}: ✓ {keywords_success}/{len(config['keywords'])} keywords, {products} products")
            else:
                logger.info(f"  {country.upper()}: ✗ FAILED - {result.get('error', 'Unknown error')}")

        logger.info(f"\n{'='*80}\n")

        # AI analysis disabled for now
        # Uncomment to re-enable GPT-5-nano analysis
        """
        # Run AI analysis on all successful country results
        try:
            openai_key = config['api_keys'].get('openai')
            if openai_key and openai_key != 'YOUR_OPENAI_API_KEY_HERE':
                logger.info(f"\n{'#'*80}")
                logger.info(f"# LAYER 4: AI ANALYSIS (GPT-5-nano)")
                logger.info(f"{'#'*80}\n")

                analyzer = AIAnalyzer(openai_key)
                successful_countries = [c for c, r in all_results.items() if r['status'] == 'success']

                if successful_countries:
                    output_dir = Path(config['settings']['output_dir'])
                    report_path = analyzer.generate_multi_country_report(output_dir, successful_countries)
                    logger.info(f"✓ AI Analysis Report: {report_path}\n")
                else:
                    logger.warning("No successful country results to analyze\n")
            else:
                logger.info("\nℹ Skipping AI analysis (OpenAI API key not configured)\n")
        except Exception as e:
            logger.error(f"\n✗ AI Analysis failed: {e}\n")
        """

        return all_results

    else:
        # Single country mode (backward compatibility)
        logger.info(f"\n{'*'*80}")
        logger.info(f"SINGLE COUNTRY MODE")
        logger.info(f"{'*'*80}\n")

        scraper = AmazonScraper(config_path)
        results = await scraper.scrape_all()

        return {scraper.country: {'status': 'success', 'results': results}}


def main():
    """Entry point for scraper"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Run scraper (supports both single and multi-country)
    results = asyncio.run(run_multi_country("config.json"))

    print("\nDone! Check output/ folder")


if __name__ == '__main__':
    main()
