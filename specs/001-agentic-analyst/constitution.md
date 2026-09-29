# System Constitution & Core Invariants
**Project:** Agentic AI Data Analyst  
**Version:** 1.0  
**Specification:** specs/001-agentic-analyst/  

---

## 1. Core Operating Principles

1. **Model Proposes, Deterministic Code Enforces**:
   - The LLM interprets natural language, resolves ambiguity, generates SQL, plans repairs, and writes business explanations.
   - Deterministic code validates SQL AST, enforces read-only connections, limits execution budgets, executes numerical Pandas calculations, and generates charts.
2. **Never Fabricate Facts or Business Meanings**:
   - Every quantitative claim in the final narrative must have an explicit fact reference verified against the computed Pandas output.
   - If an explanation fails validation or generation, the system falls back to a deterministic factual summary with an advisory warning.
3. **Explicit 5-State Terminal Outcomes**:
   - Every request must cleanly resolve into one of five states:
     - `success`: Valid query, verified calculations, grounded insights.
     - `empty`: Valid query returning 0 rows (filters are NEVER relaxed).
     - `needs_clarification`: Underspecified questions or missing business definitions.
     - `rejected`: Prohibited SQL operations, authorization violations, or unsupported requests.
     - `failed`: Exhausted repair attempts ($\le 3$ SQL attempts) or deadline timeouts.
4. **SQL Security & AST Invariants**:
   - Parse exactly one SQL statement using the SQLite dialect in `sqlglot`.
   - The root AST node must be `exp.Select`.
   - All mutations, DDL, DML (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `CREATE`, `TRUNCATE`), PRAGMAs, and attachment statements are strictly prohibited.
   - Disallow projection wildcards (`SELECT *`); explicitly allow aggregate count wildcards (`COUNT(*)`).
   - Execution is performed over a strictly read-only connection with a 10-second query deadline.
5. **Bounded Repair Invariants**:
   - The total SQL attempts per request is bounded at 3 (1 initial generation + at most 2 repair attempts).
   - Repaired queries MUST pass the identical AST validation and read-only execution safety checks before running.
   - Stale or partial query results from failed attempts must NEVER be passed to analytical nodes.
6. **Data Scope & Authorization**:
   - Client-supplied session and dataset IDs must be validated on the server.
   - Multi-tenant isolation: A session belonging to one principal cannot be queried or updated by another.
   - Retain only intentional conversational context; do not leak data across distinct datasets.
