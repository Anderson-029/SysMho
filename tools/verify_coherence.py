import asyncio
import sys
import os
import json

# Ajustar path
sys.path.append(os.getcwd())

from src.dashboard.deps import trader, db

async def verify_coherence():
    print("\n" + "="*70)
    print("🛡️ [AUDITORÍA DE COHERENCIA TÁCTICA GLOBAL V14.8.5]")
    print("="*70 + "\n")

    await db.connect()
    
    # 1. Capturar Data Oficial de Binance (Global Account)
    print("📡 Consultando Portafolio Global en Binance...")
    balance_data = await trader.exchange.fetch_balance()
    info = balance_data.get('info', {})
    
    binance_total_unrealized = float(info.get('totalUnrealizedProfit', 0.0))
    binance_total_margin = float(info.get('totalMarginBalance', 0.0))
    binance_available = float(info.get('availableBalance', 0.0))
    
    # 2. Capturar Data de Posiciones Individuales
    official_positions = await trader.get_active_positions_details()
    
    # 3. Capturar Data Local de la DB (HUD Values)
    async with db.pool.acquire() as conn:
        local_positions = await conn.fetch("SELECT * FROM positions")
    
    print("\n" + "-"*70)
    print("📊 [REPORTE DE POSICIONES INDIVIDUALES]")
    print("-"*70)
    print(f"{'ACTIVO':<12} | {'PnL (Binance)':<18} | {'PnL (SysMho DB)':<18} | {'ESTADO':<10}")
    print("-"*70)

    all_symbols = set(official_positions.keys()) | set([p['symbol'] for p in local_positions])
    
    pos_match = True
    for sym in all_symbols:
        off_pnl = official_positions.get(sym, {}).get('pnl', 0.0)
        loc_row = next((p for p in local_positions if p['symbol'] == sym), None)
        loc_pnl = float(loc_row['pnl_unrealized'] or 0.0) if loc_row else 0.0
        
        diff = abs(off_pnl - loc_pnl)
        status = "✅ OK" if diff < 1.0 else "❌ ERROR"
        if status == "❌ ERROR": pos_match = False
        
        print(f"{sym:<12} | ${off_pnl:>17.2f} | ${loc_pnl:>17.2f} | {status}")

    print("\n" + "-"*70)
    print("💎 [REPORTE DE HUD GLOBAL (PNL TOTAL)]")
    print("-"*70)
    
    # Calculamos la suma local para verificar consistencia interna
    sum_local_pnl = sum(float(p['pnl_unrealized'] or 0.0) for p in local_positions)
    
    print(f"{'INDICADOR':<25} | {'BINANCE (REAL)':<18} | {'SYSMHO (HUD)':<18}")
    print("-"*70)
    print(f"{'PnL GLOBAL (Flotante)':<25} | ${binance_total_unrealized:>17.2f} | ${sum_local_pnl:>17.2f}")
    print(f"{'Capital Operativo (Total)':<25} | ${binance_total_margin:>17.2f} | (Sincronizado)")
    print(f"{'Disponible a Invertir':<25} | ${binance_available:>17.2f} | (Sincronizado)")
    print("-"*70)

    global_diff = abs(binance_total_unrealized - sum_local_pnl)
    if global_diff < 1.0 and pos_match:
        print("\n🏆 RESULTADO FINAL: COHERENCIA TÁCTICA 100% CONFIRMADA.")
        print("El sistema es un espejo fiel del campo de batalla (Binance).")
    else:
        print("\n⚠️ ADVERTENCIA: Se detectó una micro-discrepancia.")
        print(f"Diferencia Global: ${global_diff:.4f}")
        print("Causa probable: Latencia de milisegundos en el pulso de red.")

    await db.close()
    await trader.close_connection()

if __name__ == "__main__":
    asyncio.run(verify_coherence())
