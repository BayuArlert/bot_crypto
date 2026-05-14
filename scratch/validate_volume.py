import pandas as pd
from binance.client import Client
import datetime

# Inisialisasi client public
client = Client()

print("Fetching historical data for BTCUSDT (1h interval) for the last 60 days...")
klines = client.get_historical_klines("BTCUSDT", Client.KLINE_INTERVAL_1HOUR, "60 days ago UTC")

# Create DataFrame
df = pd.DataFrame(klines, columns=[
    'timestamp', 'open', 'high', 'low', 'close', 'volume',
    'close_time', 'quote_asset_volume', 'number_of_trades',
    'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
])

# Process timestamps
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
df['volume'] = pd.to_numeric(df['volume'])
df['hour_utc'] = df['timestamp'].dt.hour

# Calculate average volume per hour
hourly_volume = df.groupby('hour_utc')['volume'].mean().sort_index()

print("\n--- Average Hourly Volume (BTCUSDT) over last 60 Days ---")
print("Hour (UTC) | Avg Volume (BTC) | Hour (WIB)")
print("-" * 50)
for hour, vol in hourly_volume.items():
    hour_wib = (hour + 7) % 24
    print(f"{hour:02d}:00 UTC  | {vol:10.2f}     | {hour_wib:02d}:00 WIB")

# Find the 5 lowest volume hours
lowest = hourly_volume.nsmallest(5)
print("\n--- 5 Jam Paling Sepi (Terendah) ---")
for hour, vol in lowest.items():
    print(f"UTC {hour:02d}:00 / WIB {(hour+7)%24:02d}:00 -> {vol:.2f} BTC")
