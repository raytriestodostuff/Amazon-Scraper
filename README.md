# Amazon Multi-Country Scraper

A layered scraper that extracts product data from Amazon search results across multiple countries.

## Features

**Multi-Market Support**
- Supports 5 Amazon markets: US, UK, Germany, Spain, Italy
- Automatic multi-language parsing (English, German, Spanish, Italian)
- Country-specific currency and domain handling
- Single-country or multi-country scraping modes

**Comprehensive Product Data Extraction**
- ASIN, title, price, currency, rating, review count
- Best Sellers Rank (BSR) with subcategory support
- Product badges (Best Seller, Amazon's Choice, etc.)
- Product images 
- Search position tracking per keyword
- Ignores inorganic search results

**ASIN Deduplication**
- Tracks products appearing across multiple keywords
- Marks duplicate products to avoid redundant API calls
- BSR always scraped fresh even for duplicates

**Parallel Processing**
- Configurable concurrency for product page enrichment
- Semaphore-based rate limiting
- Retry logic with exponential backoff

## Dependencies

**Python Version Required:** Python 3.7 or higher

Install all required packages:

```bash
pip install aiohttp beautifulsoup4 openai
```

**Required Packages:**
- `aiohttp` - Async HTTP client for making API requests to Firecrawl
- `beautifulsoup4` - HTML parsing library for extracting product data
- `openai` - OpenAI API client (only needed if using layer4_analyzer.py)

**No additional dependencies are needed** - all other modules used are part of Python's standard library:
- `asyncio`, `json`, `logging`, `re`, `urllib.parse`, `datetime`, `pathlib`

## Configuration

Create / Edit `config.json` with your API keys and settings:

```json
{
  "api_keys": {
    "scraperapi": "Scraper API here",
    "firecrawl": "Firecrawl API here",
    "openai": "OpenAi API here"
  },
  "settings": {
    "countries": ["us", "uk", "es", "de", "it"],
    "max_concurrent": 5,
    "max_products_to_scrape": 5,
    "output_dir": "output"
  },
  "keywords": [
    "berberine 1500mg",
    "berberina"
  ]
}

```

### Configuration Options

**API Keys:**
- `scraperapi` - Your ScraperAPI key (get from https://scraperapi.com)
- `firecrawl` - Your Firecrawl key (get from https://firecrawl.dev)

**Settings:**
- `countries` - Array of country codes for multi-country mode: `["uk", "us", "es", "de", "it"]`
- `country` - Single country code for single-country mode: `"uk"`
- `max_concurrent` - Concurrent product fetches per keyword 
- `max_products_to_scrape` - Products to scrape per keyword 
- `output_dir` - Output directory (default: "output")

**Keywords:**
- List of search terms to scrape (in English)

## How to Run

The scraper automatically detects whether to run in single-country or multi-country mode based on your config.

### Single Country Mode

Set `"country"` in config.json:

```json
{
  "settings": {
    "country": "uk",
    ...
  }
}
```

Run:
```bash
python layer3_orchestrator.py
```

### Multi-Country Mode

Set `"countries"` (plural) in config.json:

```json
{
  "settings": {
    "countries": ["uk", "us", "es", "de"],
    ...
  }
}
```

Run the same command:
```bash
python layer3_orchestrator.py
```

**Note**: Multi-country mode processes countries sequentially. Each country resets the ASIN deduplication cache.


## Expected Output

### File Structure

```
output/
├── uk/
│   ├── wireless_headphones_20251014_123456.json
│   ├── protein_powder_20251014_123456.json
│   └── all_keywords_20251014_123456.json
├── us/
│   └── ...
└── es/
    └── ...
```

### Output Format

Each keyword file contains:

```json
{
  "keyword": "wireless headphones",
  "country": "uk",
  "domain": "amazon.co.uk",
  "currency": "GBP",
  "status": "success",
  "total_products": 10,
  "products": [
    {
      "asin": "B08N5WRWNW",
      "search_position": 1,
      "title": "Sony WH-1000XM4 Wireless Headphones",
      "price": 279.0,
      "currency": "GBP",
      "rating": 4.7,
      "review_count": 45234,
      "bsr_rank": 3,
      "bsr_category": "Electronics",
      "badges": ["Amazon's Choice"],
      "url": "https://www.amazon.co.uk/dp/B08N5WRWNW",
      "images": ["url1", "url2", "url3", "url4", "url5", "url6"]
    }
  ]
}
```

### Duplicate Products

Products appearing in multiple keywords are marked with:

```json
{
  "asin": "B08N5WRWNW",
  "search_position": 3,
  "title": "[REPEATED - see 'wireless headphones']",
  "price": "[REPEATED]",
  "rating": "[REPEATED]",
  "review_count": "[REPEATED]",
  "bsr_rank": 3,
  "bsr_category": "Electronics",
  "badges": [],
  "images": "[REPEATED]",
  "is_duplicate": true,
  "first_seen_in": "wireless headphones"
}
```

**Note**: BSR is always scraped fresh for each keyword, even for duplicates.

## Architecture

The scraper uses a 3-layer architecture:

- **Layer 1** (`layer1_http_client.py`) - HTTP requests via Firecrawl + ScraperAPI
- **Layer 2** (`layer2_parser.py`) - HTML parsing with BeautifulSoup
- **Layer 3** (`layer3_orchestrator.py`) - Workflow coordination and output

## Troubleshooting

### Missing Dependencies
```bash
pip install aiohttp beautifulsoup4 openai
```

### API Errors
- Check ScraperAPI dashboard: https://scraperapi.com/dashboard
- Check Firecrawl dashboard: https://firecrawl.dev/dashboard
- Ensure enough credits are present for use!!!

### No Products Extracted
- Verify country code is valid: `["uk", "us", "es", "de", "it"]`
- Reduce `max_concurrent` if getting rate limit errors
---

**Ready to scrape!** 🚀
