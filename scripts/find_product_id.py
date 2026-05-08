"""Print a few real id_produto values from the DB."""
from sqlalchemy import text
from db.connection import get_engine, schema_name

with get_engine().begin() as conn:
    rows = conn.execute(text(f'SELECT id_produto, desc_produto FROM "{schema_name()}".products LIMIT 5')).all()
    for r in rows:
        print(r.id_produto, r.desc_produto)
