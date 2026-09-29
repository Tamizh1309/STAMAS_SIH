import sys
sys.path.insert(0, "backend")
from app.services import clause_service

text = open(r"C:\Users\durai\AppData\Local\Temp\opencode\stamas_debug_text.txt", encoding="utf-8").read()
print("=== first 600 chars ===")
print(text[:600])
print("=== line count:", len(text.split(chr(10))))
clauses = clause_service.extract_clauses(text, source_document_id="d", source_document_name="f")
print("clauses:", len(clauses))
for c in clauses[:10]:
    print("-", repr(c.get("number")), "|", repr(c.get("title"))[:60])
