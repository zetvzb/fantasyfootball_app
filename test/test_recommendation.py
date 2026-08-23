from pathlib import Path
import runpy


project_root = Path(__file__).resolve().parents[1]
runpy.run_path(
    str(project_root / "tests" / "test_recommendation.py"),
    run_name="__main__",
)
