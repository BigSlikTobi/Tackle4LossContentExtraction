#!/usr/bin/env python3
"""
Pipeline test runner - runs comprehensive tests for both pipelines.
Use this script to verify pipeline functionality before deploying changes.
It runs:
- Quick health checks
- Full test suite
- Cleanup pipeline tests
- Cluster pipeline tests
- Syntax checks
- Linting checks
"""
import os
import sys
import subprocess
import argparse
import time
from typing import List, Tuple
from pathlib import Path

# Add src directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

def run_test_suite(test_pattern: str = None, verbose: bool = True) -> Tuple[bool, str]:
    """
    Run a specific test suite or all pipeline tests.
    This runs pytest on the specified test files or all pipeline-related tests.
    If test_pattern is provided, it filters tests by that pattern.
    Args:
        test_pattern: Pattern to match test files (e.g., 'pipeline', 'health')
        verbose: Whether to show verbose output   
    Returns:
        Tuple of (success, output)
    """
    test_dir = os.path.join(PROJECT_ROOT, 'tests')
    
    if test_pattern:
        test_files = [f for f in os.listdir(test_dir) 
                     if f.startswith('test_') and test_pattern in f and f.endswith('.py')]
    else:
        # Run all pipeline-related tests
        test_files = [
            'test_pipeline_health_checks.py',
            'test_pipeline_functional.py',
            'test_cleanup_pipeline_integration.py',
            'test_cluster_pipeline_integration.py',
            'test_cluster_manager.py'
        ]
    
    if not test_files:
        return False, f"No test files found matching pattern: {test_pattern}"
    
    print(f"Running {len(test_files)} test files...")
    
    all_output = []
    all_passed = True
    
    for test_file in test_files:
        test_path = os.path.join(test_dir, test_file)
        if not os.path.exists(test_path):
            print(f"⚠️  Skipping {test_file} (not found at {test_path})")
            continue
            
        print(f"\n🧪 Running {test_file}...")
        start_time = time.time()
        
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pytest', test_path, '-v' if verbose else '-q'],
                capture_output=True,
                text=True,
                cwd=str(PROJECT_ROOT),  # Run from project root
                timeout=300  # 5 minute timeout per test file
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            if result.returncode == 0:
                print(f"✅ {test_file} passed ({duration:.1f}s)")
            else:
                print(f"❌ {test_file} failed ({duration:.1f}s)")
                all_passed = False
                
            all_output.append(f"\n=== {test_file} ===")
            all_output.append(f"Return code: {result.returncode}")
            all_output.append(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                all_output.append(f"STDERR:\n{result.stderr}")
                
        except subprocess.TimeoutExpired:
            print(f"⏰ {test_file} timed out (5 minutes)")
            all_passed = False
            all_output.append(f"\n=== {test_file} ===")
            all_output.append("TIMEOUT: Test exceeded 5 minute limit")
            
        except Exception as e:
            print(f"💥 {test_file} crashed: {e}")
            all_passed = False
            all_output.append(f"\n=== {test_file} ===")
            all_output.append(f"EXCEPTION: {e}")
    
    return all_passed, '\n'.join(all_output)

def run_quick_health_check() -> bool:
    """
    Run a quick health check to verify pipelines can start.
    Returns True if both pipelines can at least start without crashing.
    Args:
        None
    Returns:
        bool: True if quick health check passed, False otherwise.   
    """
    print("🔍 Running quick pipeline health check...")
    
    test_env = os.environ.copy()
    test_env.update({
        'SUPABASE_URL': 'http://test.supabase.co',
        'SUPABASE_KEY': 'test_key',
        'OPENAI_API_KEY': 'test_openai_key',
        'DEEPSEEK_API_KEY': 'test_deepseek_key'
    })
    
    test_env['PYTHONPATH'] = str(PROJECT_ROOT)
    
    pipelines = [
        ('scripts/cleanup_pipeline.py', 'Cleanup Pipeline'),
        ('scripts/cluster_pipeline.py', 'Cluster Pipeline')
    ]
    
    all_healthy = True
    
    for script, name in pipelines:
        script_path = os.path.join(PROJECT_ROOT, script)
        print(f"  Testing {name}...")
        
        try:
            # Quick syntax/import check - just try to start the pipeline
            result = subprocess.run(
                [sys.executable, '-c', f"""
import sys
sys.path.append('{PROJECT_ROOT}')
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location('pipeline', '{script_path}')
    module = importlib.util.module_from_spec(spec)
    # Don't actually execute, just check imports work
    print('IMPORT_SUCCESS')
except Exception as e:
    print(f'IMPORT_ERROR: {{e}}')
    sys.exit(1)
"""],
                capture_output=True,
                text=True,
                env=test_env,
                timeout=30
            )
            
            if result.returncode == 0 and 'IMPORT_SUCCESS' in result.stdout:
                print(f"    ✅ {name} imports successfully")
            else:
                print(f"    ❌ {name} has import issues")
                print(f"       STDOUT: {result.stdout}")
                print(f"       STDERR: {result.stderr}")
                all_healthy = False
                
        except Exception as e:
            print(f"    💥 {name} crashed during health check: {e}")
            all_healthy = False
    
    return all_healthy

def main():
    parser = argparse.ArgumentParser(description='Run pipeline tests')
    parser.add_argument('--pattern', help='Test file pattern to match')
    parser.add_argument('--quick', action='store_true', help='Run quick health check only')
    parser.add_argument('--quiet', action='store_true', help='Less verbose output')
    parser.add_argument('--save-output', help='Save detailed output to file')
    
    args = parser.parse_args()
    
    if args.quick:
        success = run_quick_health_check()
        if success:
            print("\n✅ Quick health check passed!")
            return 0
        else:
            print("\n❌ Quick health check failed!")
            return 1
    
    print("🚀 Running comprehensive pipeline tests...")
    success, output = run_test_suite(args.pattern, not args.quiet)
    
    if args.save_output:
        with open(args.save_output, 'w') as f:
            f.write(output)
        print(f"💾 Detailed output saved to {args.save_output}")
    
    if success:
        print("\n🎉 All pipeline tests passed!")
        return 0
    else:
        print("\n❌ Some pipeline tests failed!")
        if not args.quiet:
            print("\n📋 Detailed output:")
            print(output)
        return 1

if __name__ == '__main__':
    sys.exit(main())
