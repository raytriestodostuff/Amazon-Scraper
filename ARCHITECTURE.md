# Amazon Scraper V2 - Layered Architecture

## Overview

The scraper has been refactored into a clean, modular 3-layer architecture for better readability, maintainability, and debugging.

## Key Features

**Multi-Market Support**
- Supports 5 Amazon markets: US, UK, Germany, Spain, Italy
- Automatic multi-language parsing (English, German, Spanish, French, Italian)
- Country-specific currency and domain handling

**Comprehensive Product Data Extraction**
- ASIN, title, price, currency, rating, review count
- Best Sellers Rank (BSR) with subcategory support
- Product badges (Best Seller, Amazon's Choice, etc.)
- Multiple product images (5-8 per product)
- Search position tracking per keyword

**ASIN Deduplication**
- Tracks products appearing across multiple keywords
- Marks duplicate products to avoid redundant API calls
- BSR always scraped fresh even for duplicates

**Robust Extraction Logic**
- Multiple fallback methods for BSR extraction (7 methods)
- Multi-format review count extraction (handles abbreviated formats like "3K")
- Sponsored product filtering
- Image deduplication across color variants

**Parallel Processing**
- Configurable concurrency for product page enrichment
- Semaphore-based rate limiting
- Retry logic with exponential backoff

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



