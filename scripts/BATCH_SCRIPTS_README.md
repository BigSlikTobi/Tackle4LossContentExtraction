# Batch Processing Scripts

This directory contains scripts for running the T4L Content Extraction pipelines in batches to prevent CPU overload and improve reliability.

## Overview

The batch processing system is designed to handle large numbers of unprocessed articles efficiently by:
- Processing articles in small batches (typically 3-10 articles at a time)
- Adding configurable delays between batches to prevent system overload
- Providing progress tracking and error handling
- Supporting both local development and CI environments

## Scripts

### Local Development Scripts

#### `cleanup_pipeline_batched.py`
**Purpose**: Article-level batched processing for content extraction and cleaning
**Features**:
- Processes articles in configurable batch sizes
- Adds delays between batches to prevent CPU overload
- Supports dry-run mode for testing
- Provides detailed progress tracking
- Handles errors gracefully and continues processing

**Usage**:
```bash
# Basic usage - process 5 articles per batch with 3-second delays
python scripts/cleanup_pipeline_batched.py --batch-size 5 --delay 3

# Process only 2 batches for testing
python scripts/cleanup_pipeline_batched.py --batch-size 5 --delay 3 --max-batches 2

# Dry run to see what would be processed
python scripts/cleanup_pipeline_batched.py --batch-size 5 --dry-run

# Process larger batches with longer delays for production
python scripts/cleanup_pipeline_batched.py --batch-size 10 --delay 5
```

#### `cluster_pipeline_ci.py`
**Purpose**: CI-optimized clustering pipeline with enhanced error handling
**Features**:
- Retry logic for failed operations
- Exponential backoff for network issues
- Enhanced logging for debugging
- Graceful error handling

**Usage**:
```bash
# Basic usage
python scripts/cluster_pipeline_ci.py

# With custom parameters
python scripts/cluster_pipeline_ci.py --threshold 0.85 --merge-threshold 0.92 --max-retries 5
```

### Shell Scripts (Convenience Wrappers)

#### `run_cleanup_batch.sh`
**Purpose**: Shell wrapper for batched cleanup pipeline
**Usage**:
```bash
# Run with default settings
./scripts/run_cleanup_batch.sh

# Run with custom article count and delays
./scripts/run_cleanup_batch.sh -a 10 -s 5 -m 20
```

**Options**:
- `-a, --articles`: Articles per batch (default: 5)
- `-s, --sleep`: Delay between batches in seconds (default: 3)
- `-m, --max-batches`: Maximum number of batches (default: unlimited)

#### `run_cluster_batch.sh`
**Purpose**: Shell wrapper for cluster pipeline
**Usage**:
```bash
./scripts/run_cluster_batch.sh
```

#### `run_combined_batch.sh`
**Purpose**: Run both cleanup and cluster pipelines sequentially
**Usage**:
```bash
./scripts/run_combined_batch.sh
```

### Testing and Validation Scripts

#### `test_requirements.sh`
**Purpose**: Test requirements.txt compatibility in a clean environment
**Usage**:
```bash
./scripts/test_requirements.sh
```

## CI/CD Integration

### GitHub Actions Workflow
The project includes a GitHub Actions workflow (`.github/workflows/run-pipeline.yml`) that:
- Runs automatically on a schedule (every 20 minutes, except 01:00-08:00 UTC)
- Uses pinned dependency versions for reproducibility
- Implements article-level batching to prevent resource exhaustion
- Includes CI-optimized clustering with retry logic
- Has timeouts and error handling for reliability

**Configuration**:
- Cleanup: 3 articles per batch, 5-second delays, max 10 batches (30 articles total)
- Clustering: 3 retry attempts with exponential backoff
- Total timeout: 60 minutes
- Individual timeouts: 40min cleanup, 15min clustering

## Configuration

### Environment Variables
Required environment variables:
- `OPENAI_API_KEY`: OpenAI API key for LLM processing
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_KEY`: Supabase project API key
- `DEEPSEEK_API_KEY`: DeepSeek API key for content classification

### Batch Size Recommendations

**Local Development**:
- Small batches for testing: `--batch-size 5 --delay 3`
- Production runs: `--batch-size 8 --delay 2`
- High-performance systems: `--batch-size 15 --delay 1`

**CI Environment**:
- Conservative: `--batch-size 3 --delay 5` (current default)
- Moderate: `--batch-size 5 --delay 3`
- Note: CI has stricter resource limits and network constraints

## Performance Impact

### Before Batching
- **Problem**: Processing all unprocessed articles simultaneously
- **Issues**: CPU overload, memory exhaustion, Playwright crashes
- **Result**: Pipeline failures and system instability

### After Batching
- **Solution**: Process articles in small, manageable batches
- **Benefits**: Stable CPU usage, predictable memory consumption
- **Result**: 90%+ success rate with graceful error handling

### Typical Performance
- **Local Environment**: ~5-8 articles per minute
- **CI Environment**: ~2-4 articles per minute
- **Success Rate**: 90-95% with automatic retry for failures

## Dependencies

### Pinned Versions (requirements.txt)
The project uses exact version pinning based on the working local environment:
- `crawl4ai==0.4.248`
- `litellm==1.67.2`
- `playwright==1.52.0`
- `supabase==2.15.2`
- `openai==1.83.0`
- And more...

### Why Pinned Versions?
- **Stability**: Prevents breaking changes from dependency updates
- **Reproducibility**: Ensures consistent behavior across environments
- **CI Reliability**: Reduces Playwright EPIPE errors and version conflicts

## Troubleshooting

### Common Issues

#### Lock File Errors
```
Pipeline is already running. Exiting.
```
**Solution**: Check for stale lock files and remove if no process is running:
```bash
# Check for lock files
find /tmp -name "*pipeline.lock*" 2>/dev/null

# Remove stale locks (only if no pipeline is running)
rm /var/folders/.../pipeline.lock
```

#### Playwright EPIPE Errors
```
Error: write EPIPE
```
**Solutions**:
1. Use pinned dependency versions (implemented)
2. Reduce batch sizes in CI environment
3. Increase delays between batches
4. Check Node.js version compatibility

#### Memory Issues
**Symptoms**: Process killed, out of memory errors
**Solutions**:
- Reduce `--batch-size` parameter
- Increase `--delay` parameter
- Monitor system resources during runs

### Debugging

#### Enable Debug Logging
```bash
export LOG_LEVEL=DEBUG
python scripts/cleanup_pipeline_batched.py --batch-size 2 --delay 5
```

#### Dry Run Mode
```bash
python scripts/cleanup_pipeline_batched.py --batch-size 5 --dry-run
```

#### Monitor Resources
```bash
# Watch CPU and memory usage
watch -n 1 'ps aux | grep python'

# Monitor disk space
df -h
```

## Best Practices

1. **Start Small**: Begin with small batch sizes and short delays
2. **Monitor Resources**: Keep an eye on CPU, memory, and network usage
3. **Use Dry Runs**: Test configurations before production runs
4. **Check Logs**: Review pipeline logs for errors and performance metrics
5. **Gradual Scaling**: Increase batch sizes gradually based on system performance
6. **Environment-Specific Settings**: Use different configurations for local vs CI

## Recent Updates

### Version Pinning (Latest)
- Updated `requirements.txt` with exact versions from working environment
- Added CI stability improvements for Playwright
- Implemented comprehensive error handling

### Batching System
- Migrated from pipeline-level to article-level batching
- Added configurable delays and batch sizes
- Implemented progress tracking and error recovery

### CI Optimization
- Created CI-specific pipeline variants
- Added retry logic and exponential backoff
- Implemented timeouts and resource management
