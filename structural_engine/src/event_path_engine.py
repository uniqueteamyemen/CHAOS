from __future__ import annotations

from dataclasses import asdict, dataclass, field
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path as FSPath
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Provenance:
    source_id: str
    source_ref: str
    source_sha256: str
    contract_version: str = "event-path-v1"


@dataclass(frozen=True)
class Event:
    event_id: str
    domain: str
    entity: str
    timestamp: str
    value: float
    event_type: str
    provenance: Provenance
    attributes: dict[str, float | str | int | None] = field(default_factory=dict)


@dataclass(frozen=True)
class State:
    state_id: str
    label: str
    event_id: str
    features: dict[str, float | int | str]
    provenance: Provenance


@dataclass(frozen=True)
class Transition:
    transition_id: str
    source_state_id: str
    target_state_id: str
    lag: float
    metrics: dict[str, float]
    provenance: Provenance


@dataclass(frozen=True)
class EventWindow:
    window_id: str
    entity: str
    event_ids: tuple[str, ...]
    state_ids: tuple[str, ...]
    as_of: str
    width: int
    provenance: Provenance


@dataclass(frozen=True)
class Path:
    path_id: str
    window_id: str
    state_labels: tuple[str, ...]
    transition_ids: tuple[str, ...]
    outcome_label: str | None
    provenance: Provenance


@dataclass(frozen=True)
class Prediction:
    prediction_id: str
    path_id: str
    entity: str
    as_of: str
    predicted_state: str
    actual_state: str | None
    split: str
    provenance: Provenance
    baseline_persistence: str = ""
    baseline_majority: str = ""
    baseline_trend: str = ""


@dataclass
class Dataset:
    events: list[Event]
    source_id: str
    source_ref: str
    source_sha256: str


class USGSGeoJSONAdapter:
    """Adapt a frozen USGS GeoJSON earthquake query without changing Event-Path parameters."""

    def load(self, path: str | FSPath, entity: str = "gulf_of_aden") -> Dataset:
        source_path = FSPath(path)
        raw = source_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        source_id = "usgs-earthquake-catalog:gulf-of-aden-v1"
        provenance = Provenance(source_id, str(source_path), digest)
        payload = json.loads(raw.decode("utf-8"))
        events: list[Event] = []
        for feature in payload.get("features", []):
            props = feature.get("properties", {})
            geometry = feature.get("geometry") or {}
            coords = geometry.get("coordinates") or [None, None, None]
            if props.get("mag") is None or props.get("time") is None or not feature.get("id"):
                continue
            timestamp = datetime.fromtimestamp(float(props["time"]) / 1000.0, tz=timezone.utc).isoformat()
            events.append(Event(f"event:usgs:{feature['id']}", "seismic", entity, timestamp, float(props["mag"]), "earthquake", provenance, {"longitude": coords[0], "latitude": coords[1], "depth_km": coords[2], "place": props.get("place"), "mag_type": props.get("magType")}))
        events.sort(key=lambda event: event.timestamp)
        return Dataset(events, source_id, str(source_path), digest)


class AnnualPanelAdapter:
    """Adapt a governed annual panel into event-native observations without frequency mixing."""

    def __init__(self, value_column: str, domain: str = "economic") -> None:
        self.value_column = value_column
        self.domain = domain

    def load(self, path: str | FSPath, entity_column: str = "entity_code", time_column: str = "year") -> Dataset:
        raw = FSPath(path).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        source_ref = str(FSPath(path))
        source_id = f"annual-panel:{self.value_column}"
        provenance = Provenance(source_id, source_ref, digest)
        events: list[Event] = []
        with FSPath(path).open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                value = row.get(self.value_column, "")
                if value in (None, ""):
                    continue
                try:
                    numeric = float(value)
                except ValueError:
                    continue
                entity = row[entity_column]
                timestamp = row[time_column]
                event_id = f"event:{self.domain}:{entity}:{timestamp}:{self.value_column}"
                events.append(Event(event_id, self.domain, entity, timestamp, numeric, "annual_observation", provenance))
        return Dataset(events, source_id, source_ref, digest)


def _id(prefix: str, *parts: object) -> str:
    return prefix + ":" + hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:16]


def classify_state(interval_delta: float | None, relative_increment_delta: float | None) -> str:
    if interval_delta is None or relative_increment_delta is None:
        return "insufficient_history"
    interval = "shortening_intervals" if interval_delta < 0 else "lengthening_intervals" if interval_delta > 0 else "stable_intervals"
    increment = "declining_relative_increment" if relative_increment_delta < 0 else "rising_relative_increment" if relative_increment_delta > 0 else "stable_relative_increment"
    return f"{interval}+{increment}"


def _time_value(timestamp: str) -> float:
    try:
        return float(timestamp)
    except ValueError:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()


def build_states(events: Sequence[Event]) -> list[State]:
    by_entity: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        by_entity[event.entity].append(event)
    result: list[State] = []
    for entity_events in by_entity.values():
        ordered = sorted(entity_events, key=lambda event: event.timestamp)
        previous_interval: float | None = None
        previous_increment: float | None = None
        previous_event: Event | None = None
        for event in ordered:
            interval = None
            increment = None
            if previous_event is not None:
                try:
                    interval = _time_value(event.timestamp) - _time_value(previous_event.timestamp)
                except (ValueError, TypeError):
                    interval = None
                increment = (event.value - previous_event.value) / max(abs(previous_event.value), 1e-12)
            interval_delta = None if interval is None or previous_interval is None else interval - previous_interval
            increment_delta = None if increment is None or previous_increment is None else increment - previous_increment
            label = classify_state(interval_delta, increment_delta)
            features = {"interval": interval if interval is not None else 0.0, "relative_increment": increment if increment is not None else 0.0}
            state_id = _id("state", event.event_id, label)
            result.append(State(state_id, label, event.event_id, features, event.provenance))
            previous_event, previous_interval, previous_increment = event, interval, increment
    return result


def build_windows(events: Sequence[Event], states: Sequence[State], width: int) -> list[EventWindow]:
    state_by_event = {state.event_id: state for state in states}
    by_entity: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        by_entity[event.entity].append(event)
    windows: list[EventWindow] = []
    for entity, ordered in by_entity.items():
        ordered.sort(key=lambda event: event.timestamp)
        for end in range(width, len(ordered) + 1):
            selected = ordered[end - width : end]
            selected_states = [state_by_event[event.event_id] for event in selected]
            provenance = selected[-1].provenance
            windows.append(EventWindow(_id("window", entity, end, width), entity, tuple(e.event_id for e in selected), tuple(state_by_event[e.event_id].state_id for e in selected), selected[-1].timestamp, width, provenance))
    return windows


def build_paths(windows: Iterable[EventWindow], states: Sequence[State], transitions: Sequence[Transition]) -> list[Path]:
    state_by_id = {state.state_id: state for state in states}
    transition_by_pair = {(t.source_state_id, t.target_state_id): t for t in transitions}
    paths: list[Path] = []
    for window in windows:
        labels = tuple(state_by_id[state_id].label for state_id in window.state_ids)
        tids = tuple(transition_by_pair[(a, b)].transition_id for a, b in zip(window.state_ids, window.state_ids[1:]) if (a, b) in transition_by_pair)
        paths.append(Path(_id("path", window.window_id), window.window_id, labels, tids, None, state_by_id[window.state_ids[-1]].provenance))
    return paths


def build_transitions(events: Sequence[Event], states: Sequence[State]) -> list[Transition]:
    event_by_id = {event.event_id: event for event in events}
    by_entity: dict[str, list[State]] = defaultdict(list)
    for state in states:
        by_entity[event_by_id[state.event_id].entity].append(state)
    transitions: list[Transition] = []
    for entity_states in by_entity.values():
        ordered = sorted(entity_states, key=lambda state: event_by_id[state.event_id].timestamp)
        for source, target in zip(ordered, ordered[1:]):
            source_event, target_event = event_by_id[source.event_id], event_by_id[target.event_id]
            try:
                lag = _time_value(target_event.timestamp) - _time_value(source_event.timestamp)
            except (ValueError, TypeError):
                lag = 0.0
            transitions.append(Transition(_id("transition", source.state_id, target.state_id), source.state_id, target.state_id, lag, {"source_value": source_event.value, "target_value": target_event.value}, target.provenance))
    return transitions


class EventPathEngine:
    def __init__(self, window_width: int = 3, min_support: int = 2, max_path_length: int = 6) -> None:
        if window_width < 2 or max_path_length < window_width:
            raise ValueError("window_width must be >=2 and <= max_path_length")
        self.window_width, self.min_support, self.max_path_length = window_width, min_support, max_path_length

    def discover(self, paths: Sequence[Path], train_as_of: str) -> dict[tuple[str, ...], str]:
        counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
        for path in paths:
            if path.provenance.source_ref and path.window_id and path.state_labels:
                if path.window_id and path.state_labels[-1] and path.provenance and path.state_labels[-1] != "insufficient_history":
                    # Candidate outcome is supplied by the following observation during evaluation, never by OOS data.
                    counts[path.state_labels]["__support__"] += 1
        return {signature: "candidate" for signature, counter in counts.items() if counter["__support__"] >= self.min_support}

    @staticmethod
    def _majority(labels: Sequence[str], fallback: str = "insufficient_history") -> str:
        return Counter(labels).most_common(1)[0][0] if labels else fallback

    def rolling_oos_legacy(self, states: Sequence[State], events: Sequence[Event], train_size: int = 8) -> tuple[list[Prediction], dict[str, dict[str, float]]]:
        event_by_id = {event.event_id: event for event in events}
        state_by_entity: dict[str, list[State]] = defaultdict(list)
        for state in states:
            state_by_entity[event_by_id[state.event_id].entity].append(state)
        predictions: list[Prediction] = []
        for entity, series in state_by_entity.items():
            series.sort(key=lambda state: event_by_id[state.event_id].timestamp)
            if len(series) <= train_size:
                continue
            for index in range(train_size, len(series)):
                train = series[:index]
                actual = series[index]
                signature = tuple(state.label for state in train[-self.window_width:])
                matching = [series[j + 1].label for j in range(self.window_width - 1, index - 1) if tuple(s.label for s in series[j - self.window_width + 1 : j + 1]) == signature and j + 1 < index]
                predicted = self._majority(matching, fallback=train[-1].label)
                provenance = actual.provenance
                majority = self._majority([state.label for state in train])
                trend = self._majority([state.label for state in train[-3:]])
                predictions.append(Prediction(_id("prediction", entity, index), _id("path", entity, index), entity, event_by_id[actual.event_id].timestamp, predicted, actual.label, "oos", provenance, train[-1].label, majority, trend))
        return predictions, evaluate_predictions(predictions, states)

    def rolling_oos(self, states: Sequence[State], events: Sequence[Event], train_size: int = 8) -> tuple[list[Prediction], dict[str, dict[str, float]]]:
        """Public leakage-safe API; unsupported paths abstain instead of falling back."""
        return self.rolling_oos_frozen(states, events, train_size=train_size)

    def rolling_oos_frozen(self, states: Sequence[State], events: Sequence[Event], train_size: int = 8) -> tuple[list[Prediction], dict[str, dict[str, float]]]:
        """Leakage-safe predictor: discover/freeze conditional paths inside each train prefix.

        Unsupported paths abstain; they are never silently converted to persistence.
        """
        event_by_id = {event.event_id: event for event in events}
        state_by_entity: dict[str, list[State]] = defaultdict(list)
        for state in states:
            state_by_entity[event_by_id[state.event_id].entity].append(state)
        predictions: list[Prediction] = []
        for entity, series in state_by_entity.items():
            series.sort(key=lambda state: event_by_id[state.event_id].timestamp)
            for index in range(train_size, len(series)):
                train = series[:index]
                actual = series[index]
                signature = tuple(state.label for state in train[-self.window_width:])
                outcome_by_signature: dict[tuple[str, ...], list[str]] = defaultdict(list)
                for end in range(self.window_width - 1, len(train) - 1):
                    historical_signature = tuple(state.label for state in train[end - self.window_width + 1:end + 1])
                    outcome_by_signature[historical_signature].append(train[end + 1].label)
                outcomes = outcome_by_signature.get(signature, [])
                supported = len(outcomes) >= self.min_support
                predicted = self._majority(outcomes) if supported else "abstain_insufficient_support"
                majority = self._majority([state.label for state in train])
                trend = self._majority([state.label for state in train[-3:]])
                provenance = actual.provenance
                predictions.append(Prediction(_id("prediction-frozen", entity, index), _id("path-frozen", entity, index), entity, event_by_id[actual.event_id].timestamp, predicted, actual.label, "oos_frozen", provenance, train[-1].label, majority, trend))
        scored = [prediction for prediction in predictions if prediction.predicted_state != "abstain_insufficient_support"]
        actual = [prediction.actual_state for prediction in scored if prediction.actual_state is not None]
        majority_rows = [prediction for prediction in predictions if prediction.predicted_state != "abstain_insufficient_support"]
        metrics = {
            "path_model": {"n": float(len(actual)), "accuracy": _accuracy([prediction.predicted_state for prediction in scored], actual)["accuracy"] if actual else 0.0, "coverage": len(scored) / len(predictions) if predictions else 0.0},
            "majority_baseline": {"n": float(len(majority_rows)), "accuracy": _accuracy([prediction.baseline_majority for prediction in majority_rows], [prediction.actual_state for prediction in majority_rows])["accuracy"] if majority_rows else 0.0, "coverage": len(majority_rows) / len(predictions) if predictions else 0.0},
            "persistence_baseline": {"n": float(len(majority_rows)), "accuracy": _accuracy([prediction.baseline_persistence for prediction in majority_rows], [prediction.actual_state for prediction in majority_rows])["accuracy"] if majority_rows else 0.0, "coverage": len(majority_rows) / len(predictions) if predictions else 0.0},
            "abstention": {"n": float(len(predictions) - len(scored)), "rate": (len(predictions) - len(scored)) / len(predictions) if predictions else 0.0},
        }
        return predictions, metrics


def evaluate_predictions(predictions: Sequence[Prediction], states: Sequence[State]) -> dict[str, dict[str, float]]:
    actual = [p.actual_state for p in predictions if p.actual_state is not None]
    if not actual:
        return {}
    majority = Counter(actual).most_common(1)[0][0]
    persistence = [p.baseline_persistence or p.predicted_state for p in predictions]
    majority_baseline = [p.baseline_majority or majority for p in predictions]
    trend_baseline = [p.baseline_trend or p.baseline_persistence or p.predicted_state for p in predictions]
    path_predictions = [p.predicted_state for p in predictions]
    scores = {"path_model": _accuracy(path_predictions, actual), "persistence_baseline": _accuracy(persistence, actual), "majority_baseline": _accuracy(majority_baseline, actual), "simple_trend_baseline": _accuracy(trend_baseline, actual)}
    return scores


def _accuracy(predicted: Sequence[str], actual: Sequence[str]) -> dict[str, float]:
    correct = sum(p == a for p, a in zip(predicted, actual))
    return {"n": float(len(actual)), "accuracy": correct / len(actual) if actual else 0.0}


def write_artifacts(output_dir: str | FSPath, dataset: Dataset, events: Sequence[Event], states: Sequence[State], transitions: Sequence[Transition], predictions: Sequence[Prediction], metrics: dict[str, dict[str, float]]) -> None:
    out = FSPath(output_dir); out.mkdir(parents=True, exist_ok=True)
    def dump(name: str, rows: Sequence[object]) -> None:
        (out / name).write_text("\n".join(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")
    dump("EVENTS.jsonl", events); dump("STATES.jsonl", states); dump("TRANSITIONS.jsonl", transitions); dump("PREDICTIONS.jsonl", predictions)
    (out / "RUN_SUMMARY.json").write_text(json.dumps({"source": {"source_id": dataset.source_id, "source_ref": dataset.source_ref, "source_sha256": dataset.source_sha256}, "counts": {"events": len(events), "states": len(states), "transitions": len(transitions), "predictions": len(predictions)}, "metrics": metrics, "status": "provisional" if predictions else "not_testable"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
