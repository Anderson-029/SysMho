import asyncio
import ccxt.async_support as ccxt
import os
from dotenv import load_dotenv

async def test_connection():
    load_dotenv()
    api_key = os.getenv("BINANCE_API_KEY")
    secret_key = os.getenv("BINANCE_SECRET_KEY")
    
    print(f"🔍 Probando llaves: {api_key[:10]}...")
    
    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': secret_key,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })
    exchange.set_sandbox_mode(True)
    
    try:
        balance = await exchange.fetch_balance()
        print(f"✅ CONEXIÓN EXITOSA")
        print(f"💰 Balance USDT: {balance['total'].get('USDT', 'N/A')}")
    except Exception as e:
        print(f"❌ FALLO DE CONEXIÓN: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(test_connection())
