# Quick Start Guide - Amazon Scraper V2

## Running the Scraper

### Using Layered Architecture (Recommended)
```bash
python layer3_orchestrator.py
```

### Using Original Monolithic Version
```bash
python scraper.py
```

Both versions produce identical output. The layered version is recommended for better code organization and debugging.

## Configuration

Edit `config.json`:

```json
{
  "api_keys": {
    "scraperapi": "your_key_here",
    "firecrawl": "your_key_here"
  },
  "settings": {
    "country": "es",           // uk, es, de, fr, it
    "max_concurrent": 1,       // 1-3 recommended
    "max_products_to_scrape": 10,
    "output_dir": "output"
  },
  "keywords": [
    "wireless headphones",
    "laptop stand"
  ]
}
```

## Project Structure

```
amazon_scraper_v2/
├── layer1_http_client.py      # API communication layer
├── layer2_parser.py            # HTML parsing layer
├── layer3_orchestrator.py      # Main orchestrator (RUN THIS!)
├── scraper.py                  # Original version (backup)
├── config.json                 # Configuration
├── ARCHITECTURE.md             # Architecture documentation
├── QUICK_START.md              # This file
├── output/                     # Results organized by country
│   ├── uk/
│   ├── es/
│   └── ...
└── exploratory_testing/        # Test documentation
    ├── test_logs/              # Test execution logs
    ├── test_plans/             # Test plans
    └── findings/               # Issues and observations
```

## Output Format

### Individual Keyword Files
`output/{country}/{keyword}_{timestamp}.json`

Example: `output/es/wireless_headphones_20251014_125344.json`

### Consolidated Files
`output/{country}/all_keywords_{timestamp}.json`

Contains all keywords in one file.

### Data Structure
```json
{
  "keyword": "wireless headphones",
  "country": "es",
  "domain": "amazon.es",
  "currency": "EUR",
  "search_url": "https://www.amazon.es/s?k=wireless+headphones",
  "scrape_date": "2025-10-14T12:53:44.987080",
  "status": "success",
  "total_products": 10,
  "products": [
    {
      "asin": "B0D6YMGXBF",
      "title": "Product title in local language",
      "price": 14.99,
      "currency": "EUR",
      "rating": 4.0,
      "review_count": 99,
      "badges": ["Amazon's Choice"],
      "url": "https://www.amazon.es/dp/B0D6YMGXBF",
      "bsr_rank": 1,
      "bsr_category": "Headphones & Earphones",
      "images": ["url1", "url2", ...]
    }
  ]
}
```

## Supported Countries

| Code | Country | Domain | Currency |
|------|---------|--------|----------|
| uk | United Kingdom | amazon.co.uk | GBP |
| es | Spain | amazon.es | EUR |
| de | Germany | amazon.de | EUR |
| fr | France | amazon.fr | EUR |
| it | Italy | amazon.it | EUR |

## Common Issues

### Rate Limit Errors (429)
**Solution**: Reduce `max_concurrent` to 1 in config.json

### Missing BSR Data
**Cause**: Some products don't have BSR on their pages
**Solution**: Normal behavior, BSR will be `null` for these products

### Timeout Errors (408)
**Solution**: Automatic retry is built-in, usually succeeds on 2nd attempt

### Unicode Errors on Windows
**Solution**: Already fixed in layered version

## Testing

### Test Logs
Location: `exploratory_testing/test_logs/`

Latest test: `20251014_layered_architecture_test.md`

### Test Plans
Location: `exploratory_testing/test_plans/`

Multi-country plan: `multi_country_test_plan.md`

### Findings
Location: `exploratory_testing/findings/`

Architecture benefits: `layered_architecture_benefits.md`

## Performance Benchmarks

- **Products per keyword**: 10
- **Time per product**: ~16 seconds
- **Total time (1 keyword)**: ~2-3 minutes
- **Success rate**: >90%
- **Concurrency**: 1 (prevents rate limits)

## Debugging by Layer

### Layer 1 Issues (HTTP/API)
**File**: `layer1_http_client.py`
**Common Issues**: Timeouts, rate limits, API errors
**Debug**: Check logs for HTTP status codes

### Layer 2 Issues (Parsing)
**File**: `layer2_parser.py`
**Common Issues**: Missing fields, wrong data extraction
**Debug**: Test with static HTML files

### Layer 3 Issues (Workflow)
**File**: `layer3_orchestrator.py`
**Common Issues**: Output format, file organization
**Debug**: Check output directory and JSON structure

## Advanced Usage

### Running Single Layer Tests

**Test Parser Only** (no API calls):
```python
from layer2_parser import ProductParser

parser = ProductParser("amazon.es", "EUR")
html = open("test.html").read()
products = parser.parse_search_results(html)
```

**Test HTTP Client Only**:
```python
from layer1_http_client import HTTPClient
import asyncio

client = HTTPClient(scraperapi_key, firecrawl_key, "es", semaphore)
html = await client.fetch_with_firecrawl("https://amazon.es/...")
```

### Modifying Workflow

Edit `layer3_orchestrator.py`:
- Change output format in `_save_results()`
- Modify parallel processing logic
- Add new data sources

### Adding New Fields

Edit `layer2_parser.py`:
- Add extraction method (e.g., `_extract_availability()`)
- Call from `parse_search_results()` or `parse_product_page()`
- No changes needed in other layers

## Documentation

- **Architecture**: See `ARCHITECTURE.md` for detailed layer design
- **Tests**: See `exploratory_testing/` for test logs and findings
- **Code Comments**: All layers have detailed inline documentation

## Support

For issues or questions:
1. Check `exploratory_testing/findings/` for known issues
2. Review test logs in `exploratory_testing/test_logs/`
3. Read architecture documentation in `ARCHITECTURE.md`
