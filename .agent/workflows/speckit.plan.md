---
description: Spec-Driven Development - Generate technical plan from spec.md and perform strategic impact analysis.
---

# /speckit.plan - Spec-Driven Planning Mode

$ARGUMENTS

---

## 🔴 CRITICAL RULES

1. **NO CODE WRITING** - This workflow generates technical plan files only.
2. **Blast Radius Analysis** - You **MUST** run strategic impact reviews using `code-review-graph` (`get_impact_radius`) for any modified files or shared functions.
3. **Structured Output** - Write technical plan strictly to `.agents/memory/plan.md`.

---

## Task

Create a detailed, low-risk technical plan based on the specification at `.agents/memory/spec.md`.

### Steps:

1. **Read & Parse Specification**
   - Read `.agents/memory/spec.md` to grasp all goal definitions and technical constraints.

2. **Strategic Impact Analysis**
   - Identify the files that need to be created or modified.
   - For all existing files slated for modification, query `get_impact_radius` from the `code-review-graph` MCP server to map out affected dependencies and downstream nodes.
   - Log any potential risks (e.g. broken schema validators, broken imports).

3. **Generate Technical Plan**
   - Create the file `.agents/memory/plan.md` (overwriting it if it already exists).
   - The file **MUST** contain:
     - **Proposed Changes**: Grouped by components. Demarcate files with `[NEW]`, `[MODIFY]`, or `[DELETE]`. Include absolute links: `[basename](file:///path/to/file)`.
     - **Blast Radius Analysis**: Detail findings from the `code-review-graph` run and note any deconfliction strategies.
     - **Verification Plan**: Detail exact automated test command strings (always with `--no-cov`) and manual verification steps.

4. **Verify & Report**
   - Report the strategic findings and deconfliction parameters to the user.
   - Direct the user to run `/speckit.tasks` as the next step.

---

## Usage Examples

```
/speckit.plan
/speckit.plan --skip-graph (only if graph servers are offline)
```

---

## Next Steps

Tell the user:
```
[OK] Technical Plan created: .agents/memory/plan.md

Next step:
- Review the plan and strategic deconfliction details
- Run `/speckit.tasks` to instantiate the active checklists
```
