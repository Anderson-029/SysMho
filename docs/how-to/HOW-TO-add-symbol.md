# Cómo Agregar un Nuevo Símbolo de Trading

## Cuándo usar esta guía

Cuando quieres que SysMho tradee un nuevo asset cripto (ej: DOGE/USDT, PEPE/USDT).

## ⚠️ Importante: Regla Model-Guard

Agregar un símbolo cambia el rango de `symbol_encoded` en `MODEL_FEATURES`. El `xgboost_v1_1.joblib` existente fue entrenado con 10 símbolos (encoded 0-9). Un nuevo símbolo sería encoded como 10, que el modelo viejo nunca ha visto.

**Debes borrar el modelo viejo y reentrenar.** Esto es obligatorio por `.claude/rules/model-guard.md`.

---

## Paso 1: Verificar que el símbolo existe en Binance Futures

```bash
# Verificar en Python
uv run python -c "
from dotenv import load_dotenv; load_dotenv()
import ccxt
exchange = ccxt.binance({'options': {'defaultType': 'future'}})
markets = exchange.load_markets()
print('DOGE/USDT' in markets)  # Debe imprimir True
"
```

---

## Paso 2: Agregar a la lista SYMBOLS en src/constants.py

```python
# Antes:
SYMBOLS = ['BTC/USDT', 'ETH/USDT', ..., 'POL/USDT']

# Después:
SYMBOLS = ['BTC/USDT', 'ETH/USDT', ..., 'POL/USDT', 'DOGE/USDT']
```

---

## Paso 3: Agregar encoding a SYMBOL_ENCODING

Usa el siguiente entero disponible (los símbolos actuales usan 0-9):

```python
# Antes:
SYMBOL_ENCODING = {
    ...,
    'POL/USDT': 9,
}

# Después:
SYMBOL_ENCODING = {
    ...,
    'POL/USDT': 9,
    'DOGE/USDT': 10,
}
```

> ⚠️ Nunca cambies encodings existentes (BTC=0, ETH=1, etc.). XGBoost usa estos como una feature numérica — cambiarlos haría que todo el entrenamiento histórico sea inválido.

---

## Paso 4: Descargar datos históricos

El nuevo símbolo necesita al menos 3 meses de velas 5m, 1h y 4h:

```bash
# Datos 5m (3 años para estar seguro — ~315,000 velas)
uv run python src/collector/backfill.py --symbol DOGE/USDT --timeframe 5m --year 2022

# Datos 1h
uv run python src/collector/backfill.py --symbol DOGE/USDT --timeframe 1h --year 2022

# Datos 4h
uv run python src/collector/backfill.py --symbol DOGE/USDT --timeframe 4h --year 2022
```

Cada comando descarga desde `--year` hasta hoy en lotes de 1000 velas.

Verifica que los datos fueron cargados:

```sql
SELECT timeframe, COUNT(*), MIN(open_time), MAX(open_time)
FROM market_data
WHERE symbol = 'DOGE/USDT'
GROUP BY timeframe;
```

---

## Paso 5: Borrar modelo viejo (model-guard)

```bash
rm src/ai/models/xgboost_v1_1.joblib
echo "Modelo viejo borrado"
```

---

## Paso 6: Reentrenar con el nuevo símbolo incluido

```bash
# Modo rápido (usa best_params existentes)
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m

# O con tuning Bayesiano si quieres optimizar también para el nuevo símbolo
uv run python -m src.ai.trainer --symbol ALL --timeframe 5m --tune --trials 50
```

El nuevo símbolo `DOGE/USDT` será incluido en `--symbol ALL` automáticamente ya que está en `SYMBOLS`.

---

## Paso 7: Ejecutar tests

```bash
uv run test
```

---

## Paso 8: Reiniciar engine

```bash
uv run engine
```

El engine ahora incluye DOGE/USDT en sus feeds WebSocket y escáner de señales.

---

## Eliminar un símbolo (proceso inverso)

1. Elimina de `SYMBOLS` en `src/constants.py`
2. Elimina de `SYMBOL_ENCODING` (mantén los encodings existentes intactos para otros)
3. Borra modelo → reentreña → tests → reinicia

> No renumeres los encodings restantes. Si eliminas POL (9) y agregas DOGE (10), mantén DOGE=10. Los vacíos en encoding están bien.

---

## Enlaces Relacionados
- `.claude/rules/model-guard.md` — Por qué el modelo viejo debe ser borrado
- `docs/how-to/HOW-TO-retrain-model.md` — Guía completa de reentrenamiento
- `src/collector/backfill.py` — Descargador de datos históricos
- `src/constants.py` — SYMBOLS y SYMBOL_ENCODING
