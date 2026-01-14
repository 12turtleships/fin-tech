import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import numpy as np
from datetime import datetime
from ta.volatility import BollingerBands

# Get OHLC data for DOGE-USD from Coinbase (5 days of hourly data)
def get_doge_ohlc_5days(granularity=3600, days=5):
    url = "https://api.exchange.coinbase.com/products/DOGE-USD/candles"
    # Calculate number of candles needed for 5 days (1 hour candles = 5 * 24 = 120 candles)
    # Coinbase API returns up to 300 candles, so we'll request enough for 5 days
    params = {"granularity": granularity}  # 3600 = 1 hour candles
    response = requests.get(url, params=params)
    data = response.json()

    # Coinbase returns [time, low, high, open, close, volume]
    df = pd.DataFrame(data, columns=["time", "low", "high", "open", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.sort_values("time")  # sort by oldest first
    
    # Filter to last 5 days if we have more data
    if len(df) > days * 24:
        cutoff_time = df["time"].max() - pd.Timedelta(days=days)
        df = df[df["time"] >= cutoff_time]
    
    return df

df = get_doge_ohlc_5days()

# Create figure with subplots for price and volume
fig = plt.figure(figsize=(16, 9), facecolor='#0d1117')
gs = fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.05, left=0.05, right=0.95, top=0.95, bottom=0.05)
ax_price = fig.add_subplot(gs[0, 0])
ax_volume = fig.add_subplot(gs[1, 0], sharex=ax_price)

# Set dark theme colors
bg_color = '#0d1117'
grid_color = '#21262d'
text_color = '#c9d1d9'
up_color = '#26a69a'  # Green for bullish candles
down_color = '#ef5350'  # Red for bearish candles

ax_price.set_facecolor(bg_color)
ax_volume.set_facecolor(bg_color)
for ax in [ax_price, ax_volume]:
    ax.tick_params(colors=text_color)
    ax.spines['bottom'].set_color(grid_color)
    ax.spines['top'].set_color(grid_color)
    ax.spines['right'].set_color(grid_color)
    ax.spines['left'].set_color(grid_color)

# Calculate Bollinger Bands
bb_period = 20
if len(df) >= bb_period:
    bb = BollingerBands(close=df["close"], window=bb_period)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_middle"] = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
else:
    # If not enough data, calculate manually
    df["bb_middle"] = df["close"].rolling(window=min(bb_period, len(df))).mean()
    std = df["close"].rolling(window=min(bb_period, len(df))).std()
    df["bb_upper"] = df["bb_middle"] + (2 * std)
    df["bb_lower"] = df["bb_middle"] - (2 * std)

# Convert datetime to numeric for plotting
dates = mdates.date2num(df["time"])
width = 0.6 * (dates[1] - dates[0]) if len(dates) > 1 else 0.01

# Plot Bollinger Bands first (so they appear behind candlesticks)
if len(df) >= bb_period:
    bb_color = '#7c3aed'  # Purple for Bollinger Bands
    # Fill area between upper and lower bands (plot first for layering)
    ax_price.fill_between(dates, df["bb_upper"], df["bb_lower"], color=bb_color, alpha=0.1)
    ax_price.plot(dates, df["bb_upper"], color=bb_color, linestyle='--', linewidth=1.5, alpha=0.7, label='BB Upper')
    ax_price.plot(dates, df["bb_middle"], color=bb_color, linestyle='-', linewidth=1.5, alpha=0.9, label='BB Middle')
    ax_price.plot(dates, df["bb_lower"], color=bb_color, linestyle='--', linewidth=1.5, alpha=0.7, label='BB Lower')

# Plot candlesticks (on top of Bollinger Bands)
for i, (date, open_price, high, low, close) in enumerate(zip(dates, df["open"], df["high"], df["low"], df["close"])):
    # Determine if bullish (green) or bearish (red)
    is_bullish = close >= open_price
    color = up_color if is_bullish else down_color
    
    # Draw wick (high-low line)
    ax_price.plot([date, date], [low, high], color=color, linewidth=1, solid_capstyle='round')
    
    # Draw body (open-close rectangle)
    body_bottom = min(open_price, close)
    body_top = max(open_price, close)
    body_height = body_top - body_bottom if body_top != body_bottom else width * 2
    
    rect = Rectangle((date - width/2, body_bottom), width, body_height,
                     facecolor=color, edgecolor=color, linewidth=1)
    ax_price.add_patch(rect)

# Format price chart
ax_price.set_ylabel('Price (USD)', color=text_color, fontsize=12, fontweight='bold')
ax_price.grid(True, color=grid_color, linestyle='-', linewidth=0.5, alpha=0.3)
ax_price.set_title('DOGE-USD (5 Days)', color=text_color, fontsize=16, fontweight='bold', pad=10)
ax_price.legend(loc='upper left', facecolor=bg_color, edgecolor=grid_color, labelcolor=text_color, fontsize=9)

# Format x-axis dates for 5 days
ax_price.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
ax_price.xaxis.set_major_locator(mdates.HourLocator(interval=12))  # Every 12 hours

# Plot volume bars
ax_volume.bar(dates, df["volume"], width=width*1.5, 
              color=[up_color if close >= open else down_color 
                     for close, open in zip(df["close"], df["open"])],
              alpha=0.6)
ax_volume.set_ylabel('Volume', color=text_color, fontsize=10, fontweight='bold')
ax_volume.grid(True, color=grid_color, linestyle='-', linewidth=0.5, alpha=0.3)

# Format x-axis for volume chart
ax_volume.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
ax_volume.xaxis.set_major_locator(mdates.HourLocator(interval=12))  # Every 12 hours
plt.setp(ax_volume.xaxis.get_majorticklabels(), rotation=45, ha='right')

# Hide top x-axis labels on price chart
plt.setp(ax_price.xaxis.get_majorticklabels(), visible=False)

# Add current price annotation
current_price = df["close"].iloc[-1]
ax_price.axhline(y=current_price, color=text_color, linestyle='--', linewidth=1, alpha=0.5)
ax_price.annotate(f'${current_price:.6f}', 
                  xy=(dates[-1], current_price),
                  xytext=(10, 0), textcoords='offset points',
                  color=text_color, fontsize=10, fontweight='bold',
                  bbox=dict(boxstyle='round,pad=0.5', facecolor=bg_color, edgecolor=text_color, alpha=0.8))

# Save chart as image with high resolution
output_path = "doge_chart.png"
plt.savefig(output_path, dpi=200, bbox_inches='tight', facecolor=bg_color, edgecolor='none')
plt.close()

print(f"Chart saved as {output_path}")
