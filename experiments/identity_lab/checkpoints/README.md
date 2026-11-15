# Durable experiment checkpoints

A completed package must survive connection loss without being rerun.

## Completion rule
A package is marked completed only when tests pass, experiment execution
succeeds, the result JSON exists and is hashed, the Actions artifact upload
succeeds with an ID and digest, and the checkpoint record is committed to Git.
Any failed or interrupted package is recorded as incomplete and is rerun.

## Resume rule
Each workflow declares every code, test, schema, configuration, workflow and
data file that influences its package. Their content hashes form an input
fingerprint. An exact matching completed fingerprint is skipped. Changed
inputs, missing records and incomplete records are rerun.

This is package-level resume, not an assertion that a Python process resumes
mid-function. Expensive pipelines should be divided into independently
checkpointed packages at stable boundaries.

## Durability
The Git checkpoint stores source commit, input hashes, run identity, test and
experiment results, result JSON hash, artifact ID/digest/URL and a compact
result summary. Raw output stays in the Actions artifact. Checkpoint commits
are excluded from workflow path filters to avoid recursive runs.

A hosted GitHub Actions runner continues if the browser or ChatGPT connection
drops. On reconnection, the next run checks this ledger and skips only packages
whose exact inputs already completed.
