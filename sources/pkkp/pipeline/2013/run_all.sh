#!/bin/bash
# Full 2013 pipeline: extract -> validate -> cross-year restatement audit.
# Adjacent-year reference = 2014. printed_page = pdf_page - 24. RMKe-10, pre-GST.
set -e
cd /home/claude/pkkp/work/2013
WH=/home/claude/pkkp/warehouse2013
mkdir -p $WH
python3 pipeline/extract_core.py
python3 pipeline/extract_lampiran1.py    > /tmp/l1_13.log
python3 pipeline/extract_devex.py        > /tmp/dv_13.log
python3 pipeline/extract_lampiran2_projects.py > /tmp/l2_13.log
python3 pipeline/extract_memoranda.py    > /tmp/mem_13.log
python3 pipeline/extract_investments.py  > /tmp/inv_13.log
python3 pipeline/extract_notes_detail_2013.py > /tmp/nd_13.log
python3 pipeline/extract_timeseries_2013.py   > /tmp/ts_13.log
python3 pipeline/extract_nota5_statement_2013.py
python3 pipeline/extract_nota6_statement_2013.py
python3 pipeline/build_dims.py
python3 pipeline/validate_2013.py
python3 pipeline/compare_2013.py > /tmp/cmp_13.log
echo "run_all 2013 complete"
