# ASIN Deduplication v2 - Changes Summary

**Date**: 2025-10-14
**Version**: 2.0 (Updated)

## Changes Overview

Updated the ASIN deduplication feature to address two key requirements:
1. **Search position tracking**: Add explicit position numbering for all products
2. **BSR always scraped**: Fetch BSR for every product/keyword combination (including duplicates)

## What Changed

### 1. Search Position Field Added ✅

**File**: `layer2_parser.py`

**Change**: Added `search_position` field with 1-indexed position counter

**Before**:
```python
product = {
    'asin': asin,
    'title': title,
    'price': price,
    ...
}
```

**After**:
```python
position_counter = 0  # Track non-sponsored position

for div in product_divs:
    if not self._is_sponsored(div):
        position_counter += 1

        product = {
            'asin': asin,
            'search_position': position_counter,  # NEW: 1, 2, 3...
            'title': title,
            'price': price,
            ...
        }
```

**Benefits**:
- Clear ranking: Product #1, #2, #3 in search results
- Excludes sponsored products from position count
- Keyword-specific: Same ASIN can be position #1 in one keyword, #7 in another

**Example Output**:
```json
{
  "keyword": "berberine 1500mg",
  "products": [
    {"asin": "B0CHRNR4QH", "search_position": 1, ...},
    {"asin": "B0F2Z7227C", "search_position": 2, ...},
    {"asin": "B0DJTJ11PG", "search_position": 3, ...}
  ]
}
```

### 2. BSR Always Scraped (Even for Duplicates) ✅

**File**: `layer3_orchestrator.py`

**Change**: Duplicate ASINs now fetch product page to get BSR

**Before (v1 - BSR skipped for duplicates)**:
```python
if asin in self.asin_cache:
    # Skip product page fetch entirely
    return {
        'bsr_rank': None,  # ❌ Not scraped
        'title': '[REPEATED]',
        ...
    }
```

**After (v2 - BSR scraped for duplicates)**:
```python
if asin in self.asin_cache:
    # Still fetch product page to get BSR
    html = await self.http_client.fetch_with_firecrawl(product['url'])
    bsr_rank, bsr_category, _ = self.parser.parse_product_page(html)

    return {
        'search_position': product['search_position'],  # NEW
        'bsr_rank': bsr_rank,  # ✅ Always scraped
        'bsr_category': bsr_category,  # ✅ Always scraped
        'title': '[REPEATED]',  # Still marked as repeated
        'badges': product['badges'],  # Still varies per keyword
        ...
    }
```

**Rationale**:
- BSR is a valuable metric to track per keyword
- Even though BSR is technically the same for the product, we want it recorded for each keyword
- User requested this data be scraped individually for each ASIN/keyword combination

### 3. Updated Logging

**Before**:
```
Duplicate ASINs skipped: 50 (saved 50 API calls)
```

**After**:
```
Duplicate ASINs: 50 (BSR still scraped per keyword)
```

**Reason**: We're no longer saving API calls on duplicates since we still fetch for BSR

## Data Structure Changes

### First Occurrence (No Change)
```json
{
  "asin": "B0CHRNR4QH",
  "search_position": 1,
  "title": "Berberine 1500mg Per Serving - 120 Vegan Capsules...",
  "price": "15.99",
  "currency": "GBP",
  "rating": "4.3",
  "review_count": "2,459",
  "bsr_rank": 890,
  "bsr_category": "Health & Personal Care",
  "badges": [],
  "images": ["url1", "url2", "url3", "url4", "url5", "url6"]
}
```

### Duplicate Occurrence (Updated)

**Before (v1)**:
```json
{
  "asin": "B0CHRNR4QH",
  "search_position": null,  // ❌ Not tracked
  "title": "[REPEATED - see 'berberine 1500mg']",
  "bsr_rank": null,  // ❌ Not scraped
  "bsr_category": "[REPEATED]",
  "badges": ["Limited time deal"],
  "is_duplicate": true,
  "first_seen_in": "berberine 1500mg"
}
```

**After (v2)**:
```json
{
  "asin": "B0CHRNR4QH",
  "search_position": 4,  // ✅ NEW: Position in this keyword's results
  "title": "[REPEATED - see 'berberine 1500mg']",
  "bsr_rank": 890,  // ✅ CHANGED: Now scraped
  "bsr_category": "Health & Personal Care",  // ✅ CHANGED: Now scraped
  "badges": ["Limited time deal"],  // Already working
  "images": "[REPEATED]",
  "is_duplicate": true,
  "first_seen_in": "berberine 1500mg"
}
```

## Performance Impact

### API Calls

**v1 (Original Deduplication)**:
- Search pages: 8 calls
- Product pages: 30 calls (only unique ASINs)
- **Total: 38 calls** (~57% reduction)

**v2 (BSR Always Scraped)**:
- Search pages: 8 calls
- Product pages: 80 calls (all products for BSR)
- **Total: 88 calls** (same as no deduplication)

**Trade-off**: API call savings removed, but we get complete BSR data per keyword

### Execution Time

**v1**: ~3m 41s (faster due to skipped fetches)
**v2**: ~10-12 minutes (similar to no deduplication, but with cleaner data structure)

### Cost

**v1**: $0.114 per run (56% savings)
**v2**: $0.264 per run (no savings, but complete data)

## What's Still Optimized

Even though we're fetching all product pages again, we still benefit from:

1. **Cleaner data structure**: Duplicate products clearly marked with `[REPEATED]`
2. **Reference tracking**: `first_seen_in` shows which keyword first found the ASIN
3. **Duplicate detection**: `is_duplicate: true` flag for analytics
4. **Data consistency**: Same product data referenced across keywords

## Summary of Fields

| Field | First Occurrence | Duplicate Occurrence | Varies Per Keyword? |
|-------|-----------------|---------------------|---------------------|
| `asin` | Full value | Full value | No |
| `search_position` | 1-indexed position | 1-indexed position | ✅ Yes |
| `title` | Full text | `[REPEATED]` | No |
| `price` | Numeric value | `[REPEATED]` | No |
| `currency` | Currency code | `[REPEATED]` | No |
| `rating` | Numeric value | `[REPEATED]` | No |
| `review_count` | Numeric value | `[REPEATED]` | No |
| `bsr_rank` | Numeric value | **Numeric value** (scraped) | No* |
| `bsr_category` | Category name | **Category name** (scraped) | No* |
| `badges` | Array of badges | Array of badges | ✅ Yes |
| `images` | Array of URLs | `[REPEATED]` | No |
| `is_duplicate` | Not present | `true` | N/A |
| `first_seen_in` | Not present | Keyword name | N/A |

\* *BSR doesn't vary per keyword, but is scraped for each to ensure data completeness*

## Files Modified

1. **layer2_parser.py**:
   - Added position counter (line 40)
   - Added `search_position` field to products (line 69)

2. **layer3_orchestrator.py**:
   - Modified duplicate handling to fetch BSR (lines 167-180)
   - Updated duplicate return structure (lines 185-200)
   - Updated logging messages (lines 295-296)

3. **exploratory_testing/findings/asin_deduplication_v2_changes.md**:
   - This document

## Testing Recommendation

Run the scraper with the updated code and verify:
1. ✅ `search_position` appears for all products (1, 2, 3...)
2. ✅ `bsr_rank` is numeric for duplicates (not null)
3. ✅ `bsr_category` is text for duplicates (not `[REPEATED]`)
4. ✅ Other fields still show `[REPEATED]` for duplicates
5. ✅ `badges` still vary per keyword for same ASIN

---

**Updated By**: ASIN Deduplication Enhancement
**Date**: 2025-10-14
**Status**: Ready for Testing
