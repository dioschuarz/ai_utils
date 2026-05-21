---
description: Spec-Driven Development - Generate active task checklist from plan.md.
---

# /speckit.tasks - Spec-Driven Checklist Mode

$ARGUMENTS

---

## 🔴 CRITICAL RULES

1. **Structured Tasks** - This workflow generates the active checklist `tasks.md` at `.agents/memory/tasks.md`.
2. **Standard Task Format**:
   - `[ ]` for uncompleted tasks.
   - `[/]` for in-progress tasks.
   - `[x]` for completed tasks.
3. **Compaction Integration** - If output or checklists are long, use token-saving patterns to keep the context window highly optimized.

---

## Task

Generate the actionable developer execution checklist based on the technical plan at `.agents/memory/plan.md`.

### Steps:

1. **Read & Parse Technical Plan**
   - Read `.agents/memory/plan.md` to compile the proposed files, impact nodes, and verification commands.

2. **Generate Active Checklist**
   - Create the file `.agents/memory/tasks.md` (overwriting it if it already exists).
   - Break down the plan into component-level, granular sub-tasks:
     - **Preparation**: Rule adjustments, environment syncs.
     - **Component Development**: Specific code additions or refactors.
     - **Verification**: Exact `pytest --no-cov` terminal strings and manual run parameters.
   - Set all tasks to state `[ ]` (uncompleted) initially.

3. **Initialize & Sync**
   - Report the created `tasks.md` checklist path to the user.
   - Inform the user that execution is ready to begin. Instruct them to approve or trigger the implementation.

---

## Usage Examples

```
/speckit.tasks
```

---

## Next Steps

Tell the user:
```
[OK] Active checklist created: .agents/memory/tasks.md

Next step:
- Review the checklist
- Instruct the agent to start executing the tasks, updating `tasks.md` incrementally as they are completed
```
