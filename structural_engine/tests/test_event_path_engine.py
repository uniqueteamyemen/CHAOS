from pathlib import Path
import tempfile

from src.event_path_engine import AnnualPanelAdapter, EventPathEngine, build_states, build_transitions, build_windows, build_paths, evaluate_predictions


def _fixture(path: Path) -> None:
    path.write_text(
        "entity_code,year,value\n"
        "X,2000,10\nX,2001,9\nX,2002,7\nX,2003,4\nX,2004,2\n"
        "Y,2000,2\nY,2001,3\nY,2002,5\nY,2003,8\nY,2004,13\n",
        encoding="utf-8",
    )


def test_adapter_preserves_source_provenance_and_frequency():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "panel.csv"
        _fixture(path)
        dataset = AnnualPanelAdapter("value").load(path)
        assert len(dataset.events) == 10
        assert dataset.events[0].provenance.source_sha256
        assert dataset.events[0].event_type == "annual_observation"


def test_path_objects_and_rolling_oos_are_reproducible():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "panel.csv"
        _fixture(path)
        dataset = AnnualPanelAdapter("value").load(path)
        states = build_states(dataset.events)
        transitions = build_transitions(dataset.events, states)
        windows = build_windows(dataset.events, states, width=3)
        paths = build_paths(windows, states, transitions)
        assert len(states) == len(dataset.events)
        assert len(transitions) == 8
        assert all(len(p.state_labels) == 3 for p in paths)
        predictions, metrics = EventPathEngine(window_width=3, min_support=1).rolling_oos(states, dataset.events, train_size=3)
        assert predictions
        assert metrics["path_model"]["n"] == float(len(predictions))
        assert 0.0 <= metrics["majority_baseline"]["accuracy"] <= 1.0


def test_insufficient_history_is_explicit():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "panel.csv"
        path.write_text("entity_code,year,value\nX,2000,10\nX,2001,11\n", encoding="utf-8")
        dataset = AnnualPanelAdapter("value").load(path)
        states = build_states(dataset.events)
        assert states[0].label == "insufficient_history"
