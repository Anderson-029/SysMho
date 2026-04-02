---
name: sysmho-logs
description: Lee y analiza la telemetría neuronal de SysMho agrupando por tipo de evento
user-invocable: true
allowed-tools: Bash, Read
---

Lee las últimas líneas del log neuronal de SysMho y presenta un análisis estructurado.

1. Lee el log:
```bash
tail -100 "/home/anderson/Documentos/programas personales/SysMho/src/sysmho_brain.log" 2>/dev/null
```

2. Agrupa y presenta los eventos por categoría en este orden de prioridad:

**❌ Errores y fallos** (líneas con ERROR, ❌, Exception, Traceback)
- Muestra cada uno con contexto

**🛑 Circuit Breaker** (líneas con [CIRCUIT BREAKER], CB, TRIGGERED)
- Muestra qué stop se activó y cuándo

**🤖 Decisiones Autónomas** (líneas con [AUTONOMÍA], APPROVED, REJECTED, meta_score)
- Muestra símbolo, decisión y razón principal

**✅ Ejecuciones** (líneas con orden ejecutada, MARKET, confirmación Binance)
- Muestra símbolo, dirección y confirmación

**📡 Actividad normal** (scans, señales, aprendizaje) — solo si no hay nada más urgente

3. Si el log está vacío o no existe: informa que SysMho está detenido.

4. Cierra con: "Última actividad hace X minutos" basado en el timestamp de la última línea.
