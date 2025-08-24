"""
Test runner specifically for batch pipeline tests.
This script runs all batch-related tests and provides detailed reporting.
"""

import unittest
import sys
import os
import subprocess
from pathlib import Path

# Add project paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

def run_batch_tests():
    """Run all batch pipeline tests with detailed output."""
    
    print("=" * 70)
    print("BATCH PIPELINE TEST SUITE")
    print("=" * 70)
    
    # Test modules to run
    test_modules = [
        'tests.test_cleanup_pipeline_batched',
        'tests.test_batch_shell_scripts'
    ]
    
    total_tests = 0
    total_failures = 0
    total_errors = 0
    
    for module_name in test_modules:
        print(f"\n{'=' * 50}")
        print(f"Running: {module_name}")
        print('=' * 50)
        
        try:
            # Load and run the test module
            suite = unittest.TestLoader().loadTestsFromName(module_name)
            runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
            result = runner.run(suite)
            
            total_tests += result.testsRun
            total_failures += len(result.failures)
            total_errors += len(result.errors)
            
            # Print module summary
            print(f"\nModule Summary:")
            print(f"  Tests run: {result.testsRun}")
            print(f"  Failures: {len(result.failures)}")
            print(f"  Errors: {len(result.errors)}")
            
            if result.failures:
                print(f"\nFailures in {module_name}:")
                for test, traceback in result.failures:
                    print(f"  - {test}: {traceback.split()[-1] if traceback else 'Unknown failure'}")
            
            if result.errors:
                print(f"\nErrors in {module_name}:")
                for test, traceback in result.errors:
                    print(f"  - {test}: {traceback.split()[-1] if traceback else 'Unknown error'}")
                    
        except Exception as e:
            print(f"Failed to load or run {module_name}: {e}")
            total_errors += 1
    
    # Print overall summary
    print(f"\n{'=' * 70}")
    print("OVERALL TEST SUMMARY")
    print('=' * 70)
    print(f"Total tests run: {total_tests}")
    print(f"Total failures: {total_failures}")
    print(f"Total errors: {total_errors}")
    
    if total_failures == 0 and total_errors == 0:
        print("🎉 ALL BATCH PIPELINE TESTS PASSED!")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1

def run_integration_test():
    """Run a simple integration test of the batch pipeline."""
    
    print(f"\n{'=' * 50}")
    print("INTEGRATION TEST")
    print('=' * 50)
    
    try:
        # Test that we can import the batch pipeline modules
        print("Testing imports...")
        
        # Test cleanup pipeline batched
        cmd = [sys.executable, '-c', 
               'import sys; sys.path.insert(0, "scripts"); '
               'from cleanup_pipeline_batched import process_article_batch; '
               'print("✓ cleanup_pipeline_batched import successful")']
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
        if result.returncode == 0:
            print("✓ cleanup_pipeline_batched imports successfully")
        else:
            print(f"✗ cleanup_pipeline_batched import failed: {result.stderr}")
        
        # Test cluster pipeline CI
        cmd = [sys.executable, '-c',
               'import sys; sys.path.insert(0, "scripts"); '
               'from cluster_pipeline_ci import process_new_ci; '
               'print("✓ cluster_pipeline_ci import successful")']
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
        if result.returncode == 0:
            print("✓ cluster_pipeline_ci imports successfully")
        else:
            print(f"✗ cluster_pipeline_ci import failed: {result.stderr}")
        
        # Test help output
        print("\nTesting command line interfaces...")
        
        # Test cleanup pipeline help
        cmd = [sys.executable, 'scripts/cleanup_pipeline_batched.py', '--help']
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root, timeout=10)
        if result.returncode == 0 and '--batch-size' in result.stdout:
            print("✓ cleanup_pipeline_batched CLI working")
        else:
            print(f"✗ cleanup_pipeline_batched CLI failed")
        
        # Test cluster pipeline help
        cmd = [sys.executable, 'scripts/cluster_pipeline_ci.py', '--help']
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root, timeout=10)
        if result.returncode == 0 and '--threshold' in result.stdout:
            print("✓ cluster_pipeline_ci CLI working")
        else:
            print(f"✗ cluster_pipeline_ci CLI failed")
        
        print("✓ Integration test completed")
        return True
        
    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        return False

def check_test_environment():
    """Check that the test environment is properly set up."""
    
    print("Checking test environment...")
    
    # Check Python version
    print(f"Python version: {sys.version}")
    
    # Check required files exist
    required_files = [
        'scripts/cleanup_pipeline_batched.py',
        'scripts/cluster_pipeline_ci.py',
        'requirements.txt',
        '.github/workflows/run-pipeline.yml'
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = project_root / file_path
        if not full_path.exists():
            missing_files.append(file_path)
        else:
            print(f"✓ {file_path}")
    
    if missing_files:
        print("✗ Missing required files:")
        for file_path in missing_files:
            print(f"  - {file_path}")
        return False
    
    # Check test files exist
    test_files = [
        'tests/test_cleanup_pipeline_batched.py',
        'tests/test_cluster_pipeline_ci.py',
        'tests/test_batch_shell_scripts.py'
    ]
    
    missing_test_files = []
    for file_path in test_files:
        full_path = project_root / file_path
        if not full_path.exists():
            missing_test_files.append(file_path)
        else:
            print(f"✓ {file_path}")
    
    if missing_test_files:
        print("✗ Missing test files:")
        for file_path in missing_test_files:
            print(f"  - {file_path}")
        return False
    
    print("✓ Test environment check passed")
    return True

if __name__ == '__main__':
    print("Batch Pipeline Test Runner")
    print(f"Project root: {project_root}")
    
    # Check environment first
    if not check_test_environment():
        print("❌ Environment check failed")
        sys.exit(1)
    
    # Run integration test
    integration_success = run_integration_test()
    
    # Run unit tests
    test_result = run_batch_tests()
    
    # Final result
    if integration_success and test_result == 0:
        print("\n🎉 ALL TESTS PASSED! Batch pipelines are ready for production.")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED! Please review the output above.")
        sys.exit(1)
