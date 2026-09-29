"""REAL E2E part 1: tender -> upload real PDF -> extract -> clauses ->
Gemini opportunity analysis (+quality check vs ground truth) -> failures.
Uses a unique tenderNo per run; cleans up its own rows/files at the end.
Writes TENDER_ID to temp file for part 2 (post-restart persistence check).
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8000"
FX = Path(r"C:\Users\durai\AppData\Local\Temp\opencode\stamas_real_tender.pdf")
passed = []
RUN = int(time.time())
TENDER_NO = f"CPCL/TEST/REAL-{RUN}"

GT = {  # must match stamas_gen_real.py
    "ref": "7812345",
    "value": "8,40,00,000",
    "value_short": "8.40",
    "emd": "16,80,000",
    "deadline": "21-Oct-2026",
    "org": "Chennai Petroleum",
    "duration": "12 months",
}


def check(name, cond, extra=""):
    assert cond, "FAIL: " + name + " " + str(extra)
    passed.append(name)
    print("  ok:", name, ("| " + str(extra) if extra else ""))


def api(method, path, body=None, raw=None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": ctype} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


print("== 1-2. health + create tender ==")
st, h = api("GET", "/api/system/health")
check("health connected", st == 200 and h["database"]["connected"] is True)
check("gemini live", h.get("isLiveAI") is True, h.get("aiEngine"))
st, nt = api("POST", "/api/tenders", {"title": "REAL E2E Cryogenic Vessels", "tenderNo": TENDER_NO})
check("create 201", st == 201)
tid = nt["data"]["id"]

try:
    print("== 3-5. real PDF upload ==")
    pdf = FX.read_bytes()
    check("fixture size sane", 1000 < len(pdf) < 500000, len(pdf))
    bnd = "REALBND"
    body = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"cryo_tender.pdf\"\r\n"
            f"Content-Type: application/pdf\r\n\r\n").encode() + pdf + f"\r\n--{bnd}--\r\n".encode()
    st, up = api("POST", f"/api/tenders/{tid}/documents", raw=body,
                 ctype=f"multipart/form-data; boundary={bnd}")
    check("upload 201", st == 201, up.get("message", ""))
    doc = up["documents"][0]
    check("PROCESSED", doc["status"] == "PROCESSED", doc.get("error") or "")
    check("pages tracked", (doc.get("pageCount") or 0) >= 2, doc.get("pageCount"))
    check("file on disk", any(Path("backend/storage/documents").glob(f"{doc['id']}__*")))
    doc_id = doc["id"]

    print("== 6-7. text + clauses ==")
    st, tx = api("GET", f"/api/tenders/{tid}/documents/{doc_id}/text")
    check("text has NACE", st == 200 and "NACE MR0175" in tx["text"], f"len={tx.get('textLength')}")
    check("text has value", GT["value"] in tx["text"])
    st, cl = api("GET", f"/api/tenders/{tid}/clauses")
    check("clauses >= 5", st == 200 and cl["count"] >= 5, cl.get("count"))
    check("numbered+source", any(c["number"] for c in cl["clauses"])
          and all(c["sourceDocumentId"] == doc_id for c in cl["clauses"]))
    titles = [c["title"] for c in cl["clauses"]]
    check("scope clause", any("SCOPE" in t.upper() for t in titles), titles)

    print("== 8-9. Gemini opportunity analysis ==")
    st, an = api("POST", f"/api/tenders/{tid}/analyze", {"bidderName": "Probe Valves Ltd"})
    check("analyze 200", st == 200, str(st))
    rec = an["analysis"]
    check("engine Gemini", rec["engine"] == "Gemini AI", rec["engine"])
    r = rec["result"]
    for k in ("tenderInfo", "eligibility", "commercial", "technical", "risks",
              "bidderFit", "opportunitySignal", "signalReasoning"):
        check(f"key {k}", k in r)
    check("signal valid", r["opportunitySignal"] in ("HIGH", "MEDIUM", "LOW", "INSUFFICIENT DATA"),
          r["opportunitySignal"])
    analysis_id = rec["id"]

    print("== 10. quality check vs ground truth ==")
    info = r["tenderInfo"]
    field_map = {"ref": "referenceNumber", "value": "estimatedValue", "emd": "emd",
                 "deadline": "submissionDeadline", "org": "organization", "duration": "contractDuration"}
    gt_vals = {"ref": [GT["ref"]], "value": [GT["value"], GT["value_short"]], "emd": [GT["emd"]],
               "deadline": [GT["deadline"]], "org": [GT["org"]], "duration": [GT["duration"]]}
    for k, cands in gt_vals.items():
        got = str(info.get(field_map[k], ""))
        check(f"ground-truth {k}", any(c in got for c in cands), got[:70])
    print("   signal:", r["opportunitySignal"], "| reasoning:", str(r["signalReasoning"])[:130])

    print("== 11. persistence via latest ==")
    st, latest = api("GET", f"/api/tenders/{tid}/analyses/latest")
    check("latest same id", st == 200 and latest["analysis"]["id"] == analysis_id)

    print("== 12. failure matrix ==")
    def up_files(files, tender=tid):
        b = "FBND"
        body = b""
        for fname, data, ctype in files:
            body += f"--{b}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"{fname}\"\r\nContent-Type: {ctype}\r\n\r\n".encode() + data + b"\r\n"
        body += f"--{b}--\r\n".encode()
        return api("POST", f"/api/tenders/{tender}/documents", raw=body,
                   ctype=f"multipart/form-data; boundary={b}")

    st, _ = up_files([("x.txt", b"hello", "text/plain")])
    check("bad ext 415", st == 415)
    st, _ = up_files([("e.pdf", b"", "application/pdf")])
    check("empty 400", st == 400)
    st, bad = up_files([("c.pdf", b"%PDF garbage not a pdf" * 50, "application/pdf")])
    check("corrupt FAILED honest", st == 201 and bad["documents"][0]["status"] == "FAILED")
    st, _ = up_files([("big.pdf", b"0" * (16 * 1024 * 1024), "application/pdf")])
    check("oversize 413", st == 413)
    st, _ = api("POST", f"/api/tenders/{tid}/clauses/nope/verify", {})
    check("bogus clause 404", st == 404)

    Path(r"C:\Users\durai\AppData\Local\Temp\opencode\stamas_e2e_tid.txt").write_text(tid)
    print(f"\nPART 1 PASSED ({len(passed)} checks). TENDER_UNDER_TEST={tid}")
finally:
    # remove ONLY this run's rows + files; never touch other data
    import asyncio
    sys.path.insert(0, "backend")
    from sqlalchemy import text as _t
    from app.db.database import session_scope, dispose_engine

    async def wipe():
        async with session_scope() as s:
            docs = (await s.execute(
                _t("SELECT id, storage_path FROM documents WHERE tender_id = :i"), {"i": tid}
            )).all()
            await s.execute(_t("DELETE FROM clauses WHERE tender_id = :i"), {"i": tid})
            await s.execute(_t("DELETE FROM analyses WHERE tender_id = :i"), {"i": tid})
            await s.execute(_t("DELETE FROM documents WHERE tender_id = :i"), {"i": tid})
            await s.execute(_t("DELETE FROM tenders WHERE id = :i"), {"i": tid})
            await s.commit()
        for _, spath in docs:
            try:
                Path(spath).unlink(missing_ok=True)
            except OSError:
                pass
        await dispose_engine()

    asyncio.run(wipe())
    print("cleanup: test rows + files removed")
