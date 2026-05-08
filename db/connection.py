"""SQLAlchemy engine that authenticates to RDS Postgres with IAM auth tokens.

IAM tokens expire after 15 minutes, so we never cache one. The engine's
``creator`` callable mints a fresh token on every checkout via boto3, and we
keep ``pool_recycle`` well under the TTL so idle connections are dropped before
their token would expire.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import boto3
import psycopg2
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parent.parent


def _pg_cfg() -> dict:
    return dict(st.secrets["postgres"])


def _aws_cfg() -> dict:
    return dict(st.secrets.get("aws", {}))


def _resolve_ca_path(value: str | None) -> str | None:
    if not value:
        return None
    p = Path(value)
    if not p.is_absolute():
        p = ROOT / p
    return str(p) if p.exists() else None


def _generate_iam_token() -> str:
    pg = _pg_cfg()
    aws = _aws_cfg()
    session_kwargs = {}
    if aws.get("profile"):
        session_kwargs["profile_name"] = aws["profile"]
    session = boto3.Session(**session_kwargs)
    rds = session.client("rds", region_name=aws.get("region") or os.environ.get("AWS_REGION"))
    return rds.generate_db_auth_token(
        DBHostname=pg["host"],
        Port=int(pg["port"]),
        DBUsername=pg["user"],
        Region=aws.get("region") or os.environ.get("AWS_REGION"),
    )


def _connect():
    pg = _pg_cfg()
    kwargs = {
        "host": pg["host"],
        "port": int(pg["port"]),
        "dbname": pg["database"],
        "user": pg["user"],
        "password": _generate_iam_token(),
        "sslmode": pg.get("sslmode", "require"),
    }
    sslrootcert = _resolve_ca_path(pg.get("sslrootcert"))
    if sslrootcert:
        kwargs["sslrootcert"] = sslrootcert
    return psycopg2.connect(**kwargs)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(
        "postgresql+psycopg2://",
        creator=_connect,
        pool_pre_ping=True,
        pool_recycle=600,  # < 15-min IAM token TTL
        pool_size=5,
        max_overflow=5,
        future=True,
    )


def schema_name() -> str:
    return _pg_cfg().get("schema", "drsistemas")


def init_db() -> None:
    """Run schema.sql idempotently."""
    schema_sql = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    schema_sql = schema_sql.replace("{{SCHEMA}}", schema_name())
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name()}"'))
        for stmt in [s.strip() for s in schema_sql.split(";")]:
            if stmt:
                conn.execute(text(stmt))
