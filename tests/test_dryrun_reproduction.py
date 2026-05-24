"""RFC-0002/0005: ADaM reproduction and dry-run validation stub."""

from clinique.dryrun import DryRunHarness, SyntheticDataProvider, SyntheticDataset


def test_adam_reproduction_stub():
    # 1. Initialize synthetic provider and dataset mirroring R-pilot/ADSL structures
    provider = SyntheticDataProvider()
    # In a real validation, this would be generated from the metadata spec (metacore)
    synthetic_ds = provider.generate("ADSL", n=10, scenario="null")

    # 2. Define a reproduction program (stub representing Admiral/pharmaverse ADSL derivation)
    def derive_adsl(dataset: SyntheticDataset) -> list[dict]:
        output_rows = []
        for row in dataset.rows:
            # Simulate basic ADaM derivations (e.g., SITEID, TRT01P, TRTSDT)
            subj = row["subject"]
            site_id = "SITE-01" if int(subj[1:]) % 2 == 0 else "SITE-02"
            trt = "Active Drug" if int(subj[1:]) % 2 == 0 else "Placeboard"
            output_rows.append(
                {
                    "USUBJID": f"STUDY-001-{subj}",
                    "SITEID": site_id,
                    "TRT01P": trt,
                    "AGE": 40 + (int(subj[1:]) % 30),
                    "ARM": trt,
                }
            )
        return output_rows

    # 3. Known-correct output structure validation target
    expected_columns = {"USUBJID", "SITEID", "TRT01P", "AGE", "ARM"}

    # 4. Execute the program through the DryRunHarness
    harness = DryRunHarness(provider)
    programs = {"ADSL-DERIVATION": derive_adsl}
    checks = harness.run(programs, synthetic_ds)

    # 5. Assert the harness ran the program successfully
    assert any(c.check == "PROGRAM-RUNS" and c.passed for c in checks)
    assert any(c.check == "SHELL-POPULATES" and c.passed for c in checks)

    # 6. Verify output vs known-correct expectations (the reproduction stub check)
    reproduced_data = derive_adsl(synthetic_ds)
    assert len(reproduced_data) == 10
    for row in reproduced_data:
        assert set(row.keys()) == expected_columns
        assert row["USUBJID"].startswith("STUDY-001-S")
