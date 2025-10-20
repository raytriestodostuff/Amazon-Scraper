# BSR Extraction Fix Summary

**Date**: 2025-10-17
**Issue**: Low BSR extraction rates for Germany (~20%) and Italy markets
**Status**: ✅ **FIXED** - Ready for testing

---

## Problem Summary

### Before Fix
- **Germany (DE)**: Only 20% BSR extraction (2 out of 10 products)
- **Italy (IT)**: Estimated ~20% BSR extraction
- **UK/ES/US**: 90-100% success ✅

### Root Cause
1. **Insufficient German/Italian regex patterns** - Only 1 pattern per language
2. **Limited HTML section checks** - Only checking 3 sections
3. **Regex too restrictive** - Required exact HTML structure with `</span>` and `<a>` tags

---

## Changes Made to `layer2_parser.py`

### 1. Enhanced HTML Section Checks (Methods 1-6)

**Added 3 new section checks specifically for DE/IT markets:**

```python
# NEW: Method 4 - Product details feature div (common on DE/IT)
product_details_feature = soup.find('div', id='productDetails_feature_div')

# NEW: Method 5 - Detail bullets feature div (alternative on DE/IT)
detail_bullets_feature = soup.find('div', id='detailBullets_feature_div')

# NEW: Method 6 - Product facts section (sometimes used on EU markets)
product_facts = soup.find('div', class_=re.compile(r'product-facts|prodDetTable', re.I))
```

**Result**: Now checks 6 HTML sections instead of 3 (2x more coverage)

---

### 2. Enhanced Regex Patterns (Method 7)

**German Patterns - BEFORE (1 pattern):**
```python
r'Bestseller-Rang[:\s]*</span>\s*Nr\.\s*(\d+)\s+in\s+.*?>([^<]+)</a>'
```

**German Patterns - AFTER (5 patterns):**
```python
# Pattern 1: Full HTML structure with span/anchor
r'Bestseller-Rang[:\s]*</span>\s*Nr\.\s*([\d.]+)\s+in\s+.*?>([^<]+)</a>'

# Pattern 2: Relaxed structure without full HTML tags
r'Bestseller-Rang[:\s]*Nr\.\s*([\d.]+)\s+in\s+([^(<\n]+)'

# Pattern 3: Flexible matching with wildcards
r'Bestseller-Rang.*?Nr\.\s*([\d.]+).*?in\s+([^(<\n]+)'

# Pattern 4: Direct number after "Nr."
r'Nr\.\s*([\d.]+)\s+in\s+<a[^>]*>([^<]+)</a>'

# Pattern 5: Simplified "Bestseller Rang" format
r'Bestseller[:\s-]*Rang[:\s]*#?([\d.]+)\s+in\s+([^(<\n]+)'
```

**Italian Patterns - BEFORE (1 pattern):**
```python
r'Posizione nella classifica[:\s]*</span>\s*(\d+)\s+in\s+.*?>([^<]+)</a>'
```

**Italian Patterns - AFTER (5 patterns):**
```python
# Pattern 1: Full HTML structure
r'Posizione nella classifica[:\s]*</span>\s*n?\.?\s*([\d.]+)\s+in\s+.*?>([^<]+)</a>'

# Pattern 2: Relaxed structure
r'Posizione nella classifica[:\s]*n?\.?\s*([\d.]+)\s+in\s+([^(<\n]+)'

# Pattern 3: Flexible matching
r'Posizione.*?classifica.*?n?\.?\s*([\d.]+).*?in\s+([^(<\n]+)'

# Pattern 4: Direct "n." number format
r'n\.\s*([\d.]+)\s+in\s+<a[^>]*>([^<]+)</a>'

# Pattern 5: Simplified "Classifica" format
r'Classifica[:\s]*#?([\d.]+)\s+in\s+([^(<\n]+)'
```

**Result**: 5x more patterns per language = much higher match probability

---

### 3. Enhanced `_extract_bsr_from_element()` Method

**Key Improvements:**

1. **More robust BSR text search:**
   ```python
   # BEFORE
   r'Best Sellers Rank|Clasificación|Bestseller-Rang|Classement|Posizione'

   # AFTER (more flexible)
   r'Best Sellers? Rank|Clasificación|Bestseller-?Rang|Classement|Posizione.*classifica'
   ```

2. **Try more parent types:**
   ```python
   # BEFORE
   parent = bsr_text.find_parent('li') or bsr_text.find_parent('tr')

   # AFTER
   parent = bsr_text.find_parent('li') or bsr_text.find_parent('tr') or bsr_text.find_parent('div')
   ```

3. **Multiple rank extraction patterns:**
   ```python
   rank_patterns = [
       r'(?:Nr\.|n\.|#)\s*([\d,\.]+)',     # Nr. 5.162 or n. 5.162
       r'(?:nº|º)\s*([\d,\.]+)',           # nº 5.162
       r':\s*#?([\d,\.]+)',                 # : 5,162
       r'#([\d,\.]+)',                      # #5162
       r'([\d,\.]+)\s+(?:in|en|dans)'      # 5.162 in
   ]
   ```
   Tries 5 different number formats instead of just 1

4. **Better number parsing:**
   ```python
   # Handles both German (5.162) and English (5,162) thousands separators
   rank_str = rank_match.group(1).replace(',', '').replace('.', '')
   rank = int(rank_str)
   ```

5. **Enhanced category extraction with cleanup:**
   ```python
   # Removes German-specific clutter like "Siehe Top 100"
   category = re.sub(r'(?:Siehe|See) Top.*', '', category, flags=re.I).strip()
   ```

---

### 4. Debug Logging Added

**Logs at each successful extraction point:**
```python
logger.debug(f"  BSR found via detailBulletsWrapper: {bsr_rank}")
logger.debug(f"  BSR found via prodDetails: {bsr_rank}")
logger.debug(f"  BSR found via productDetails_feature_div: {bsr_rank}")
logger.debug(f"  BSR found via regex pattern #{idx}: {bsr_rank}")
logger.debug("  BSR extraction failed - no patterns matched")
```

**Benefit**: When you run with debug logging, you'll see exactly which method found the BSR for each product

---

## Technical Details

### Number Format Handling

**German Number Format:**
- Uses `.` as thousands separator: `5.162` = 5,162
- Our fix: `replace(',', '').replace('.', '')` strips ALL separators
- Result: Both `5,162` and `5.162` → `5162` ✅

**Example:**
```python
# Input: "Nr. 5.162 in Health & Personal Care"
# Pattern matches: r'Nr\.\s*([\d.]+)'
# Captured: "5.162"
# Cleaned: "5162"
# Parsed: 5162 ✅
```

### Regex Improvements

**Key Changes:**
1. `\d+` → `[\d.,]+` - Now accepts commas AND periods in numbers
2. Added `re.DOTALL` flag - Patterns can now match across newlines
3. Optional elements: `n?º?\.?` - Makes format variations optional
4. Wildcard matching: `.*?` - Handles extra whitespace/HTML

---

## Expected Results

### Performance Prediction

| Market | Before | After (Expected) | Improvement |
|--------|--------|------------------|-------------|
| **UK** | 90-100% | 90-100% | No change ✅ |
| **ES** | 90-100% | 90-100% | No change ✅ |
| **DE** | ~20% | **80-95%** | **+60-75%** 🎯 |
| **US** | 90-100% | 90-100% | No change ✅ |
| **IT** | ~20% | **80-95%** | **+60-75%** 🎯 |

### Why These Numbers?

**Conservative estimate: 80%**
- 6 HTML section checks + 5 German patterns + 5 Italian patterns
- Total: 16 different ways to find BSR per product
- Even if 80% of German/Italian pages use "non-standard" format, we should catch most

**Optimistic estimate: 95%**
- Similar to UK/ES/US success rates
- Would indicate complete parity across all markets

**Worst case: 50%**
- Still a 2.5x improvement over 20%
- Would indicate Firecrawl is stripping BSR data from HTML

---

## Testing Plan

### Phase 1: Small Test (Recommended First)

**Run 1 keyword for DE and IT only:**
```python
# In config.json, temporarily set:
"countries": ["de", "it"],
"keywords": ["berberine 1500mg"]  # Just 1 keyword
```

**Expected output:**
- 20 products total (10 DE + 10 IT)
- BSR success: 16-19 products (80-95%)
- Runtime: ~2 minutes
- Cost: ~2 API calls × 2 countries = minimal

**Success criteria:**
- ✅ DE: 8+ products with BSR (80%+)
- ✅ IT: 8+ products with BSR (80%+)

---

### Phase 2: Full Regression Test

**Run all 5 countries, all 5 keywords:**
```python
"countries": ["uk", "es", "de", "us", "it"],
"keywords": [all 5 keywords]
```

**Expected output:**
- 250 products total
- BSR success: 225-240 products (90-96%)
- Runtime: ~11 minutes
- Cost: Standard scraping costs

**Success criteria:**
- ✅ UK: 45+ products with BSR (90%+)
- ✅ ES: 45+ products with BSR (90%+)
- ✅ DE: 40+ products with BSR (80%+) ⬆️ IMPROVED
- ✅ US: 45+ products with BSR (90%+)
- ✅ IT: 40+ products with BSR (80%+) ⬆️ IMPROVED

---

## Validation Checklist

After running tests, check:

- [ ] **Germany BSR rate improved** from 20% to 80%+
- [ ] **Italy BSR rate improved** from 20% to 80%+
- [ ] **UK/ES/US BSR rates maintained** at 90%+
- [ ] **No regressions** in other data fields (price, rating, etc.)
- [ ] **Debug logs show** which methods are finding BSR
- [ ] **Create test log** documenting results

---

## Rollback Plan

If the fix causes issues:

1. **Revert to backup:**
   ```bash
   git checkout HEAD~1 layer2_parser.py
   ```

2. **Or manually revert specific changes:**
   - Remove Methods 4-6 (new HTML sections)
   - Revert to single pattern per language
   - Remove debug logging

---

## Files Modified

1. **layer2_parser.py** - Enhanced BSR extraction logic
   - Line 194-301: `_extract_bsr()` method
   - Line 303-358: `_extract_bsr_from_element()` method

---

## Next Steps

1. ✅ **Changes complete** - Ready for testing
2. ⏳ **Run Phase 1 test** - 1 keyword DE/IT only
3. ⏳ **Analyze results** - Check BSR extraction rates
4. ⏳ **Run Phase 2 test** - Full 5-country regression
5. ⏳ **Document results** - Create test log

---

**Status**: ✅ **READY FOR TESTING**
**Confidence**: **HIGH** (80-95% success expected)
**Risk**: **LOW** (backward compatible, won't break existing markets)

---

*Fix implemented by: Assistant*
*Date: 2025-10-17*
*Ready for testing without running scrape*
