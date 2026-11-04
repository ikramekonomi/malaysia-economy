"""Turn a FAIL into SOURCE_ANOMALY only when the source's anomaly register proves it (golden rule 2).

A validator computes its checks as usual, then passes its rows through `classify` before writing:

    sys.path.insert(0, os.path.join(REPO, "qa")); from source_anomaly import classify
    out = classify(out, ANOMALY_CSV)

The register (`_source_anomalies*.csv`) gains a column `explains`: the validation rows it accounts
for, each written as the row's cells except its status, joined by `|`, several separated by ` ; `.
The match is on the whole row, expected and got values included, so an explained discrepancy that
changes (a re-extraction, a new edition) is a FAIL again until someone looks at it. Rows the
register does not name keep their status. Nothing is ever corrected: only the label changes, and
the register carries the page and the proof.
"""
import csv
import os


def explained(anomaly_csv):
    if not os.path.exists(anomaly_csv):
        return set()
    with open(anomaly_csv, newline="") as f:
        r = csv.DictReader(f)
        if "explains" not in (r.fieldnames or []):
            return set()
        return {k.strip() for row in r for k in (row["explains"] or "").split(" ; ") if k.strip()}


def classify(rows, anomaly_csv, status_col=-1):
    keys = explained(anomaly_csv)
    out = []
    for row in rows:
        row = list(row)
        if str(row[status_col]) == "FAIL":
            cells = [str(c) for i, c in enumerate(row) if i != (status_col % len(row))]
            if "|".join(cells) in keys:
                row[status_col] = "SOURCE_ANOMALY"
        out.append(row)
    return out
