# Integrity

## Objective
Protect the frozen contract, selected identities, source artifacts and execution provenance.

## Scope and workflow
The Evidence workflow is manual-only through `workflow_dispatch`. Its default mode is `contract_only`, which runs contract gates and a lightweight runtime preflight. The 20-series C1 matrix is reachable only by explicit selection of `full_20_series` after both gates pass.

The capability-contract workflow is also manual-only; neither workflow launches automatically on push.

## Runtime dependencies
The active runner does not import `arch` and does not execute Track B. The runtime pins `numpy==1.26.4` and `pandas==2.2.3` consistently across contract, preflight, calibration and postprocess jobs.

## Integrity outputs
Run evidence includes source commit, workflow run ID, artifact SHA-256 inventory and replay commands. Raw series values are not written into Pilot results.
