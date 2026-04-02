import asyncio
import asyncpg
import os
import sys

sys.path.append(os.path.join(os.getcwd()))
sys.path.append(os.path.join(os.getcwd(), 'src'))
from config.settings import DATABASE_URL

async def fix_accounting():
    conn = await asyncpg.connect(DATABASE_URL)
    
    print("🛡️ [ACCOUTING FIX] Iniciando auditoría de capital...")
    
    # 1. Obtener margen real de la tabla positions
    real_margin = await conn.fetchval("SELECT COALESCE(SUM(invested_usdt), 0) FROM positions")
    real_margin = float(real_margin)
    
    # 2. Obtener estado actual del portafolio
    portfolio = await conn.fetchrow("SELECT * FROM portfolio ORDER BY recorded_at DESC LIMIT 1")
    if not portfolio:
        print("❌ No se encontró registro de portafolio.")
        return

    curr_available = float(portfolio['available_balance'])
    curr_in_positions = float(portfolio['in_positions'])
    curr_total = float(portfolio['total_balance'])
    
    print(f"Estado Actual: Disponible=${curr_available}, En Posiciones=${curr_in_positions}, Total=${curr_total}")
    print(f"Margen Real Detectado: ${real_margin}")
    
    # El capital "atrapado" es la diferencia entre lo que dice la tabla portfolio y la tabla positions
    diff = curr_in_positions - real_margin
    
    if abs(diff) > 0.0001:
        print(f"⚠️ ¡Desajuste detectado!: ${diff} están atrapados o faltan en 'in_positions'.")
        # Corregimos: Liberamos o bloqueamos la diferencia hacia available_balance
        new_available = curr_available + diff
        new_in_positions = real_margin
        # El total balance no debería cambiar por un movimiento entre cajas, 
        # pero nos aseguramos de que sea consistente
        new_total = new_available + new_in_positions
        
        await conn.execute("""
            UPDATE portfolio 
            SET available_balance = $1,
                in_positions = $2,
                total_balance = $3
            WHERE id = $4
        """, new_available, new_in_positions, new_total, portfolio['id'])
        
        print(f"✅ [ÉXITO] Contabilidad Sincronizada: Nuevo Disponible=${new_available}, Nuevo En Posiciones=${new_in_positions}")
    else:
        print("✅ La contabilidad ya está sincronizada.")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_accounting())
