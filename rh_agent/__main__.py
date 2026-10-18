import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    spec = importlib.util.spec_from_file_location("project_main", ROOT / "__main__.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load project entry module.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hasattr(module, "main"):
        return module.main()
    raise RuntimeError("Project entry module does not define a main() function.")


if __name__ == "__main__":
    raise SystemExit(main())
