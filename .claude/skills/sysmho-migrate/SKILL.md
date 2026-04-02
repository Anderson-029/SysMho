---
name: sysmho-migrate
description: Aplica migraciones SQL de SysMho de forma segura y verifica que se aplicaron correctamente
user-invocable: true
allowed-tools: Bash, Read, Glob
---

Orquesta la aplicación segura de migraciones SQL en SysMho.

## Paso 1 — Detectar migraciones pendientes

Lista todos los archivos de migración:
```bash
ls -la "/home/anderson/Documentos/programas personales/SysMho/src/database/"*.sql | sort
```

Lee cada migration_vX.sql y determina cuáles podrían no estar aplicadas comparando con las tablas/columnas que crean vs las que existen en la BD.

## Paso 2 — Verificar estado actual de la BD

Consulta las tablas existentes:
```bash
PGPASSWORD=ander123 psql -h localhost -U postgres -d sysmho -c "\dt" 2>&1
```

## Paso 3 — Aplicar la migración indicada

Si el usuario especificó un archivo, aplícalo:
```bash
PGPASSWORD=ander123 psql -h localhost -U postgres -d sysmho -f "ARCHIVO.sql" 2>&1
```

Si no especificó, pregunta cuál aplicar antes de proceder.

## Paso 4 — Verificar que se aplicó correctamente

Después de aplicar, verifica cada tabla/columna que debería haber creado:
```bash
PGPASSWORD=ander123 psql -h localhost -U postgres -d sysmho -c "\d nombre_tabla" 2>&1
```

Confirma: ✅ tabla existe con columnas correctas / ❌ algo falló.

## Paso 5 — Verificar coherencia con el código

Lee los archivos Python que usan las nuevas tablas/columnas y confirma que los nombres de campos coinciden exactamente con el DDL aplicado. Alerta si hay discrepancias.

## Resultado

Reporta:
- Migración aplicada: nombre del archivo
- Tablas creadas/modificadas con sus columnas
- Coherencia código ↔ BD: ✅ o ❌ con detalle
