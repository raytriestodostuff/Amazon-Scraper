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

### Direct Calls

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

### Indirect Calls

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

### Example: 8 keywords, 10 products each

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

## API Parameters Explained

### ScraperAPI Parameters

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
- **Without it**: Missing prices, reviews, BSR, images

#### `country_code: gb` (or `es`, `de`, `fr`, `it`)
- **Purpose**: Route through residential IP in target country
- **Why**: Amazon shows different content per country
- **Result**: See prices in local currency, local BSR rankings, local language
- **Without it**: May get redirected or see US content

### Firecrawl Parameters

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
- **Concurrent Requests**: We use semaphore to control concurrency
- **Rate Limit**: Can hit 429 errors at high concurrency (>5)
- **Our Setting**: `max_concurrent: 2-3` (prevents 429 errors)
- **Retry Logic**: 3 attempts with exponential backoff

### ScraperAPI Limits
- **Concurrent Requests**: Handled by Firecrawl
- **Monthly Credits**: Depends on your plan
- **Throttling**: None observed with concurrency=2-3

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

## Monitoring API Usage

### Check Firecrawl Usage
Dashboard: https://firecrawl.dev/dashboard
- View API calls per day
- Monitor usage
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
1. **Firecrawl** (directly by us): All page requests
2. **ScraperAPI** (by Firecrawl): All page requests (via Firecrawl)

### What Each API Does
- **Firecrawl**: Fetches HTML cleanly, handles retries
- **ScraperAPI**: Provides proxy/IP rotation, renders JavaScript, bypasses blocks

### Performance
- **~7-10 seconds per page**
- **~1-2 minutes per keyword** (search + 10 products)
- **~10-15 minutes for 8 keywords** (with concurrency=2-3)

---

**Last Updated**: 2025-10-14
**Architecture**: Firecrawl + ScraperAPI
**Recommended Concurrency**: 2-3
