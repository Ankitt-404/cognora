from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, UploadFile
from app.auth import current_user, router as auth_router
from pydantic import BaseModel, Field
from app.answer import answer_question
from app.search import search
from app.db import get_conn
from fastapi.middleware.cors import CORSMiddleware
from app.ingestion import create_document, process_document
from app.memory import create_conversation, load_history, save_turn
from app.agent import run_agent
MAX_BYTES = 25 * 1024 * 1024    

app = FastAPI()
app.include_router(auth_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"status": "ok"}


@app.post("/documents", status_code=202)
def upload(file: UploadFile, background: BackgroundTasks, user: str = Depends(current_user)):
    data = file.file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large (max 25 MB).")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "Not a PDF file.")
    doc_id, status, is_new = create_document(user, file.filename or "upload.pdf", data)
    if is_new:
        background.add_task(process_document, doc_id, data)
    return {"id": doc_id, "status": status}


@app.get("/documents")
def list_documents(user: str = Depends(current_user)):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, status, page_count FROM documents "
            "WHERE owner_id = %s ORDER BY id DESC",
            (user,),
        ).fetchall()
    return [{"id": r[0], "title": r[1], "status": r[2], "pages": r[3]} for r in rows]


@app.get("/documents/{doc_id}")
def get_document(doc_id: int, user : str = Depends(current_user)):
    with get_conn() as conn:
        document = conn.execute(
            "SELECT d.id, d.title, d.status, d.error, d.page_count, "
            "(SELECT COUNT(*) FROM chunks WHERE document_id = d.id) "
            "FROM documents d WHERE d.id = %s AND d.owner_id=%s",
            (doc_id,user),
        ).fetchone()
        if not document:
            raise HTTPException(404, "Document not found.")
        return {
        "id": document[0],
        "title": document[1],
        "status": document[2],
        "error": document[3],
        "pages": document[4],
        "chunks": document[5],
    }


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    document_ids: list[int] | None = None
    k: int = Field(default=6, ge=1, le=20)


@app.post("/search")
def search_endpoint(body: SearchRequest, user: str = Depends(current_user)):
    return search(body.query,user, body.document_ids, body.k)

class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    document_ids: list[int] | None = None
    k: int = Field(default=3, ge=1, le=10)
    conversation_id: int | None = None


@app.post("/chat")
def chat(body: ChatRequest, user: str =Depends(current_user)):
    if not body.conversation_id:
        cid = create_conversation(user,body.question)
        history = []
    else:
        cid = body.conversation_id
        history = load_history(cid,user)
    result = answer_question(body.question,user, body.document_ids, body.k, history)
    save_turn(cid, body.question,user, result["answer"], result["sources"])
    return {"conversation_id": cid, **result}

class AgentRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    document_ids: list[int] | None = None
    conversation_id: int | None = None


@app.post("/agent")
def agent_endpoint(body: AgentRequest, user: str = Depends(current_user)):
    if not body.conversation_id:
        cid = create_conversation(body.question)
        history = []
    else:
        cid = body.conversation_id
        history = load_history(cid)
    result = run_agent(body.question, history, body.document_ids,user)
    save_turn(cid,user, body.question, result["answer"], result["sources"])
    return {"conversation_id": cid, **result}