---
name: sysmho-refactor
description: Analiza un módulo específico y lista oportunidades concretas de limpieza con evidencia del código — no toca nada sin aprobación
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash
---

El usuario indica un módulo o área a refactorizar.
Si no indica nada, solicita cuál quiere mejorar.

## Paso 1 — Leer el módulo completo

Lee el archivo o archivos del módulo indicado.

## Paso 2 — Detectar oportunidades de mejora

Analiza buscando:

**Código duplicado:**
```bash
# Buscar patrones repetidos
grep -rn "PATRÓN_SOSPECHOSO" \
  "/home/anderson/Documentos/programas personales/SysMho/src" \
  --include="*.py"
```

**Funciones demasiado largas** (>50 líneas): identificarlas y proponer división

**Lógica compleja que se puede simplificar**: condicionales anidados, flag variables, etc.

**Imports no usados:**
```bash
grep -n "^from\|^import" ARCHIVO
# Verificar que cada import se usa en el cuerpo
```

**Constantes hardcodeadas** dentro del archivo que deberían estar en `constants.py`

**Comentarios desactualizados**: comentarios que describen comportamiento diferente al actual

**Type hints faltantes** en funciones públicas

## Paso 3 — Verificar que los cambios no rompen nada

Para cada cambio propuesto, verifica:
- ¿Cambia la interfaz pública? (nombres de función, parámetros)
- ¿Qué archivos dependen de lo que se va a cambiar?

```bash
grep -rn "nombre_funcion_a_cambiar" \
  "/home/anderson/Documentos/programas personales/SysMho/src" \
  --include="*.py"
```

## Paso 4 — Reporte de oportunidades

Presenta ANTES de tocar nada:

```
MÓDULO: src/executor/trader.py
OPORTUNIDADES DE REFACTOR
─────────────────────────────────────────────────────
1. [BAJO RIESGO] Eliminar db.connect() redundante en _log_trade() (línea 366)
   Razón: el pool ya existe. Es safe pero es ruido.
   Impacto: 0 archivos externos afectados.

2. [BAJO RIESGO] Extraer lógica de SL/TP a función _place_sl_tp()
   Razón: 20 líneas repetidas si se agrega lógica adicional.
   Impacto: solo interno al archivo.

3. [MEDIO RIESGO] Renombrar parámetro 'risk_approved_data' → 'signal'
   Razón: nombre muy largo y verboso.
   Impacto: main.py línea 593 llama execute_trade(dictamen).

¿Aplico los cambios? Puedo hacerlos todos, o indicame cuáles.
```

Espera aprobación antes de modificar.

## Paso 5 — Aplicar cambios aprobados

Aplica uno por uno con el Edit tool, verificando importación después de cada cambio:
```bash
python3 -c "from src.MODULO import CLASE; print('✅')" 2>&1
```
