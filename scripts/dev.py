#!/usr/bin/env python3
"""
Development helper script for common pipeline tasks.
This script provides shortcuts for testing, running, and maintaining the pipelines.
It includes commands for:
- Quick health checks
- Full test suite execution
- Running the cleanup and cluster pipelines
- Syntax checking and linting
- Combined checks for CI/CD environments
It is designed to be run from the command line with various subcommands.
Usage:
    python dev.py <command>
Available commands:
    quick-test   : Run quick health checks
    test         : Run comprehensive pipeline tests
    all-tests    : Run full pytest suite
    cleanup      : Run the cleanup pipeline
    cluster      : Run the cluster pipeline
    syntax       : Check Python syntax for pipeline files
    lint         : Run code linting
    check        : Run syntax check + quick test
    ci           : Run all checks (syntax + lint + tests)
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path

# Get project root and add src directory to PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

def run_command(cmd, description, cwd=None):
    """
    Run a command and return success status.
    Args:
        cmd (str): The command to run.
        description (str): Description of the command for logging.
        cwd (str): Optional working directory to run the command in.
    Returns:
        bool: True if command succeeded, False otherwise.
    """
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd or PROJECT_ROOT, 
                              capture_output=False, text=True)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            return True
        else:
            print(f"❌ {description} failed with code {result.returncode}")
            return False
    except Exception as e:
        print(f"💥 {description} crashed: {e}")
        return False

def quick_test():
    """
    Run quick health checks.
    This runs a minimal set of tests to ensure the pipeline is functional.
    Args:
        None
    Returns:
        bool: True if quick tests passed, False otherwise.
    """
    return run_command(
        f"cd {PROJECT_ROOT} && python scripts/run_pipeline_tests.py --quick",
        "Quick pipeline health check"
    )

def full_test():
    """Run comprehensive tests.
    This runs the full test suite to ensure all components are functioning correctly.
    Args:
        None
    Returns:
        bool: True if full tests passed, False otherwise.
    """
    return run_command(
        f"cd {PROJECT_ROOT} && python scripts/run_pipeline_tests.py",
        "Full pipeline test suite"
    )

def run_cleanup_pipeline():
    """
    Run the cleanup pipeline.
    This pipeline processes unprocessed articles, extracts content, creates embeddings, 
    and stores them in a vector database.
    Args:
        None
    Returns:
        bool: True if cleanup pipeline succeeded, False otherwise.
    """
    return run_command(
        f"cd {PROJECT_ROOT} && python scripts/cleanup_pipeline.py",
        "Cleanup pipeline execution"
    )

def run_cluster_pipeline():
    """
    Run the cluster pipeline.
    This pipeline groups articles into clusters based on their content and metadata.
    Args:
        None
    Returns:
        bool: True if cluster pipeline succeeded, False otherwise.
    """
    return run_command(
        f"cd {PROJECT_ROOT} && python scripts/cluster_pipeline.py",
        "Cluster pipeline execution"
    )

def run_all_tests():
    """
    Run the full pytest suite.
    This runs all tests in the project to ensure everything is functioning as expected.
    Args:
        None
    Returns:
        bool: True if all tests passed, False otherwise."""
    return run_command(
        f"cd {PROJECT_ROOT} && python -m pytest tests/ -v",
        "Full pytest suite"
    )

def check_syntax():
    """
    Check Python syntax for all pipeline files.
    This runs a syntax check on the specified files to ensure they are valid Python code.
    Args:
        None
    Returns:
        bool: True if syntax check passed, False otherwise."""
    files_to_check = [
        "scripts/cleanup_pipeline.py",
        "scripts/cluster_pipeline.py",
        "src/core/clustering/cluster_manager.py",
        "src/modules/processing/article_processor.py"
    ]
    
    all_good = True
    for file_path in files_to_check:
        full_path = PROJECT_ROOT / file_path
        if full_path.exists():
            result = run_command(
                f"python -m py_compile {full_path}",
                f"Syntax check for {file_path}"
            )
            all_good = all_good and result
        else:
            print(f"⚠️  File not found: {file_path}")
            all_good = False
    
    return all_good

def lint_code():
    """
    Run basic linting on pipeline files.
    This checks the code style and formatting using flake8.
    Args:
        None
    Returns:
        bool: True if linting passed, False otherwise.
    """
    return run_command(
        f"cd {PROJECT_ROOT} && python -m flake8 scripts/cleanup_pipeline.py scripts/cluster_pipeline.py src/core/ src/modules/ --max-line-length=120 --ignore=E501,W503",
        "Code linting"
    )

def main():
    parser = argparse.ArgumentParser(description='Development helper for pipelines')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Test commands
    subparsers.add_parser('quick-test', help='Run quick health checks')
    subparsers.add_parser('test', help='Run comprehensive pipeline tests')
    subparsers.add_parser('all-tests', help='Run full pytest suite')
    
    # Pipeline commands
    subparsers.add_parser('cleanup', help='Run cleanup pipeline')
    subparsers.add_parser('cluster', help='Run cluster pipeline')
    
    # Code quality commands
    subparsers.add_parser('syntax', help='Check Python syntax')
    subparsers.add_parser('lint', help='Run code linting')
    
    # Combined commands
    subparsers.add_parser('check', help='Run syntax check + quick test')
    subparsers.add_parser('ci', help='Run all checks (syntax + lint + tests)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    success = True
    
    if args.command == 'quick-test':
        success = quick_test()
    elif args.command == 'test':
        success = full_test()
    elif args.command == 'all-tests':
        success = run_all_tests()
    elif args.command == 'cleanup':
        success = run_cleanup_pipeline()
    elif args.command == 'cluster':
        success = run_cluster_pipeline()
    elif args.command == 'syntax':
        success = check_syntax()
    elif args.command == 'lint':
        success = lint_code()
    elif args.command == 'check':
        success = check_syntax() and quick_test()
    elif args.command == 'ci':
        success = (check_syntax() and 
                  lint_code() and 
                  quick_test() and 
                  full_test())
    
    if success:
        print(f"\n🎉 Command '{args.command}' completed successfully!")
        return 0
    else:
        print(f"\n❌ Command '{args.command}' failed!")
        return 1

if __name__ == '__main__':
    sys.exit(main())
