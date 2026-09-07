"""Checks that don't need the LLM or the database: SQL guard rails and role permissions."""
from guards import check_sql, denied_tables, tables_in_sql


def test_finds_tables_in_sql():
    sql = "SELECT * FROM inv_items i JOIN inv_current_stock s ON s.item_id = i.id"
    assert tables_in_sql(sql) == ["inv_current_stock", "inv_items"]


def test_cte_names_are_not_tables():
    sql = "WITH monthly AS (SELECT 1 FROM inv_transactions) SELECT * FROM monthly"
    assert tables_in_sql(sql) == ["inv_transactions"]


def test_inventory_owner_cannot_see_vendors():
    sql = "SELECT name FROM proc_vendors"
    assert denied_tables(sql, "Inventory Owner") == ["proc_vendors"]


def test_procurement_owner_cannot_see_issue_history():
    sql = "SELECT * FROM inv_transactions"
    assert denied_tables(sql, "Procurement Owner") == ["inv_transactions"]


def test_business_owner_sees_everything():
    sql = "SELECT * FROM proc_po_payment_tranches t JOIN inv_transactions x ON true"
    assert denied_tables(sql, "Business Owner") == []


def test_procurement_owner_cannot_change_stock_levels():
    sql = "UPDATE inv_current_stock SET min_stock_level = 5 WHERE id = 'x'"
    assert denied_tables(sql, "Procurement Owner", write=True) == ["inv_current_stock"]


def test_read_must_be_select():
    assert check_sql("SELECT 1", "read") is None
    assert check_sql("WITH a AS (SELECT 1) SELECT * FROM a", "read") is None
    assert check_sql("UPDATE inv_items SET name = 'x' WHERE id = '1'", "read") is not None


def test_dangerous_statements_are_blocked():
    assert check_sql("DROP TABLE inv_items", "read") is not None
    assert check_sql("DELETE FROM inv_items WHERE id = '1'", "write") is not None
    assert check_sql("SELECT 1; DROP TABLE inv_items", "read") is not None


def test_update_needs_where():
    assert check_sql("UPDATE inv_current_stock SET min_stock_level = 5", "write") is not None
    assert check_sql("UPDATE inv_current_stock SET min_stock_level = 5 WHERE id = '1'", "write") is None


def test_created_at_column_is_not_mistaken_for_create():
    assert check_sql("SELECT created_at FROM inv_transactions", "read") is None


def test_write_with_lookup_subqueries_is_allowed():
    sql = ("UPDATE inv_current_stock SET min_stock_level = 20 "
           "WHERE item_id = (SELECT id FROM inv_items WHERE item_code = 'X') "
           "AND location_id = (SELECT id FROM inv_locations WHERE name = '132-1')")
    assert denied_tables(sql, "Inventory Owner", write=True) == []
    assert denied_tables(sql, "Procurement Owner", write=True) == ["inv_current_stock"]


def test_write_lookup_must_still_be_readable():
    sql = "INSERT INTO proc_vendors (id, name) SELECT id, name FROM inv_transactions"
    assert denied_tables(sql, "Procurement Owner", write=True) == ["inv_transactions"]
