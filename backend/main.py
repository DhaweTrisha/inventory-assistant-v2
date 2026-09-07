"""FastAPI backend. The Next.js frontend talks to these three endpoints."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import ask, confirm_write
from roles import ROLES

app = FastAPI(title="Inventory & Procurement Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str
    role: str
    history: list = []


class ConfirmRequest(BaseModel):
    sql: str
    role: str


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/roles")
def roles():
    # The UI uses this for the role dropdown and the suggested questions
    return {
        name: {"description": r["description"], "suggested_questions": r["suggested_questions"]}
        for name, r in ROLES.items()
    }


@app.post("/chat")
def chat(req: ChatRequest):
    if req.role not in ROLES:
        raise HTTPException(400, f"Unknown role: {req.role}")
    return ask(req.question, req.role, req.history)


@app.post("/confirm")
def confirm(req: ConfirmRequest):
    if req.role not in ROLES:
        raise HTTPException(400, f"Unknown role: {req.role}")
    return confirm_write(req.sql, req.role)
