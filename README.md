# Amazon UK Scraper with ScraperAPI + Firecrawl

Simple, powerful scraper that:
- ✅ Uses **ScraperAPI** (renders JS, bypasses blocks)
- ✅ Uses **Firecrawl** (clean HTML/markdown)
- ✅ Extracts **ASINs** and **product images**
- ✅ Runs **multiple keywords in parallel**
- ✅ UK only (for now)
- ✅ **No hardcoded API keys** - all in config.json

## Quick Start

### 1. Install Dependency
```bash
pip install aiohttp
```

### 2. Edit Keywords
Edit `config.json` and add your keywords:
```json
{
  "keywords": [
    "wireless headphones",
    "protein powder",
    "gaming laptop"
  ]
}
```

### 3. Run
```bash
python scraper.py
```

## What It Does

1. **Fetches** search pages via ScraperAPI (UK, with JS rendering)
2. **Cleans** HTML via Firecrawl /scrape endpoint
3. **Extracts** ASINs and product images
4. **Outputs** two JSON files:
   - `uk_results_TIMESTAMP.json` - Full data
   - `uk_gpt_ready_TIMESTAMP.json` - Optimized for GPT-5 Nano

## Configuration

Edit `config.json`:

```json
{
  "api_keys": {
    "scraperapi": "YOUR_KEY_HERE",
    "firecrawl": "YOUR_KEY_HERE"
  },
  "settings": {
    "country": "uk",
    "max_concurrent": 10,
    "extract_images": true,
    "output_dir": "output"
  },
  "keywords": [
    "your keywords here"
  ]
}
```

**Note**: Copy `config.example.json` to `config.json` and add your API keys.

## Output

### uk_results_TIMESTAMP.json
```json
{
  "keyword": "wireless headphones",
  "country": "uk",
  "status": "success",
  "asins": ["B08N5WRWNW", "B09JQMJHXY", ...],
  "total_asins": 48,
  "images": ["https://m.media-amazon.com/images/I/...", ...],
  "total_images": 156,
  "scraperapi_html": "<html>...</html>",
  "firecrawl_markdown": "# Products\n..."
}
```

### uk_gpt_ready_TIMESTAMP.json
```json
{
  "keyword": "wireless headphones",
  "country": "uk",
  "asins": ["B08N5WRWNW", ...],
  "images": ["https://...", ...],
  "markdown": "# Products\n...",
  "html_snippet": "<div>..."
}
```

## Features

✅ **ScraperAPI + Firecrawl combo** - Best of both worlds
✅ **Image extraction** - All product images from search
✅ **ASIN extraction** - All organic product ASINs
✅ **Parallel scraping** - 10 keywords at once
✅ **UK focused** - amazon.co.uk with GB country code
✅ **Config-based** - No hardcoded keys
✅ **Retry logic** - 3 attempts with backoff
✅ **Clean output** - Ready for GPT-5 Nano

## Extracted Data

For each keyword:
- **ASINs**: List of all product ASINs found
- **Images**: All product image URLs (high-res)
- **HTML**: Full HTML from ScraperAPI
- **Markdown**: Clean markdown from Firecrawl
- **Metadata**: Firecrawl metadata

## Cost per Run

With 5 keywords (default config):
- ScraperAPI: 5 requests × $0.001 = **$0.005**
- Firecrawl: 5 requests × $0.002 = **$0.010**
- **Total**: ~$0.015

## Troubleshooting

### "ModuleNotFoundError: No module named 'aiohttp'"
```bash
pip install aiohttp
```

### "ScraperAPI error"
Check your usage at: https://www.scraperapi.com/dashboard

### "Firecrawl error"
Verify your API key at: https://firecrawl.dev/dashboard

### No images extracted
Set `"extract_images": true` in config.json

## Next Steps

1. **Edit keywords** in `config.json`
2. **Run**: `python scraper.py`
3. **Check output**: `ls output/`
4. **Feed to GPT-5 Nano** for product extraction

---

## Version 2 - Layered Architecture (Recommended)

**NEW**: Refactored into clean, maintainable layers for production use.

### What's New in V2

✅ **3-Layer Architecture** - Separated HTTP, parsing, and orchestration
✅ **Complete Product Data** - Title, price, rating, reviews, BSR, badges, images
✅ **Multi-Country Support** - UK, Spain, Germany, France, Italy
✅ **Exploratory Testing Framework** - Comprehensive test logs and findings
✅ **Better Debugging** - Clear separation of concerns per layer
✅ **90% BSR Extraction** - Multi-language pattern matching

### Quick Start V2

```bash
python layer3_orchestrator.py
```

### V2 Architecture

- **Layer 1** (`layer1_http_client.py`) - ScraperAPI + Firecrawl communication
- **Layer 2** (`layer2_parser.py`) - BeautifulSoup HTML parsing and data extraction
- **Layer 3** (`layer3_orchestrator.py`) - Workflow coordination and output

### Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Complete architecture guide with diagrams
- **[QUICK_START.md](QUICK_START.md)** - Quick reference for configuration
- **[exploratory_testing/](exploratory_testing/)** - Test logs, plans, and findings

### V2 Output Format

```json
{
  "keyword": "wireless headphones",
  "country": "es",
  "domain": "amazon.es",
  "currency": "EUR",
  "status": "success",
  "total_products": 10,
  "products": [
    {
      "asin": "B0D6YMGXBF",
      "title": "XIAOMI Redmi Buds 6 Active...",
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

### Performance

- **Execution Time**: 2-3 minutes for 10 products
- **BSR Extraction**: 90% success rate
- **Data Stability**: 96% consistency across runs
- **Concurrency**: 1 (prevents rate limits)

---

**Simple, clean, and ready to scale!** 🚀
