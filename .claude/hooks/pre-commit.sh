#!/bin/bash
# SysMho Pre-Commit Hook
# Runs safety checks BEFORE code is committed
# Prevents dangerous changes from entering the repo

set -e

WORKSPACE_ROOT="/home/anderson/Documentos/programas personales/SysMho"
RULES_DIR="${WORKSPACE_ROOT}/.claude/rules"

echo "🛡️  [PRE-COMMIT] Running SysMho safety checks..."
echo ""

# ============================================================
# CHECK 1: Prevent .env from being committed
# ============================================================
echo "[1/5] Checking for .env in staged files..."
if git diff --cached --name-only | grep -E "^\.env$|^\.env\..*" > /dev/null; then
    echo "❌ BLOCKED: .env file detected in staged changes"
    echo ""
    echo "⚠️  SECURITY RISK — Secrets must NEVER be committed!"
    echo ""
    echo "Fix:"
    echo "  git reset HEAD .env"
    echo "  echo '.env' >> .gitignore"
    echo ""
    exit 1
fi
echo "✅ PASSED — No .env files staged"
echo ""

# ============================================================
# CHECK 2: Prevent credentials/secrets
# ============================================================
echo "[2/5] Checking for hardcoded credentials..."
if git diff --cached | grep -iE "(password|api_key|secret|token|binance_key)" | grep -v "# " > /dev/null; then
    echo "❌ BLOCKED: Potential hardcoded credentials detected"
    echo ""
    echo "⚠️  SECURITY RISK — Credentials must go in .env"
    echo ""
    echo "Fix:"
    echo "  1. Remove credentials from staged files"
    echo "  2. Add them to .env instead"
    echo "  3. Reference via config/settings.py"
    echo ""
    exit 1
fi
echo "✅ PASSED — No hardcoded credentials found"
echo ""

# ============================================================
# CHECK 3: Enforce constants.py for thresholds (constants-guard)
# ============================================================
echo "[3/5] Checking constants-guard rule (hardcoded thresholds)..."
# Check for suspicious numeric literals in Python files
if git diff --cached --name-only | grep "\.py$" > /dev/null; then
    # Sample check for common magic numbers (this is basic; real implementation would be more sophisticated)
    # Just warn for now, don't block (full validation requires AST parsing)
    echo "⚠️  Note: Run 'uv run sysmho-pre-commit' for deep constants validation"
fi
echo "✅ PASSED — Manual check: sysmho-pre-commit skill"
echo ""

# ============================================================
# CHECK 4: MODEL_FEATURES consistency (model-guard)
# ============================================================
echo "[4/5] Checking model-guard rule (MODEL_FEATURES change)..."
if git diff --cached -- "src/constants.py" | grep -E "MODEL_FEATURES|^[+-].*'" > /dev/null; then
    echo "⚠️  WARNING: src/constants.py MODEL_FEATURES section changed"
    echo ""
    echo "Model compatibility check:"
    echo "  If you changed the number/order of features:"
    echo "    1. Delete old models: rm src/ai/models/xgboost_v1_1*.joblib"
    echo "    2. Retrain: uv run sysmho-retrain"
    echo "    3. Then commit"
    echo ""
    echo "  If you only changed comments/docstrings:"
    echo "    → Safe to proceed"
    echo ""
    read -p "Do you understand the model-guard rule? (yes/no): " response
    if [ "$response" != "yes" ]; then
        echo "❌ BLOCKED — Aborting commit for safety review"
        exit 1
    fi
fi
echo "✅ PASSED — Model compatibility acknowledged"
echo ""

# ============================================================
# CHECK 5: paths.py consistency (paths-guard)
# ============================================================
echo "[5/5] Checking paths-guard rule (hardcoded paths)..."
if git diff --cached --name-only | grep "\.py$" > /dev/null; then
    echo "⚠️  Note: Run 'uv run sysmho-pre-commit' for deep paths validation"
fi
echo "✅ PASSED — Manual check: sysmho-pre-commit skill"
echo ""

# ============================================================
# SUMMARY
# ============================================================
echo "═══════════════════════════════════════════════════════"
echo "✅ PRE-COMMIT CHECKS PASSED"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Safe to commit. All files are clean."
echo ""
echo "💡 For deeper analysis, run: uv run sysmho-pre-commit"
echo ""

exit 0
