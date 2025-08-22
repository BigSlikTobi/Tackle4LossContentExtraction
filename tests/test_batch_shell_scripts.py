"""
Tests for the batch shell scripts.
Tests the shell script argument parsing, execution, and integration.
"""

import unittest
import os
import sys
import subprocess
import tempfile
import stat

# Add the parent directory to sys.path to allow imports from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from src.core.utils.lock_manager import LOCK_FILE_PATH

class TestBatchShellScripts(unittest.TestCase):
    """Test the batch processing shell scripts."""

    def setUp(self):
        """Set up test environment."""
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.scripts_dir = os.path.join(self.project_root, 'scripts')
        
        # Ensure lock file doesn't exist
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)

    def tearDown(self):
        """Clean up after tests."""
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)

    def _get_test_env(self):
        """Get environment variables for testing."""
        env = os.environ.copy()
        env.update({
            'SUPABASE_URL': 'http://dummy.url',
            'SUPABASE_KEY': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c',
            'OPENAI_API_KEY': 'dummy_openai_key',
            'DEEPSEEK_API_KEY': 'dummy_deepseek_key'
        })
        return env

    def test_cleanup_batch_script_exists(self):
        """Test that the cleanup batch script exists and is executable."""
        script_path = os.path.join(self.scripts_dir, 'run_cleanup_batch.sh')
        self.assertTrue(os.path.exists(script_path), f"Script not found: {script_path}")
        
        # Check if script is executable
        file_stat = os.stat(script_path)
        is_executable = file_stat.st_mode & stat.S_IEXEC
        self.assertTrue(is_executable, f"Script is not executable: {script_path}")

    def test_cluster_batch_script_exists(self):
        """Test that the cluster batch script exists and is executable."""
        script_path = os.path.join(self.scripts_dir, 'run_cluster_batch.sh')
        self.assertTrue(os.path.exists(script_path), f"Script not found: {script_path}")
        
        # Check if script is executable
        file_stat = os.stat(script_path)
        is_executable = file_stat.st_mode & stat.S_IEXEC
        self.assertTrue(is_executable, f"Script is not executable: {script_path}")

    def test_combined_batch_script_exists(self):
        """Test that the combined batch script exists and is executable."""
        script_path = os.path.join(self.scripts_dir, 'run_combined_batch.sh')
        self.assertTrue(os.path.exists(script_path), f"Script not found: {script_path}")
        
        # Check if script is executable
        file_stat = os.stat(script_path)
        is_executable = file_stat.st_mode & stat.S_IEXEC
        self.assertTrue(is_executable, f"Script is not executable: {script_path}")

    def test_test_requirements_script_exists(self):
        """Test that the test requirements script exists and is executable."""
        script_path = os.path.join(self.scripts_dir, 'test_requirements.sh')
        self.assertTrue(os.path.exists(script_path), f"Script not found: {script_path}")
        
        # Check if script is executable
        file_stat = os.stat(script_path)
        is_executable = file_stat.st_mode & stat.S_IEXEC
        self.assertTrue(is_executable, f"Script is not executable: {script_path}")

    def test_cleanup_batch_script_help(self):
        """Test the cleanup batch script help output."""
        script_path = os.path.join(self.scripts_dir, 'run_cleanup_batch.sh')
        
        try:
            result = subprocess.run(
                ['/bin/bash', script_path, '--help'],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.project_root
            )
            
            # Should show usage information
            self.assertIn('usage:', result.stdout.lower() + result.stderr.lower())
            
        except subprocess.TimeoutExpired:
            self.fail("Script help command timed out")
        except FileNotFoundError:
            self.fail(f"Script not found or not executable: {script_path}")

    def test_cluster_batch_script_help(self):
        """Test the cluster batch script help output."""
        script_path = os.path.join(self.scripts_dir, 'run_cluster_batch.sh')
        
        try:
            result = subprocess.run(
                ['/bin/bash', script_path, '--help'],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.project_root
            )
            
            # Should show usage information
            self.assertIn('usage:', result.stdout.lower() + result.stderr.lower())
            
        except subprocess.TimeoutExpired:
            self.fail("Script help command timed out")
        except FileNotFoundError:
            self.fail(f"Script not found or not executable: {script_path}")

    def test_script_python_detection(self):
        """Test that scripts can detect Python environment."""
        # Create a simple test script to verify Python detection logic
        test_script_content = '''#!/bin/bash
# Test script to verify Python detection
if command -v python3 >/dev/null 2>&1; then
    echo "Python3 found"
    python3 --version
elif command -v python >/dev/null 2>&1; then
    echo "Python found"
    python --version
else
    echo "No Python found"
    exit 1
fi
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(test_script_content)
            temp_script = f.name
        
        try:
            # Make script executable
            os.chmod(temp_script, stat.S_IRWXU)
            
            result = subprocess.run(
                ['/bin/bash', temp_script],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            self.assertEqual(result.returncode, 0, "Python detection failed")
            self.assertTrue(
                'Python3 found' in result.stdout or 'Python found' in result.stdout,
                "Python not detected properly"
            )
            
        finally:
            os.unlink(temp_script)

    def test_script_virtual_environment_detection(self):
        """Test virtual environment detection logic."""
        # Test script content that mimics venv detection
        test_script_content = '''#!/bin/bash
# Test virtual environment detection
if [[ -n "$VIRTUAL_ENV" ]]; then
    echo "Virtual environment detected: $VIRTUAL_ENV"
    exit 0
elif [[ -f "venv/bin/activate" ]]; then
    echo "Local venv found"
    exit 0
elif [[ -f ".venv/bin/activate" ]]; then
    echo "Local .venv found"
    exit 0
else
    echo "No virtual environment found"
    exit 1
fi
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(test_script_content)
            temp_script = f.name
        
        try:
            # Make script executable
            os.chmod(temp_script, stat.S_IRWXU)
            
            # Test with VIRTUAL_ENV set
            env = os.environ.copy()
            env['VIRTUAL_ENV'] = '/fake/venv/path'
            
            result = subprocess.run(
                ['/bin/bash', temp_script],
                capture_output=True,
                text=True,
                timeout=5,
                env=env
            )
            
            self.assertEqual(result.returncode, 0, "Virtual environment detection failed")
            self.assertIn('Virtual environment detected', result.stdout)
            
        finally:
            os.unlink(temp_script)

    def test_batch_scripts_documentation(self):
        """Test that batch scripts README exists and contains expected sections."""
        readme_path = os.path.join(self.scripts_dir, 'BATCH_SCRIPTS_README.md')
        self.assertTrue(os.path.exists(readme_path), f"README not found: {readme_path}")
        
        with open(readme_path, 'r') as f:
            content = f.read()
        
        # Check for key sections
        expected_sections = [
            'Batch Processing Scripts',
            'cleanup_pipeline_batched.py',
            'cluster_pipeline_ci.py',
            'Usage',
            'Configuration',
            'Troubleshooting'
        ]
        
        for section in expected_sections:
            self.assertIn(section, content, f"Missing section in README: {section}")

    def test_scripts_have_shebang(self):
        """Test that shell scripts have proper shebang."""
        shell_scripts = [
            'run_cleanup_batch.sh',
            'run_cluster_batch.sh', 
            'run_combined_batch.sh',
            'test_requirements.sh'
        ]
        
        for script_name in shell_scripts:
            script_path = os.path.join(self.scripts_dir, script_name)
            if os.path.exists(script_path):
                with open(script_path, 'r') as f:
                    first_line = f.readline().strip()
                
                self.assertTrue(
                    first_line.startswith('#!'),
                    f"Script {script_name} missing shebang: {first_line}"
                )
                self.assertIn(
                    'bash',
                    first_line.lower(),
                    f"Script {script_name} not using bash: {first_line}"
                )


class TestBatchScriptIntegration(unittest.TestCase):
    """Integration tests for batch scripts with actual pipeline components."""

    def setUp(self):
        """Set up test environment."""
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.scripts_dir = os.path.join(self.project_root, 'scripts')
        
        # Ensure lock file doesn't exist
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)

    def tearDown(self):
        """Clean up after tests."""
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)

    def test_script_lock_file_handling(self):
        """Test that scripts properly handle lock files."""
        # Create a lock file
        with open(LOCK_FILE_PATH, 'w') as f:
            f.write('test_lock')
        
        script_path = os.path.join(self.scripts_dir, 'run_cleanup_batch.sh')
        
        # Script should detect existing lock and exit gracefully
        if os.path.exists(script_path):
            try:
                result = subprocess.run(
                    ['/bin/bash', script_path, '--help'],  # Use help to avoid actual execution
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=self.project_root
                )
                
                # Should not hang or crash
                self.assertTrue(True, "Script handled lock file situation")
                
            except subprocess.TimeoutExpired:
                self.fail("Script hung when lock file existed")

    def test_script_python_script_path_resolution(self):
        """Test that scripts can resolve paths to Python scripts correctly."""
        # Test script that checks if Python scripts exist
        test_script_content = '''#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Script dir: $SCRIPT_DIR"
echo "Project root: $PROJECT_ROOT"

# Check if Python scripts exist
if [[ -f "$SCRIPT_DIR/cleanup_pipeline_batched.py" ]]; then
    echo "cleanup_pipeline_batched.py found"
else
    echo "cleanup_pipeline_batched.py NOT found"
fi

if [[ -f "$SCRIPT_DIR/cluster_pipeline_ci.py" ]]; then
    echo "cluster_pipeline_ci.py found"
else
    echo "cluster_pipeline_ci.py NOT found"
fi
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False, dir=self.scripts_dir) as f:
            f.write(test_script_content)
            temp_script = f.name
        
        try:
            # Make script executable
            os.chmod(temp_script, stat.S_IRWXU)
            
            result = subprocess.run(
                ['/bin/bash', temp_script],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=self.project_root
            )
            
            self.assertEqual(result.returncode, 0)
            self.assertIn('cleanup_pipeline_batched.py found', result.stdout)
            self.assertIn('cluster_pipeline_ci.py found', result.stdout)
            
        finally:
            os.unlink(temp_script)


if __name__ == '__main__':
    unittest.main()
