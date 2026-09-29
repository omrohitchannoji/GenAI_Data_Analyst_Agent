import os
import sqlite3
import json
from typing import List, Dict, Any, Optional

GLOSSARY_DB = os.environ.get("GLOSSARY_DB", "business_glossary.db")

class BusinessGlossary:
    """
    Manages approved business metric glossaries with versioning and dataset scoping.
    Guarantees that business terms (e.g. 'High Value Customer') map to approved definitions
    rather than allowing the LLM to invent arbitrary calculation rules.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or GLOSSARY_DB
        self._init_db()
        self._seed_default_terms()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS glossary_terms (
                    term_id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL,
                    term_name TEXT NOT NULL,
                    definition TEXT NOT NULL,
                    sql_expression TEXT NOT NULL,
                    version TEXT NOT NULL
                );
            """)
        conn.close()

    def register_term(
        self,
        term_id: str,
        dataset_id: str,
        term_name: str,
        definition: str,
        sql_expression: str,
        version: str = "1.0"
    ):
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO glossary_terms
                (term_id, dataset_id, term_name, definition, sql_expression, version)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (term_id, dataset_id, term_name, definition, sql_expression, version))
        conn.close()

    def search_glossary(self, query: str, dataset_id: str = "default", top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieves matching approved glossary terms for a query within dataset scope.
        """
        q_words = [w.lower() for w in query.split() if len(w) > 2]
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT term_id, dataset_id, term_name, definition, sql_expression, version
            FROM glossary_terms
            WHERE dataset_id = ?
        """, (dataset_id,))
        rows = cursor.fetchall()
        conn.close()

        matches = []
        for r in rows:
            term_id, ds_id, name, desc, expr, ver = r
            name_lower = name.lower()
            
            # 1. Exact substring match
            if name_lower in query.lower():
                matches.append({
                    "term_id": term_id,
                    "dataset_id": ds_id,
                    "term_name": name,
                    "definition": desc,
                    "sql_expression": expr,
                    "version": ver
                })
                continue
                
            # 2. Significant word overlap (requires at least 2 distinct words or >= 66% word match)
            name_words = set(w for w in name_lower.split() if len(w) > 2)
            matching_words = name_words.intersection(set(q_words))
            if len(matching_words) >= 2 or (name_words and len(matching_words) / len(name_words) >= 0.66):
                matches.append({
                    "term_id": term_id,
                    "dataset_id": ds_id,
                    "term_name": name,
                    "definition": desc,
                    "sql_expression": expr,
                    "version": ver
                })

        return matches[:top_k]

    def _seed_default_terms(self):
        """Seed initial approved enterprise terms for default telco and sales fixtures."""
        self.register_term(
            term_id="GLOSS-001",
            dataset_id="default",
            term_name="High Value Customer",
            definition="Customers with TotalCharges greater than $5000",
            sql_expression="CAST(TotalCharges AS FLOAT) > 5000",
            version="1.0"
        )
        self.register_term(
            term_id="GLOSS-002",
            dataset_id="default",
            term_name="Churn Risk Customer",
            definition="Customers with Month-to-month contract and tenure of 6 months or less",
            sql_expression="Contract = 'Month-to-month' AND tenure <= 6",
            version="1.0"
        )
        self.register_term(
            term_id="GLOSS-003",
            dataset_id="sales",
            term_name="High Margin Order",
            definition="Orders where revenue minus cost is greater than $500",
            sql_expression="(revenue - cost) > 500",
            version="1.0"
        )

# Global default instance
default_glossary = BusinessGlossary()
