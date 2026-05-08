"""Standalone bootstrap: load secrets.toml directly and run init_db().

Useful for the first cold-run so the schema exists before Streamlit starts.
"""
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Stuff secrets.toml into streamlit's runtime *before* importing db.connection.
import streamlit as st  # noqa: E402

secrets_path = ROOT / ".streamlit" / "secrets.toml"
data = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
for section, values in data.items():
    if isinstance(values, dict):
        for k, v in values.items():
            st.secrets._secrets = getattr(st.secrets, "_secrets", {}) or {}
            st.secrets._secrets.setdefault(section, {})[k] = v
    else:
        st.secrets._secrets = getattr(st.secrets, "_secrets", {}) or {}
        st.secrets._secrets[section] = values

# Sanity print
print(f"loaded secrets sections: {list(data.keys())}")

from db.connection import init_db, get_engine, schema_name  # noqa: E402
from sqlalchemy import text  # noqa: E402

print(f"target schema: {schema_name()}")
init_db()
print("init_db() ok")

with get_engine().connect() as conn:
    rows = conn.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = :s ORDER BY table_name"
        ),
        {"s": schema_name()},
    ).fetchall()
print("tables present:")
for (t,) in rows:
    print(f"  - {schema_name()}.{t}")
