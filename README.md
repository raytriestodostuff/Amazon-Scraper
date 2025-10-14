# Amazon Multi-Country Scraper

A layered scraper that extracts product data from Amazon search results across multiple countries.

## Features

- ✅ **Multi-country support** - UK, US, Spain, Germany, France, Italy
- ✅ **Complete product data** - Title, price, rating, reviews, BSR, badges, images
- ✅ **ASIN deduplication** - Tracks duplicate products across keywords
- ✅ **Search position tracking** - Records product ranking per keyword
- ✅ **Multi-language parsing** - English, Spanish, German, French, Italian

## Dependencies

Install required packages:

```bash
pip install aiohttp beautifulsoup4
```

## Configuration

Edit `config.json` with your API keys and settings:

```json
{
  "api_keys": {
    "scraperapi": "YOUR_SCRAPERAPI_KEY",
    "firecrawl": "YOUR_FIRECRAWL_KEY"
  },
  "settings": {
    "countries": ["uk"],
    "max_concurrent": 2,
    "max_products_to_scrape": 10,
    "output_dir": "output"
  },
  "keywords": [
    "wireless headphones",
    "protein powder",
    "gaming laptop"
  ]
}
```

### Configuration Options

**API Keys:**
- `scraperapi` - Your ScraperAPI key (get from https://scraperapi.com)
- `firecrawl` - Your Firecrawl key (get from https://firecrawl.dev)

**Settings:**
- `countries` - Array of country codes for multi-country mode: `["uk", "us", "es", "de", "fr", "it"]`
- `country` - Single country code for single-country mode: `"uk"`
- `max_concurrent` - Concurrent product fetches per keyword (recommended: 2-5)
- `max_products_to_scrape` - Products to scrape per keyword (max: 10)
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

### Estimated Runtime

Based on testing with concurrency=5:
- **1 country** (8 keywords, 10 products each): ~5 minutes
- **2 countries**: ~10-11 minutes
- **4 countries**: ~20-22 minutes

Adjust `max_concurrent` to balance speed vs API rate limits.

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
pip install aiohttp beautifulsoup4
```

### API Errors
- Check ScraperAPI dashboard: https://scraperapi.com/dashboard
- Check Firecrawl dashboard: https://firecrawl.dev/dashboard

### No Products Extracted
- Verify country code is valid: `["uk", "us", "es", "de", "fr", "it"]`
- Check that keywords are in English
- Reduce `max_concurrent` to 1 if getting rate limit errors

### Missing BSR Data
- BSR extraction rates vary by country
- Expected rates: UK/US (95-100%), Spain (90%), Germany (55-85%)
- Some products don't have BSR rankings

## Documentation

- **[API_USAGE.md](API_USAGE.md)** - API architecture and request flow
- **[exploratory_testing/](exploratory_testing/)** - Test logs and findings

---

**Ready to scrape!** 🚀
