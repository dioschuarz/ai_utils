---
description: Spec-Driven Development - Gather specifications and generate spec.md.
---

# /speckit.specify - Spec-Driven Specification Mode

$ARGUMENTS

---

## 🔴 CRITICAL RULES

1. **NO CODE WRITING** - This workflow gathers specs and creates a specification document only.
2. **Socratic Gate** - Ask the user clarifying questions if the request is underspecified or ambiguous.
3. **Structured Output** - Write findings strictly to `.specify/memory/spec.md` or `.agents/memory/spec.md`.

---

## Task

Gather specifications for the requested feature or refactoring: `$ARGUMENTS`.

### Steps:

1. **Context Check**
   - Read `.agents/memory/techContext.md` and `.agents/memory/activeContext.md` to understand the codebase state.
   - Run search queries using `code-review-graph` or `CodeGraphContext` if details about affected components are requested.

2. **Socratic Gate (Clarification)**
   - If requirements are unclear, ask the user 1-3 targeted multiple-choice or direct questions.
   - Do not make assumptions on security, external APIs, or database schemas.

3. **Generate Specification**
   - Create the file `.agents/memory/spec.md` (overwriting it if it already exists).
   - The file **MUST** contain:
     - **Goal Description**: User request context and high-level goal.
     - **Functional Requirements**: Specific checklist of what the code must do.
     - **Technical Boundaries**: Tech stack, models, databases, and dependencies.
     - **Constraints & Edge Cases**: Security, validation errors, fallbacks.

4. **Verify & Report**
   - Notify the user of the created specification file.
   - Direct the user to run `/speckit.plan` as the next step.

---

## Expected Output Format for `.agents/memory/spec.md`

```markdown
# Specification: [Task Name]

## 🎯 Goal
Description of the feature/refactoring.

## 📋 Requirements
- [ ] Requirement 1
- [ ] Requirement 2

## 📐 Technical Boundaries
- **Runtime**: Python 3.13 / FastAPI / LangGraph
- **Data Store**: Supabase / MongoDB
- **Observability**: LangFuse

## ⚠️ Constraints & Edge Cases
- No hardcoded secrets
- Robust exception fallbacks
```

---

## Usage Examples

```
/speckit.specify implement supabse migration for positions
/speckit.specify add google authentication endpoints
/speckit.specify optimize news feed summarization latency
```

---

## Next Steps

Tell the user:
```
[OK] Specification created: .agents/memory/spec.md

Next step:
- Review the specification
- Run `/speckit.plan` to generate the technical plan
```
