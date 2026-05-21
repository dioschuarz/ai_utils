# AI-Utils Developer Constitution

This document defines the core developmental principles and strict operational rules for the **AI Utils** repository. All AI assistants, developers, and workflows must comply with these guidelines.

---

## 🏛️ Foundational Principles

### 📌 P1: Pydantic Model Purity
To guarantee high-conviction runtime validation and prevent silent type leakage:
* **No `Any` Types**: The `Any` type is strictly forbidden in Pydantic models and schemas. All fields must use concrete types, nested Pydantic models, or standard types/containers.
* **Explicit Typing Imports**: All Pydantic model files must explicitly import every typing annotation used (e.g. `Union`, `Dict`, `List`, `Literal`, `Optional`) from the standard `typing` module. Never assume annotations are pre-loaded in the model context.

### 📌 P2: Strategic Impact Analysis
To prevent code decay and protect shared graph infrastructure:
* **Blast Radius Inspection**: Before making any modification to a shared helper function, module, or database view, you **MUST** run the `get_impact_radius` tool from the `code-review-graph` MCP server.
* **Flow Protection**: Check `get_affected_flows` to verify that your planned edits will not disrupt downstream graph execution nodes (e.g., Lead Strategist synthesis).

### 📌 P3: Test Execution Hygiene
To avoid false-negative test failures triggered by arbitrary code-coverage thresholds:
* **Coverage Bypass**: Local and sandbox test suites must be executed with the `--no-cov` parameter appended (e.g., `uv run pytest --no-cov`). Do not fail active development workflows due to missing code coverage on untouched legacy files.

---

## 💻 Environment & Command Rules

### 1. Python Environment Execution
* All Python executables, scripts, and tests must be run using the repository's dedicated virtual environment (`.venv/bin/python` or `uv run`).
* Under no circumstances should global system python or external compilers be invoked directly without the `uv` sandbox wrapper.

### 2. Token Optimization (RTK)
* All shell commands must be prefixed with the **Rust Token Killer (RTK)** wrapper (e.g. `rtk git status`, `rtk pytest`). This reduces token overhead on development operations by 60-90%.

### 3. Database Security
* Direct raw SQL commands are restricted. All database operations must be channeled through standard database view/connector files or authorized MCP tools.

---
**Status**: ACTIVE & ENFORCED
**Location**: `.agents/rules/CONSTITUTION.md`
