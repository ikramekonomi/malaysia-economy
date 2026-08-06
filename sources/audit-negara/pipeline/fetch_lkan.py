#!/usr/bin/env python3
"""Fetch the federal LKAN volumes (Auditor-General's Reports) into raw/.

Route: audit.gov.my's own portal (lkan.audit.gov.my) sits behind an F5 WAF that
rejects non-browser clients, but every LKAN is also tabled in the Dewan Rakyat as
a Command Paper (Kertas Perintah, "CMD") and parlimen.gov.my serves those PDFs at
stable URLs:  /ipms/eps/<tabling-date>/CMD.<n>.<year> - CMD<n>.<year>.pdf
CMD numbering per tabling day: federal volume(s) first, then the 13 states
alphabetically (Johor..Terengganu) — always confirm from the PDF cover, not the
number (data/lkan_reports.csv records the cover-verified identity + sha256).

TLS note: www.parlimen.gov.my serves its leaf certificate WITHOUT the intermediate
("Sectigo Public Server Authentication CA DV R36"). This script bootstraps the
intermediate from crt.sh (id 4267304690), verifies it against the system trust
store, and only then fetches — never disables verification.

Run:  python3 pipeline/fetch_lkan.py     (re-downloads everything in the manifest)
"""
import csv
import hashlib
import os
import ssl
import subprocess
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "raw")
MANIFEST = os.path.join(HERE, "..", "data", "lkan_reports.csv")
SYSTEM_CA = "/etc/ssl/certs/ca-certificates.crt"
INTERMEDIATE_URL = "https://crt.sh/?d=4267304690"  # Sectigo DV R36 (PEM)


def build_trust_file() -> str:
    """System roots + the missing Sectigo intermediate, verified before use."""
    pem = urllib.request.urlopen(INTERMEDIATE_URL, timeout=240).read()
    tf = tempfile.NamedTemporaryFile(mode="wb", suffix=".pem", delete=False)
    tf.write(pem)
    tf.close()
    subprocess.run(["openssl", "verify", "-CAfile", SYSTEM_CA, tf.name], check=True)
    trust = os.path.join(RAW, "trust.pem")
    with open(trust, "wb") as out:
        out.write(open(SYSTEM_CA, "rb").read())
        out.write(pem)
    os.unlink(tf.name)
    return trust


def main():
    os.makedirs(RAW, exist_ok=True)
    ctx = ssl.create_default_context(cafile=build_trust_file())
    for r in csv.DictReader(open(MANIFEST)):
        dest = os.path.join(RAW, r["file_name"])
        if os.path.exists(dest) and hashlib.sha256(
                open(dest, "rb").read()).hexdigest() == r["sha256"]:
            print(f"{r['file_name']}: present, sha256 OK")
            continue
        print(f"fetching {r['file_name']} ({r['report']}) ...")
        with urllib.request.urlopen(r["source_url"], timeout=1800, context=ctx) as resp, \
                open(dest, "wb") as f:
            while chunk := resp.read(1 << 20):
                f.write(chunk)
        got = hashlib.sha256(open(dest, "rb").read()).hexdigest()
        status = "OK" if got == r["sha256"] else f"HASH CHANGED (manifest {r['sha256']})"
        print(f"{r['file_name']}: {os.path.getsize(dest)} bytes, sha256 {status}")


if __name__ == "__main__":
    main()
