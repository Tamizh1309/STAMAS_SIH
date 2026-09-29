import sys

sys.path.insert(0, "backend")
from app.services.clause_service import _NUMBER_RE, extract_clauses

for s in ["1. SCOPE OF SUPPLY", "2.1 Bidder shall have average annual turnover", "3.1 Vessels shall be designed"]:
    mm = _NUMBER_RE.match(s.strip())
    print(repr(s[:45]), "->", mm.groups() if mm else None)

print("---extract---")
out = extract_clauses(
    "1. SCOPE OF SUPPLY\nSupply of two numbers 25 KL vessels for the refinery unit here.\n2. WARRANTY\nWarranty period of twenty four months from commissioning date applies.",
    source_document_id="d",
    source_document_name="f",
)
print("n:", len(out))
for c in out:
    print("-", repr(c["number"]), "|", repr(c["title"]))
