#!/bin/bash
# Full 2016 pipeline: extract -> validate -> cross-year. One canonical check file.
set -e
cd /home/claude/pkkp/work/2016
WH=/home/claude/pkkp/warehouse2016
rm -f $WH/_validation_checks_2016.csv
python3 pipeline/extract_core.py
python3 pipeline/extract_nota5_statement.py
python3 pipeline/extract_nota6_statement.py
python3 pipeline/extract_lampiran1.py > /tmp/l1.log 2>&1 || { tail -5 /tmp/l1.log; exit 1; }
python3 pipeline/extract_devex.py > /tmp/devex.log
python3 pipeline/extract_lampiran2_projects.py > /tmp/l2.log
python3 pipeline/extract_memoranda.py
python3 pipeline/extract_investments.py > /tmp/inv.log
python3 pipeline/extract_timeseries.py > /tmp/ts.log
python3 pipeline/build_dims.py
# header for the canonical check file, then appenders
python3 - <<'PY'
import csv
with open('/home/claude/pkkp/warehouse2016/_validation_checks_2016.csv','w',newline='') as f:
    csv.writer(f).writerow(['status','check','extracted_value','printed_value','difference'])
PY
python3 pipeline/extract_notes_detail.py > /tmp/notes.log || true
python3 pipeline/validate.py > /tmp/validate.log || true
python3 pipeline/validate_memoranda.py > /tmp/vmem.log || true
python3 - <<'PY'
import csv
rows = list(csv.reader(open('/home/claude/pkkp/warehouse2016/_validation_checks_memoranda_2016.csv')))[1:]
with open('/home/claude/pkkp/warehouse2016/_validation_checks_2016.csv','a',newline='') as f:
    w = csv.writer(f)
    for st, chk, got, want in rows:
        try:
            diff = float(got) - float(want)
        except ValueError:
            diff = ''
        w.writerow([st, 'memoranda: ' + chk, got, want, diff])
PY
if [ -f /home/claude/pkkp/warehouse2017/fact_opex_maksud.csv ]; then
  python3 pipeline/compare_cross_year.py > /tmp/cross.log || true
  echo "cross-year restatement audit: run (see _restatements_2016_vs_2017volume.csv)"
else
  echo "cross-year restatement audit: DEFERRED (warehouse2017 not yet built)"
fi
grep -E 'checks' /tmp/validate.log | tail -1
grep -E 'checks' /tmp/vmem.log | tail -1
echo "run_all complete"
