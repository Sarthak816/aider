from unittest import TestCase, mock

from aider.llm import LazyLiteLLM


class TestLazyLiteLLM(TestCase):
    def test_missing_dependency_names_the_package(self):
        # #5792: litellm imports aiohttp, which was missing in the reporter's env
        err = ModuleNotFoundError("No module named 'aiohttp'", name="aiohttp")
        lazy = LazyLiteLLM()

        with mock.patch("aider.llm.importlib.import_module", side_effect=err):
            with self.assertRaises(ModuleNotFoundError) as ctx:
                lazy._load_litellm()

        self.assertEqual(ctx.exception.name, "aiohttp")
        self.assertIn("'aiohttp'", str(ctx.exception))
        self.assertIn("pip install aiohttp", str(ctx.exception))
        self.assertIn("pip install --upgrade --force-reinstall aider-chat", str(ctx.exception))
        self.assertIsNone(lazy._lazy_module)

    def test_missing_dependency_without_package_name(self):
        err = ModuleNotFoundError("No module named 'aiohttp'")
        lazy = LazyLiteLLM()

        with mock.patch("aider.llm.importlib.import_module", side_effect=err):
            with self.assertRaises(ModuleNotFoundError) as ctx:
                lazy._load_litellm()

        self.assertIn("a required dependency is missing", str(ctx.exception))
        self.assertIn("pip install --upgrade --force-reinstall aider-chat", str(ctx.exception))
