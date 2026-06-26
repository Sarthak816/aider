import importlib
import os
import ssl
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
    _import_error = None

    def __getattr__(self, name):
        if name in ("_lazy_module", "_import_error"):
            raise AttributeError(name)
        if self._import_error:
            raise self._import_error
        if self._lazy_module is None:
            self._load_litellm()
        return getattr(self._lazy_module, name)

    def _load_litellm(self):
        if VERBOSE:
            print("Loading litellm...")

        try:
            self._lazy_module = importlib.import_module("litellm")
        except Exception as e:
            if "partially initialized module" in str(e) and "circular import" in str(e):
                wrapped = ImportError(
                    "litellm failed to import due to a circular dependency in your installed"
                    " version. Try upgrading or reinstalling litellm:\n"
                    "  pip install --upgrade litellm"
                )
                self._import_error = wrapped
                raise wrapped from e
            if isinstance(e, ssl.SSLError) and "NOT_ENOUGH_DATA" in str(e):
                wrapped = ImportError(
                    "litellm failed to import due to an SSL certificate store error on"
                    " Windows. This is a known OpenSSL 3.0.21+ compatibility issue."
                    " Try:\n"
                    "  1. Upgrade Python to the latest patch version (3.9.26+, 3.10.x,"
                    " 3.11.x, 3.12.x, 3.13.x or newer)\n"
                    "  2. Or set SSL_CERT_FILE to a valid CA bundle:\n"
                    "     pip install certifi\n"
                    "     set SSL_CERT_FILE=$(python -c \"import certifi; print(certifi.where())\")\n"
                    "  3. Or install pip-system-certs to sync with Windows cert store:\n"
                    "     pip install pip-system-certs"
                )
                self._import_error = wrapped
                raise wrapped from e
            self._import_error = e
            raise

        self._lazy_module.suppress_debug_info = True
        self._lazy_module.set_verbose = False
        self._lazy_module.drop_params = True
        self._lazy_module._logging._disable_debugging()


litellm = LazyLiteLLM()

__all__ = [litellm]
