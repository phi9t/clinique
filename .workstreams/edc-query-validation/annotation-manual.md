# EDC Query Annotation Manual

## Unit Of Annotation

Annotate one candidate discrepancy at the `(snapshot_id, subject_id, form, field)` level.

## Label Values

- `missing`: required field is blank or unavailable when the rule is active.
- `inconsistent`: field conflicts with another available field or related date.
- `impossible`: value is structurally impossible, such as a future visit date in a frozen
  snapshot.
- `source_mismatch`: EDC value conflicts with approved source verification evidence.
- `duplicate`: a query already covers the same subject, form, and field.
- `no_query`: reviewed case where no query should be opened.

## Resolution Values

- `corrected`: site/data manager changed data after query.
- `confirmed`: value was confirmed as entered.
- `no_query_needed`: adjudicator agrees no query is needed.
- `duplicate`: candidate repeats an existing query.
- `waived`: discrepancy is acceptable under documented study rules.

## Review Process

Two data-management reviewers independently label ambiguous cases. Disagreements are adjudicated
by a lead data manager. Report agreement as percent agreement and Cohen-style category agreement
when label counts support it.

Outcome labels from later resolution may be used for evaluation only. They must not be exposed
to the agent during timestamped replay.

