import threading

from src.fantasypros_bundle import load_fantasypros_bundle


def test_bundle_preserves_successful_resources_when_one_endpoint_fails():
    bundle = load_fantasypros_bundle(
        {
            "rankings": lambda: (_ for _ in ()).throw(PermissionError("forbidden")),
            "players": lambda: {"players": [{"id": 1}]},
            "projections": lambda: {"players": [{"id": 2}]},
        }
    )

    assert bundle.data["rankings"] == {}
    assert bundle.data["players"]["players"][0]["id"] == 1
    assert bundle.data["projections"]["players"][0]["id"] == 2
    assert "forbidden" in bundle.errors["rankings"]


def test_bundle_starts_independent_loaders_concurrently():
    barrier = threading.Barrier(3, timeout=1)

    def loader(value):
        barrier.wait()
        return value

    bundle = load_fantasypros_bundle(
        {
            "one": lambda: loader(1),
            "two": lambda: loader(2),
            "three": lambda: loader(3),
        }
    )

    assert bundle.data == {"one": 1, "two": 2, "three": 3}
    assert bundle.errors == {}
