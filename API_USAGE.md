# API Usage Documentation

## Overview

The scraper uses **two APIs working together**:
1. **ScraperAPI** - Proxy service for IP rotation and bypassing blocks
2. **Firecrawl** - HTML fetching service

## Architecture Flow

```
Your Scraper
    ↓
Firecrawl API (we call this directly)
    ↓
ScraperAPI Proxy (Firecrawl routes through this)
    ↓
Amazon Website
```

**Key Point**: We only make direct calls to **Firecrawl**. Firecrawl then routes through ScraperAPI to reach Amazon.

## API Calls Made

### Direct Calls (What We Pay For)

#### 1. Firecrawl API Calls

**Endpoint**: `https://api.firecrawl.dev/v1/scrape`

**Method**: POST

**Headers**:
```json
{
  "Authorization": "Bearer YOUR_FIRECRAWL_KEY",
  "Content-Type": "application/json"
}
```

**Payload**:
```json
{
  "url": "http://api.scraperapi.com/?api_key=YOUR_KEY&url=https://amazon.co.uk/...",
  "formats": ["html"]
}
```

**What It Does**:
- Firecrawl receives our request
- Firecrawl fetches the ScraperAPI URL we provide
- ScraperAPI then fetches Amazon
- Firecrawl returns clean HTML to us

**Response**:
```json
{
  "data": {
    "html": "<html>...</html>"
  }
}
```

### Indirect Calls (Included in Firecrawl)

#### 2. ScraperAPI Proxy (Called by Firecrawl)

**URL Format**:
```
http://api.scraperapi.com/?api_key=YOUR_KEY&url=AMAZON_URL&render=true&country_code=gb
```

**Parameters**:
- `api_key`: Your ScraperAPI authentication
- `url`: The Amazon URL to fetch (e.g., `https://amazon.co.uk/s?k=berberine`)
- `render`: `true` (enables JavaScript rendering)
- `country_code`: `gb` (UK), `es` (Spain), `de` (Germany), etc.

**What It Does**:
- Routes request through residential IP in target country
- Renders JavaScript (loads dynamic content)
- Bypasses Amazon anti-bot protection
- Returns raw HTML to Firecrawl

## API Call Count Per Run

### UK Test Example (8 keywords, 10 products each)

```
Total Firecrawl Calls: 88
├── Search pages: 8 calls (1 per keyword)
└── Product pages: 80 calls (10 per keyword × 8 keywords)

Total ScraperAPI Calls: 88
├── Search pages: 8 calls (via Firecrawl)
└── Product pages: 80 calls (via Firecrawl)
```

**Formula**: `(Number of Keywords) + (Number of Keywords × Products per Keyword)`

**For 8 keywords with 10 products each**:
- 8 search page calls
- 8 × 10 = 80 product page calls
- **Total: 88 API calls to both Firecrawl and ScraperAPI**

### Spain Test Example (1 keyword, 10 products)

```
Total Firecrawl Calls: 11
├── Search page: 1 call
└── Product pages: 10 calls

Total ScraperAPI Calls: 11
├── Search page: 1 call (via Firecrawl)
└── Product pages: 10 calls (via Firecrawl)
```

## Cost Breakdown

### Per API Call

| API | Cost per Call | Notes |
|-----|---------------|-------|
| Firecrawl | ~$0.002 | Scrape endpoint pricing |
| ScraperAPI | ~$0.001 | JS rendering enabled |
| **Combined** | **~$0.003** | Per page fetched |

**Note**: ScraperAPI is "free" in our architecture because Firecrawl calls it, not us directly.

### Per Test Run

#### UK Test (8 keywords, 80 products)
```
Firecrawl: 88 calls × $0.002 = $0.176
ScraperAPI: 88 calls × $0.001 = $0.088
Total Cost: ~$0.26
```

#### Spain Test (1 keyword, 10 products)
```
Firecrawl: 11 calls × $0.002 = $0.022
ScraperAPI: 11 calls × $0.001 = $0.011
Total Cost: ~$0.03
```

### Monthly Estimates

**Scenario 1**: Daily scraping of 8 keywords
```
Daily: 88 calls × $0.003 = $0.26
Monthly: $0.26 × 30 = $7.80
```

**Scenario 2**: Weekly scraping of 20 keywords
```
Per Run: 220 calls × $0.003 = $0.66
Weekly: $0.66 × 1 = $0.66
Monthly: $0.66 × 4 = $2.64
```

**Scenario 3**: Daily scraping of 50 keywords (high volume)
```
Daily: 550 calls × $0.003 = $1.65
Monthly: $1.65 × 30 = $49.50
```

## API Parameters Explained

### ScraperAPI Parameters (Set by Us)

```python
params = {
    'api_key': 'YOUR_SCRAPERAPI_KEY',
    'url': 'https://www.amazon.co.uk/s?k=berberine+1500mg',
    'render': 'true',
    'country_code': 'gb'
}
```

#### `render: true`
- **Purpose**: Enable JavaScript rendering
- **Why**: Amazon loads product data dynamically with JavaScript
- **Impact**: More expensive but necessary for complete data
- **Without it**: Missing prices, reviews, BSR, images

#### `country_code: gb` (or `es`, `de`, `fr`, `it`)
- **Purpose**: Route through residential IP in target country
- **Why**: Amazon shows different content per country
- **Result**: See prices in local currency, local BSR rankings, local language
- **Without it**: May get redirected or see US content

### Firecrawl Parameters (Set by Us)

```python
payload = {
    'url': scraperapi_url,
    'formats': ['html']
}
```

#### `formats: ['html']`
- **Purpose**: Return raw HTML only
- **Alternatives**: `markdown`, `extract` (we don't use these)
- **Why HTML**: We parse with BeautifulSoup for full control
- **Cost**: Cheapest option (scrape endpoint)

## Request Flow Example

### Step-by-Step: Fetching a Product Page

**1. Our Code Calls Firecrawl**
```python
POST https://api.firecrawl.dev/v1/scrape
Headers: {
  "Authorization": "Bearer YOUR_FIRECRAWL_KEY"
}
Body: {
  "url": "http://api.scraperapi.com/?api_key=YOUR_SCRAPERAPI_KEY&url=https://amazon.co.uk/dp/B0DJTJ11PG&render=true&country_code=gb",
  "formats": ["html"]
}
```

**2. Firecrawl Calls ScraperAPI**
```
GET http://api.scraperapi.com/?api_key=YOUR_SCRAPERAPI_KEY&url=https://amazon.co.uk/dp/B0DJTJ11PG&render=true&country_code=gb
```

**3. ScraperAPI Routes Through UK Proxy**
```
Proxy IP: 192.168.x.x (UK residential)
GET https://www.amazon.co.uk/dp/B0DJTJ11PG
User-Agent: Chrome/120.0 (renders JavaScript)
```

**4. Amazon Returns HTML**
```html
<html>
  <div class="product">
    <span class="price">£12.69</span>
    <span class="rating">4.3 stars</span>
    ...
  </div>
</html>
```

**5. ScraperAPI Returns to Firecrawl**
```
HTML with rendered JavaScript (prices, reviews, BSR visible)
```

**6. Firecrawl Returns to Us**
```json
{
  "data": {
    "html": "<html>...</html>"
  }
}
```

**7. We Parse with BeautifulSoup**
```python
soup = BeautifulSoup(html, 'html.parser')
price = soup.find('span', class_='a-price-whole')
rating = soup.find('span', class_='a-icon-alt')
bsr = extract_bsr(soup)
```

**Total Time**: ~7-10 seconds per page

## Rate Limits

### Firecrawl Limits
- **Concurrent Requests**: We use semaphore (concurrency=1)
- **Rate Limit**: Unknown, but we hit 429 errors at concurrency=10
- **Our Setting**: `max_concurrent: 1` (prevents 429 errors)
- **Retry Logic**: 3 attempts with exponential backoff

### ScraperAPI Limits
- **Concurrent Requests**: Handled by Firecrawl
- **Monthly Credits**: Depends on your plan
- **Our Usage**: ~88 credits per 8-keyword run
- **Throttling**: None observed with concurrency=1

## Why This Architecture?

### Option 1: Direct ScraperAPI (What We DON'T Do)
```
Our Code → ScraperAPI → Amazon
```
**Problems**:
- Have to handle proxies ourselves
- No HTML cleaning
- More complex retry logic

### Option 2: Direct Firecrawl (What We DON'T Do)
```
Our Code → Firecrawl → Amazon
```
**Problems**:
- Gets blocked by Amazon quickly
- No IP rotation
- No country-specific routing

### Option 3: Firecrawl + ScraperAPI (What We DO) ✅
```
Our Code → Firecrawl → ScraperAPI → Amazon
```
**Benefits**:
- ✅ Firecrawl handles HTML fetching
- ✅ ScraperAPI handles proxy/IP rotation
- ✅ ScraperAPI handles country routing
- ✅ Single API call from our side (simple code)
- ✅ Best of both services

## Optimization Opportunities

### Current Setup (Most Reliable)
- Concurrency: 1
- Retries: 3
- Cost per run (8 keywords): ~$0.26
- Success rate: 100%

### Potential Optimizations

#### 1. Increase Concurrency (Risky)
```python
"max_concurrent": 3  # Instead of 1
```
**Benefits**: 3x faster (3m 30s vs 10m 42s for 8 keywords)
**Risks**: May trigger Firecrawl 429 rate limits
**Recommendation**: Test with monitoring

#### 2. Reduce Retries (Cost Savings)
```python
for attempt in range(2):  # Instead of 3
```
**Benefits**: Fail faster, fewer wasted calls
**Risks**: Lower success rate
**Recommendation**: Only if success rate >99%

#### 3. Cache Search Pages (Moderate Savings)
```python
# Cache search results for 1 hour
cache_search_results(keyword, html)
```
**Benefits**: Save 8 calls per re-run (1 per keyword)
**Savings**: ~$0.024 per re-run
**Use Case**: Testing/debugging

#### 4. Skip Low-Value Products (High Savings)
```python
# Only enrich top 5 products instead of 10
max_products_to_scrape: 5
```
**Benefits**: 50% fewer product page calls
**Savings**: ~$0.12 per run
**Trade-off**: Less complete data

## Monitoring API Usage

### Check Firecrawl Usage
Dashboard: https://firecrawl.dev/dashboard
- View API calls per day
- Monitor costs
- Check rate limits

### Check ScraperAPI Usage
Dashboard: https://www.scraperapi.com/dashboard
- View concurrent requests
- Monitor monthly credits
- Check success rate

### Our Logging
```python
logger.info(f"  + Fetched: {len(html)} chars")
logger.warning(f"  ! Rate limit (429) - attempt {attempt + 1}/3")
logger.error(f"  ✗ Failed to fetch after 3 attempts")
```

**Look for**:
- 429 errors = hitting rate limits (reduce concurrency)
- 408 errors = timeouts (normal, retry handles it)
- Multiple retries = network issues or API problems

## Summary

### What APIs Are Called
1. **Firecrawl** (directly by us): 88 calls for 8 keywords
2. **ScraperAPI** (by Firecrawl): 88 calls for 8 keywords

### What Each API Does
- **Firecrawl**: Fetches HTML cleanly, handles retries
- **ScraperAPI**: Provides proxy/IP rotation, renders JavaScript, bypasses blocks

### Cost
- **~$0.003 per page**
- **~$0.26 per 8-keyword run**
- **~$8 per month** for daily 8-keyword scraping

### Performance
- **~8 seconds per page**
- **~1m 20s per keyword** (search + 10 products)
- **~10m 42s for 8 keywords** (with concurrency=1)

---

**Last Updated**: 2025-10-14
**Architecture**: Firecrawl + ScraperAPI
**Concurrency**: 1 (optimal for reliability)
