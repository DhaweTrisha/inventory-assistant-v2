"""Who can see and change what.

Kept deliberately simple: the user picks a role in the UI, there is no login.
Access is controlled per table (not per column).
"""

INVENTORY_TABLES = [
    "inv_items", "inv_categories", "inv_sub_categories", "inv_sub_categories_2",
    "inv_current_stock", "inv_transactions", "inv_locations", "inv_issued_to_targets",
    "inv_field_definitions",
]

PROCUREMENT_TABLES = [
    "proc_purchase_orders", "proc_po_lines", "proc_po_receipts", "proc_vendors",
    "proc_po_payment_tranches", "proc_po_line_regularisations",
    "proc_unexpected_receipts", "proc_unexpected_receipt_headers",
    "po_templates", "po_template_lines",
]

ALL_TABLES = INVENTORY_TABLES + PROCUREMENT_TABLES + ["user_alert_emails"]

ROLES = {
    "Business Owner": {
        "description": (
            "Owns the business and approves spend. Wants the overall picture: "
            "spend, vendors, payments and stock health. Can see everything."
        ),
        "read_tables": ALL_TABLES,
        "write_tables": ["inv_current_stock", "proc_vendors"],
        "suggested_questions": [
            "How much did we spend on purchase orders last month?",
            "Who are our top 5 vendors by PO value?",
            "How much is still unpaid on purchase orders?",
            "Show inbound vs outbound stock movement for the last 6 months",
        ],
    },
    "Procurement Owner": {
        "description": (
            "Creates and tracks purchase orders, deals with vendors and payments. "
            "Can see procurement tables plus items and current stock (for reorder decisions), "
            "but not the detailed stock issue history."
        ),
        "read_tables": PROCUREMENT_TABLES + [
            "inv_items", "inv_categories", "inv_sub_categories", "inv_sub_categories_2",
            "inv_locations", "inv_current_stock",
        ],
        "write_tables": ["proc_vendors"],
        "suggested_questions": [
            "Which purchase orders are still open?",
            "Which POs are past their expected delivery date?",
            "Show the number of POs by status",
            "Which unexpected receipts are not yet matched to a PO?",
        ],
    },
    "Inventory Owner": {
        "description": (
            "Receives goods and manages stock across locations. Can see inventory tables "
            "and incoming POs / receipts, but not vendor details or payments."
        ),
        "read_tables": INVENTORY_TABLES + [
            "proc_purchase_orders", "proc_po_lines", "proc_po_receipts",
            "proc_unexpected_receipts", "proc_unexpected_receipt_headers",
        ],
        "write_tables": ["inv_current_stock"],
        "suggested_questions": [
            "Show inventory movement of items for the last 6 months",
            "Which items are below their minimum stock level?",
            "What stock do we hold at location 132-1?",
            "Which teams were issued the most stock last month?",
        ],
    },
}
