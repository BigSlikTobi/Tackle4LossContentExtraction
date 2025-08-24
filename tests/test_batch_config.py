"""
Batch Pipeline Test Configuration and Integration.

This module provides utilities for integrating batch pipeline tests
into the existing test suite and CI/CD pipeline.
"""

import os
import sys
from pathlib import Path

# Test configuration for batch pipelines
BATCH_TEST_MODULES = [
    'test_cleanup_pipeline_batched',
    'test_cluster_pipeline_ci', 
    'test_batch_shell_scripts'
]

BATCH_TEST_CATEGORIES = {
    'unit': [
        'test_cleanup_pipeline_batched.TestBatchedPipelineUnit',
        'test_cluster_pipeline_ci.TestCIClusterPipelineUnit'
    ],
    'integration': [
        'test_cleanup_pipeline_batched.TestCleanupPipelineBatched',
        'test_cluster_pipeline_ci.TestClusterPipelineCI',
        'test_batch_shell_scripts.TestBatchShellScripts',
        'test_batch_shell_scripts.TestBatchScriptIntegration'
    ],
    'shell': [
        'test_batch_shell_scripts.TestBatchShellScripts',
        'test_batch_shell_scripts.TestBatchScriptIntegration'
    ]
}

def get_batch_test_files():
    """Get list of batch test files."""
    return [f"tests/{module}.py" for module in BATCH_TEST_MODULES]

def get_batch_tests_by_category(category):
    """Get batch tests filtered by category."""
    return BATCH_TEST_CATEGORIES.get(category, [])

def verify_batch_test_environment():
    """Verify that the batch test environment is properly configured."""
    project_root = Path(__file__).parent.parent
    
    # Check that all test files exist
    missing_files = []
    for test_file in get_batch_test_files():
        if not (project_root / test_file).exists():
            missing_files.append(test_file)
    
    if missing_files:
        raise FileNotFoundError(f"Missing batch test files: {missing_files}")
    
    # Check that batch pipeline scripts exist
    batch_scripts = [
        'scripts/cleanup_pipeline_batched.py',
        'scripts/cluster_pipeline_ci.py'
    ]
    
    missing_scripts = []
    for script in batch_scripts:
        if not (project_root / script).exists():
            missing_scripts.append(script)
    
    if missing_scripts:
        raise FileNotFoundError(f"Missing batch pipeline scripts: {missing_scripts}")
    
    return True

if __name__ == '__main__':
    """Run verification when called directly."""
    try:
        verify_batch_test_environment()
        print("✓ Batch test environment verification passed")
        
        print("\nBatch Test Modules:")
        for module in BATCH_TEST_MODULES:
            print(f"  - {module}")
        
        print("\nTest Categories:")
        for category, tests in BATCH_TEST_CATEGORIES.items():
            print(f"  {category}:")
            for test in tests:
                print(f"    - {test}")
                
    except Exception as e:
        print(f"✗ Batch test environment verification failed: {e}")
        sys.exit(1)
