---
name: sysmho-cleanup
description: Depura el codebase eliminando código muerto, imports no usados, indicadores sin consumir, campos API obsoletos y archivos huérfanos — siempre con evidencia y confirmación antes de borrar
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash, Edit, Write
---

Audita y limpia el codebase de SysMho. Trabaja en pasadas sucesivas: primero detecta todo, luego aplica por categoría con confirmación.

## PASADA 1 — Detectar archivos huérfanos

Módulos que no son importados por ningún archivo del sistema en vivo:
```bash
BASE="/home/anderson/Documentos/programas personales/SysMho/src"
for f in $(find "$BASE" -name "*.py" | grep -v __init__ | grep -v "__pycache__"); do
  modname=$(echo $f | sed "s|$BASE/||" | sed 's|/|.|g' | sed 's|\.py$||')
  shortname=$(basename $f .py)
  count=$(grep -rn "from.*$shortname import\|import.*$shortname" "$BASE" --include="*.py" | grep -v "^$f" | wc -l)
  if [ "$count" -eq "0" ]; then
    echo "HUÉRFANO ($count refs): $f"
  fi
done
```

## PASADA 2 — Detectar indicadores técnicos no usados por el modelo

Lee `src/constants.py` para obtener `MODEL_FEATURES`.
Lee `src/analysis/indicators.py` para ver todos los indicadores calculados.

Compara: qué columnas calcula `add_all_indicators()` pero NO están en `MODEL_FEATURES` ni en los prefijos `h1_`, `h4_` que usa `features.py`.

Los indicadores sin ningún consumidor son candidatos a eliminar de `indicators.py`.

## PASADA 3 — Detectar imports muertos en cada archivo

```bash
for f in $(find "/home/anderson/Documentos/programas personales/SysMho/src" -name "*.py" | grep -v __init__ | grep -v "__pycache__"); do
  while IFS= read -r line; do
    if [[ "$line" =~ ^from.*import|^import ]]; then
      # Extraer el nombre importado
      name=$(echo "$line" | grep -oP '(?<=import )\w+' | head -1)
      if [ -n "$name" ]; then
        count=$(grep -c "\b$name\b" "$f" || true)
        if [ "$count" -le "1" ]; then
          echo "POSIBLE IMPORT MUERTO en $f: $line"
        fi
      fi
    fi
  done < "$f"
done 2>/dev/null | head -40
```

## PASADA 4 — Detectar campos API obsoletos

Busca campos marcados "por compatibilidad" o con comentarios de deprecación:
```bash
grep -rn "compatibilidad\|deprecated\|obsoleto\|ya no se usa\|dead\|unused" \
  "/home/anderson/Documentos/programas personales/SysMho/src" \
  --include="*.py" -n
```

## PASADA 5 — Detectar constantes definidas pero no usadas

```bash
# Extrae nombres de constantes de constants.py
grep -E "^[A-Z_]+ =" \
  "/home/anderson/Documentos/programas personales/SysMho/src/constants.py" | \
  awk -F' =' '{print $1}' | while read const; do
    count=$(grep -rn "\b$const\b" \
      "/home/anderson/Documentos/programas personales/SysMho/src" \
      --include="*.py" | grep -v "constants.py" | wc -l)
    if [ "$count" -eq "0" ]; then
      echo "CONSTANTE SIN USO: $const"
    fi
  done
```

## PASADA 6 — Detectar funciones definidas pero no llamadas

Para archivos pequeños y medianos, identifica funciones que solo aparecen en su definición:
```bash
grep -rn "^    def \|^def " \
  "/home/anderson/Documentos/programas personales/SysMho/src" \
  --include="*.py" | grep -v "__init__\|__str__\|__repr__" | \
  awk -F'def ' '{print $2}' | awk -F'(' '{print $1}' | while read fn; do
    count=$(grep -rn "\b$fn\b" \
      "/home/anderson/Documentos/programas personales/SysMho/src" \
      --include="*.py" | wc -l)
    if [ "$count" -le "1" ]; then
      echo "FUNCIÓN POSIBLEMENTE MUERTA: $fn"
    fi
  done 2>/dev/null | sort | head -30
```

## PRESENTAR REPORTE COMPLETO

Antes de eliminar CUALQUIER cosa, presenta todo lo encontrado:

```
LIMPIEZA DE CODEBASE — SYSMHO [FECHA]
─────────────────────────────────────────────────────
ARCHIVOS HUÉRFANOS (no importados por el sistema):
  src/collector/market_data.py — duplica backfill.py, 0 importaciones

INDICADORES SIN CONSUMIDOR EN EL MODELO:
  indicators.py calcula pero MODEL_FEATURES no usa:
  - williams_r
  - stoch_rsi_d
  - ema_9, ema_50
  - adx_neg
  - bb_high, bb_low, bb_mid
  - macd (raw), macd_signal

CAMPOS API OBSOLETOS:
  portfolio.py:138 — "pnl_global" marcado "para compatibilidad"

CONSTANTES SIN USO:
  [lista si se encuentran]

FUNCIONES POSIBLEMENTE MUERTAS:
  [lista si se encuentran]

─────────────────────────────────────────────────────
PLAN DE LIMPIEZA (de menor a mayor riesgo):

  SEGURO (impacto cero):
  □ Eliminar campos "por compatibilidad" en API responses
  □ Eliminar imports muertos en archivos individuales
  □ Actualizar comentarios incorrectos

  MODERADO (verificar antes):
  □ Eliminar indicadores no usados de indicators.py
    → Requiere confirmar que ningún test los verifica directamente
  □ Eliminar market_data.py
    → Requiere confirmar que no hay script externo que lo llame

  REQUIERE ANÁLISIS:
  □ Eliminar funciones sin llamadores
    → Pueden ser públicas usadas desde tests o desde fuera del src/

─────────────────────────────────────────────────────
¿Qué categorías quieres limpiar?
Indica: "todo", "solo lo seguro", o los items específicos.
```

## EJECUTAR LIMPIEZA

Solo cuando el usuario aprueba:

1. Para cada item aprobado, lee el archivo afectado completamente primero
2. Aplica el cambio con Edit tool
3. Verifica que el módulo importa correctamente:
```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) python3 -c "
from src.analysis.indicators import TechnicalIndicators
from src.ai.predictor import ModelPredictor
print('✅ Imports OK')
" 2>&1
```
4. Si hay tests relacionados, corre solo esos tests:
```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) pytest tests/ -v --tb=short -q 2>&1
```
5. Registra qué se eliminó y por qué en un comentario de resumen al final

## RESUMEN POST-LIMPIEZA

```
LIMPIEZA COMPLETADA
─────────────────────────────────────────────────────
Eliminado:
  ✅ indicators.py — 8 indicadores sin consumidor (-45 líneas)
  ✅ portfolio.py — campo pnl_global obsoleto (-2 líneas)
  ✅ market_data.py — archivo huérfano (-118 líneas)

Total reducción: ~165 líneas de código muerto
Tests: todos pasan ✅
Imports: todos OK ✅
```
