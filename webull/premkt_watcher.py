import os
import json
import time
import threading
from datetime import datetime

import requests
import pytz
import yfinance as yf
from dotenv import load_dotenv
from rich.live import Live
from rich.table import Table
from rich.console import Console
from rich.align import Align

load_dotenv()

WEBULL_API = "https://quotes-gw.webullfintech.com/api/bgw/market/pcIndex?regionId=6&pageSize=50"
SNAPSHOT_FILE = "premkt_snapshot.json"
SPIKE_THRESHOLD = 2.0
MIN_MARKET_CAP = 10_000_000  # $10M — ignore micro-cap stocks

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TZ_NY = pytz.timezone("America/New_York")
PREMKT_START = 4   # 4:00 AM ET
MARKET_OPEN = 9    # 9:30 AM ET — round down, minute check below


def is_premarket_hours():
    now = datetime.now(TZ_NY)
    if now.weekday() >= 5:
        return False
    total_min = now.hour * 60 + now.minute
    return PREMKT_START * 60 <= total_min < int(MARKET_OPEN * 60 + 30)


API_HEADERS = {
    "Referer": "https://www.webull.com/",
    "appid": "wb_web_us",
    "platform": "web",
    "app": "global",
    "device-type": "Web",
    "Origin": "https://www.webull.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15",
}

console = Console()


def load_snapshot():
    if os.path.exists(SNAPSHOT_FILE):
        try:
            with open(SNAPSHOT_FILE, "r") as f:
                data = json.load(f)
            snapshots = data.get("snapshots", [])
            if snapshots:
                return snapshots[-1]
            return {}
        except Exception:
            return {}
    return {}


def load_history():
    if os.path.exists(SNAPSHOT_FILE):
        try:
            with open(SNAPSHOT_FILE, "r") as f:
                data = json.load(f)
            return data.get("snapshots", [])
        except Exception:
            return []
    return []


def save_history(snapshots):
    snapshots = snapshots[-60:]
    with open(SNAPSHOT_FILE, "w") as f:
        json.dump({"snapshots": snapshots}, f, indent=2)


def fetch_premarket():
    try:
        r = requests.get(WEBULL_API, headers=API_HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        for group in data.get("groups", []):
            if group.get("id") == "gainers":
                return group.get("data", [])
        return []
    except Exception as e:
        console.print(f"[red]API fetch error: {e}[/red]")
        return None


def build_stock_map(raw_data):
    stock_map = {}
    for item in raw_data:
        t = item.get("ticker", {})
        symbol = t.get("symbol", "")
        if not symbol:
            continue
        raw_vol = t.get("volume", "0")
        price = t.get("pprice")
        shares = int(raw_vol) if raw_vol and raw_vol.isdigit() else 0
        usd_vol = round(shares * float(price)) if price and shares else 0
        stock_map[symbol] = {
            "name": t.get("name", symbol),
            "price": price,
            "pchRatio": t.get("pchRatio"),
            "pchange": t.get("pchange"),
            "volume": shares,
            "usd_vol": usd_vol,
        }
    return stock_map


_market_cap_cache = {}


def filter_by_market_cap(stock_map):
    new_map = {}
    for symbol, data in stock_map.items():
        if symbol not in _market_cap_cache:
            try:
                ticker = yf.Ticker(symbol)
                _market_cap_cache[symbol] = ticker.info.get("marketCap")
            except Exception:
                _market_cap_cache[symbol] = None
        cap = _market_cap_cache[symbol]
        if cap is None or cap >= MIN_MARKET_CAP:
            new_map[symbol] = data
        else:
            console.print(f"[yellow]Skipping {symbol} - Market Cap: ${cap:,}[/yellow]")
    return new_map


TF_OFFSETS = [(1, "1m"), (3, "3m"), (5, "5m"), (10, "10m"), (15, "15m")]


MOM_W = {"1m": 0.35, "3m": 0.25, "5m": 0.20, "10m": 0.12, "15m": 0.08}


def compute_deltas(current, history):
    n = len(history)
    for symbol, data in current.items():
        for offset, label in TF_OFFSETS:
            idx = n - offset
            if idx >= 0 and symbol in history[idx]:
                prev = history[idx][symbol]
                if isinstance(prev, dict):
                    cur_price = data.get("price")
                    prev_price = prev.get("price")
                    cur_vol = data.get("volume", 0)
                    prev_vol = prev.get("volume", 0)

                    if prev_price and cur_price:
                        pf, cf = float(prev_price), float(cur_price)
                        data[f"{label}_chg"] = ((cf - pf) / abs(pf) * 100) if pf != 0 else 0.0
                    else:
                        data[f"{label}_chg"] = None

                    data[f"{label}_vol"] = cur_vol - prev_vol
            else:
                data[f"{label}_chg"] = None
                data[f"{label}_vol"] = 0

        total = float(data.get("pchRatio", 0) or 0) * 100
        score = 0.0
        for l, w in MOM_W.items():
            v = data.get(f"{l}_chg")
            score += w * (v if v is not None else total)
        data["mom"] = round(score, 2)

    return current


def detect_spikes(current):
    spikes = []
    for symbol, data in current.items():
        min1 = data.get("1m_chg")
        if min1 is not None and abs(min1) >= SPIKE_THRESHOLD:
            spikes.append({
                "symbol": symbol,
                "name": data["name"],
                "price": data["price"],
                "min1_change": min1,
                "total_change": float(data["pchRatio"]) * 100 if data.get("pchRatio") else 0,
            })
    return spikes


def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
        }, timeout=5)
    except Exception as e:
        console.print(f"[red]Telegram error: {e}[/red]")


def send_spike_alerts(spikes):
    if not spikes:
        return
    now = datetime.now(pytz.timezone("Europe/Istanbul")).strftime("%H:%M:%S")
    msg = f"\U0001f4e1 *Premarket Spike Alert* ({now})\n\n"
    for s in spikes[:10]:
        direction = "\U0001f7e2" if s["min1_change"] > 0 else "\U0001f534"
        msg += (
            f"{direction} *{s['symbol']}* ({s['name']})\n"
            f"   Price: ${float(s['price']):.2f}\n"
            f"   1m Change: %{s['min1_change']:+.2f}\n"
            f"   Total Premkt: %{s['total_change']:+.2f}\n\n"
        )
    threading.Thread(target=send_telegram, args=(msg,), daemon=True).start()


def format_change(val_signed):
    if val_signed is None:
        return "[dim]N/A[/dim]"
    v = float(val_signed)
    if v > 0:
        return f"[green]%{v:+.2f}[/green]"
    elif v < 0:
        return f"[red]%{v:+.2f}[/red]"
    else:
        return f"[dim]%{v:+.2f}[/dim]"


def format_volume(val):
    if val >= 1_000_000:
        return f"{val/1_000_000:.1f}M"
    elif val >= 1_000:
        return f"{val/1_000:.1f}K"
    return str(val)


def format_usd(val):
    if val >= 1_000_000:
        return f"${val/1_000_000:.1f}M"
    elif val >= 1_000:
        return f"${val/1_000:.1f}K"
    return f"${val}"


def format_vol_change(val):
    if val is None:
        return "[dim]N/A[/dim]"
    v = int(val)
    if v > 0:
        return f"[green]{format_volume(v)}[/green]"
    elif v < 0:
        return f"[red]{format_volume(abs(v))}[/red]"
    return "[dim]0[/dim]"


def build_table(current):
    now = datetime.now().strftime("%H:%M:%S")
    labels = [l for _, l in TF_OFFSETS]

    sorted_stocks = sorted(current.items(), key=lambda x: x[1].get("mom", 0), reverse=True)

    title = (
        f"[bold cyan]Premarket Gainers Watcher[/bold cyan]  |  "
        f"{now}  |  "
        f"[bold]{len(current)}[/bold] stocks  |  "
        f"Score: [yellow]momentum[/yellow]"
    )

    table = Table(title=title, title_justify="center", border_style="cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Tick", style="bold white", width=7)
    table.add_column("Name", width=18, no_wrap=True)
    table.add_column("Price", justify="right", width=9)
    table.add_column("Vol$", justify="right", width=12)
    table.add_column("Mom", justify="right", width=7)
    for l in labels:
        table.add_column(f"{l}%", justify="right", width=9)
    for l in labels:
        table.add_column(f"\u0394{l}V", justify="right", width=7)

    for idx, (symbol, data) in enumerate(sorted_stocks, 1):
        name = data.get("name", symbol)[:16]
        price = data.get("price")
        pch_ratio = data.get("pchRatio")
        usd_vol = data.get("usd_vol", 0)
        mom = data.get("mom")

        price_str = f"${float(price):.2f}" if price is not None else "[dim]-[/dim]"
        total_pct = (float(pch_ratio) * 100) if pch_ratio is not None else None
        usd_str = format_usd(usd_vol) if usd_vol else "[dim]$0[/dim]"
        mom_str = f"[bold]{mom:+.2f}[/bold]" if mom is not None else "[dim]N/A[/dim]"

        row = [str(idx), symbol, name, price_str, usd_str, mom_str]
        for l in labels:
            row.append(format_change(data.get(f"{l}_chg", total_pct)))
        for l in labels:
            row.append(format_vol_change(data.get(f"{l}_vol", 0)))

        table.add_row(*row)

    return table


def main():
    console.clear()

    history = load_history()
    if history:
        console.print(f"[green]Loaded {len(history)} historical snapshots.[/green]")
    else:
        console.print("[yellow]No previous history. Starting fresh.[/yellow]")

    send_telegram(
        f"\U0001f7e2 *Premarket Watcher Started*\n"
        f"Tracking top gainers every 60s\n"
        f"Spike threshold: \u00b1%{SPIKE_THRESHOLD:.1f}\n"
        f"{datetime.now().strftime('%H:%M:%S')}"
    )

    snooze_until = None

    try:
        with Live(console=console, refresh_per_second=4, screen=True) as live:
            while True:
                if not is_premarket_hours():
                    now_ny = datetime.now(TZ_NY)
                    if now_ny.weekday() >= 5:
                        # Weekends → snoozes until Monday 4:00 AM
                        msg = "[yellow]Weekend — next check Mon 4:00 AM ET[/yellow]"
                        snooze_until = "Mon 4:00 AM ET"
                    elif now_ny.hour < PREMKT_START:
                        # Before 4:00 AM ET → shows "Premarket hasn't started" and snoozes until 4:00 AM
                        snooze_until = f"Today {PREMKT_START}:00 AM ET"
                        msg = f"[yellow]Premarket hasn't started — next check {snooze_until}[/yellow]"
                    else:
                        # After 9:30 AM ET → shows "Market open — premarket data stale" and snoozes until next day 4:00 AM
                        snooze_until = "Tomorrow 4:00 AM ET"
                        msg = "[yellow]Market open — premarket data stale. Resuming tomorrow 4:00 AM ET[/yellow]"
                    live.update(Align.center(msg))
                    time.sleep(60)
                    continue

                # Weekdays 4:00–9:30 AM ET → polls normally
                if snooze_until:
                    send_telegram(
                        f"\U0001f7e2 *Premarket Watcher Resumed*\n"
                        f"Premarket hours detected. Tracking resumed.\n"
                        f"{datetime.now().strftime('%H:%M:%S')}"
                    )
                    snooze_until = None

                raw_data = fetch_premarket()

                if raw_data is None:
                    live.update(
                        Align.center(
                            "[red]API unreachable. Retrying in 60s...[/red]"
                        )
                    )
                    time.sleep(60)
                    continue

                current = build_stock_map(raw_data)
                current = filter_by_market_cap(current)

                if current:
                    current = compute_deltas(current, history)

                    spikes = detect_spikes(current)
                    if spikes:
                        send_spike_alerts(spikes)

                    history.append(current)
                    save_history(history)

                if current:
                    table = build_table(current)
                    live.update(table)
                else:
                    live.update(
                        Align.center("[yellow]No premarket data available.[/yellow]")
                    )

                time.sleep(60 - time.time() % 60)

    except KeyboardInterrupt:
        console.print("\n[yellow]Watcher stopped.[/yellow]")


if __name__ == "__main__":
    main()
