"""The LangGraph agent.

Flow:  question -> write_sql -> check_access -> run_sql -> answer
                                     |               |
                                     +-> (blocked / write needs confirmation / just chat) -> END
                                                     +-> on SQL error, go back to write_sql once
"""
import json
import os
from typing import Optional, TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from db import run_read_query, run_write_query
from guards import check_sql, denied_tables
from roles import ROLES
from schema import SCHEMA_NOTES

load_dotenv()

llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), temperature=0).bind(
    response_format={"type": "json_object"}
)

MAX_ATTEMPTS = 2


class AgentState(TypedDict, total=False):
    question: str
    role: str
    history: list
    kind: str            # "read", "write" or "chat"
    sql: str
    reply: str
    columns: list
    rows: list
    error: str
    attempts: int
    answer: str
    chart: Optional[dict]
    needs_confirmation: bool
    blocked: bool


def ask_llm(system, user):
    response = llm.invoke([("system", system), ("user", user)])
    return json.loads(response.content)


# ---------- node 1: turn the question into SQL ----------

SQL_PROMPT = """You are a data assistant for a manufacturing company's inventory and procurement system.
Turn the user's question into ONE PostgreSQL query.

{schema}

The user is the {role}. {role_description}

Reply in JSON exactly like this: {{"kind": "read" | "write" | "chat", "sql": "...", "reply": "..."}}
- kind "read": the question needs data. Put a single SELECT in "sql".
- kind "write": the user clearly asks to CHANGE data (e.g. set a minimum stock level, add a vendor).
  Put a single INSERT or UPDATE in "sql". Never DELETE. Always include a WHERE clause on UPDATE.
- kind "chat": greeting, thanks, or something unrelated to the data. Put a short friendly reply in "reply".

SQL rules:
- Only use tables and columns from the schema above. Join through the ids shown.
- Show human readable names (item name, vendor name, location name), not ids.
- For trends over time group by month: to_char(date_trunc('month', <date column>), 'YYYY-MM') AS month, ordered by month.
- Use short, readable column aliases (month, item_name, total_quantity, total_amount ...).
- Round money to 2 decimals. LIMIT lists to 50 rows unless asked otherwise.
- Answer ONLY the current question. Earlier turns matter only for follow-ups like "and for last month?"
  or "same for vendor X". Never carry a date or other filter over from an earlier question.
- Wrap totals in COALESCE(SUM(...), 0) so an empty period shows 0 instead of nothing.
- For trends over time keep it to a few series that fit on one chart: group by month and ONE category
  (e.g. transaction_type, status, category name). Do not break a trend down by individual item unless the
  user names specific items. For stock movement show inbound and outbound separately.
  Example: "Show inventory of items for the last 6 months" means ALL items together ->
  one row per month with total_inbound and total_outbound columns.
"""


def write_sql(state: AgentState):
    role = state["role"]
    system = SQL_PROMPT.format(
        schema=SCHEMA_NOTES, role=role, role_description=ROLES[role]["description"]
    )

    parts = []
    history = state.get("history", [])[-6:]
    if history:
        parts.append("Earlier conversation (context only, do NOT reuse its filters unless the new question refers to them):")
        for turn in history:
            parts.append(f"  {turn['role']}: {turn['content']}")
        parts.append("")
    parts.append(f"Current question to answer: {state['question']}")

    if state.get("error"):
        parts.append(
            f"\nYour previous SQL failed:\n{state.get('sql')}\nError: {state['error']}\n"
            "Please fix it and return the corrected query."
        )

    result = ask_llm(system, "\n".join(parts))
    return {
        "kind": result.get("kind", "read"),
        "sql": (result.get("sql") or "").strip(),
        "reply": result.get("reply", ""),
        "error": "",
    }


# ---------- node 2: role based access + safety ----------

def check_access(state: AgentState):
    role = state["role"]
    kind = state["kind"]
    sql = state.get("sql", "")

    if kind == "chat":
        return {"answer": state.get("reply") or "Hi! Ask me about stock, purchase orders or vendors.", "sql": ""}

    problem = check_sql(sql, kind)
    if problem:
        return {"blocked": True, "answer": f"I can't run that: {problem}"}

    denied = denied_tables(sql, role, write=(kind == "write"))
    if denied:
        nice = ", ".join(denied)
        action = "change" if kind == "write" else "see"
        return {
            "blocked": True,
            "answer": f"Sorry, as the {role} you don't have permission to {action} {nice}. "
                      "Please ask the Business Owner.",
        }

    if kind == "write":
        return {
            "needs_confirmation": True,
            "answer": "Here is the change I'm about to make. Please confirm before I save it.",
        }

    return {}


# ---------- node 3: run the query ----------

def run_sql(state: AgentState):
    try:
        columns, rows = run_read_query(state["sql"])
        return {"columns": columns, "rows": rows, "error": ""}
    except Exception as e:
        return {"error": str(e).split("\n")[0], "attempts": state.get("attempts", 0) + 1}


# ---------- node 4: explain the result and pick a chart ----------

ANSWER_PROMPT = """You explain query results to a business user in plain English.

Reply in JSON exactly like this:
{"answer": "...", "chart": {"type": "bar" | "line" | "none", "title": "...", "x": "<column>", "y": ["<numeric column>", ...]}}

- Keep the answer short (1 to 4 sentences) and mention the key numbers. Never mention SQL.
- Only money columns (amount, value, price, total_amount) are in INR. Quantities are units of stock, not money.
- Use "line" for trends over time (months), "bar" for comparing items / vendors / locations / statuses,
  and "none" for a single number, a yes/no, or a plain list of names.
- x must be a column from the results. y must be numeric columns from the results.
- If there are no rows, say that no matching data was found and suggest a nearby question
  (e.g. "try last month" - the data covers April to August 2026).
"""


def pivot_if_needed(rows, columns, chart):
    """Charts want one row per x value. If the query came back "long" (e.g. month, transaction_type,
    total) turn it "wide" (month, inbound, outbound) so every series gets its own line / bar."""
    x, y = chart.get("x"), chart.get("y", [])
    xs = [r[x] for r in rows]
    if len(set(xs)) == len(xs):
        return rows, y  # already one row per x, nothing to do
    if len(y) != 1 or len(columns) != 3:
        return None, y  # repeated x values we can't untangle -> skip the chart
    series_col = [c for c in columns if c not in (x, y[0])][0]
    series = sorted({str(r[series_col]) for r in rows})
    if len(series) > 6:
        return None, y  # too many series for one chart
    wide = {}
    for r in rows:
        wide.setdefault(r[x], {x: r[x]})[str(r[series_col])] = r[y[0]]
    return list(wide.values()), series


def answer(state: AgentState):
    if state.get("error"):
        return {
            "answer": "Sorry, I couldn't get that data from the database. Could you rephrase the question?",
            "chart": None,
        }

    rows = state.get("rows", [])
    columns = state.get("columns", [])
    user = (
        f"Question: {state['question']}\n"
        f"Columns: {columns}\n"
        f"Row count: {len(rows)}\n"
        f"First rows (JSON): {json.dumps(rows[:40], default=str)}"
    )
    result = ask_llm(ANSWER_PROMPT, user)

    chart = result.get("chart") or {"type": "none"}
    if chart.get("type") in ("bar", "line") and rows:
        y = [c for c in chart.get("y", []) if c in columns]
        if chart.get("x") in columns and y:
            chart["y"] = y
            data, chart["y"] = pivot_if_needed(rows, columns, chart)
            chart["data"] = data[:50] if data else []
            if not data:
                chart = {"type": "none"}
        else:
            chart = {"type": "none"}
    else:
        chart = {"type": "none"}

    return {"answer": result.get("answer", ""), "chart": chart}


# ---------- wire the graph ----------

def after_access(state: AgentState):
    if state.get("blocked") or state.get("needs_confirmation") or state.get("kind") == "chat":
        return END
    return "run_sql"


def after_run(state: AgentState):
    if state.get("error") and state.get("attempts", 0) < MAX_ATTEMPTS:
        return "write_sql"
    return "answer"


graph = StateGraph(AgentState)
graph.add_node("write_sql", write_sql)
graph.add_node("check_access", check_access)
graph.add_node("run_sql", run_sql)
graph.add_node("answer", answer)

graph.add_edge(START, "write_sql")
graph.add_edge("write_sql", "check_access")
graph.add_conditional_edges("check_access", after_access, {"run_sql": "run_sql", END: END})
graph.add_conditional_edges("run_sql", after_run, {"write_sql": "write_sql", "answer": "answer"})
graph.add_edge("answer", END)

app_graph = graph.compile()


# ---------- what the API calls ----------

def ask(question, role, history=None):
    """Answer one question for one role. Returns a plain dict for the API."""
    if role not in ROLES:
        raise ValueError(f"Unknown role: {role}")

    state = app_graph.invoke({"question": question, "role": role, "history": history or [], "attempts": 0})
    return {
        "answer": state.get("answer", ""),
        "kind": state.get("kind", ""),
        "sql": state.get("sql", ""),
        "columns": state.get("columns", []),
        "rows": state.get("rows", []),
        "chart": state.get("chart"),
        "blocked": bool(state.get("blocked")),
        "needs_confirmation": bool(state.get("needs_confirmation")),
    }


def confirm_write(sql, role):
    """Run a write the user has confirmed in the UI. Re-checks safety and permissions."""
    if role not in ROLES:
        raise ValueError(f"Unknown role: {role}")
    problem = check_sql(sql, "write")
    if problem:
        return {"ok": False, "answer": f"I can't run that: {problem}"}
    denied = denied_tables(sql, role, write=True)
    if denied:
        return {"ok": False, "answer": f"As the {role} you can't change {', '.join(denied)}."}
    try:
        affected = run_write_query(sql)
    except Exception as e:
        return {"ok": False, "answer": f"The database rejected the change: {str(e).splitlines()[0]}"}
    if affected == 0:
        return {"ok": True, "answer": "I ran the change but no matching record was found, so nothing was updated."}
    return {"ok": True, "answer": f"Done. {affected} row(s) updated."}
