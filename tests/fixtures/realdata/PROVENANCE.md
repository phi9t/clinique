# Real-data fixtures — provenance

These are genuine public clinical-trial submission artifacts used for real-data validation
(RFC-0001 / RFC-0004), not synthetic data.

| File | Source | Notes |
|---|---|---|
| `define.xml` | [RConsortium/submissions-pilot1-to-fda](https://github.com/RConsortium/submissions-pilot1-to-fda) `m5/datasets/rconsortiumpilot1/analysis/adam/datasets/define.xml` | Real ADaM Define-XML 2.0 from the R Consortium pilot submitted to FDA |
| `adsl.xpt` | same repo, `.../adsl.xpt` | Real ADSL (subject-level) SAS transport dataset |
| `adtte.xpt` | same repo, `.../adtte.xpt` | Real ADTTE (time-to-event) SAS transport dataset |

The R Consortium Submissions Working Group pilot data is publicly available for demonstrating
FDA submission packages. Re-fetch with:

```bash
base="https://raw.githubusercontent.com/RConsortium/submissions-pilot1-to-fda/main/m5/datasets/rconsortiumpilot1/analysis/adam/datasets"
curl -sSL "$base/define.xml" -o define.xml
curl -sSL "$base/adsl.xpt"  -o adsl.xpt
curl -sSL "$base/adtte.xpt" -o adtte.xpt
```

Observed real finding: the define.xml contains 51 dangling `MethodDef` references — `ItemRef`s
use `MethodOID="ADADAS.PARAM"` etc. while the methods are defined as `OID="MT.ADADAS.PARAM"`
(missing the `MT.` prefix). The checker detects these; ADSL variable metadata matches the dataset.
