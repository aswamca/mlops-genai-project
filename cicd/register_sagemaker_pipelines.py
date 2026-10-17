"""Jenkins entry point for registering SageMaker pipeline definitions."""

from pathlib import Path
import runpy


runpy.run_path(
    str(
        Path(__file__).parents[1]
        / "PredML"
        / "AWS"
        / "pipelines"
        / "register_pipelines.py"
    ),
    run_name="__main__",
)
