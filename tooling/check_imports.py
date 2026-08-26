import importlib

modules = [
    "tigramite",
    "causallearn",
    "ruptures",
    "networkx",
    "statsmodels",
    "aeon",
    "duckdb",
    "pyarrow",
    "polars",
    "pydantic",
    "requests",
]

for module in modules:
    try:
        loaded = importlib.import_module(module)
        version = getattr(loaded, "__version__", "unknown")
        print(f"{module}: OK ({version})")
    except Exception as exc:
        print(f"{module}: FAIL ({type(exc).__name__}: {exc})")
