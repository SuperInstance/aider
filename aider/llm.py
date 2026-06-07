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

# ── SuperInstance: Configure z.ai / DeepInfra providers ──────────────
# These environment variables tell litellm where to route requests
# when using openai/ prefixed models with our providers.
#
# Users should set ZAI_API_KEY and DEEPINFRA_API_KEY in their environment.
# The base URLs default to the standard endpoints.
#
# To use z.ai as primary (default):
#   export ZAI_API_KEY="your-key"
#   export OPENAI_API_KEY=$ZAI_API_KEY        # litellm reads this
#   export OPENAI_API_BASE="https://api.z.ai/v1"
#
# To use DeepInfra as fallback:
#   export DEEPINFRA_API_KEY="your-key"
#
# See SUPERINSTANCE_CHANGES.md for full configuration details.

_zai_key = os.environ.get("ZAI_API_KEY", "")
_di_key = os.environ.get("DEEPINFRA_API_KEY", "")

# If ZAI_API_KEY is set and no OPENAI_API_KEY, configure z.ai as default
if _zai_key and not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = _zai_key
    os.environ.setdefault("OPENAI_API_BASE", "https://api.z.ai/v1")

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

        self._lazy_module = importlib.import_module("litellm")

        self._lazy_module.suppress_debug_info = True
        self._lazy_module.set_verbose = False
        self._lazy_module.drop_params = True
        self._lazy_module._logging._disable_debugging()


litellm = LazyLiteLLM()

__all__ = [litellm]
