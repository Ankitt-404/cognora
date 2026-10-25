import time
from app.search import search, _search

qs = ["How many credits does Data Structures carry?",
      "Which tree structures are taught in Data Structures?",
      "Which queuing models and measures are taught?"] * 3

search("warmup", k=3)                       # load models once
for name, fn in [("hybrid only", lambda q: _search(q, None, 10)),
                 ("hybrid + rerank", lambda q: search(q, k=10))]:
    t = []
    for q in qs:
        s = time.perf_counter(); fn(q); t.append(time.perf_counter() - s)
    print(f"{name}: avg {sum(t)/len(t)*1000:.0f} ms")