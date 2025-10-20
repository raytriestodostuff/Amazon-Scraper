"""
LAYER 1: HTTP Client & API Communication
- Handles all external API calls (ScraperAPI, Firecrawl)
- Manages request retries and rate limiting
- Builds proxy URLs and authentication
"""

import asyncio
import aiohttp
import logging
from urllib.parse import urlencode
from typing import Optional

logger = logging.getLogger(__name__)


class HTTPClient:
    """Handles all HTTP communication with external APIs"""

    def __init__(self, scraperapi_key: str, firecrawl_key: str, country_code: str, semaphore: asyncio.Semaphore):
        self.scraperapi_key = scraperapi_key
        self.firecrawl_key = firecrawl_key
        self.country_code = country_code
        self.semaphore = semaphore

    def build_scraperapi_url(self, amazon_url: str) -> str:
        """
        Build ScraperAPI proxy URL that wraps Amazon URL

        Args:
            amazon_url: Direct Amazon product/search URL

        Returns:
            ScraperAPI proxy URL with authentication, country routing, and English language
        """
        params = {
            'api_key': self.scraperapi_key,
            'url': amazon_url,
            'render': 'true',
            'country_code': self.country_code,
            'custom_headers': 'true'  # Enable custom headers to set language
        }

        # Add Accept-Language header to request English content
        # This will make Amazon return English BSR labels while using IT/DE proxy
        params['accept_language'] = 'en-US,en;q=0.9'

        return f"http://api.scraperapi.com/?{urlencode(params)}"

    async def fetch_with_firecrawl(self, url: str) -> Optional[str]:
        """
        Fetch HTML via Firecrawl scrape endpoint using ScraperAPI proxy

        Args:
            url: Amazon URL to scrape

        Returns:
            HTML content as string, or None if failed

        Flow:
            1. Wrap Amazon URL with ScraperAPI (for IP rotation)
            2. Send ScraperAPI URL to Firecrawl scrape endpoint
            3. Firecrawl fetches via ScraperAPI proxy
            4. Return raw HTML
        """
        if not self.firecrawl_key:
            logger.warning("Firecrawl API key not configured")
            return None

        # Wrap Amazon URL with ScraperAPI proxy
        scraperapi_url = self.build_scraperapi_url(url)

        firecrawl_url = "https://api.firecrawl.dev/v1/scrape"
        headers = {
            'Authorization': f'Bearer {self.firecrawl_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'url': scraperapi_url,
            'formats': ['html']  # Only fetch HTML (not markdown, not extract)
        }

        async with self.semaphore:  # Rate limiting
            for attempt in range(3):  # 3 retry attempts
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

                                # Check for suspiciously small HTML (likely error/empty response)
                                if len(html) < 1000:
                                    logger.warning(f"  ! Suspicious HTML size: {len(html)} chars - attempt {attempt + 1}/3")
                                    if attempt < 2:
                                        continue  # Retry
                                    else:
                                        logger.error(f"  ✗ Empty HTML after 3 attempts")
                                        return html  # Return anyway, parser will handle

                                logger.info(f"  + Fetched: {len(html)} chars")
                                return html
                            elif response.status == 429:
                                logger.warning(f"  ! Rate limit (429) - attempt {attempt + 1}/3")
                            else:
                                logger.warning(f"  ! HTTP {response.status} - attempt {attempt + 1}/3")

                except asyncio.TimeoutError:
                    logger.warning(f"  ! Timeout - attempt {attempt + 1}/3")
                except Exception as e:
                    logger.warning(f"  ! Error: {str(e)[:50]} - attempt {attempt + 1}/3")

                # Exponential backoff
                if attempt < 2:
                    wait_time = 2 ** attempt
                    logger.info(f"  ... Waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)

        logger.error(f"  ✗ Failed to fetch after 3 attempts")
        return None
