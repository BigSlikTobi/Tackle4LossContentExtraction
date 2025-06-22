# Final Test Fix - store_embedding CI Detection

## Issue Identified and Fixed

### Problem
The test `TestStoreEmbeddingFunction::test_store_embedding_supabase_client_none` was failing because of how CI environment detection was implemented in the `store_embedding` function.

**Error**:
```
AssertionError: Expected 'warning' to be called once. Called 0 times.
```

### Root Cause
The issue was in `core/utils/create_embeddings.py` where the `IS_CI` variable was evaluated at module import time:

```python
# At module level - evaluated once at import
IS_CI = os.getenv("CI") == 'true' or os.getenv("GITHUB_ACTIONS") == 'true'

def store_embedding(article_id: int, embedding: List[float]) -> None:
    # Used cached IS_CI value
    if supabase_client is None and not IS_CI:
        logger.error(...)
    elif supabase_client is None and IS_CI:
        logger.warning(...)
```

**Problem**: The test sets environment variables within the test method, but the module had already cached the `IS_CI` value during import, before the test environment variables were set.

### Solution Applied

Changed the `store_embedding` function to check CI environment dynamically instead of using the cached value:

```python
def store_embedding(article_id: int, embedding: List[float]) -> None:
    """
    Store the embedding in the ArticleVector table
    """
    # Check CI status dynamically for tests
    is_ci = os.getenv("CI") == 'true' or os.getenv("GITHUB_ACTIONS") == 'true'
    
    if supabase_client is None and not is_ci:
        logger.error("Supabase client not initialized. Cannot store embedding for article_id %s.", article_id)
        return
    elif supabase_client is None and is_ci:
        logger.warning("Supabase client not initialized in CI. Skipping embedding storage for article_id %s.", article_id)
        return
    # ... rest of function
```

### Files Modified
- `core/utils/create_embeddings.py`: Updated `store_embedding` function to use dynamic CI detection

### Verification Results

**Individual Test**:
```bash
pytest tests/test_create_embeddings.py::TestStoreEmbeddingFunction::test_store_embedding_supabase_client_none -v
# ✅ PASSED
```

**Full create_embeddings Test Suite**:
```bash
pytest tests/test_create_embeddings.py -v
# ✅ 18 passed
```

**Complete Test Suite (CI Environment)**:
```bash
CI=true GITHUB_ACTIONS=true ... pytest tests/ -q
# ✅ 88 passed, 1 skipped
```

**Complete Test Suite (Local Environment)**:
```bash
pytest tests/ -q
# ✅ 89 passed
```

### Key Benefits

1. **Dynamic CI Detection**: Environment variables are checked at runtime, not import time
2. **Test Flexibility**: Tests can set environment variables and have them respected immediately
3. **Behavior Consistency**: Function behaves correctly in both CI and local environments
4. **No Breaking Changes**: All existing functionality preserved

## Status: ✅ RESOLVED

The failing test has been fixed and all tests now pass in both local development and CI environments. The dynamic CI detection ensures proper behavior regardless of when environment variables are set during test execution.
