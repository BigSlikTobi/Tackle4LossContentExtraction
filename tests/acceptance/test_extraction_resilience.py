import unittest
from unittest.mock import patch, MagicMock, AsyncMock, call
import asyncio
import sys
import os
import json
import logging

# Adjust path to import module from the project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

# Modules to be tested or that contain components to be mocked
from src.modules.extraction.extractContent import main as run_extraction_main, extract_main_content
# Mocked crawl4ai result structure (simplified)
class MockCrawl4aiResult:
    def __init__(self, extracted_content=None, error_message=None):
        self.extracted_content = extracted_content
        self.error_message = error_message

# Configure a simple logger for the test output
test_logger = logging.getLogger("AcceptanceTestLogger_Extraction")
test_logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler(sys.stdout) # Output to stdout for this conceptual test
test_logger.addHandler(stream_handler)

class TestExtractionResilience(unittest.IsolatedAsyncioTestCase): # Use IsolatedAsyncioTestCase for async tests

    def setUp(self):
        self.sample_articles_for_extraction = [
            {"id": "art1", "url": "http://example.com/success_article"},
            {"id": "art2", "url": "http://example.com/crawl_error_article"},
            {"id": "art3", "url": "http://example.com/insufficient_content_article"},
            {"id": "art4", "url": "http://example.com/another_success_article"},
        ]
        self.long_content = "This is a long and valid piece of content that is definitely over fifty characters long."
        self.short_content = "Too short."

    @patch('src.modules.extraction.extractContent.get_unprocessed_articles')
    @patch('src.modules.extraction.extractContent.AsyncWebCrawler') # To mock arun
    @patch('builtins.open', new_callable=unittest.mock.mock_open) # To mock json.dump's file writing
    @patch('json.dump') # To capture what's "written" to file
    @patch('builtins.print') # To capture log messages from main and extract_main_content
    @patch('src.modules.extraction.extractContent.asyncio.sleep', new_callable=AsyncMock) # Mock sleep in extract_main_content
    def test_extraction_failures_are_handled(self, mock_asyncio_sleep, mock_builtin_print, mock_json_dump, mock_file_open, MockAsyncWebCrawler, mock_get_unprocessed_articles):
        test_logger.info("\n--- Scenario 2: Web Scraping/Extraction Failure ---")

        mock_get_unprocessed_articles.return_value = self.sample_articles_for_extraction

        # Configure AsyncWebCrawler.arun mock behavior
        mock_crawler_instance = MockAsyncWebCrawler.return_value.__aenter__.return_value

        async def arun_side_effect(url, **kwargs):
            if url == "http://example.com/success_article":
                return MockCrawl4aiResult(extracted_content=self.long_content)
            elif url == "http://example.com/crawl_error_article":
                # This will be caught by the retry loop first, then by the outer try-except in extract_main_content
                raise Exception("Simulated crawl/network error")
            elif url == "http://example.com/insufficient_content_article":
                # extract_main_content's retry loop will try a few times then return this
                return MockCrawl4aiResult(extracted_content=self.short_content)
            elif url == "http://example.com/another_success_article":
                return MockCrawl4aiResult(extracted_content=self.long_content + " (Article 4)")
            return MockCrawl4aiResult(extracted_content=None) # Default for any other URL

        mock_crawler_instance.arun = AsyncMock(side_effect=arun_side_effect)

        # --- Execution ---
        test_logger.info("Running main extraction process...")
        # Run the main function from the script
        run_extraction_main()


        # --- Verification ---
        test_logger.info("\nVerifying results...")

        # IMPORTANT: Print captured logs immediately for debugging before any assertions
        captured_prints = [str(call_args[0][0]) if call_args[0] else "" for call_args in mock_builtin_print.call_args_list]
        test_logger.info(f"Captured print outputs for debugging:\n{json.dumps(captured_prints, indent=2)}") # Use the correct logger name

        # 1. Check logs for appropriate error messages (via mocked print)
        # extract_main_content prints errors to sys.stderr if outer exception, or stdout for retry attempts / insufficient content
        # The main loop in extractContent.py prints warnings or success messages.

        # Example logs to check:
        # - Article 2 (crawl_error_article):
        #   - Multiple "API error on attempt..." (from extract_main_content retry loop)
        #   - Final error from extract_main_content: "[ERROR] Outer exception during extraction for http://example.com/crawl_error_article..." (if error escapes retry)
        #     OR "Failed to extract content after X attempts. Last error: Simulated crawl/network error"
        #   - From main loop: "Warning: Extraction issue for http://example.com/crawl_error_article"
        # - Article 3 (insufficient_content_article):
        #   - Multiple "LLM returned insufficient content on attempt..."
        #   - "Using best available content after all attempts" (if it returns the short content)
        #   - From main loop: "Warning: Extraction issue for http://example.com/insufficient_content_article"

        # captured_prints = [args[0] for args, kwargs in mock_builtin_print.call_args_list] # Old line
        # # test_logger.info(f"Captured print outputs:\n{json.dumps(captured_prints, indent=2)}") # Moved up


        # For art2 (crawl error)
        self.assertTrue(any("API error on attempt" in str(log) and "Simulated crawl/network error" in str(log) for log in captured_prints))
        self.assertTrue(any("Warning: Extraction issue for http://example.com/crawl_error_article" in str(log) for log in captured_prints))

        # For art3 (insufficient content)
        self.assertTrue(any("LLM returned insufficient content on attempt" in str(log) for log in captured_prints))
        self.assertTrue(any("Using best available content after all attempts" in str(log) for log in captured_prints))
        # The main loop will consider short content a "success" if it's returned, not a "warning"
        self.assertTrue(any(f"Successfully extracted {len(self.short_content)} characters from http://example.com/insufficient_content_article" in str(log) for log in captured_prints))

        # For art1 & art4 (success)
        self.assertTrue(any(f"Successfully extracted {len(self.long_content)} characters from http://example.com/success_article" in str(log) for log in captured_prints))
        self.assertTrue(any(f"Successfully extracted {len(self.long_content + ' (Article 4)')} characters from http://example.com/another_success_article" in str(log) for log in captured_prints))

        test_logger.info("Verified: Log messages for successes, warnings, and errors.")

        # 2. Check output (captured from json.dump)
        # The new pipeline creates two outputs: extracted_contents.json and cleaned_contents.json
        # We'll check the cleaned_contents.json which contains processed articles
        self.assertTrue(mock_json_dump.called, "json.dump was not called.")
        
        # Get the last call which should be the cleaned_contents.json
        output_data = mock_json_dump.call_args_list[-1][0][0]
        
        # Verify that all articles were processed (should have dictionaries with extracted fields)
        self.assertIn("art1", output_data)
        self.assertIn("art2", output_data)
        self.assertIn("art3", output_data)
        self.assertIn("art4", output_data)
        
        # Verify structure of processed articles (they should be dictionaries with extracted fields)
        for article_id in ["art1", "art2", "art3", "art4"]:
            article = output_data[article_id]
            self.assertIsInstance(article, dict)
            self.assertIn("title", article)
            self.assertIn("publication_date", article)
            self.assertIn("author", article)
            self.assertIn("main_content", article)
            self.assertIn("content_type", article)
            self.assertIn("type_confidence", article)
        
        # art1 should have processed the long content successfully 
        self.assertEqual(len(output_data["art1"]["main_content"]), 88)
        
        # art2 should show some error handling (was crawl error, should have error content)
        self.assertTrue(len(output_data["art2"]["main_content"]) > 0)
        
        # art3 should have the short content (was insufficient content)
        self.assertEqual(len(output_data["art3"]["main_content"]), 10)
        
        # art4 should have processed the long content with article 4 suffix
        self.assertEqual(len(output_data["art4"]["main_content"]), 100)

        test_logger.info("Verified: Output JSON content is as expected.")

        # 3. The script completes without crashing (implicitly verified by test completion)
        test_logger.info("Verified: Script completed without crashing.")
        test_logger.info("--- Test Scenario 2 Complete ---")

if __name__ == '__main__':
    # To run this specific test file
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestExtractionResilience)
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
    asyncio.run(runner.run(suite)) # Use asyncio.run if test case methods are async and runner doesn't handle it by default
                                   # However, IsolatedAsyncioTestCase handles its own loop.
                                   # For direct script execution, it might be simpler to just call:
                                   # unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
                                   # but since it's async, this setup is more robust.
    # A simpler way for direct execution of async tests if your unittest version supports it well:
    # unittest.main(verbosity=2)
    # For this conceptual test, this runner setup is okay.

    # Let's use the standard way for IsolatedAsyncioTestCase
    # unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
    # For running directly, this is simpler for async:
    async def run_tests():
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(TestExtractionResilience)
        runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
        runner.run(suite)

    if __name__ == '__main__':
        asyncio.run(run_tests())
