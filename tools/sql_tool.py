import os
import sqlite3
import pathlib
from typing import Any
from langchain.tools import tool
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from dotenv import load_dotenv
load_dotenv()


# 1. Download sample database
local_path = pathlib.Path("D:\\langchain\\database\\database.db")


# 2. Define tools for database interaction
@tool
def sql_db_list_tables() -> str:
    """Input is an empty string, output is a comma-separated list of tables."""
    con = sqlite3.connect(local_path)
    try:
        cursor = con.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]
        return ", ".join(tables)
    finally:
        con.close()

@tool
def sql_db_schema(table_names: str) -> str:
    """Input is a comma-separated list of tables, output is the schema and sample rows."""
    con = sqlite3.connect(local_path)
    try:
        cursor = con.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        valid_tables = {row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")}
        results = []
        for table in table_names.split(","):
            table = table.strip()
            if table not in valid_tables:
                continue
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (table,))
            schema_row = cursor.fetchone()
            if schema_row:
                results.append(schema_row[0])
        return "\n\n".join(results)
    finally:
        con.close()

@tool
def sql_db_query(query: str) -> dict[str, Any]:
    """Execute one read-only SQLite SELECT query and return structured columns and rows.

    Use this after inspecting the relevant table schemas. The result is capped
    at 500 rows so it can be passed safely to analysis and plotting tools.
    """
    normalized = query.strip().rstrip(";").strip()
    if not normalized or ";" in normalized:
        return {"error": "Exactly one SQL statement is allowed."}
    if not normalized.lower().startswith(("select", "with")):
        return {"error": "Only read-only SELECT queries are allowed."}

    con = sqlite3.connect(f"file:{local_path.as_posix()}?mode=ro", uri=True)
    try:
        con.execute("PRAGMA query_only = ON")
        cursor = con.cursor()
        cursor.execute(normalized)
        columns = [column[0] for column in cursor.description or []]
        rows = cursor.fetchmany(501)
        truncated = len(rows) > 500
        rows = rows[:500]
        return {
            "columns": columns,
            "rows": [list(row) for row in rows],
            "row_count": len(rows),
            "truncated": truncated,
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        con.close()

tools = [sql_db_list_tables, sql_db_schema, sql_db_query]

# 3. Initialize model and agent
os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY")
model = init_chat_model("gpt-5.4-mini-2026-03-17")

system_prompt = """
You are an agent designed to interact with a SQL database.
Given an input question, create a syntactically correct sqlite query to run,
then look at the results and return the answer. Always limit your query to at most 5 results.
"""

sql_agent = create_agent(
    model,
    tools,
    system_prompt=system_prompt,
)

