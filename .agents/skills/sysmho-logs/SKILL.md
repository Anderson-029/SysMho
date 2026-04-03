---
name: sysmho-logs
description: Reads and analyzes neural telemetry from the brain log grouped by event type. Use when investigating runtime behavior or errors.
allowed-tools: Read Shell
---

Read the neural telemetry log of SysMho and present a structured analysis.

1. **Read the log**: Read the last 100 lines of `src/sysmho_brain.log`.

2. **Group and present events by category** in this priority order:

**❌ Errors and failures** (lines with ERROR, ❌, Exception, Traceback)
- Show each one with context

**🛑 Circuit Breaker** (lines with [CIRCUIT BREAKER], CB, TRIGGERED)
- Show which stop was triggered and when

**🤖 Autonomous Decisions** (lines with [AUTONOMY], APPROVED, REJECTED, meta_score)
- Show symbol, decision and main reason

**✅ Executions** (lines with executed order, MARKET, Binance confirmation)
- Show symbol, direction and confirmation

**📡 Normal activity** (scans, signals, learning) — only if nothing more urgent exists

3. **If the log is empty or does not exist**: report that SysMho is stopped.

4. Close with: "Last activity X minutes ago" based on the timestamp of the last line.
