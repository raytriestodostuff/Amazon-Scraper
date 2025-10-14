# Exploratory Testing Log

This folder contains structured test documentation for the Amazon Scraper v2 project.

## Folder Structure

- `test_logs/` - Individual test execution logs with timestamps
- `test_plans/` - Test plans and objectives for different features
- `findings/` - Bugs, issues, and observations discovered during testing

## Latest Test Results

### Most Recent Run
- **Date**: 2025-10-14 13:06:00
- **Test**: Spain Market Run #2 (ES-002)
- **Status**: ✅ PASSED
- **Products**: 10/10 extracted
- **Execution Time**: 2m 4s
- **Log**: `test_logs/20251014_130600_spain_run.md`

### Key Findings
1. **BSR Variability**: BSR data changes between runs (expected behavior)
2. **Price Stability**: 100% price consistency across runs
3. **Performance**: 24% faster than previous run (no retries needed)
4. **Architecture**: All 3 layers performing optimally

## Test Coverage

### Completed Tests
- ✅ Spain Market Test (ES-001) - Initial run
- ✅ Spain Market Test (ES-002) - Consistency validation
- ✅ Layered Architecture Refactor Test (ARCH-001)
- ✅ Run Comparison Analysis (COMP-001)

### Pending Tests
- ⏳ UK Market Test
- ⏳ Germany Market Test
- ⏳ France Market Test
- ⏳ Italy Market Test
- ⏳ Multi-keyword Test
- ⏳ Peak Load Test (concurrency=3)

## Test Statistics

| Metric | Value |
|--------|-------|
| Total Tests Run | 4 |
| Pass Rate | 100% |
| Total Products Scraped | 20 |
| Average Execution Time | 2m 23s |
| BSR Extraction Rate | 90% |
| Price Stability | 100% |

## Test Template

Each test should include:
1. **Test Objective** - What are we testing?
2. **Test Setup** - Configuration and environment details
3. **Test Steps** - What actions were performed
4. **Expected Results** - What should happen
5. **Actual Results** - What actually happened
6. **Findings** - Issues, bugs, or observations
7. **Next Steps** - Follow-up actions or improvements needed

## Quick Links

### Test Logs
- [Spain Test #1 (ES-001)](test_logs/20251014_spain_test.md)
- [Spain Test #2 (ES-002)](test_logs/20251014_130600_spain_run.md)
- [Layered Architecture Test](test_logs/20251014_layered_architecture_test.md)

### Test Plans
- [Multi-Country Test Plan](test_plans/multi_country_test_plan.md)

### Findings
- [Layered Architecture Benefits](findings/layered_architecture_benefits.md)
- [Run Comparison: ES-001 vs ES-002](findings/run_comparison_es001_vs_es002.md)

## How to Add New Tests

1. Run the scraper: `python layer3_orchestrator.py`
2. Create test log in `test_logs/` using timestamp format: `YYYYMMDD_HHMMSS_description.md`
3. Document findings in `findings/` if significant issues or insights discovered
4. Update this README with latest statistics
