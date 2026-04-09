#!/bin/bash
# SysMho Post-Edit Hook
# Runs AFTER you edit certain files to warn about downstream impacts
# Triggered by: editing constants.py, paths.py, etc.

# This is a template hook — in real usage, would be integrated with IDE/editor
# For now, used manually or via VS Code tasks

WORKSPACE_ROOT="/home/anderson/Documentos/programas personales/SysMho"

# Check which file was edited (passed as argument)
EDITED_FILE="${1:-.}"

echo "🔔 [POST-EDIT] Analyzing impact of changes..."
echo ""

# ============================================================
# HOOK 1: constants.py edited
# ============================================================
if [[ "$EDITED_FILE" == *"constants.py"* ]]; then
    echo "⚠️  DETECTED: src/constants.py was edited"
    echo ""

    # Check if MODEL_FEATURES changed
    git diff HEAD -- "src/constants.py" | grep -E "^[+-].*'h[0-9]|^[+-].*'rsi|^[+-].*'macd" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "🔴 IMPORTANT: MODEL_FEATURES likely changed!"
        echo ""
        echo "   Impact: XGBoost model may be incompatible"
        echo ""
        echo "   Action required:"
        echo "     1. Delete old models:"
        echo "        rm ${WORKSPACE_ROOT}/src/ai/models/xgboost_v1_1.joblib"
        echo "        rm ${WORKSPACE_ROOT}/src/ai/models/xgboost_v1_1_backup_*.joblib"
        echo ""
        echo "     2. Retrain with new features:"
        echo "        uv run sysmho-retrain"
        echo ""
        echo "     3. Verify model loads:"
        echo "        uv run python -c \"from src.ai.predictor import ModelPredictor; ModelPredictor()\""
        echo ""
        echo "   Why? XGBoost cannot use a 27-feature model if you give it 28 features."
        echo ""
    else
        echo "✅ Safe change — No MODEL_FEATURES change detected"
    fi
    echo ""
fi

# ============================================================
# HOOK 2: paths.py edited
# ============================================================
if [[ "$EDITED_FILE" == *"paths.py"* ]]; then
    echo "⚠️  DETECTED: src/paths.py was edited"
    echo ""
    echo "   Impact: File paths changed project-wide"
    echo ""
    echo "   Check:"
    echo "     • Are relative paths still used? (no absolute /home/... paths)"
    echo "     • Do all consumers import from paths.py?"
    echo "     • Update src/AGENTS.md 'Paths' section if needed"
    echo ""
fi

# ============================================================
# HOOK 3: schema migration files edited
# ============================================================
if [[ "$EDITED_FILE" == *"migration_"* ]]; then
    echo "⚠️  DETECTED: Database migration edited"
    echo ""
    echo "   Impact: Schema changes — must be tested before merging"
    echo ""
    echo "   Check:"
    echo "     • Run migration locally: uv run db-migrate"
    echo "     • Verify rollback works"
    echo "     • Update src/database/AGENTS.md"
    echo ""
fi

# ============================================================
# HOOK 4: ML model training code edited
# ============================================================
if [[ "$EDITED_FILE" == *"src/ai/trainer"* ]]; then
    echo "⚠️  DETECTED: Trainer logic changed"
    echo ""
    echo "   Impact: Model retraining behavior changed"
    echo ""
    echo "   Check:"
    echo "     • Run test suite: uv run test"
    echo "     • Test on small dataset first"
    echo "     • Update src/ai/AGENTS.md if needed"
    echo ""
fi

# ============================================================
# HOOK 5: Trade executor edited
# ============================================================
if [[ "$EDITED_FILE" == *"src/execution/executor"* ]] || [[ "$EDITED_FILE" == *"src/risk/manager"* ]]; then
    echo "🔴 CRITICAL: Trade execution or risk logic changed!"
    echo ""
    echo "   Impact: Live trading behavior affected — HIGH RISK"
    echo ""
    echo "   MUST DO:"
    echo "     1. Run full test suite: uv run test"
    echo "     2. Backtest impact: uv run sysmho-backtest"
    echo "     3. Code review by another person (MANDATORY)"
    echo "     4. Do NOT deploy to production immediately"
    echo ""
fi

# ============================================================
# SUMMARY
# ============================================================
echo "═══════════════════════════════════════════════════════"
echo "✅ POST-EDIT ANALYSIS COMPLETE"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Review the warnings above. Take recommended actions."
echo ""
echo "When ready: git add -A && git commit"
echo ""

exit 0
