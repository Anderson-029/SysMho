---
name: sysmho-ctx
description: Carga el contexto completo de desarrollo de SysMho — activa todas las skills (operativas + desarrollo) e instrucciones para sesión de trabajo
user-invocable: true
allowed-tools: Read, Bash, Glob, Grep, Edit, Write
---

Eres el asistente de desarrollo de SysMho. Acabas de cargar el contexto completo del proyecto. Lee los siguientes archivos para tener todo el contexto disponible en esta sesión, luego confirma con un resumen.

## PASO 1 — Cargar todas las skills disponibles

Lee el contenido completo de cada uno de estos SKILL.md en paralelo (son las instrucciones de cada comando):

### Skills Operativas (13)
```
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-status/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-deploy/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-signals/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-logs/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-performance/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-market/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-test/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-audit/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-review/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-migrate/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-retrain/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-cb-tune/SKILL.md
```

### Skills de Desarrollo (7)
```
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-diff/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-impact/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-fix/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-refactor/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-test-coverage/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-pre-commit/SKILL.md
/home/anderson/Documentos/programas personales/SysMho/.claude/skills/sysmho-cleanup/SKILL.md
```

## PASO 2 — Cargar memoria del proyecto

Lee:
```
/home/anderson/.claude/projects/-home-anderson-Documentos-programas-personales-SysMho/memory/MEMORY.md
/home/anderson/.claude/projects/-home-anderson-Documentos-programas-personales-SysMho/memory/project_sysmho.md
```

## PASO 3 — Estado rápido del sistema

```bash
ps aux | grep -E "uvicorn|src\.main" | grep -v grep && echo "PROCS_OK" || echo "PROCS_NONE"
pg_isready -h localhost -p 5432 -U postgres 2>&1
```

Lee `src/runtime_state.json`.

## PASO 4 — Confirmar contexto cargado

Responde con este panel de confirmación:

```
╔══════════════════════════════════════════════════════════╗
║         SYSMHO — Contexto de Desarrollo Cargado          ║
╠══════════════════════════════════════════════════════════╣
║ SKILLS OPERATIVAS (13)                                   ║
║  /sysmho              Panel maestro de diagnóstico       ║
║  /sysmho-status       Estado del sistema                 ║
║  /sysmho-deploy       Reinicio controlado                ║
║  /sysmho-signals      Vista táctica de señales           ║
║  /sysmho-logs         Telemetría neuronal                ║
║  /sysmho-performance  KPIs y rendimiento                 ║
║  /sysmho-market       Contexto de mercado                ║
║  /sysmho-test         Suite de tests                     ║
║  /sysmho-audit        Auditoría de integridad            ║
║  /sysmho-review       Análisis pre-modificación          ║
║  /sysmho-migrate      Migraciones SQL                    ║
║  /sysmho-retrain      Reentrenamiento XGBoost            ║
║  /sysmho-cb-tune      Calibración Circuit Breaker        ║
╠══════════════════════════════════════════════════════════╣
║ SKILLS DE DESARROLLO (7)                                 ║
║  /sysmho-diff         Impacto cruzado entre archivos     ║
║  /sysmho-impact       Análisis profundo de un archivo    ║
║  /sysmho-fix          Diagnóstico y fix de bugs          ║
║  /sysmho-refactor     Limpieza de módulo con evidencia   ║
║  /sysmho-test-coverage  Mapa de cobertura de tests       ║
║  /sysmho-pre-commit   Checklist antes de guardar cambios ║
║  /sysmho-cleanup      Elimina código muerto del proyecto ║
╠══════════════════════════════════════════════════════════╣
║ SISTEMA: [Dashboard ✅/❌] [Motor ✅/❌] [BD ✅/❌]       ║
║ MODO: [AUTÓNOMO/MANUAL]  CB: [OK/ACTIVO]                 ║
╠══════════════════════════════════════════════════════════╣
║ 20 skills cargadas. ¿En qué trabajamos hoy?              ║
╚══════════════════════════════════════════════════════════╝
```

A partir de este punto, cuando el usuario pida ejecutar cualquier skill (ej. "ejecuta el cleanup", "haz un fix del bug X", "analiza el impacto de trader.py"), aplica directamente las instrucciones que ya tienes cargadas en contexto, sin necesidad de invocar el comando por separado.
