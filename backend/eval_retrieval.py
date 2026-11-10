import json
import re
from pathlib import Path

from app.search import search
OWNER_ID = "b7306d90-fe1b-4e6f-91c8-2c2761ce4c73"
K = 10
cases = json.loads((Path(__file__).parent / "tests" / "questions.json").read_text(encoding="utf-8"))


def norm(s):
    return re.sub(r"\s+", " ", s.lower())


ranks = []
for case in cases:
    rank = None
    for rank, result in enumerate(search(case["question"], OWNER_ID, None, K), 1):
        text = norm(result["content"])
        if all(norm(t) in text for t in case["must_contain"]):
                
            break
    ranks.append(rank)
    print(f"[{rank if rank else 'MISS':>4}] {case['question']}")

n = len(ranks)
print()
for k in (1, 3, 5):
    print(f"Hit@{k}: {sum(1 for r in ranks if r and r <= k)}/{n}")
print(f"MRR: {sum(1 / r for r in ranks if r) / n:.3f}")