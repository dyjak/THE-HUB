from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ai_param_pkg_name = __name__ + ".ai_param_test"
_ai_param_pkg_path = Path(__file__).parent / "ai-param-test"

if _ai_param_pkg_path.exists() and _ai_param_pkg_name not in sys.modules:
	spec = importlib.util.spec_from_file_location(
		_ai_param_pkg_name,
		_ai_param_pkg_path / "__init__.py",
		submodule_search_locations=[str(_ai_param_pkg_path)]
	)
	if spec is not None:
		module = importlib.util.module_from_spec(spec)
		module.__path__ = [str(_ai_param_pkg_path)]  # type: ignore[attr-defined]
		sys.modules[_ai_param_pkg_name] = module
		loader = spec.loader
		if loader is not None:
			loader.exec_module(module)
