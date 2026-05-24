# Silent Prospective Protocol

## Purpose

Run the EDC/query agent hidden beside normal data-management operations for 4-12 weeks after
offline and retrospective gates pass on approved internal data.

## Operating Mode

- Agent recommendations are logged silently.
- Humans continue the normal workflow.
- No recommendation is shown to sites or used to issue, close, or suppress a query.
- No live EDC write-back is permitted.

## Logged Labels

- Hidden agent recommendation and evidence.
- Usual human action.
- Later adjudicated ground truth or operational outcome.
- Time delta between agent surfacing and human action.
- False-positive burden per reviewer/week.
- Reviewer feedback on sampled recommendations.

## Stop Criteria

Pause the silent run for any privacy incident, blinding-boundary concern, unsupported evidence
pattern, unauthorized write attempt, or false-positive burden above the predefined tolerance.

## Required Approvals Before Run

Data owner approval, privacy review, validation lead approval, and data-management lead approval.

