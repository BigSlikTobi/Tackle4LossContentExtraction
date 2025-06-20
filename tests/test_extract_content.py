import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import sys
import os

# Adjust path to import module from parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.extraction.extractContent import extract_main_content #, main as run_main_extraction
# Importing litellm directly for mocking its specific errors if needed, though crawl4ai might wrap them.
# For now, we'll assume generic Exception or string checks as per current extractContent.py logic.
# import litellm

# Mock crawl4ai.AsyncWebCrawler and its Result object structure
class MockCrawl4aiResult:
    def __init__(self, extracted_content=None, error_message=None):
        self.extracted_content = extracted_content
        self.error_message = error_message # Assuming crawl4ai might return errors this way

class TestExtractMainContent(unittest.IsolatedAsyncioTestCase): # Use IsolatedAsyncioTestCase for async tests

    @patch('modules.extraction.extractContent.AsyncWebCrawler')
    @patch('modules.extraction.extractContent.asyncio.sleep', new_callable=AsyncMock) # Mock sleep
    async def test_extract_content_success(self, mock_sleep, MockAsyncWebCrawler):
        """Test successful content extraction."""
        mock_crawler_instance = MockAsyncWebCrawler.return_value.__aenter__.return_value
        expected_success_content = "This is a sufficiently long successful content string for testing. Over 50 chars."
        mock_crawler_instance.arun = AsyncMock(return_value=MockCrawl4aiResult(extracted_content=expected_success_content))

        url = "http://example.com/success"
        content = await extract_main_content(url)

        self.assertEqual(content, expected_success_content)
        mock_crawler_instance.arun.assert_called_once()
        # Check if arun was called with the url and other expected params (like extraction_strategy)
        args, kwargs = mock_crawler_instance.arun.call_args
        self.assertEqual(kwargs.get('url'), url)
        self.assertIsNotNone(kwargs.get('extraction_strategy'))

    @patch('modules.extraction.extractContent.AsyncWebCrawler')
    @patch('builtins.print') # To check log messages
    @patch('modules.extraction.extractContent.asyncio.sleep', new_callable=AsyncMock)
    async def test_extract_content_arun_generic_exception_first_try(self, mock_sleep, mock_print, MockAsyncWebCrawler):
        """Test generic Exception from arun on the first try, leading to retries and eventual failure."""
        mock_crawler_instance = MockAsyncWebCrawler.return_value.__aenter__.return_value
        mock_crawler_instance.arun = AsyncMock(side_effect=Exception("Generic crawl error"))

        url = "http://example.com/generic_fail"
        # Expected max_attempts from extractContent.py is 4
        expected_attempts = 4

        content = await extract_main_content(url)

        self.assertTrue(content.startswith(f"Failed to extract content after {expected_attempts} attempts."))
        self.assertIn("Generic crawl error", content)
        self.assertEqual(mock_crawler_instance.arun.call_count, expected_attempts)

        # Check log messages for retries and final error
        # Example: print(f"API error on attempt {attempt+1}: {error_str}")
        # Example: print(f"API attempt {attempt+1}/{max_attempts}, waiting {wait_time:.1f} seconds...")
        # There should be (expected_attempts -1) sleep calls
        self.assertEqual(mock_sleep.call_count, expected_attempts -1)

        # Check for some of the print calls (can be more specific if needed)
        # At least one "API error on attempt..." should be present for each attempt
        # At least one "API attempt... waiting..." should be present for retries
        error_logs_count = 0
        retry_wait_logs_count = 0
        for call_args in mock_print.call_args_list:
            args_tuple = call_args[0]
            if args_tuple: # Ensure there are positional arguments
                log_message = str(args_tuple[0])
                if "API error on attempt" in log_message:
                    error_logs_count += 1
                if "API attempt" in log_message and "waiting" in log_message:
                    retry_wait_logs_count +=1

        self.assertEqual(error_logs_count, expected_attempts)
        self.assertEqual(retry_wait_logs_count, expected_attempts -1)


    @patch('modules.extraction.extractContent.AsyncWebCrawler')
    @patch('builtins.print')
    @patch('modules.extraction.extractContent.asyncio.sleep', new_callable=AsyncMock)
    async def test_extract_content_insufficient_content_first_try_then_success(self, mock_sleep, mock_print, MockAsyncWebCrawler):
        """Test insufficient content on first try, then success on retry."""
        mock_crawler_instance = MockAsyncWebCrawler.return_value.__aenter__.return_value
        expected_successful_retry_content = "This is sufficient content on the second attempt, and it is definitely over fifty characters long."
        mock_crawler_instance.arun.side_effect = [
            MockCrawl4aiResult(extracted_content="short"), # First attempt: insufficient
            MockCrawl4aiResult(extracted_content=expected_successful_retry_content) # Second attempt: success
        ]

        url = "http://example.com/insufficient_then_success"
        content = await extract_main_content(url)

        self.assertEqual(content, expected_successful_retry_content)
        self.assertEqual(mock_crawler_instance.arun.call_count, 2) # Should succeed on 2nd attempt
        mock_sleep.assert_called_once() # One sleep between 1st and 2nd attempt

        # Verify "LLM returned insufficient content on attempt 1" is printed
        insufficient_log_found = False
        for call_args in mock_print.call_args_list:
            args_tuple = call_args[0]
            if args_tuple and "LLM returned insufficient content on attempt 1" in str(args_tuple[0]):
                insufficient_log_found = True
                break
        self.assertTrue(insufficient_log_found)

    @patch('modules.extraction.extractContent.AsyncWebCrawler')
    @patch('builtins.print')
    @patch('modules.extraction.extractContent.asyncio.sleep', new_callable=AsyncMock)
    async def test_extract_content_insufficient_content_all_attempts(self, mock_sleep, mock_print, MockAsyncWebCrawler):
        """Test insufficient content on all attempts."""
        mock_crawler_instance = MockAsyncWebCrawler.return_value.__aenter__.return_value
        # Simulate insufficient content for all 4 attempts
        mock_crawler_instance.arun.return_value = MockCrawl4aiResult(extracted_content="short")

        url = "http://example.com/insufficient_all_attempts"
        expected_attempts = 4

        content = await extract_main_content(url)

        # The function returns the best available content ("short") after all attempts
        self.assertEqual(content, "short")
        self.assertEqual(mock_crawler_instance.arun.call_count, expected_attempts)
        self.assertEqual(mock_sleep.call_count, expected_attempts - 1)

        # Verify "Using best available content after all attempts" is printed
        best_available_log_found = False
        for call_args in mock_print.call_args_list:
            args_tuple = call_args[0]
            if args_tuple and "Using best available content after all attempts" in str(args_tuple[0]):
                best_available_log_found = True
                break
        self.assertTrue(best_available_log_found)

    @patch('modules.extraction.extractContent.AsyncWebCrawler')
    @patch('builtins.print', new_callable=MagicMock) # Using MagicMock for print to check stderr
    @patch('modules.extraction.extractContent.asyncio.sleep', new_callable=AsyncMock)
    async def test_extract_content_outer_exception(self, mock_sleep, mock_print, MockAsyncWebCrawler):
        """Test an exception outside the retry loop (e.g., during AsyncWebCrawler setup)."""
        # Make the AsyncWebCrawler constructor call itself raise an error
        MockAsyncWebCrawler.side_effect = Exception("Crawler setup error")

        url = "http://example.com/outer_fail"
        content = await extract_main_content(url)

        expected_error_message_part = f"Extraction failed for {url}. Type: Exception, Error: Crawler setup error"
        self.assertEqual(content, expected_error_message_part)

        # Check that the error was printed to stderr
        # mock_print.assert_any_call(f"[ERROR] Outer exception during extraction for {url}. Type: Exception, Message: Crawler setup error", file=sys.stderr)
        # Check stderr by inspecting call_args_list
        stderr_logged = False
        for call in mock_print.call_args_list:
            args, kwargs = call
            if args and f"[ERROR] Outer exception during extraction for {url}. Type: Exception, Message: Crawler setup error" in args[0] and kwargs.get('file') == sys.stderr:
                stderr_logged = True
                break
        self.assertTrue(stderr_logged, "Error message was not logged to sys.stderr")


    @patch('modules.extraction.extractContent.AsyncWebCrawler')
    @patch('builtins.print')
    @patch('modules.extraction.extractContent.asyncio.sleep', new_callable=AsyncMock)
    async def test_extract_content_litellm_api_error_handling(self, mock_sleep, mock_print, MockAsyncWebCrawler):
        """Test handling of litellm.APIError leading to retry with modified strategy."""
        mock_crawler_instance = MockAsyncWebCrawler.return_value.__aenter__.return_value

        # Simulate litellm.APIError on first attempt, then success on second
        # The error message must contain "litellm.APIError" for current detection logic
        expected_litellm_retry_success_content = "Success after litellm error, and this content is also very long, well over fifty characters for sure."
        mock_crawler_instance.arun.side_effect = [
            Exception("Some litellm.APIError: Rate limit or something."),
            MockCrawl4aiResult(extracted_content=expected_litellm_retry_success_content)
        ]

        url = "http://example.com/litellm_fail_then_success"
        content = await extract_main_content(url)

        self.assertEqual(content, expected_litellm_retry_success_content)
        self.assertEqual(mock_crawler_instance.arun.call_count, 2)
        mock_sleep.assert_called_once() # One sleep between attempts

        # Verify that the strategy modification print log occurs (or check strategy object if possible)
        # For now, checking print log for "API error on attempt 1: Some litellm.APIError..."
        litellm_error_log_found = False
        attempt_log_found = False
        for call_args in mock_print.call_args_list:
            args_tuple = call_args[0]
            if args_tuple:
                log_msg = str(args_tuple[0])
                if "API error on attempt 1: Some litellm.APIError: Rate limit or something." in log_msg:
                    litellm_error_log_found = True
                # The strategy modification happens, then "API attempt 2/4, waiting..." is logged
                # The actual instruction change isn't logged, but the retry logic is.
                # We can also check that the LLMExtractionStrategy object's properties were changed.
                # This requires getting hold of the strategy object passed to arun.
                if "API attempt 2/4" in log_msg and "waiting" in log_msg: # Check for the retry log after the error
                    attempt_log_found = True


        self.assertTrue(litellm_error_log_found, "Log for litellm.APIError not found")
        self.assertTrue(attempt_log_found, "Log for retry after litellm.APIError not found")

        # More advanced: Check if the strategy's instructions and config were actually modified
        self.assertGreaterEqual(len(mock_crawler_instance.arun.call_args_list), 2)
        second_call_args, second_call_kwargs = mock_crawler_instance.arun.call_args_list[1]
        modified_strategy = second_call_kwargs.get('extraction_strategy') # type: LLMExtractionStrategy
        self.assertIsNotNone(modified_strategy)
        self.assertIn("Attempt 2:", modified_strategy.instructions)
        # Timeout is no longer dynamically adjusted in extractContent.py due to API limitations,
        # so we don't assert its change here. We've already asserted that a retry happened.


if __name__ == '__main__':
    unittest.main()
