# Project Directory Structure

## Main Documentation (Keep)
- `FINAL_RMS_IMPLEMENTATION_SUMMARY.md` - Complete RMS feature documentation
- `RMS_CRITICAL_FIX_APPLIED.md` - Critical sign fix documentation
- `PRODUCTION_WORKFLOWS.md` - Production workflows guide
- `PRODUCTION_USAGE_GUIDE.md` - Usage guide
- `Info_personal_2.md` - Personal notes (150KB)

## Test Files (Keep)
- `test_rms_numpy.py` - RMS validation test suite (7 test cases)

## Batch Processing Files
- `dunkirk_test.csv` - Test CSV for Dunkirk files
- `example_batch.csv` - Example batch file
- `Rubble.csv` - Rubble batch file
- `rubble_crew_analysis.json` - Analysis results
- `rubble_crew_ep110_analysis.json` - Episode 110 results

## Key Configuration
- `fastapi_app/app/core/config.py` - LONG_FILE_THRESHOLD_SECONDS = 150.0

## To Use CLI Batch Processor:
```bash
cd /mnt/data/amcmurray/Sync_dub/v1.3-presentation

PYTHONPATH=. python scripts/batch/csv_batch_processor.py dunkirk_test.csv \
  --use-optimized-cli \
  --gpu \
  --output-dir batch_results/
```

This command will correctly detect the 15-second offset using the direct analyzer.

---
**Directory cleaned**: November 7, 2025
**Temporary test files**: Removed
**Essential documentation**: Retained
