import sys
sys.path.insert(0, r"d:\Downloads\Hackathon\Github\Deldot-Contract-team\src")
from extract import load_package

pkg = load_package(r"d:\Downloads\Hackathon\Github\Deldot-Contract-team\Contract_Clause_Risk_Flagging\Development\Harbor_Crossing")
for doc in pkg.documents:
    print(f"\n########## {doc.file_name} ({doc.document_type}) ##########")
    for ln in doc.lines:
        print(f"[p{ln.page}:L{ln.line_on_page}] <{ln.heading[:34]}> {ln.text}")
