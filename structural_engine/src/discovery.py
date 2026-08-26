from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class TemporalEdge:
    source: str
    target: str
    lag: int
    score: float
    p_value: float | None
    algorithm: str
    interpretation: str = "temporal_candidate_not_causal_proof"


def discover_pcmci(
    data: np.ndarray,
    variable_names: Sequence[str],
    *,
    tau_min: int = 1,
    tau_max: int = 12,
    pc_alpha: float = 0.01,
    ci_test: str = "ParCorr",
) -> list[TemporalEdge]:
    """Discover candidate time-directed edges; no DAG is supplied by the caller.

    This function deliberately fails clearly when Tigramite is unavailable rather than
    silently replacing structural discovery with correlation or mock output.
    """
    if data.ndim != 2 or data.shape[1] != len(variable_names):
        raise ValueError("data must be 2-D with one column per variable name")
    if tau_min < 1 or tau_max < tau_min:
        raise ValueError("tau range must satisfy 1 <= tau_min <= tau_max")
    try:
        from tigramite import data_processing as pp
        from tigramite.independence_tests.parcorr import ParCorr
        from tigramite.pcmci import PCMCI
    except ImportError as exc:
        raise RuntimeError("Tigramite is required for PCMCI discovery; no fallback inference is used") from exc

    if ci_test != "ParCorr":
        raise ValueError("this implementation currently exposes ParCorr explicitly; add and test other CI tests before use")
    dataframe = pp.DataFrame(data, var_names=list(variable_names))
    pcmci = PCMCI(dataframe=dataframe, cond_ind_test=ParCorr(significance="analytic"), verbosity=0)
    result = pcmci.run_pcmci(tau_min=tau_min, tau_max=tau_max, pc_alpha=pc_alpha)
    graph = result["graph"]
    val_matrix = result["val_matrix"]
    p_matrix = result.get("p_matrix")
    edges: list[TemporalEdge] = []
    for target_index, target in enumerate(variable_names):
        for source_index, source in enumerate(variable_names):
            for tau in range(tau_min, tau_max + 1):
                label = graph[source_index, target_index, tau]
                if label == "-->" or (isinstance(label, str) and "->" in label):
                    p_value = None if p_matrix is None else float(p_matrix[source_index, target_index, tau])
                    edges.append(
                        TemporalEdge(
                            source=source,
                            target=target,
                            lag=tau,
                            score=float(val_matrix[source_index, target_index, tau]),
                            p_value=p_value,
                            algorithm="Tigramite_PCMCI_ParCorr",
                        )
                    )
    return edges


def write_edges(edges: Sequence[TemporalEdge], path: str | Path) -> None:
    Path(path).write_text(
        json.dumps([asdict(edge) for edge in edges], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit("Use discover_pcmci with a real observed matrix; this module never creates data.")
