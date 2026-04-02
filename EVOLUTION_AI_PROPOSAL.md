# 🧠 Propuesta de Evolución Estratégica: SysMho AI v15.3.0

> **De la "Precisión Teórica" a la "Rentabilidad Real"**
> Fecha: 31 de marzo de 2026
> Diagnóstico basado en Auditoría Forense de BD (6.7M registros)

---

## 1. El Diagnóstico: La "Paradoja del Accuracy"

Tras auditar la base de datos y los últimos 66 trades, hemos identificado el **bloqueador principal** del crecimiento de SysMho:

*   **El Síntoma:** El modelo reporta un **92% de Accuracy** en el entrenamiento, pero un **48.5% de Win Rate** en la operativa real.
*   **La Causa:** En un mercado de 5 minutos, el 85% del tiempo "no pasa nada" (clase **WAIT**). El modelo se vuelve experto en predecir que NO debe operar, lo cual infla su precisión estadística, pero es mediocre prediciendo los movimientos explosivos (BUY/SELL).
*   **El Resultado:** El sistema opera con señales de "baja calidad" que parecen seguras estadísticamente pero fallan en la ejecución, resultando en un **PnL neto de -$46.45**.

---

## 2. Las 5 Mejoras de Alto Impacto

Para evolucionar SysMho hacia un sistema de crecimiento sostenido, implementaremos las siguientes mejoras organizadas por su impacto técnico:

### 1️⃣ Etiquetado Adaptativo por Volatilidad (ATR)
*   **Qué arreglamos:** Actualmente usamos un umbral fijo de 0.7% para todos los activos. Esto es un error: 0.7% en BTC es un movimiento enorme, mientras que en una altcoin volátil es ruido.
*   **La Optimización:** Sustituiremos el umbral fijo por un **Umbral Dinámico basado en el ATR (Average True Range)**.
*   **Argumento:** La IA aprenderá a identificar "movimientos significativos" en relación a la personalidad de cada moneda, no a un número arbitrario.

### 2️⃣ Métricas de Precisión Quirúrgica (Split Class Metrics)
*   **Qué arreglamos:** Dejaremos de mirar el "Accuracy Global". 
*   **La Optimización:** Obligaremos a la IA a reportar su **Precisión Específica en BUY y SELL** por separado en la base de datos.
*   **Argumento:** Lo que no se mide no se mejora. Si sabemos que el modelo tiene 90% en WAIT pero 40% en BUY, podemos ajustar los pesos de entrenamiento para penalizar fallos en las entradas reales.

### 3️⃣ Auditoría de Features e IA de "Podado" (Pruning)
*   **Qué arreglamos:** El modelo usa 27 features. Algunas podrían estar metiendo ruido (correlación falsa).
*   **La Optimización:** Implementaremos un log automático de **Feature Importance** al final de cada entrenamiento.
*   **Argumento:** Eliminaremos las variables que no aportan valor, reduciendo el "overfitting" y haciendo que el modelo sea más robusto ante cambios repentinos de mercado.

### 4️⃣ Filtro de Supervivencia (Auto-Pena de Activos)
*   **Qué arreglamos:** Activos como ETH y BNB están destruyendo capital (WR < 30%).
*   **La Optimización:** El **MetaEvaluador** detectará automáticamente si un activo es un "perdedor crónico" y penalizará su score de entrada un 70%.
*   **Argumento:** Protegemos el capital de forma algorítmica. Si una moneda no se deja predecir por el modelo actual, el sistema deja de tocarla hasta que el siguiente reentrenamiento demuestre mejoría.

### 5️⃣ Calibración de Confianza por Régimen (Multi-Horizonte)
*   **Qué arreglamos:** Las señales a veces ignoran si el mercado está en tendencia o rango.
*   **La Optimización:** Cruzaremos la probabilidad de la IA con la alineación de las tendencias de 1h y 4h en el momento de la decisión.
*   **Argumento:** Solo se aprobarán señales de alta convicción cuando la estructura macro respalde la micro (Scalping Inteligente).

---

## 3. Plan de Ejecución por Fases

Para garantizar la estabilidad del capital, la implementación se dividirá en 4 fases lógicas:

### Fase 1: Instrumentación y Transparencia
*   **Acción:** Crear la migración v15.3.0 en PostgreSQL y actualizar `base.py` para medir precisiones por clase.
*   **Argumento:** No podemos ganar si no sabemos exactamente dónde fallamos. Esta fase nos da visión.

### Fase 2: Inteligencia Adaptativa
*   **Acción:** Implementar el **Etiquetado ATR** y el log de **Feature Importance**.
*   **Argumento:** Ataca la raíz del problema de los datos. Menos ruido, más señal.

### Fase 3: Protección de Capital (Resiliencia)
*   **Acción:** Actualizar el `MetaEvaluator` con la lógica de auto-penalización por Win Rate histórico.
*   **Argumento:** Detiene el sangrado de capital mientras el modelo evoluciona.

### Fase 4: Reentrenamiento Maestro y Validación
*   **Acción:** Ejecutar un entrenamiento completo de los 10 activos con la nueva lógica.
*   **Argumento:** Es el "Nacimiento" de la v15.3.0, un modelo diseñado para ganar, no solo para dar respuestas correctas estadísticamente.

---

## 4. Conclusión: El Camino al Éxito
SysMho tiene los datos (6.7M de velas) y la infraestructura. Esta evolución transforma al bot de un "apostador estadístico" a un **"operador de precisión"**. La meta es que cada reentrenamiento no sea solo "más datos", sino "mejores criterios".

---
*Generado por SysMho AI Evolution Team*
