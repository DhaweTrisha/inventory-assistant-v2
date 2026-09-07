"""Safety checks that run on every SQL the agent writes, before it touches the DB."""
import re

from roles import ALL_TABLES, ROLES

FORBIDDEN_WORDS = re.compile(r"\b(drop|delete|truncate|alter|grant|revoke|create)\b", re.IGNORECASE)


def tables_in_sql(sql):
    """Find table names after FROM / JOIN / UPDATE / INTO. Only real tables are returned."""
    found = re.findall(r"\b(?:from|join|update|into)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, re.IGNORECASE)
    return sorted({t.lower() for t in found if t.lower() in ALL_TABLES})


def target_table(sql):
    """The table an INSERT / UPDATE changes (the one right after UPDATE or INTO)."""
    match = re.search(r"\b(?:update|insert\s+into)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, re.IGNORECASE)
    return match.group(1).lower() if match else None


def denied_tables(sql, role, write=False):
    """Tables used in the SQL that this role is not allowed to touch.

    For a write, the table being changed must be in the role's write list and any
    other tables (used for lookups like "WHERE item_id = (SELECT id FROM inv_items ...)")
    must be in the role's read list.
    """
    read_ok = ROLES[role]["read_tables"]
    write_ok = ROLES[role]["write_tables"]
    denied = []
    target = target_table(sql) if write else None
    for table in tables_in_sql(sql):
        allowed = write_ok if table == target else read_ok
        if table not in allowed:
            denied.append(table)
    return denied


def check_sql(sql, kind):
    """Return an error message if the SQL is not safe to run, otherwise None."""
    s = (sql or "").strip().rstrip(";").strip()
    if not s:
        return "Empty query."
    if ";" in s:
        return "Only one statement at a time."
    if FORBIDDEN_WORDS.search(s):
        return "Only SELECT, INSERT and UPDATE are allowed."
    first_word = s.split()[0].lower()
    if kind == "read" and first_word not in ("select", "with"):
        return "Read queries must start with SELECT."
    if kind == "write":
        if first_word not in ("insert", "update"):
            return "Write queries must be INSERT or UPDATE."
        if first_word == "update" and not re.search(r"\bwhere\b", s, re.IGNORECASE):
            return "UPDATE must have a WHERE clause."
    return None
