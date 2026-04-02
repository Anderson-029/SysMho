import pandas as pd
import numpy as np
import os
import sys

sys.path.append(os.path.join(os.getcwd(), 'src'))
from ai.predictor import ModelPredictor

def test_aggressive_logic():
    predictor = ModelPredictor()
    if not predictor.model:
        print("❌ No hay modelo cargado.")
        return

    # Crear datos ficticios basados en las features del modelo
    # Intentamos encontrar un punto donde la probabilidad sea baja (ej 20%)
    # pero el ratio sea aceptable para agresivo (1.5) pero no para normal (2.0)
    
    print("🔬 [UNIT TEST] Validando Desbloqueo de Agresividad...")
    
    # Nota: No podemos controlar las probabilidades directamente sin los datos X reales,
    # pero podemos mockear el método predict_proba para este test específico de la lógica de decisión.
    
    original_predict_proba = predictor.model.predict_proba
    
    # Caso: Probabilidades [SELL: 0.10, WAIT: 0.70, BUY: 0.20]
    # Normal: min_conf 0.15 (Pasa), Ratio 0.20/0.10 = 2.0 (Pasa justo)
    # Vamos a probar un caso más límite: [SELL: 0.12, WAIT: 0.76, BUY: 0.12] -> Ratio 1.0 (Falla)
    # Caso Target: [SELL: 0.08, WAIT: 0.80, BUY: 0.12]
    # Normal: Conf 12% < 15% (FALLA) | Ratio 1.5 < 2.0 (FALLA)
    # Agresivo: Conf 12% > 10% (PASA) | Ratio 1.5 >= 1.5 (PASA)
    
    test_probs = np.array([[0.08, 0.80, 0.12]])
    predictor.model.predict_proba = lambda x: test_probs
    
    # Simulamos un dataframe con las columnas necesarias (aunque no las usemos por el mock)
    df = pd.DataFrame(np.zeros((1, len(predictor.features))), columns=predictor.features)
    
    print("\nPROBABILIDADES MOCK: [Sell: 8%, Wait: 80%, Buy: 12%]")
    
    res_normal = predictor.predict_signal(df, aggressive=False)
    print(f"Modo NORMAL: {res_normal['signal_str']} (Motivo: {res_normal.get('reason', 'N/A')})")
    
    res_agg = predictor.predict_signal(df, aggressive=True)
    print(f"Modo AGGRESSIVE: {res_agg['signal_str']} (Tipo: {res_agg.get('signal_type', 'N/A')})")
    
    if res_normal['signal_str'] == 'WAIT' and res_agg['signal_str'] == 'BUY':
        print("\n✅ ¡CERTIFICADO! El motor agresivo ahora desbloquea señales que antes eran invisibles.")
    else:
        print("\n❌ Error: La lógica de agresividad no está funcionando como se esperaba.")

    # Restaurar
    predictor.model.predict_proba = original_predict_proba

if __name__ == "__main__":
    test_aggressive_logic()
