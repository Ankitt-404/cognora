import re 
from app.search import search

CASES = [
    ("which complexity classes does the thoery course cover?",
     ["np hard and np complete", "complexity classes"]),
     ("which techniques solve linear programming problems in optimisation technique?",
      ["simplex alogritm", "big-m method", "duality"])
]

norm = lambda s: re.sub(r"\s+", " ",s.lower())

for q, phrases in CASES: 
    print("\n==", q)
    for rank, r in enumerate(search(q, k=10)[:5],1):
        c = norm(r["content"])
        found = [p for p in phrases if p in c]
        print(f"\n#{rank} pages {r['pages']} found {len(found)}/{len(phrases)}: {found}")
        print(r["content"][:250].replace("\n", " "))