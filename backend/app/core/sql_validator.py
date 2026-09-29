import sqlglot
import sqlglot.expressions as exp
from typing import Optional, List, Tuple, Set

# Forbidden statement and expression types
FORBIDDEN_EXPRESSION_TYPES = (
    exp.Drop,
    exp.Delete,
    exp.Update,
    exp.Insert,
    exp.Create,
    exp.Alter,
    exp.Command,
    exp.Pragma,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Attach,
    exp.Detach,
    exp.TruncateTable
)

FORBIDDEN_FUNCTIONS = {
    "load_extension",
    "writefile",
    "readfile",
    "edit"
}

def validate_sql_security(
    sql: str,
    allowed_tables: Optional[List[str]] = None,
    allowed_columns: Optional[List[str]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validates a SQL query using Abstract Syntax Tree (AST) analysis via sqlglot.
    Enforces read-only safety, single statement constraint, wildcard restrictions,
    and schema authorization.
    """
    if not sql or not sql.strip():
        return False, "SQL query cannot be empty."

    cleaned_sql = sql.strip()

    # 1. Parse statement with SQLite dialect
    try:
        statements = sqlglot.parse(cleaned_sql, read="sqlite")
    except Exception as e:
        return False, f"SQL Syntax Error: Unable to parse query. Details: {str(e)}"

    if not statements or len(statements) == 0:
        return False, "No valid SQL statement found."

    # 2. Enforce exactly one statement (reject stacked / chained queries)
    if len(statements) > 1:
        return False, f"Multiple statements detected ({len(statements)} statements). Only single statements are permitted."

    stmt = statements[0]

    # 3. Verify root expression is SELECT or UNION
    if not isinstance(stmt, (exp.Select, exp.Union)):
        return False, f"Only read-only SELECT queries are allowed. Found root statement type: {type(stmt).__name__}."

    # 4. Check for any mutation / DDL / DML / administrative nodes anywhere in AST
    for forbidden_type in FORBIDDEN_EXPRESSION_TYPES:
        violating_nodes = list(stmt.find_all(forbidden_type))
        if violating_nodes:
            return False, f"Security Policy Violation: Prohibited operation '{forbidden_type.__name__}' detected."

    # 5. Check for prohibited functions (e.g. load_extension)
    for func in stmt.find_all(exp.Anonymous):
        func_name = func.this.lower() if isinstance(func.this, str) else ""
        if func_name in FORBIDDEN_FUNCTIONS:
            return False, f"Security Policy Violation: Forbidden function '{func_name}' is not permitted."

    # 6. Check for projection wildcards (SELECT * is disallowed; COUNT(*) is allowed)
    for star in stmt.find_all(exp.Star):
        # Must be enclosed in an aggregate Count ancestor
        if star.find_ancestor(exp.Count) is None:
            return False, "Policy Violation: Projection wildcards (SELECT *) are prohibited. Specify explicit column names."

    # 7. Collect and validate table references (accounting for CTE aliases)
    cte_names: Set[str] = {
        cte.alias_or_name.lower()
        for cte in stmt.find_all(exp.CTE)
        if cte.alias_or_name
    }

    if allowed_tables:
        allowed_set = {t.lower() for t in allowed_tables}.union(cte_names)
        for tbl in stmt.find_all(exp.Table):
            tbl_name = tbl.name.lower()
            # Allow sqlite internal schema tables if explicitly permitted, otherwise block
            if tbl_name.startswith("sqlite_"):
                return False, f"Access to SQLite internal metadata table '{tbl.name}' is prohibited."
            if tbl_name not in allowed_set:
                return False, f"Unauthorized table access: Table '{tbl.name}' is not in the authorized dataset tables: {allowed_tables}."

    # 8. Check column references if column whitelist provided
    if allowed_columns:
        allowed_col_set = {c.lower() for c in allowed_columns}
        # In SQL, aliases defined in CTEs or SELECT can be referenced downstream,
        # so we check Column nodes whose table matches an allowed table
        for col in stmt.find_all(exp.Column):
            col_name = col.name.lower()
            # If not a recognized column and not a known wildcard/alias, report if it matches source table
            table_ref = col.table.lower() if col.table else None
            if table_ref and allowed_tables and table_ref in [t.lower() for t in allowed_tables]:
                if col_name not in allowed_col_set:
                    return False, f"Unknown column '{col.name}' referenced on table '{col.table}'."

    return True, None
