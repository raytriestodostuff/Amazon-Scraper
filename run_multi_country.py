"""
Multi-Country Runner
Runs scraper for multiple countries specified in config.json
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from layer3_orchestrator import AmazonScraper

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_country(country: str, keywords: list, api_keys: dict, settings: dict):
    """Run scraper for a single country"""
    logger.info(f"\n{'='*80}")
    logger.info(f"COUNTRY: {country.upper()}")
    logger.info(f"{'='*80}\n")

    # Create temporary config for this country
    temp_config = {
        "api_keys": api_keys,
        "settings": {
            "country": country,
            "max_concurrent": settings.get("max_concurrent", 2),
            "max_products_to_scrape": settings.get("max_products_to_scrape", 10),
            "output_dir": settings.get("output_dir", "output")
        },
        "keywords": keywords
    }

    # Save temp config
    temp_file = f"config_{country}_temp.json"
    with open(temp_file, 'w') as f:
        json.dump(temp_config, f, indent=2)

    try:
        # Run scraper
        scraper = AmazonScraper(temp_file)
        results = await scraper.scrape_all()

        # Cleanup temp file
        Path(temp_file).unlink()

        return {
            'country': country,
            'status': 'success',
            'results': results
        }
    except Exception as e:
        logger.error(f"✗ {country.upper()} failed: {e}")
        Path(temp_file).unlink(missing_ok=True)
        return {
            'country': country,
            'status': 'failed',
            'error': str(e)
        }


async def main():
    """Run scraper for all countries in config"""
    start_time = datetime.now()

    # Load config
    with open('config.json') as f:
        config = json.load(f)

    countries = config['settings'].get('countries', ['uk'])
    keywords = config['keywords']
    api_keys = config['api_keys']
    settings = config['settings']

    logger.info(f"\n{'#'*80}")
    logger.info(f"# MULTI-COUNTRY SCRAPER")
    logger.info(f"{'#'*80}")
    logger.info(f"Countries: {', '.join(c.upper() for c in countries)}")
    logger.info(f"Keywords: {len(keywords)} ({', '.join(keywords[:3])}{'...' if len(keywords) > 3 else ''})")
    logger.info(f"Products per keyword: {settings.get('max_products_to_scrape', 10)}")
    logger.info(f"Concurrency: {settings.get('max_concurrent', 2)}")
    logger.info(f"{'#'*80}\n")

    # Run each country sequentially
    all_results = []
    for country in countries:
        result = await run_country(country, keywords, api_keys, settings)
        all_results.append(result)

    # Calculate totals
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    successful_countries = sum(1 for r in all_results if r['status'] == 'success')
    total_products = 0
    for r in all_results:
        if r['status'] == 'success':
            for result in r['results']:
                total_products += result.get('total_products', 0)

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info(f"MULTI-COUNTRY SCRAPE COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"Duration: {duration:.0f}s ({duration/60:.1f}m)")
    logger.info(f"Countries: {successful_countries}/{len(countries)} successful")
    logger.info(f"Total Products: {total_products}")
    logger.info(f"")

    for result in all_results:
        country = result['country'].upper()
        if result['status'] == 'success':
            products = sum(r.get('total_products', 0) for r in result['results'])
            keywords_success = sum(1 for r in result['results'] if r['status'] == 'success')
            logger.info(f"  {country}: ✓ {keywords_success}/{len(keywords)} keywords, {products} products")
        else:
            logger.info(f"  {country}: ✗ FAILED - {result.get('error', 'Unknown error')}")

    logger.info(f"\n{'='*80}\n")

    print(f"\nDone! Check output/ folders for results")


if __name__ == '__main__':
    asyncio.run(main())
