# BSR Extraction Improvement Plan

**Date**: 2025-10-17
**Issue**: Low BSR extraction rates for Germany (20%) and Italy markets
**Current Status**: UK/ES have 90-100% success, DE/IT have ~20% success

---

## Problem Analysis

### Current Performance

| Market | BSR Success Rate | Sample Data |
|--------|-----------------|-------------|
| **UK** | 90-100% | 9/10 products |
| **ES** | 90-100% | 10/10 products |
| **DE** | ~20% | 2/10 products ❌ |
| **US** | 90-100% | 10/10 products |
| **IT** | ~20% | Estimated ❌ |

### Root Cause Analysis

Looking at Germany output (all_keywords_20251017_151419.json):

**Keyword: "berberine 1500mg" (DE)**
- Position 1-6: NO BSR extracted ❌
- Position 7: BSR = 5,162 ✅
- Position 8: NO BSR extracted ❌
- Position 9: BSR = 13,718 ✅
- Position 10: NO BSR extracted ❌

**Success Rate**: 2/10 = 20%

### Identified Issues

1. **HTML Structure Variation**
   - German pages may use different HTML structure than UK/ES
   - BSR may be in different sections (product info vs detail bullets)

2. **Language Pattern Mismatch**
   - Current German pattern: `r'Bestseller-Rang[:\s]*</span>\s*Nr\.\s*(\d+)\s+in\s+.*?>([^<]+)</a>'`
   - May not match actual HTML structure on German pages

3. **Number Formatting**
   - German uses `.` for thousands (5.162) vs `,` for UK (5,162)
   - Parser handles this (line 272: `replace(',', '').replace('.', '')`)
   - So this is NOT the issue

4. **Firecrawl HTML Quality**
   - Firecrawl might be stripping or modifying BSR sections
   - Need to verify if raw HTML contains BSR data

---

## Proposed Solutions

### Phase 1: Diagnostic Testing (1-2 hours)

**Goal**: Understand WHY BSR extraction is failing

**Steps**:

1. **Fetch Sample German Product Page**
   - Manually fetch one of the failing products (e.g., B0DJDP6XVN)
   - Save raw HTML to file
   - Manually search for BSR text in HTML

2. **Test Current Parser on Sample**
   - Run parser on saved HTML
   - Add debug logging to show which methods/patterns are being tried
   - Identify which extraction method should work

3. **Identify Missing Patterns**
   - Extract actual German BSR HTML structure
   - Compare to current regex patterns
   - Document correct patterns

**Deliverables**:
- Sample HTML file: `test_de_product_B0DJDP6XVN.html`
- Debug log showing parser attempts
- Document of actual German BSR HTML structure

### Phase 2: Parser Enhancement (2-3 hours)

**Goal**: Add robust German/Italian BSR extraction

**Proposed Changes to layer2_parser.py**:

```python
# Enhanced German patterns
german_patterns = [
    # Current pattern (keep)
    r'Bestseller-Rang[:\s]*</span>\s*Nr\.\s*(\d+)\s+in\s+.*?>([^<]+)</a>',

    # Additional patterns to try
    r'Bestseller-Rang[:\s]*Nr\.\s*([\d.]+)\s+in\s+([^(<\n]+)',  # Without span
    r'Nr\.\s*([\d.]+)\s+in\s+<a[^>]*>([^<]+)</a>',  # Direct number
    r'Bestseller[:\s]*#?([\d.]+)\s+in\s+([^(<\n]+)',  # Variation
]

# Enhanced Italian patterns
italian_patterns = [
    # Current pattern (keep)
    r'Posizione nella classifica[:\s]*</span>\s*(\d+)\s+in\s+.*?>([^<]+)</a>',

    # Additional patterns
    r'Posizione nella classifica[:\s]*n\.\s*([\d.]+)\s+in\s+([^(<\n]+)',
    r'n\.\s*([\d.]+)\s+in\s+<a[^>]*>([^<]+)</a>',
    r'Classifica[:\s]*#?([\d.]+)\s+in\s+([^(<\n]+)',
]
```

**Enhanced Extraction Logic**:
1. Try BeautifulSoup methods first (unchanged)
2. If those fail, try language-specific regex in order:
   - English patterns
   - Spanish patterns
   - **ENHANCED German patterns (multiple attempts)**
   - French patterns
   - **ENHANCED Italian patterns (multiple attempts)**
   - Generic fallbacks

3. Add debug logging for each pattern attempt:
   ```python
   logger.debug(f"  Trying BSR pattern: {pattern[:50]}...")
   ```

### Phase 3: Fallback Strategy (1 hour)

**Goal**: Maximize BSR extraction even when primary methods fail

**Strategy 1: Alternative HTML Sections**
- Current code checks 3 sections (detailBulletsWrapper, prodDetails, detail-bullets)
- Add more sections to check:
  - `id='detailBullets_feature_div'`
  - `id='productDetails_feature_div'`
  - `class='product-facts-detail'`

**Strategy 2: Broad Text Search**
- If all structured methods fail, do a final pass:
  ```python
  # Last resort: search entire HTML for any BSR-like pattern
  full_text = soup.get_text()
  if 'Bestseller-Rang' in full_text or 'Posizione' in full_text:
      # Try to extract number near that text
  ```

### Phase 4: Testing & Validation (1-2 hours)

**Test Plan**:

1. **Unit Testing on Samples**
   - Test enhanced parser on saved German/Italian HTML samples
   - Verify BSR extraction works
   - Verify no regressions on UK/ES/US

2. **Small-Scale Live Test**
   - Run scraper on 1 keyword for DE and IT
   - Check BSR extraction rate
   - **Target**: 80%+ success

3. **Full Regression Test**
   - Run full 5-country, 5-keyword scrape
   - Verify all markets maintain or improve BSR rates
   - Document results in test log

**Success Criteria**:
- Germany BSR extraction: 20% → 80%+ ✅
- Italy BSR extraction: 20% → 80%+ ✅
- UK/ES/US: Maintain 90%+ ✅

### Phase 5: Monitoring & Maintenance (Ongoing)

**Logging Enhancements**:
```python
# Add BSR extraction logging to layer3_orchestrator.py
logger.info(f"  BSR Success Rate: {bsr_count}/{total_products} ({bsr_pct:.1f}%)")
```

**Alerting**:
- If BSR extraction rate drops below 70% for any market, log warning
- Track BSR rates over time in test logs

---

## Implementation Priority

### High Priority (Do Now)
1. ✅ **Phase 1: Diagnostic Testing**
   - Required to understand the problem
   - Can be done without code changes
   - Estimated: 1-2 hours

2. ✅ **Phase 2: Parser Enhancement**
   - Core fix for the problem
   - Estimated: 2-3 hours

### Medium Priority (Do Soon)
3. **Phase 3: Fallback Strategy**
   - Improves robustness
   - Estimated: 1 hour

4. **Phase 4: Testing & Validation**
   - Verify fixes work
   - Estimated: 1-2 hours

### Low Priority (Do Later)
5. **Phase 5: Monitoring**
   - Long-term maintenance
   - Can be added incrementally

---

## Alternative Approaches

If parser enhancement doesn't improve rates:

### Option A: Different HTML Extraction
- Switch from Firecrawl to direct ScraperAPI HTML
- Firecrawl might be stripping BSR sections
- **Pros**: May preserve more HTML structure
- **Cons**: Requires architecture change

### Option B: Use Amazon Product API
- If available, Amazon's official API may provide BSR directly
- **Pros**: 100% reliable BSR data
- **Cons**: May require different API subscription

### Option C: Accept Lower Rates for DE/IT
- Focus scraping on UK/ES/US markets (90%+ success)
- Use DE/IT data with caveat about missing BSR
- **Pros**: No code changes needed
- **Cons**: Incomplete data for DE/IT markets

---

## Estimated Total Effort

**Minimum (Phase 1-2)**: 3-5 hours
**Recommended (Phase 1-4)**: 6-9 hours
**Complete (All phases)**: 8-12 hours

---

## Next Steps

1. **Immediate**: Run Phase 1 diagnostic test
   - Fetch sample German product HTML
   - Analyze BSR structure
   - Identify correct extraction patterns

2. **After diagnosis**: Implement Phase 2 enhancements
   - Add new patterns to layer2_parser.py
   - Test on sample data

3. **Validate**: Run Phase 4 testing
   - Small-scale test (1 keyword DE/IT)
   - Full regression test (5 countries)

---

**Owner**: TBD
**Status**: Plan Created - Awaiting Implementation
**Last Updated**: 2025-10-17
