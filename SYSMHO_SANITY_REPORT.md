# 🩺 Reporte de Saneamiento y Funcionalidad: SysMho v15.3.0

> **Estado: CRÍTICO (Desajuste Contable + Insolvencia + Paradoja de IA)**
> Basado en la Auditoría Forense `SYSMHO_DNA.md` (31 de marzo de 2026)

---

## 1. Análisis de Coherencia y "Red Flags"

Tras revisar detalladamente el "ADN" del proyecto, hemos detectado 3 fallas que comprometen la estabilidad total del sistema:

### 🚨 Falla A: Desajuste Contable Crítico (Vulnerabilidad de Estado)
*   **Hallazgo:** `portfolio.in_positions` marca **$563.55**, pero la tabla `positions` está **vacía**.
*   **Consecuencia:** El sistema tiene "fondos fantasma" bloqueados. Para el `CircuitBreaker`, el bot cree que ya agotó su margen, impidiendo nuevas operaciones aunque la cuenta esté libre en Binance.
*   **Origen:** El motor perdió la sincronización en un cierre de posición (probablemente una desconexión o error en el callback de Binance que impidió disparar `_close_position` en la BD).

### 📉 Falla B: Insolvencia Operativa (Balance Negativo)
*   **Hallazgo:** `total_balance` es **-$40.49**.
*   **Consecuencia:** Es matemáticamente imposible operar con saldo negativo. Las proyecciones de riesgo (`RiskManager`) calculan el tamaño de posición basado en este balance; al ser negativo, el bot está paralizado o genera tamaños erróneos.

### 🧠 Falla C: Desconexión de Inteligencia (Paradoja del Accuracy)
*   **Hallazgo:** Accuracy del 97% en entrenamiento vs 47% Win Rate real.
*   **Consecuencia:** El sistema está operando a ciegas estadísticamente. El modelo está "sobre-entrenado" en la clase WAIT (ruido) y es ineficiente en la acción real.

---

## 2. Plan de Saneamiento (Ataque Quirúrgico)

Para restaurar la coherencia, funcionalidad y estabilidad, atacaremos los problemas en las siguientes 4 fases:

### Fase 1: Restauración de Integridad Contable (Saneamiento Inmediato)
*   **Arreglamos:** El desajuste entre `portfolio` y `positions`.
*   **Cómo:** Ejecutar `tools/fix_portfolio.py` para poner `in_positions` en 0.00 y usar `adjust_capital` en el dashboard para sincronizar el balance real desde Binance.
*   **Qué saneamos:** La solvencia del sistema. El bot vuelve a tener "sentido de la realidad" financiera.

### Fase 2: Persistencia y Congruencia IA (Saneamiento de Datos)
*   **Arreglamos:** La tabla `meta_stats` (vacía) y la falta de métricas por clase.
*   **Cómo:** 
    1. Migrar `SelfLearner` para que escriba en la tabla PostgreSQL `meta_stats` además de en el archivo JSON.
    2. Implementar métricas `buy_precision` y `sell_precision` en `model_performance`.
*   **Qué saneamos:** La desconfianza en los números. Ahora sabremos exactamente qué tan bueno es el bot operando, no solo "esperando".

### Fase 3: Etiquetado Adaptativo y Volatilidad (Optimización Funcional)
*   **Arreglamos:** El umbral fijo de 0.7% que causa señales falsas en activos lentos y omisiones en activos rápidos.
*   **Cómo:** Implementar **Etiquetado ATR-Based**. El umbral de ganancia será `ATR * 1.5` en lugar de un número estático.
*   **Qué optimizamos:** La calidad de la señal. El modelo será sensible a la "respiración" natural de cada mercado.

### Fase 4: Refactorización y Resiliencia (Estabilidad Estructural)
*   **Arreglamos:** El monolito de 840 líneas en `main.py`.
*   **Cómo:** Extraer los loops de escaneo a un módulo `src/bot/scanners.py` y la lógica de decisión autónoma a `src/bot/decision_engine.py`.
*   **Qué optimizamos:** La mantenibilidad. Un código modular es menos propenso a errores catastróficos durante actualizaciones.

---

## 3. Argumentación Técnica de las Mejoras

### ¿Por qué Etiquetado Adaptativo (ATR)?
En el trading, la volatilidad es cíclica. Usar un umbral fijo es como intentar pescar con la misma red en el mar que en un río. El ATR permite que la IA entienda que un 0.5% en un mercado de baja volatilidad es **valioso**, mientras que un 1% en un mercado salvaje es **ruido**. Esto incrementará la precisión (Precision) de las señales reales.

### ¿Por qué persistencia en DB para `meta_stats`?
Tener estadísticas solo en un archivo JSON es frágil. PostgreSQL nos permite hacer queries complejas (ej: "¿Cuál es el mejor horario para operar SOL/USDT?") que el dashboard puede visualizar en tiempo real. Esto da al operador (tú) una herramienta de decisión basada en evidencia, no en intuición.

### ¿Por qué penalizar activos perdedores?
La congruencia exige reconocer fallos. Si ETH tiene un Win Rate del 25% tras 30 trades, el sistema debe "autocensurarse". Esto garantiza que el capital fluya hacia los activos donde la IA sí tiene una ventaja competitiva.

---

## 4. Conclusión y Siguiente Paso

El sistema actual es una infraestructura potente pero "descalibrada". Aplicando este saneamiento, SysMho pasará de ser un bot que intenta operar a ser un **fondo de inversión neuronal automatizado**.

**Siguiente paso:** Iniciar **Fase 1** (Corrección de portfolio y reset de capital real).

---
*Documento de Saneamiento v15.3.0*
