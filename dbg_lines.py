import sys

sys.path.insert(0, "backend")
from app.services.clause_service import _NUMBER_RE, _MD_HEADING_RE, _MARKER_RE, _keyword_heading

text = open(r"C:\Users\durai\AppData\Local\Temp\opencode\stamas_debug_text.txt", encoding="utf-8").read()
for raw in text.split("\n"):
    line = raw.strip()
    if not line or _MARKER_RE.match(line):
        continue
    md = _MD_HEADING_RE.match(line)
    num = _NUMBER_RE.match(line)
    kw = None if (md or num) else _keyword_heading(line)
    upper = line.isupper() and 4 <= len(line) <= 100 and not line.endswith(".")
    if md or num or kw or upper:
        print(f"num={bool(num)} kw={kw!r:.40} upper={upper} | {line[:70]!r}")
print("---- raw repr of heading lines ----")
for raw in text.split("\n"):
    if "SCOPE OF SUPPLY" in raw or raw.strip().startswith("2. WARRANTY"):
        print(repr(raw))
