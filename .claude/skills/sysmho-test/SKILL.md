---
name: sysmho-test
description: Runs the complete test suite and reports results with failure context. Use when validating code changes or checking test health.
allowed-tools: Read Shell Grep
---

Execute the SysMho test suite following these steps:

1. **Run pytest** from the workspace root:

```bash
uv run pytest tests/ -v --tb=short
```

2. **Analyze the output**:
   - If all tests pass: confirm how many tests passed and the total time
   - If there are failures: for each failed test show the name, the exact error, and the relevant source file to understand the cause
   - If there are import errors: identify which module fails and why

3. **For failures**: read the failing test file and the module that fails to give a concrete diagnosis — not just a repeat of the traceback.

4. **Close with a summary**: ✅ N passed | ❌ N failed | ⚠️ N errors
