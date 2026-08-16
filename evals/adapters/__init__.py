"""Adapters for the Knowledge Quality Golden Set V1 harness.

An adapter translates the LLM-driven `prompts/learning-extractor.md` and
`prompts/knowledge-librarian.md` pipeline into concrete calls.

Two adapters are provided:

* `hermes`   — production adapter. Calls a model via the active Hermes
  provider (default MiniMax API, configurable via `MODEL_COMMAND`).
* `mock_stub`— deterministic, 0-token adapter used for CI smoke and the
  V1 baseline report. It never invokes any model and is explicitly
  *not* a substitute for `hermes` in production.

Selecting an adapter:

    python3 evals/run_eval.py --adapter mock-stub
    python3 evals/run_eval.py --adapter hermes

Selecting via environment variable:

    EVAL_ADAPTER=hermes python3 evals/run_eval.py
"""

from .base import Adapter, AdapterError
from .mock_stub import MockStubAdapter
from .hermes import HermesAdapter

ADAPTERS = {
    "mock-stub": MockStubAdapter,
    "hermes": HermesAdapter,
}


def get_adapter(name: str) -> Adapter:
    cls = ADAPTERS.get(name)
    if cls is None:
        raise AdapterError(
            f"Unknown adapter: {name!r}. Available: {sorted(ADAPTERS)}"
        )
    return cls()


__all__ = [
    "Adapter",
    "AdapterError",
    "MockStubAdapter",
    "HermesAdapter",
    "get_adapter",
    "ADAPTERS",
]
