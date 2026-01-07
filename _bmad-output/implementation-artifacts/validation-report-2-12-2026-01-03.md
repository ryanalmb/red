# Validation Report

**Document:** `/root/red/_bmad-output/implementation-artifacts/2-12-engagement-database-schema.md`
**Checklist:** `_bmad/bmm/workflows/4-implementation/create-story/checklist.md`
**Date:** 2026-01-03T17:41:43Z

## Summary
- Overall: 21/26 passed (81%)
- Critical Issues: 2
- Enhancements: 3

---

## Section Results

### 3.1 Reinvention Prevention Gaps
Pass Rate: 3/4 (75%)

✓ **PASS** Code reuse opportunities identified
Evidence: Lines 200-214 list existing `CheckpointManager` infrastructure to leverage; lines 206-214 show current schema DDL.

✓ **PASS** Existing solutions mentioned for extension
Evidence: Lines 114-119 explicitly state "Maintain backward compatibility with existing API" and "All existing checkpoint tests still pass".

✓ **PASS** Previous story context included
Evidence: Lines 319-325 reference story 2-11 learnings (atomic save, content signature, WAL mode).

⚠ **PARTIAL** Data model alignment with core/models.py
**Gap:** The story uses a `Finding` class in `checkpoint.py` (lines 62-71) with different fields than `core/models.py` Finding class (10 required fields including signature, topic, tool). The schema defines `finding_json: str` which is correct, but story doesn't clarify relationship with existing Finding dataclass.
**Impact:** Developer may create duplicate Finding model or miss that checkpoint Finding is a storage wrapper, not the core model.

---

### 3.2 Technical Specification Gaps
Pass Rate: 5/6 (83%)

✓ **PASS** Library versions specified
Evidence: Lines 223-230 specify `sqlalchemy>=2.0.0` and `alembic>=1.13.0` with clear rationale.

✓ **PASS** Schema DDL provided
Evidence: Lines 232-293 provide complete SQL schema with all tables, FKs, and indexes.

✓ **PASS** Foreign key enforcement documented
Evidence: Lines 185-188 document SQLite FK pragma requirement.

✓ **PASS** Backward compatibility addressed
Evidence: Task 8 (lines 104-110) covers legacy migration path with v1.0.0 detection and data preservation.

✓ **PASS** WAL mode mentioned
Evidence: Lines 190 confirms WAL mode already implemented.

✗ **FAIL** Audit table location mismatch with architecture
**Gap:** Architecture (lines 160, 866) specifies `audit.sqlite` as a separate file, not part of `checkpoint.sqlite`. The story places audit table in the same schema as checkpoint tables.
**Impact:** Developer will create audit in wrong database file, violating architecture's append-only isolation guarantee.
**Evidence from architecture.md line 160:**
```
├── audit.sqlite         # Append-only authorization log (NTP-synced)
```
**Recommendation:** Either clarify that this story only defines the schema (which can be used in both files), or explicitly split audit table to `storage/audit.py` as a separate story scope.

---

### 3.3 File Structure Gaps
Pass Rate: 4/4 (100%)

✓ **PASS** Project structure documented
Evidence: Lines 295-309 list all files to create/modify.

✓ **PASS** Test file locations specified
Evidence: Lines 302-304 specify test locations matching project conventions.

✓ **PASS** Module export updates listed
Evidence: Line 307 specifies `storage/__init__.py` update.

✓ **PASS** Dependencies listed for pyproject.toml
Evidence: Line 309 mentions adding sqlalchemy/alembic to pyproject.toml.

---

### 3.4 Regression Prevention Gaps
Pass Rate: 3/3 (100%)

✓ **PASS** Existing test pass requirement
Evidence: Line 119 states "All existing checkpoint tests still pass" as verification.

✓ **PASS** Backward compatibility explicitly required
Evidence: Lines 196, 106-109 address v1.0.0 checkpoint migration.

✓ **PASS** 100% coverage gate included
Evidence: Task 14 (lines 154-158) requires 100% coverage.

---

### 3.5 Implementation Clarity
Pass Rate: 4/5 (80%)

✓ **PASS** Tasks have clear acceptance criteria mapping
Evidence: Each task links to specific AC number (e.g., "AC: #3, #4, #5").

✓ **PASS** Verification steps per task
Evidence: Each task includes "Verification:" line.

✓ **PASS** Phased implementation approach
Evidence: 5 phases clearly organized.

✓ **PASS** Schema version strategy documented
Evidence: Lines 35, 183 address version bumping.

⚠ **PARTIAL** SQLAlchemy vs raw SQL migration strategy unclear
**Gap:** Task 9 says "Use SQLAlchemy for all DB operations (vs raw SQL)" but existing checkpoint.py uses raw sqlite3. Story doesn't clarify if this is a full rewrite or gradual migration.
**Impact:** Developer may attempt full rewrite when incremental refactor would be safer.
**Recommendation:** Clarify if Phase 3 is a full replacement or if raw SQL is acceptable for some operations initially.

---

### 3.6 LLM Optimization
Pass Rate: 2/4 (50%)

✓ **PASS** Clear task structure
Evidence: Checkbox lists with subtasks are scannable.

✓ **PASS** Design decisions section
Evidence: Lines 175-196 provide clear rationale.

⚠ **PARTIAL** Verbose schema DDL
**Gap:** Full SQL schema (60+ lines) in Dev Notes may waste tokens for dev agent. Consider moving to a separate reference file or condensing.
**Recommendation:** Keep summary table of tables/columns; move full DDL to appendix or linked file.

⚠ **PARTIAL** References section could be more actionable
**Gap:** References list file paths but don't specify what to extract from each.
**Recommendation:** Add 1-line note per reference: "See CheckpointManager.save() for atomic write pattern".

---

## Failed Items

### ✗ FAIL: Audit table location mismatch

**Severity:** CRITICAL

**Current state:** Story defines `audit` table in the same schema as `checkpoint.sqlite`, with same FK relationships to `engagements` table.

**Architecture requirement (lines 160-161):**
```
├── checkpoint.sqlite    # Agent state, findings, resume support
├── audit.sqlite         # Append-only authorization log (NTP-synced)
```

**Recommendation:** 
1. **Option A:** Remove `audit` table from this story's scope; create separate story for `storage/audit.py` with its own SQLite schema.
2. **Option B:** Keep schema definition but add explicit note that `audit` table lives in separate `audit.sqlite` file, not `checkpoint.sqlite`. Update Alembic to manage two separate databases.

---

## Partial Items

### ⚠ Data model alignment with core/models.py

**Missing context:** `checkpoint.py` already has its own `Finding` dataclass (line 88-95) that's a storage wrapper, distinct from `core/models.py` Finding (10-field stigmergic message). Story should clarify this distinction.

**Recommendation:** Add to Dev Notes:
```
**Finding Model Distinction:**
- `core/models.Finding` — 10-field stigmergic message (id, type, severity, target, evidence, agent_id, timestamp, tool, topic, signature)
- `storage/checkpoint.Finding` — Storage wrapper (finding_id, data, agent_id, timestamp) where `data` contains serialized core.Finding
```

### ⚠ SQLAlchemy migration strategy

**Recommendation:** Clarify in Task 9:
```
- [ ] Gradual refactor: Keep sqlite3 for performance-critical paths, use SQLAlchemy for schema management
- [ ] OR Full migration: Replace all raw SQL with SQLAlchemy ORM operations
```

### ⚠ LLM optimization - verbose DDL

**Recommendation:** Move full SQL DDL to reference section or collapse to table summary:
```
| Table | PK | FKs | Key Columns |
|-------|-----|-----|-------------|
| engagements | id | - | name, scope_hash, state |
| agents | agent_id | engagement_id | agent_type, state_json |
| findings | finding_id | engagement_id, agent_id | finding_json, timestamp |
| checkpoints | id | engagement_id | checkpoint_path, signature |
| audit | id | engagement_id | event_type, actor, signature |
```

---

## Recommendations

### 1. Must Fix (Critical)

1. **Clarify audit table location** — Add explicit note that `audit` table schema is defined but stored in separate `audit.sqlite` file per architecture. Consider splitting to separate story.

### 2. Should Improve (Important)

2. **Add Finding model distinction** — Clarify relationship between `checkpoint.Finding` (storage wrapper) and `core/models.Finding` (10-field message).

3. **Clarify SQLAlchemy migration approach** — Specify if Task 9 is full rewrite or gradual migration.

### 3. Consider (Optimization)

4. **Condense DDL preview** — Move full SQL to appendix, keep summary table in main flow.

5. **Make references actionable** — Add one-line description of what to extract from each reference.

---

## Validation Conclusion

**Overall Assessment:** GOOD with 2 critical clarifications needed

The story provides comprehensive developer guidance with clear phases, tasks, and verification steps. The main issues are:
1. Architecture alignment for audit table location (separate file)
2. Clarity on data model relationships

Recommend applying "critical" and "should improve" fixes before dev-story execution.
