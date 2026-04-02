---
name: sysmho-fix
description: Diagnóstico completo de un bug — lee los archivos involucrados, identifica la causa raíz y propone el fix exacto antes de tocar nada
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash
---

El usuario describe el bug o comportamiento incorrecto.
Si la descripción es vaga, busca en el log y la BD para reproducirlo.

## Paso 1 — Recolectar evidencia

**En el log neuronal:**
```bash
grep -n "ERROR\|Exception\|Traceback\|❌\|FALLO" \
  "/home/anderson/Documentos/programas personales/SysMho/src/sysmho_brain.log" \
  | tail -30
```

**En la BD si aplica:**
```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "
import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='ander123', database='sysmho')
    # Consulta relevante al bug reportado
    await conn.close()
asyncio.run(main())
" 2>&1
```

## Paso 2 — Localizar el código culpable

Busca el síntoma en el código:
```bash
grep -rn "TÉRMINO_DEL_ERROR\|función_sospechosa" \
  "/home/anderson/Documentos/programas personales/SysMho/src" \
  --include="*.py" -n
```

Lee los archivos relevantes completos para entender el flujo exacto.

## Paso 3 — Reproducir mentalmente el bug

Traza el flujo de ejecución paso a paso:
- ¿Qué función inicia la cadena?
- ¿Dónde se introduce el valor incorrecto?
- ¿Qué condición hace que falle?
- ¿Es un bug de lógica, de tipos, de timing async, o de estado en BD?

## Paso 4 — Proponer el fix

ANTES de tocar nada, presenta:

```
BUG DIAGNOSTICADO:
─────────────────────────────────────────────────────
Síntoma: [lo que reportó el usuario]
Causa raíz: [el problema real encontrado]
Archivo: src/ARCHIVO.py línea N
Código actual:
  [fragmento exacto con el bug]

Fix propuesto:
  [código corregido]

Archivos afectados: [lista]
Tests a actualizar: [lista o "ninguno"]
Riesgo de regresión: BAJO / MEDIO / ALTO

¿Aplico el fix? (sí/no)
```

Espera confirmación antes de modificar cualquier archivo.

## Paso 5 — Aplicar y verificar

Solo si el usuario confirma:
1. Aplica el fix con el Edit tool
2. Si hay test relevante, lo actualiza
3. Verifica que no se rompió nada adyacente con:
```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "from src.MODULO import CLASE; print('✅ Import OK')" 2>&1
```
