---
name: sysmho-test
description: Corre el suite completo de tests de SysMho y reporta resultados con contexto de fallo
user-invocable: true
allowed-tools: Bash, Read, Grep
---

Ejecuta el suite de tests de SysMho siguiendo estos pasos:

1. Corre pytest con el entorno virtual activado:
```bash
cd "/home/anderson/Documentos/programas personales/SysMho"
source venv/bin/activate && PYTHONPATH=$(pwd) pytest tests/ -v --tb=short 2>&1
```

2. Analiza la salida:
   - Si todos pasan: confirma cuántos tests pasaron y en cuánto tiempo
   - Si hay fallos: para cada test fallido muestra el nombre, el error exacto, y el archivo fuente relevante para entender la causa
   - Si hay errores de import: identifica qué módulo falla y por qué

3. Si hay fallos, lee el archivo del test fallido y el módulo que falla para dar un diagnóstico concreto, no solo repetir el traceback.

4. Termina con un resumen: ✅ N pasaron | ❌ N fallaron | ⚠️ N errores
