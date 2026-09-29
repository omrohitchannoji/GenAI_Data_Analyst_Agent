import os
import json
import sqlite3
import time
from typing import Dict, Any, Optional, List

REGISTRY_DB = os.environ.get("REGISTRY_DB", "dataset_registry.db")
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MiB limit (Spec Section 6.2)

class DatasetRegistry:
    """
    Manages dataset persistence, metadata, and access scoping.
    Guarantees isolation between principals and durability across application restarts.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or REGISTRY_DB
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dataset_metadata (
                    dataset_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    db_path TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    column_types TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
            """)
        conn.close()

    def register_dataset(
        self,
        dataset_id: str,
        principal_id: str,
        filename: str,
        table_name: str,
        db_path: str,
        row_count: int,
        column_types: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """Registers a new uploaded dataset under an authorized principal."""
        created_at = time.time()
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO dataset_metadata
                (dataset_id, principal_id, filename, table_name, db_path, row_count, column_types, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dataset_id,
                principal_id,
                filename,
                table_name,
                db_path,
                row_count,
                json.dumps(column_types),
                created_at
            ))
        conn.close()

        return {
            "dataset_id": dataset_id,
            "principal_id": principal_id,
            "filename": filename,
            "table_name": table_name,
            "db_path": db_path,
            "row_count": row_count,
            "column_types": column_types,
            "created_at": created_at
        }

    def get_dataset(self, dataset_id: str, principal_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves dataset metadata if authorized for the given principal."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT dataset_id, principal_id, filename, table_name, db_path, row_count, column_types, created_at
            FROM dataset_metadata
            WHERE dataset_id = ? AND principal_id = ?
        """, (dataset_id, principal_id))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "dataset_id": row[0],
            "principal_id": row[1],
            "filename": row[2],
            "table_name": row[3],
            "db_path": row[4],
            "row_count": row[5],
            "column_types": json.loads(row[6]),
            "created_at": row[7]
        }

    def is_authorized(self, dataset_id: str, principal_id: str) -> bool:
        """Checks whether principal owns or is authorized to query dataset."""
        return self.get_dataset(dataset_id, principal_id) is not None

    def validate_upload_size(self, file_size_bytes: int) -> bool:
        """Validates that file size does not exceed max allowed bytes."""
        if file_size_bytes > MAX_UPLOAD_SIZE_BYTES:
            raise ValueError(f"File size {file_size_bytes / (1024*1024):.2f} MiB exceeds 10 MiB limit.")
        return True

# Default global instance
default_registry = DatasetRegistry()
