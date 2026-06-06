import importlib
import os
import warnings

from aider.dump import dump  # noqa: F401

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

AIDER_SITE_URL = "https://aider.chat"
AIDER_APP_NAME = "Aider"

os.environ["OR_SITE_URL"] = AIDER_SITE_URL
os.environ["OR_APP_NAME"] = AIDER_APP_NAME
os.environ["LITELLM_MODE"] = "PRODUCTION"

# `import litellm` takes 1.5 seconds, defer it!

VERBOSE = False


class LazyLiteLLM:
    _lazy_module = None

    def __getattr__(self, name):
        if name == "_lazy_module":
            return super()
        self._load_litellm()
        return getattr(self._lazy_module, name)

    def _load_litellm(self):
        if self._lazy_module is not None:
            return

        if VERBOSE:
            print("Loading litellm...")

        try:
            self._lazy_module = importlib.import_module("litellm")
        except ModuleNotFoundError as err:
            print(
                "Error: Failed to import litellm - a core dependency is missing or"
                " incompatible."
            )
            print(f"Missing module: {err.name}")
            print(
                "This is often caused by incompatible dependency versions. Try"
                " reinstalling aider:"
            )
            print()
            print("    pip install --upgrade aider-chat")
            print()
            print(
                "Or, if you installed in development mode, upgrade the openai package:"
            )
            print()
            print("    pip install --upgrade openai")
            raise

        self._lazy_module.suppress_debug_info = True
        self._lazy_module.set_verbose = False
        self._lazy_module.drop_params = True
        self._lazy_module._logging._disable_debugging()


litellm = LazyLiteLLM()

__all__ = [litellm]
