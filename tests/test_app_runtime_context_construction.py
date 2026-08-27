import ast
import dataclasses
from pathlib import Path

from src.app_runtime import AppRuntimeContext


def test_app_py_passes_every_dataclass_field_to_the_direct_constructor():
    """AppRuntimeContext deliberately has no field defaults -- every view
    dependency must be passed explicitly (see its docstring). If a field
    is added to the dataclass but missed at app.py's direct construction
    site, the app crashes with a TypeError the moment a view that uses
    the full (non build_view_runtime) context is opened. Catch that here
    statically instead of at runtime.
    """

    app_source = Path("app.py").read_text(encoding="utf-8")
    tree = ast.parse(app_source)

    direct_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "AppRuntimeContext"
    ]

    assert len(direct_calls) == 1, (
        "Expected exactly one direct AppRuntimeContext(...) construction "
        "in app.py -- if this changed intentionally, update this test."
    )

    passed_kwargs = {keyword.arg for keyword in direct_calls[0].keywords}
    expected_fields = {
        field.name for field in dataclasses.fields(AppRuntimeContext)
    }

    missing = expected_fields - passed_kwargs
    assert not missing, (
        "app.py's direct AppRuntimeContext(...) call is missing required "
        "field(s): {0}".format(sorted(missing))
    )
