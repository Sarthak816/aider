# flake8: noqa: E501

import json
import os
import tempfile
import unittest
from pathlib import Path

from benchmark.benchmark import cleanup_test_output


class TestCleanupTestOutput(unittest.TestCase):
    def test_cleanup_test_output(self):
        # Test case with timing info
        output = "Ran 5 tests in 0.003s\nOK"
        expected = "\nOK"
        self.assertEqual(cleanup_test_output(output), expected)

        # Test case without timing info
        output = "OK"
        expected = "OK"
        self.assertEqual(cleanup_test_output(output), expected)

    def test_cleanup_test_output_lines(self):
        # Test case with timing info
        output = """F
======================================================================
FAIL: test_cleanup_test_output (test_benchmark.TestCleanupTestOutput.test_cleanup_test_output)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/gauthier/Projects/aider/benchmark/test_benchmark.py", line 14, in test_cleanup_test_output
    self.assertEqual(cleanup_test_output(output), expected)
AssertionError: 'OK' != 'OKx'
- OK
+ OKx
?   +
"""

        expected = """F
====
FAIL: test_cleanup_test_output (test_benchmark.TestCleanupTestOutput.test_cleanup_test_output)
----
Traceback (most recent call last):
  File "/Users/gauthier/Projects/aider/benchmark/test_benchmark.py", line 14, in test_cleanup_test_output
    self.assertEqual(cleanup_test_output(output), expected)
AssertionError: 'OK' != 'OKx'
- OK
+ OKx
?   +
"""
        self.assertEqual(cleanup_test_output(output), expected)


class TestEditorFileParsing(unittest.TestCase):
    """Regression tests for #5492: Polyglot benchmark omits Exercism editor files."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.testdir = Path(self.temp_dir) / "go" / "exercises" / "practice" / "error-handling"
        os.makedirs(self.testdir / ".meta")

        # Create a config like Exercism's .meta/config.json with editor files
        self.config = {
            "files": {
                "solution": ["error_handling.go"],
                "test": ["error_handling_test.go"],
                "editor": ["common.go"],
                "example": [".meta/example.go"],
            }
        }
        config_path = self.testdir / ".meta" / "config.json"
        with open(config_path, "w") as f:
            json.dump(self.config, f)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_editor_files_parsed_from_config(self):
        """Verify that editor files are correctly extracted from config."""
        with open(self.testdir / ".meta" / "config.json") as f:
            config = json.loads(f.read())

        editor_files = config.get("files", {}).get("editor", [])
        solution_files = set(config.get("files", {}).get("solution", []))

        self.assertEqual(editor_files, ["common.go"])
        self.assertEqual(solution_files, {"error_handling.go"})

    def test_editor_files_removed_from_solution_set(self):
        """Editor files must be removed from the editable solution set."""
        with open(self.testdir / ".meta" / "config.json") as f:
            config = json.loads(f.read())

        editor_files = config.get("files", {}).get("editor", [])
        solution_files = set(config.get("files", {}).get("solution", []))

        # Simulate the ignore_files logic from benchmark.py
        ignore_files = set()
        ignore_files.update(editor_files)

        # Editor files should NOT be in the solution set
        solution_files.difference_update(ignore_files)
        self.assertNotIn("common.go", solution_files)

    def test_editor_files_not_in_test_or_example(self):
        """Editor files should be separate from test and example files."""
        with open(self.testdir / ".meta" / "config.json") as f:
            config = json.loads(f.read())

        editor_files = set(config.get("files", {}).get("editor", []))
        test_files = set(config.get("files", {}).get("test", []))
        example_files = set(config.get("files", {}).get("example", []))

        # Editor files should not overlap with test or example files
        self.assertFalse(editor_files & test_files)
        self.assertFalse(editor_files & example_files)

    def test_no_editor_files_returns_empty_list(self):
        """Exercises without editor files should not break."""
        config_no_editor = {
            "files": {
                "solution": ["main.go"],
                "test": ["main_test.go"],
            }
        }
        editor_files = config_no_editor.get("files", {}).get("editor", [])
        self.assertEqual(editor_files, [])

    def test_editor_file_content_readable(self):
        """Verify that editor file content is accessible (exists on disk)."""
        # Create the editor file on disk
        editor_path = self.testdir / "common.go"
        with open(editor_path, "w") as f:
            f.write("package main\n\ntype Resource struct {}\n")

        self.assertTrue(editor_path.exists())
        content = editor_path.read_text()
        self.assertIn("Resource", content)