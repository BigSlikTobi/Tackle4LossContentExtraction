# Pipeline Testing Guide

This document explains how to test the content extraction and clustering pipelines to ensure they continue working correctly when you make changes.

## Quick Start

### Run Health Checks (Fastest)
```bash
python dev.py quick-test
```
This runs a quick import/syntax check to verify both pipelines can start without crashing.

### Run Comprehensive Pipeline Tests
```bash
python dev.py test
```
This runs all pipeline-specific tests including health checks, functional tests, and integration tests.

### Run All Tests
```bash
python dev.py all-tests
```
This runs the entire pytest suite (all 69+ tests).

## Test Files Overview

### Core Pipeline Tests

1. **`test_pipeline_health_checks.py`** - Health checks that verify:
   - Pipelines can import without syntax errors
   - Pipelines handle no-data scenarios gracefully
   - Lock mechanism works correctly
   - Error handling doesn't crash the pipelines

2. **`test_pipeline_functional.py`** - Functional tests with mocked dependencies:
   - URL decoding functionality (fixes the original bug)
   - Cluster similarity matching logic
   - Pipeline main logic flow
   - Lock acquisition/release behavior

3. **`test_cleanup_pipeline_integration.py`** - Integration tests for cleanup pipeline
4. **`test_cluster_pipeline_integration.py`** - Integration tests for cluster pipeline
5. **`test_cluster_manager.py`** - Unit tests for cluster manager components

### Test Runners

- **`run_pipeline_tests.py`** - Comprehensive test runner for pipeline-specific tests
- **`dev.py`** - Development helper with shortcuts for common tasks

## When to Run Tests

### Before Making Changes
```bash
python dev.py quick-test
```
Baseline check to ensure your environment is working.

### After Making Changes
```bash
python dev.py check
```
Runs syntax check + quick test to catch basic issues.

### Before Committing
```bash
python dev.py ci
```
Runs full CI suite: syntax check + linting + all pipeline tests.

### Before Deploying
```bash
python dev.py all-tests
```
Runs the complete test suite to ensure nothing is broken.

## Development Workflow

1. **Make your changes** to pipeline code
2. **Quick check**: `python dev.py quick-test`
3. **Functional test**: `python dev.py test`
4. **Manual test**: `python dev.py cleanup` or `python dev.py cluster`
5. **Full verification**: `python dev.py all-tests`

## Specific Test Categories

### URL Decoding Tests
These verify that the original URL encoding bug is fixed:
```bash
python -m pytest tests/test_pipeline_functional.py::TestPipelineFunctionalTests::test_article_processor_handles_url_decoding -v
```

### Cluster Logic Tests
These verify clustering algorithm works correctly:
```bash
python -m pytest tests/test_pipeline_functional.py -k cluster -v
```

### Integration Tests
These test actual pipeline execution:
```bash
python -m pytest tests/test_*pipeline_integration.py -v
```

## Test Environment

Tests use dummy credentials and mock external dependencies, so they can run in any environment without requiring:
- Valid Supabase credentials
- Valid OpenAI API keys
- Network connectivity

## Troubleshooting

### Tests fail with import errors
```bash
python dev.py syntax
```
Check for Python syntax errors in pipeline files.

### Tests pass but pipelines fail in production
1. Check environment variables are set correctly
2. Verify database connectivity
3. Run actual pipelines in test mode:
   ```bash
   python dev.py cleanup
   python dev.py cluster
   ```

### Need more verbose output
```bash
python run_pipeline_tests.py --pattern health
python -m pytest tests/test_pipeline_health_checks.py -v -s
```

## Adding New Tests

1. **For pipeline logic**: Add to `test_pipeline_functional.py`
2. **For health checks**: Add to `test_pipeline_health_checks.py`
3. **For integration**: Add to existing integration test files
4. **Update test runner**: Add new test files to `run_pipeline_tests.py` if needed

## Continuous Integration

The `dev.py ci` command runs a complete check suitable for CI environments:
- Syntax validation
- Code linting
- Quick health checks
- Full pipeline test suite

This ensures code quality and functionality before deployment.
