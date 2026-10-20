import os
import shutil
import tempfile
import unittest
from pathlib import Path

from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model


class TestPatchCoder(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.tempdir = tempfile.mkdtemp()
        os.chdir(self.tempdir)

        self.GPT35 = Model("gpt-3.5-turbo")

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def make_coder(self, io=None):
        if io is None:
            io = InputOutput(yes=True, pretty=False, fancy_input=False)
        return Coder.create(
            main_model=self.GPT35,
            edit_format="patch",
            io=io,
            use_git=False,
        )

    def test_add_file_creates_new_file(self):
        """`*** Add File` must create the file, even though prepare_to_edit() touches it."""
        coder = self.make_coder()
        coder.partial_response_content = (
            "*** Begin Patch\n"
            "*** Add File: hello.py\n"
            "+def hello():\n"
            '+    print("hello")\n'
            "*** End Patch\n"
        )

        coder.apply_updates()

        self.assertEqual(coder.num_malformed_responses, 0)
        hello = Path("hello.py")
        self.assertTrue(hello.exists())
        self.assertEqual(hello.read_text(), 'def hello():\n    print("hello")\n')

    def test_add_file_fills_empty_placeholder(self):
        """An empty file left behind (eg by an earlier failed attempt) is creatable."""
        Path("hello.py").touch()
        coder = self.make_coder()
        coder.partial_response_content = (
            "*** Begin Patch\n*** Add File: hello.py\n+print('hi')\n*** End Patch\n"
        )

        coder.apply_updates()

        self.assertEqual(coder.num_malformed_responses, 0)
        self.assertEqual(Path("hello.py").read_text(), "print('hi')\n")

    def test_add_file_over_existing_file_is_rejected(self):
        """Add File must still refuse to clobber a file that has content."""
        Path("hello.py").write_text("print('existing')\n")
        coder = self.make_coder()
        coder.partial_response_content = (
            "*** Begin Patch\n*** Add File: hello.py\n+print('new')\n*** End Patch\n"
        )

        coder.apply_updates()

        self.assertEqual(coder.num_malformed_responses, 1)
        self.assertIn("ADD Error: File already exists: hello.py", coder.reflected_message)
        self.assertEqual(Path("hello.py").read_text(), "print('existing')\n")


if __name__ == "__main__":
    unittest.main()
