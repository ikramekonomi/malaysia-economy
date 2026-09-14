import os

import duckdb

DEFAULT_DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "curated", "warehouse.duckdb")
)
DB_PATH = os.environ.get("FISKAL_DB_PATH", DEFAULT_DB_PATH)


def get_connection():
    if not os.path.exists(DB_PATH):
        raise RuntimeError(
            f"warehouse DuckDB not found at {DB_PATH}. Build it first: "
            "python3 curated/pipeline/build_warehouse_duckdb.py"
        )
    return duckdb.connect(DB_PATH, read_only=True)
