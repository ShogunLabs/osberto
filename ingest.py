#!/usr/bin/env python3
"""
Augur DRHP Database Ingestion & Migration Script

This script parses all JSON prospectuses in data/drhp/ and persists them into
a queryable SQL database (SQLite locally or PostgreSQL in production via Supabase/Neon).

Usage:
  1. Local SQLite (zero setup, creates ipos.db):
     python ingest.py

  2. Cloud PostgreSQL / Supabase / Neon:
     export DATABASE_URL="postgresql://user:password@host:port/dbname"
     python ingest.py
"""

import os
import glob
import json
import re
import sys
from datetime import datetime
from typing import Dict, Any, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", "drhp")
DATABASE_URL = os.getenv("DATABASE_URL")


def slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-")


def derive_symbol(name: str) -> str:
    clean = re.sub(r"[^\w\s]", " ", name)
    boilerplate = {
        "limited", "ltd", "pvt", "private", "india", "industries",
        "services", "technologies", "corporation", "corp", "co"
    }
    words = [w.upper() for w in re.split(r"\s+", clean) if w and w.lower() not in boilerplate]
    if not words:
        words = [w.upper() for w in re.split(r"\s+", clean) if w]
    if len(words) >= 3:
        return "".join(w[0] for w in words[:4])
    elif len(words) == 2:
        return (words[0][:3] + words[1][:3])
    elif len(words) == 1:
        return words[0][:6]
    return "IPO"


def determine_issue_type(issue: Dict[str, Any], name: str, industry: str) -> str:
    total = (issue or {}).get("total_cr")
    fresh = (issue or {}).get("fresh_cr")
    val = total if total is not None else fresh
    if val is not None and val < 50.0:
        return "sme"
    return "regular"


def parse_json_files() -> List[Dict[str, Any]]:
    json_files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    records = []
    seen = {}

    for filepath in json_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict) or "name" not in data:
                continue

            name = data.get("name", "").strip()
            if not name:
                continue

            base_slug = slugify(name)
            if base_slug in seen:
                seen[base_slug] += 1
                unique_id = f"{base_slug}-{seen[base_slug]}"
            else:
                seen[base_slug] = 1
                unique_id = base_slug

            issue = data.get("issue") or {}
            total_cr = issue.get("total_cr")
            fresh_cr = issue.get("fresh_cr")
            ofs_cr = issue.get("ofs_cr")
            issue_size = total_cr if total_cr is not None else fresh_cr
            issue_type = determine_issue_type(issue, name, data.get("industry", ""))
            symbol = derive_symbol(name)

            mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
            now_str = datetime.utcnow().isoformat()

            records.append({
                "id": unique_id,
                "symbol": symbol,
                "name": name,
                "status": "upcoming",
                "isin": None,
                "issue_type": issue_type,
                "issue_size": issue_size,
                "industry": data.get("industry", "Diversified"),
                "minimum_price": None,
                "maximum_price": None,
                "listing_exchange": "NSE / BSE",
                "drhp_url": data.get("drhp_url", ""),
                "rhp_url": None,
                "timeline": json.dumps({"drhp_stage": True, "basis": data.get("basis", "consolidated")}),
                "registrar_info": json.dumps({"source": "DRHP", "file": os.path.basename(filepath)}),
                "raw_data": json.dumps(data),
                "first_seen_at": mtime,
                "last_synced_at": now_str,
                "updated_at": now_str,
            })
        except Exception as e:
            print(f"⚠️  Error reading {filepath}: {e}")

    return records


def ingest_sqlite(records: List[Dict[str, Any]]):
    import sqlite3
    db_path = os.path.join(BASE_DIR, "ipos.db")
    print(f"📦 Connecting to local SQLite database: {db_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ipos (
        id TEXT PRIMARY KEY,
        symbol TEXT,
        name TEXT NOT NULL,
        status TEXT DEFAULT 'upcoming',
        isin TEXT,
        issue_type TEXT,
        issue_size REAL,
        industry TEXT,
        minimum_price REAL,
        maximum_price REAL,
        listing_exchange TEXT,
        drhp_url TEXT,
        rhp_url TEXT,
        timeline TEXT,
        registrar_info TEXT,
        raw_data TEXT,
        first_seen_at TEXT,
        last_synced_at TEXT,
        updated_at TEXT
    );
    """)

    # Create indexes for high-speed search and filtering
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ipos_symbol ON ipos(symbol);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ipos_status ON ipos(status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ipos_issue_type ON ipos(issue_type);")

    # Upsert
    inserted = 0
    updated = 0
    for r in records:
        cur.execute("SELECT id FROM ipos WHERE id = ?", (r["id"],))
        exists = cur.fetchone()

        cur.execute("""
        INSERT INTO ipos (
            id, symbol, name, status, isin, issue_type, issue_size,
            industry, minimum_price, maximum_price, listing_exchange,
            drhp_url, rhp_url, timeline, registrar_info, raw_data,
            first_seen_at, last_synced_at, updated_at
        ) VALUES (
            :id, :symbol, :name, :status, :isin, :issue_type, :issue_size,
            :industry, :minimum_price, :maximum_price, :listing_exchange,
            :drhp_url, :rhp_url, :timeline, :registrar_info, :raw_data,
            :first_seen_at, :last_synced_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            symbol = excluded.symbol,
            name = excluded.name,
            issue_type = excluded.issue_type,
            issue_size = excluded.issue_size,
            industry = excluded.industry,
            raw_data = excluded.raw_data,
            updated_at = excluded.updated_at;
        """, r)

        if exists:
            updated += 1
        else:
            inserted += 1

    conn.commit()
    conn.close()

    print(f"✅ Ingestion complete: {inserted} inserted, {updated} updated (Total: {len(records)})")
    print(f"💾 SQLite file ready at: {db_path}")


def ingest_postgres(records: List[Dict[str, Any]], db_url: str):
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        print("❌ 'psycopg2' is required for PostgreSQL ingestion.")
        print("   Install it with: pip install psycopg2-binary")
        sys.exit(1)

    print(f"🐘 Connecting to PostgreSQL database...")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ipos (
        id VARCHAR(255) PRIMARY KEY,
        symbol VARCHAR(50),
        name VARCHAR(255) NOT NULL,
        status VARCHAR(50) DEFAULT 'upcoming',
        isin VARCHAR(50),
        issue_type VARCHAR(50),
        issue_size NUMERIC,
        industry VARCHAR(100),
        minimum_price NUMERIC,
        maximum_price NUMERIC,
        listing_exchange VARCHAR(50),
        drhp_url TEXT,
        rhp_url TEXT,
        timeline JSONB,
        registrar_info JSONB,
        raw_data JSONB,
        first_seen_at TIMESTAMP,
        last_synced_at TIMESTAMP,
        updated_at TIMESTAMP
    );
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_ipos_symbol ON ipos(symbol);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ipos_status ON ipos(status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ipos_issue_type ON ipos(issue_type);")

    query = """
    INSERT INTO ipos (
        id, symbol, name, status, isin, issue_type, issue_size,
        industry, minimum_price, maximum_price, listing_exchange,
        drhp_url, rhp_url, timeline, registrar_info, raw_data,
        first_seen_at, last_synced_at, updated_at
    ) VALUES (
        %(id)s, %(symbol)s, %(name)s, %(status)s, %(isin)s, %(issue_type)s, %(issue_size)s,
        %(industry)s, %(minimum_price)s, %(maximum_price)s, %(listing_exchange)s,
        %(drhp_url)s, %(rhp_url)s, %(timeline)s, %(registrar_info)s, %(raw_data)s,
        %(first_seen_at)s, %(last_synced_at)s, %(updated_at)s
    )
    ON CONFLICT (id) DO UPDATE SET
        symbol = EXCLUDED.symbol,
        name = EXCLUDED.name,
        issue_type = EXCLUDED.issue_type,
        issue_size = EXCLUDED.issue_size,
        industry = EXCLUDED.industry,
        raw_data = EXCLUDED.raw_data,
        updated_at = EXCLUDED.updated_at;
    """

    for r in records:
        cur.execute(query, r)

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Ingested {len(records)} IPOs into PostgreSQL successfully!")


if __name__ == "__main__":
    records = parse_json_files()
    if not records:
        print(f"⚠️  No JSON prospectuses found in {DATA_DIR}")
        sys.exit(0)

    print(f"🔍 Discovered {len(records)} DRHP prospectuses in {DATA_DIR}")

    if DATABASE_URL:
        ingest_postgres(records, DATABASE_URL)
    else:
        ingest_sqlite(records)
