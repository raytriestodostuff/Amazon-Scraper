# Amazon Scraper V2 - Layered Architecture

## Overview

The scraper has been refactored into a clean, modular 3-layer architecture for better readability, maintainability, and debugging.

## Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│         LAYER 3: Orchestrator                   │
│    (Workflow coordination & output)             │
│    File: layer3_orchestrator.py                 │
│                                                  │
│  - Coordinates entire scraping workflow         │
│  - Manages parallel processing                  │
│  - Generates output files                       │
└────────────┬────────────────────────────────────┘
             │
             ├── Uses ──────────────────┐
             │                          │
┌────────────▼──────────────┐  ┌───────▼──────────────────┐
│   LAYER 1: HTTP Client    │  │   LAYER 2: Parser        │
│   (API communication)     │  │   (Data extraction)      │
│   File: layer1_http_client│  │   File: layer2_parser.py │
│                           │  │                          │
│  - ScraperAPI proxy URLs  │  │  - BeautifulSoup parsing │
│  - Firecrawl API calls    │  │  - Multi-language regex  │
│  - Rate limiting          │  │  - Data validation       │
│  - Retry logic            │  │  - Field extraction      │
└───────────────────────────┘  └──────────────────────────┘
```

## Layer Responsibilities

### Layer 1: HTTP Client (`layer1_http_client.py`)
**Purpose**: Handle all external API communication

**Responsibilities**:
- Build ScraperAPI proxy URLs with authentication
- Send requests to Firecrawl scrape endpoint
- Manage rate limiting via semaphore
- Implement retry logic with exponential backoff
- Handle HTTP errors and timeouts

**Key Classes**:
- `HTTPClient`: Main class for API communication

**Key Methods**:
- `build_scraperapi_url(amazon_url)`: Wrap Amazon URL with ScraperAPI proxy
- `fetch_with_firecrawl(url)`: Fetch HTML via Firecrawl using ScraperAPI

**Why separate?**:
- Isolates all network I/O logic
- Easy to swap API providers
- Centralized error handling
- Testable without live API calls

---

### Layer 2: Parser (`layer2_parser.py`)
**Purpose**: Extract structured data from HTML

**Responsibilities**:
- Parse HTML using BeautifulSoup
- Extract product fields (ASIN, title, price, rating, reviews, badges)
- Handle multi-language content (EN, ES, DE, FR, IT)
- Validate and clean extracted data
- Extract BSR with multiple fallback methods

**Key Classes**:
- `ProductParser`: Main parser for Amazon HTML

**Key Methods**:
- `parse_search_results(html)`: Extract products from search page
- `parse_product_page(html)`: Extract BSR and images from product page
- `_extract_bsr(soup, html)`: Multi-method BSR extraction
- `_extract_badges(div)`: Extract and deduplicate badges
- `_is_sponsored(div)`: Detect and filter sponsored products

**Why separate?**:
- Pure data transformation (no side effects)
- Easy to test with static HTML files
- Regex patterns organized by language
- Can be used independently of HTTP layer

---

### Layer 3: Orchestrator (`layer3_orchestrator.py`)
**Purpose**: Coordinate workflow and generate output

**Responsibilities**:
- Load configuration from JSON
- Coordinate HTTP client and parser
- Manage workflow: search → parse → enrich → save
- Handle parallel processing of keywords and products
- Generate organized output files (by country)
- Logging and progress tracking

**Key Classes**:
- `AmazonScraper`: Main orchestrator

**Key Methods**:
- `scrape_keyword(keyword)`: Complete workflow for one keyword
- `scrape_all()`: Scrape all keywords and save results
- `_enrich_product(product)`: Fetch and parse individual product page
- `_save_results(results)`: Save individual and consolidated JSON files

**Why separate?**:
- High-level business logic
- Easy to modify workflow
- Centralized configuration management
- Clear entry point (`main()`)

---

## Data Flow

```
1. User runs: python layer3_orchestrator.py
                    ↓
2. Orchestrator loads config.json
                    ↓
3. For each keyword:
   a. Orchestrator → HTTP Client: Fetch search page
   b. HTTP Client → Firecrawl API (via ScraperAPI proxy)
   c. Firecrawl → Returns HTML
   d. Orchestrator → Parser: Extract products from HTML
   e. Parser → Returns list of products
   f. For each product:
      i.  Orchestrator → HTTP Client: Fetch product page
      ii. Parser → Extract BSR and images
   g. Orchestrator → Save JSON files
                    ↓
4. Done! Output in output/{country}/ folder
```

## File Organization

```
amazon_scraper_v2/
├── layer1_http_client.py      # API communication
├── layer2_parser.py            # HTML parsing
├── layer3_orchestrator.py      # Main orchestrator (run this!)
├── scraper.py                  # Original monolithic version (backup)
├── config.json                 # Configuration
├── ARCHITECTURE.md             # This file
├── output/                     # Results (organized by country)
│   ├── uk/
│   ├── es/
│   ├── de/
│   └── ...
└── exploratory_testing/        # Test documentation
    ├── test_logs/
    ├── test_plans/
    └── findings/
```

## Running the Scraper

### Using New Layered Architecture (Recommended)
```bash
python layer3_orchestrator.py
```

### Using Original Monolithic Version
```bash
python scraper.py
```

## Benefits of Layered Architecture

### 1. **Readability**
- Each file has a single, clear purpose
- Functions are shorter and more focused
- Easy to understand data flow

### 2. **Maintainability**
- Changes to HTTP logic don't affect parsing
- Changes to parsing don't affect workflow
- Easy to locate bugs by layer

### 3. **Testability**
- Layer 1: Mock HTTP responses
- Layer 2: Test with static HTML files
- Layer 3: Test workflow with mocked layers

### 4. **Reusability**
- Parser can be used independently
- HTTP client can fetch any URL
- Easy to add new features per layer

### 5. **Debugging**
- Clear separation of concerns
- Easy to add logging per layer
- Can test layers independently

## Adding New Features

### Example: Add new data field
1. **Layer 2** (`layer2_parser.py`): Add extraction method
2. **Layer 3** (`layer3_orchestrator.py`): No changes needed
3. **Layer 1** (`layer1_http_client.py`): No changes needed

### Example: Switch API provider
1. **Layer 1** (`layer1_http_client.py`): Update HTTP methods
2. **Layer 2** (`layer2_parser.py`): No changes needed
3. **Layer 3** (`layer3_orchestrator.py`): No changes needed

### Example: Change output format
1. **Layer 3** (`layer3_orchestrator.py`): Update `_save_results()`
2. **Layer 1** (`layer1_http_client.py`): No changes needed
3. **Layer 2** (`layer2_parser.py`): No changes needed

## Multi-Language Support

The parser handles 5 languages automatically:
- **English** (UK): amazon.co.uk
- **Spanish** (Spain): amazon.es
- **German** (Germany): amazon.de
- **French** (France): amazon.fr
- **Italian** (Italy): amazon.it

Language detection is automatic based on HTML content. No manual translation needed.

## Configuration

Edit `config.json` to customize:
- **country**: 'uk', 'es', 'de', 'fr', or 'it'
- **keywords**: List of search terms (always in English)
- **max_concurrent**: Concurrency limit (1-3 recommended)
- **max_products_to_scrape**: Products per keyword (default 10)

## Troubleshooting

### Issue: Rate limit errors (429)
**Solution**: Reduce `max_concurrent` in config.json to 1

### Issue: Missing BSR data
**Layer 2**: Add more regex patterns to `_extract_bsr()`

### Issue: API timeout
**Layer 1**: Increase timeout in `fetch_with_firecrawl()`

### Issue: Wrong data extracted
**Layer 2**: Debug with `logger.debug()` in parser methods
