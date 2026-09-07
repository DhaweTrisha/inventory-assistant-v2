"""Small helper for talking to the Postgres database on Railway."""
import os
from datetime import date, datetime
from decimal import Decimal

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()


def _url():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
    return url


def _clean(value):
    # Make values JSON friendly so the API and the charts can use them
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def run_read_query(sql, limit=200):
    """Run a SELECT in a read-only transaction. Returns (columns, rows)."""
    with psycopg.connect(_url(), row_factory=dict_row, options="-c statement_timeout=20000") as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [d.name for d in cur.description]
            rows = cur.fetchmany(limit)
    rows = [{k: _clean(v) for k, v in row.items()} for row in rows]
    return columns, rows


def run_write_query(sql):
    """Run a single INSERT or UPDATE and commit. Returns number of rows affected."""
    with psycopg.connect(_url(), options="-c statement_timeout=20000") as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            affected = cur.rowcount
        conn.commit()
    return affected
