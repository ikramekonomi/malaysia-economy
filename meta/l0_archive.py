#!/usr/bin/env python3
"""L0 archive: keep a copy of every raw document, outside the publisher (decision D17, D23).

The PDFs are too big for git (13 GB; single files over GitHub's 100 MB limit), so they are kept
as assets of one release of this (private) repository, tag `l0-archive`, each named by its
sha256: `<sha256>.pdf`. `meta/l0_archive.csv` is the index (committed); `meta/build_registry.py`
reads it. Runs on GitHub Actions (`.github/workflows/l0-archive.yml`), where the publishers'
sites are reachable and `gh` is authenticated.

  python3 meta/l0_archive.py --plan                    # what is missing, no network
  python3 meta/l0_archive.py --run [--max-gb 9] [--max-minutes 300]

Two kinds of target:
  verify    a file the registry already knows by sha256 + URL (LKAN, state volumes, MOF outlook,
            Anggaran, Anggaran Hasil). Downloaded; archived only if the sha256 matches. A
            different sha256 means the publisher changed the file: recorded as MISMATCH, never
            substituted.
  identify  a file our rows cite but whose sha256 was never recorded (PKKP), from
            meta/l0_candidates.csv. Each candidate URL is tried; the first download that passes
            meta/l0_identity.py (the cited amounts are printed on the cited pages) is archived and
            written to that source's data/_documents_manifest.csv.

Never disables TLS verification. Some government hosts serve an incomplete certificate chain;
the missing intermediate is fetched from the certificate's own AIA "CA Issuers" URL and must
still chain to a trusted root.
"""
import csv
import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
INDEX = os.path.join(HERE, "l0_archive.csv")
REGISTRY = os.path.join(HERE, "registry_file.csv")
CANDIDATES = os.path.join(HERE, "l0_candidates.csv")
TAG = "l0-archive"
FIELDS = ["sha256", "file_name", "series_id", "source_url", "size_bytes", "release_tag", "asset_name",
          "status", "check", "archived_on"]
SHA = re.compile(r"^[0-9a-f]{64}$")
UA = "malaysia-economy-l0-archiver/1.0 (+https://github.com/ammarroslizar/malaysia-economy)"


def rows(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_index():
    return {r["sha256"]: r for r in rows(INDEX)}


def save_index(idx):
    with open(INDEX, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(sorted(idx.values(), key=lambda r: (r["series_id"], r["file_name"], r["sha256"])))


def targets():
    out, seen = [], set()
    for r in rows(REGISTRY):
        if SHA.match(r["sha256"] or "") and r["source_url"].startswith("http") and r["sha256"] not in seen:
            seen.add(r["sha256"])
            out.append({"mode": "verify", "sha256": r["sha256"], "file_name": r["file_name"],
                        "series_id": r["series_id"], "urls": [r["source_url"]],
                        "size": int(float(r["size_bytes"] or 0))})
    known = {(r["series_id"], r["file_name"]) for r in rows(REGISTRY) if SHA.match(r["sha256"] or "")}
    for c in rows(CANDIDATES):
        if (c["series_id"], c["file_name"]) in known:
            continue
        out.append({"mode": "identify", "sha256": "", "file_name": c["file_name"], "series_id": c["series_id"],
                    "source": c["source"], "edition": c["edition"], "urls": c["candidate_urls"].split(), "size": 0})
    return out


# ---------- TLS: complete a missing intermediate from AIA, never skip verification ----------
_ctx = {}


def _base_bundle():
    try:
        import certifi
        return certifi.where()
    except ImportError:
        return ssl.get_default_verify_paths().cafile


def _aia_intermediates(host, port=443, depth=3):
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding
    pem = ssl.get_server_certificate((host, port))   # unverified read of the leaf, only to find its issuer URL
    cert = x509.load_pem_x509_certificate(pem.encode())
    chain = []
    for _ in range(depth):
        try:
            aia = cert.extensions.get_extension_for_class(x509.AuthorityInformationAccess).value
        except x509.ExtensionNotFound:
            break
        urls = [d.access_location.value for d in aia if d.access_method == x509.oid.AuthorityInformationAccessOID.CA_ISSUERS]
        if not urls:
            break
        data = urllib.request.urlopen(urllib.request.Request(urls[0], headers={"User-Agent": UA}), timeout=30).read()
        try:
            cert = x509.load_der_x509_certificate(data)
        except ValueError:
            cert = x509.load_pem_x509_certificate(data)
        chain.append(cert.public_bytes(Encoding.PEM).decode())
        if cert.issuer == cert.subject:
            break
    return chain


def context(host, fix=False):
    if host in _ctx and not fix:
        return _ctx[host]
    ctx = ssl.create_default_context(cafile=_base_bundle())
    if fix:
        try:
            extra = _aia_intermediates(host)
        except BaseException as e:  # noqa: BLE001 - a broken crypto build must not kill the run
            print(f"  could not complete the chain for {host}: {type(e).__name__}: {e}", flush=True)
            extra = []
        if extra:
            ctx.load_verify_locations(cadata="".join(extra))
    _ctx[host] = ctx
    return ctx


_host_failures = {}
HOST_GIVE_UP = 3          # consecutive connection-level failures before a host is skipped for this run
FILE_SECONDS = 20 * 60    # wall-clock cap for one download


def _tls_error(e):
    r = e if isinstance(e, ssl.SSLCertVerificationError) else getattr(e, "reason", None)
    return r if isinstance(r, ssl.SSLCertVerificationError) else None


def download(url, dest, tries=3):
    """None on success, else the reason. Logs every attempt."""
    host = urllib.parse.urlparse(url).hostname
    if _host_failures.get(host, 0) >= HOST_GIVE_UP:
        return f"host {host} skipped this run after {HOST_GIVE_UP} consecutive failures"
    fix = False
    last = None
    i = 0
    while i < tries:
        t0 = time.time()
        try:
            req = urllib.request.Request(urllib.parse.quote(url, safe=":/%?=&+~#,;@"), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60, context=context(host, fix)) as r, open(dest, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    if time.time() - t0 > FILE_SECONDS:
                        raise TimeoutError(f"slower than {FILE_SECONDS // 60} min")
            with open(dest, "rb") as f:
                if f.read(5) != b"%PDF-":
                    raise IOError("not a PDF")
            _host_failures[host] = 0
            print(f"  got {url} ({os.path.getsize(dest):,} bytes, {time.time() - t0:.0f}s)", flush=True)
            return None
        except urllib.error.HTTPError as e:
            _host_failures[host] = 0          # the host answered
            if e.code in (404, 410):
                return f"HTTP {e.code}"
            last = f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001 - every network error is retried, then reported
            tls = _tls_error(e)
            if tls and not fix:
                print(f"  TLS {tls.verify_message} for {host}: completing the chain from AIA", flush=True)
                fix = True
                continue                       # retry at once with the completed chain (not counted)
            last = f"TLS: {tls.verify_message}" if tls else f"{type(e).__name__}: {e}"
            if not isinstance(e, urllib.error.HTTPError):
                _host_failures[host] = _host_failures.get(host, 0) + 1
                if _host_failures[host] >= HOST_GIVE_UP:
                    break
        print(f"  attempt {i + 1} failed for {url}: {last}", flush=True)
        i += 1
        time.sleep(2 ** (i + 1))
    return last


# ---------- GitHub release ----------
def gh(*args, check=True):
    p = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and p.returncode:
        raise RuntimeError(f"gh {' '.join(args)}: {p.stderr.strip()}")
    return p


def release_assets():
    if gh("release", "view", TAG, check=False).returncode:
        gh("release", "create", TAG, "--title", "L0 archive (raw source documents)", "--notes",
           "Every raw document the warehouse is built from, named by sha256. Index: meta/l0_archive.csv. "
           "Written only by .github/workflows/l0-archive.yml. Never edit or delete an asset.")
    p = gh("release", "view", TAG, "--json", "assets")
    return {a["name"] for a in json.loads(p.stdout)["assets"]}


def write_manifest(source, entry):
    p = os.path.join(REPO, source, "data", "_documents_manifest.csv")
    fields = ["edition", "file_name", "source_url", "sha256", "size_bytes", "pages", "retrieved_date", "identity_check"]
    cur = [r for r in rows(p) if r["file_name"] != entry["file_name"]]
    cur.append(entry)
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(sorted(cur, key=lambda r: (str(r["edition"]), r["file_name"])))


def main():
    idx = load_index()
    todo = [t for t in targets() if not (t["sha256"] and idx.get(t["sha256"], {}).get("status") == "ARCHIVED")
            and not (t["mode"] == "identify" and any(r["file_name"] == t["file_name"] and r["status"] == "ARCHIVED"
                                                     for r in idx.values()))]
    if "--plan" in sys.argv:
        gb = sum(t["size"] for t in todo) / 1e9
        print(f"{len(todo)} to archive (~{gb:.1f} GB known): "
              + ", ".join(f"{m} {sum(t['mode'] == m for t in todo)}" for m in ("verify", "identify")))
        return
    max_bytes = float(sys.argv[sys.argv.index("--max-gb") + 1]) * 1e9 if "--max-gb" in sys.argv else 9e9
    max_sec = float(sys.argv[sys.argv.index("--max-minutes") + 1]) * 60 if "--max-minutes" in sys.argv else 300 * 60
    have = release_assets()
    t0, done_bytes, report = time.time(), 0, []
    work = tempfile.mkdtemp()
    for t in todo:
        if done_bytes >= max_bytes or time.time() - t0 >= max_sec:
            report.append(f"stopped at budget; {len(todo) - len(report)} left for the next run")
            break
        if t["mode"] == "verify" and f"{t['sha256']}.pdf" in have:
            idx[t["sha256"]] = {"sha256": t["sha256"], "file_name": t["file_name"], "series_id": t["series_id"],
                                "source_url": t["urls"][0], "size_bytes": t["size"], "release_tag": TAG,
                                "asset_name": f"{t['sha256']}.pdf", "status": "ARCHIVED",
                                "check": "sha256 matches registry", "archived_on": date.today().isoformat()}
            continue
        result = None
        for url in t["urls"]:
            dest = os.path.join(work, "dl.pdf")
            err = download(url, dest)
            if err:
                result = ("UNREACHABLE", url, err, None)
                continue
            got = sha256(dest)
            size = os.path.getsize(dest)
            if t["mode"] == "verify":
                if got != t["sha256"]:
                    result = ("MISMATCH", url, f"publisher now serves sha256 {got} ({size} bytes)", None)
                    break
                result = ("ARCHIVED", url, "sha256 matches registry", dest)
                break
            src_dir = os.path.join(REPO, t["source"])
            p = subprocess.run([sys.executable, os.path.join(HERE, "l0_identity.py"), dest, src_dir,
                                "--name", t["file_name"]], capture_output=True, text=True)
            try:
                ident = json.loads(p.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError):
                ident = {"identity": "FAIL", "amounts_found": 0, "amounts_checked": 0, "pages": 0}
            note = f"{ident['identity']}: {ident['amounts_found']}/{ident['amounts_checked']} cited amounts on cited pages"
            if ident["identity"] == "PASS":
                result = ("ARCHIVED", url, note + " (meta/l0_identity.py)", dest)
                write_manifest(t["source"], {"edition": t["edition"], "file_name": t["file_name"], "source_url": url,
                                             "sha256": got, "size_bytes": size, "pages": ident["pages"],
                                             "retrieved_date": date.today().isoformat(),
                                             "identity_check": note + " (meta/l0_identity.py)"})
                break
            result = ("NOT_IDENTIFIED", url, note, None)
        status, url, note, path = result
        key = sha256(path) if path else (t["sha256"] or f"unarchived:{t['file_name']}")
        if path:
            asset = os.path.join(work, f"{key}.pdf")
            os.replace(path, asset)
            if f"{key}.pdf" not in have:
                gh("release", "upload", TAG, asset)
                have.add(f"{key}.pdf")
            done_bytes += os.path.getsize(asset)
            os.remove(asset)
        idx[key] = {"sha256": key, "file_name": t["file_name"],
                    "series_id": t["series_id"], "source_url": url, "size_bytes": t["size"] or "",
                    "release_tag": TAG if path else "", "asset_name": f"{key}.pdf" if path else "",
                    "status": status, "check": note, "archived_on": date.today().isoformat() if path else ""}
        report.append(f"{status:<14} {t['series_id']:<26} {t['file_name']}  {note}")
        print(report[-1], flush=True)
        save_index(idx)
    save_index(idx)
    shutil.rmtree(work, ignore_errors=True)
    from collections import Counter
    tally = Counter(r["status"] for r in idx.values())
    lines = ["## L0 archive", "", ", ".join(f"{v} {k}" for k, v in sorted(tally.items())), ""] + \
            [f"- {r}" for r in report if not r.startswith("ARCHIVED")][:60]
    dest = os.environ.get("GITHUB_STEP_SUMMARY")
    if dest:
        with open(dest, "a") as f:
            f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
