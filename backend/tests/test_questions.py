"""The questions each of the three users would actually ask.

These were written before the agent, as the definition of "done".
They call the real LLM and database, so they need the .env file.
Run with:  pytest tests/test_questions.py -v
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.path.exists(os.path.join(os.path.dirname(__file__), "..", ".env")),
    reason="needs OPENAI_API_KEY and DATABASE_URL",
)

# (role, question, what we expect)
#   kind:    read / write / chat
#   blocked: the role must be refused
#   chart:   a chart is expected in the answer
CASES = [
    # Business Owner: the big picture
    ("Business Owner", "How much did we spend on purchase orders last month?", {"kind": "read"}),
    ("Business Owner", "Who are our top 5 vendors by PO value?", {"kind": "read", "chart": True}),
    ("Business Owner", "How many purchase orders do we have by status?", {"kind": "read"}),
    ("Business Owner", "Show inbound vs outbound stock movement for the last 6 months", {"kind": "read", "chart": True}),
    ("Business Owner", "How much is still unpaid on purchase orders?", {"kind": "read"}),
    # Procurement Owner: POs, vendors, receipts
    ("Procurement Owner", "Which purchase orders are still open?", {"kind": "read"}),
    ("Procurement Owner", "Which POs are past their expected delivery date?", {"kind": "read"}),
    ("Procurement Owner", "Which unexpected receipts are not yet matched to a PO?", {"kind": "read"}),
    ("Procurement Owner", "Show the number of POs by status", {"kind": "read", "chart": True}),
    ("Procurement Owner", "Which teams were issued the most stock last month?", {"blocked": True}),
    # Inventory Owner: stock and movement
    ("Inventory Owner", "Show inventory movement of items for the last 6 months", {"kind": "read", "chart": True}),
    ("Inventory Owner", "Which items are below their minimum stock level?", {"kind": "read"}),
    ("Inventory Owner", "What stock do we hold at location 132-1?", {"kind": "read"}),
    ("Inventory Owner", "Which teams were issued the most stock last month?", {"kind": "read", "chart": True}),
    ("Inventory Owner", "What are the payment terms of our vendors?", {"blocked": True}),
    # Write (bonus): must ask for confirmation, must NOT run by itself
    ("Inventory Owner", "Set the minimum stock level of item BO-MC-0081 at location 132-1 to 20", {"kind": "write"}),
    ("Procurement Owner", "Set the minimum stock level of item BO-MC-0081 at location 132-1 to 20", {"blocked": True}),
    # Small talk
    ("Business Owner", "Hello!", {"kind": "chat"}),
]


@pytest.mark.parametrize("role,question,expect", CASES)
def test_question(role, question, expect):
    from agent import ask

    result = ask(question, role)
    print(f"\n[{role}] {question}\n  -> {result['answer']}\n  SQL: {result['sql']}")

    assert result["answer"], "the bot should always say something"

    if expect.get("blocked"):
        assert result["blocked"], "this role should have been refused"
        return

    assert not result["blocked"], f"unexpectedly blocked: {result['answer']}"
    assert result["kind"] == expect["kind"]

    if expect["kind"] == "read":
        assert result["sql"].lower().lstrip().startswith(("select", "with"))
        assert "couldn't get that data" not in result["answer"], "SQL failed twice"
    if expect["kind"] == "write":
        assert result["needs_confirmation"], "writes must wait for the user to confirm"
        assert result["sql"].lower().lstrip().startswith(("insert", "update"))
    if expect.get("chart"):
        chart = result["chart"]
        assert chart and chart["type"] in ("bar", "line"), "expected a chart"
        assert len(chart["data"]) > 0
        x_values = [row[chart["x"]] for row in chart["data"]]
        assert len(set(x_values)) == len(x_values), "chart must have one point per x value"
