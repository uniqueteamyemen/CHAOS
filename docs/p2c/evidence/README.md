# P2-C Evidence Work Items

These documents retain frozen protocol history and the evidence plan. The active P1.4 engineering runner executes only:
- Threshold-90 calibration of the frozen C1 candidate IDs
- Rearm validation (40 initial observations / 20 after a hit)
- The C1 detector-comparator Pilot against read-only A_FAST and A_CONSENSUS baselines

The following work items are historical reference only and are not invoked by the operational runner:
- `02-threshold200/README.md` — pre-registered protocol extension, deliberately not executed in the engine Pilot
- `03-structural-diagnosis/README.md`
- `04-track-b/README.md` — Track B diagnostics removed from the active runner

The frozen protocol, schema, cohort manifest and protected P1.4 contract/audit files remain unchanged. The operational workflow is `.github/workflows/p1-4-evidence-pipeline.yml`; it is manual-only and defaults to `contract_only`.
