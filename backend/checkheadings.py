
from app.ingestion import extract_pages
p = extract_pages(open(r"c:\Users\ankit\OneDrive\Documents\B_Tech_3rd sem syllabus.pdf", "rb").read())
for n, ls in p[:6]:
    for t, lv in ls:
        if lv is not None: print(n, lv, t)