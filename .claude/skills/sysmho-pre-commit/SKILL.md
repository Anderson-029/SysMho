---
name: sysmho-pre-commit
description: Checklist de consistencia antes de guardar cambios — versiones, SQL sin bind params, constantes, comentarios desactualizados y imports muertos
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash
---

Ejecuta este checklist completo antes de considerar un cambio listo.

## CHECK 1 — Versión consistente

```bash
grep -rn "SYSMHO_VERSION\|v1[0-9]\.[0-9]\|version" \
  "/home/anderson/Documentos/programas personales/SysMho/src" \
  --include="*.py" | grep -v ".pyc"
```

Verifica que todas las referencias a la versión sean iguales.

## CHECK 2 — SQL sin parámetros bindados (injection risk)

```bash
grep -rn 'f".*SELECT\|f".*INSERT\|f".*UPDATE\|f".*DELETE\|f".*{' \
  "/home/anderson/Documentos/programas personales/SysMho/src" \
  --include="*.py"
```

Cualquier query SQL construida con f-strings o concatenación es una alerta.

## CHECK 3 — Constantes hardcodeadas fuera de constants.py

```bash
# Números mágicos en archivos que no son constants.py
grep -rn "[0-9]\{3,\}" \
  "/home/anderson/Documentos/programas personales/SysMho/src" \
  --include="*.py" \
  --exclude="constants.py" \
  --exclude="*.sql" | grep -v "#\|test\|print\|log\|sleep\|port\|1000\|pool"
```

## CHECK 4 — Comentarios que no coinciden con el código

Lee los archivos modificados recientemente y verifica:
- Porcentajes en comentarios que ya no coinciden con el código
- Nombres de variables/funciones mencionados en comentarios que ya no existen
- Referencias a versiones antiguas

```bash
grep -rn "25%\|MATIC\|trade_history\|pnl_usdt\|closed_at\|confidence.*direction" \
  "/home/anderson/Documentos/programas personales/SysMho/src" \
  --include="*.py"
```

## CHECK 5 — Imports no utilizados

Para cada archivo modificado:
```bash
grep -n "^from\|^import" ARCHIVO
```
Verifica que cada import aparece al menos una vez en el cuerpo del archivo.

## CHECK 6 — Archivos huérfanos (no importados por nadie)

```bash
for f in $(find "/home/anderson/Documentos/programas personales/SysMho/src" -name "*.py" | grep -v __init__); do
  modname=$(basename $f .py)
  count=$(grep -rn "import.*$modname\|from.*$modname" \
    "/home/anderson/Documentos/programas personales/SysMho/src" \
    --include="*.py" | grep -v "$f" | wc -l)
  if [ "$count" -eq "0" ]; then
    echo "HUÉRFANO: $f"
  fi
done
```

## CHECK 7 — Coherencia de interfaces

Si se cambió una función pública, verifica que todos los llamadores usan la nueva firma:
```bash
grep -rn "nombre_funcion_modificada" \
  "/home/anderson/Documentos/programas personales/SysMho/src" \
  --include="*.py"
```

## Reporte final

```
PRE-COMMIT CHECKLIST — [FECHA]
─────────────────────────────────────────────────────
✅ Versión consistente: 15.2.0
❌ SQL injection potencial: repository.py:330 (time_filter)
✅ Sin constantes hardcodeadas nuevas
⚠️ Comentario desactualizado: risk/manager.py:177 ("Max 25%")
✅ Sin imports muertos detectados
✅ Sin archivos huérfanos nuevos

VEREDICTO: HAY 2 ITEMS A RESOLVER ANTES DE COMMIT
```
