"""
매일 시장 지표 + 관심 종목을 받아 daily_news/{YMD}_지표.json 으로 저장한다.

- Fear & Greed : CNN 비공식 API (requests + 브라우저 헤더 → 봇차단 우회)
- VIX/WTI/Brent/10Y : 야후(실시간) 우선 → 실패 시 FRED(무료키, 며칠 지연)
- 관심 종목 : 야후 종가 + 등락률 (달러/원화 자동 구분)

노션 루틴은 이 JSON을 GitHub raw로 읽기만 한다(API 직접 호출 X → 차단 문제 원천 제거).
"""
import os
import json
from datetime import datetime, timedelta

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO_ROOT, "daily_news")

KST_NOW = datetime.utcnow() + timedelta(hours=9)
YMD = KST_NOW.strftime("%y%m%d")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

CNN_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://edition.cnn.com/markets/fear-and-greed",
    "Origin": "https://edition.cnn.com",
}

YAHOO_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://finance.yahoo.com/",
    "Origin": "https://finance.yahoo.com",
}


def fetch_fear_greed():
    """CNN F&G — score(현재값)와 rating 반환. 실패 시 None."""
    try:
        r = requests.get(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers=CNN_HEADERS, timeout=20,
        )
        r.raise_for_status()
        fg = r.json()["fear_and_greed"]
        return {"score": round(float(fg["score"])), "rating": fg["rating"]}
    except Exception as e:
        print(f"[F&G] 실패: {e}")
        return None


def fetch_yahoo(symbol):
    """야후 파이낸스 실시간 시세. 실패 시 None."""
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            headers=YAHOO_HEADERS, timeout=20,
        )
        r.raise_for_status()
        meta = r.json()["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        if price is None:
            return None
        ts = meta.get("regularMarketTime")
        if ts:
            date = (datetime.utcfromtimestamp(ts) + timedelta(hours=9)).strftime("%Y-%m-%d")
        else:
            date = KST_NOW.strftime("%Y-%m-%d")
        return {"value": round(float(price), 2), "date": date, "source": "yahoo"}
    except Exception as e:
        print(f"[Yahoo {symbol}] 실패: {e}")
        return None


def fetch_fred(series_id):
    """FRED 최신 관측치(며칠 지연). 키 없거나 실패 시 None."""
    key = os.environ.get("FRED_API_KEY")
    if not key:
        return None
    try:
        r = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id": series_id, "api_key": key, "file_type": "json",
                "sort_order": "desc", "limit": 5,
            },
            timeout=20,
        )
        r.raise_for_status()
        for obs in r.json().get("observations", []):
            if obs.get("value") not in (".", "", None):
                return {"value": float(obs["value"]), "date": obs["date"], "source": "fred"}
        return None
    except Exception as e:
        print(f"[FRED {series_id}] 실패: {e}")
        return None


def fetch_indicator(yahoo_symbol, fred_series):
    """야후(실시간) 우선, 실패하면 FRED(지연)로 대체."""
    return fetch_yahoo(yahoo_symbol) or fetch_fred(fred_series)


# 관심 종목 (야후 티커, 표시 이름)
WATCHLIST = [
    ("IREN", "아이렌"),
    ("IRE",  "디파이언스 2X IREN ETF"),
    ("RKLB", "로켓랩"),
    ("DRAM", "라운드힐 메모리 ETF"),
    ("INFQ", "인플렉션"),
    ("MRVL", "마벨"),
    ("442580.KS", "PLUS 글로벌HBM반도체"),  # 원화(KRW) ETF
]


def fetch_stock(symbol):
    """관심 종목 종가 + 등락률 + 통화. 실패 시 None."""
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            headers=YAHOO_HEADERS, timeout=20,
        )
        r.raise_for_status()
        m = r.json()["chart"]["result"][0]["meta"]
        price = m.get("regularMarketPrice")
        prev = m.get("chartPreviousClose") or m.get("previousClose")
        if price is None or prev is None:
            return None
        change = price - prev
        pct = (change / prev * 100) if prev else 0
        ts = m.get("regularMarketTime")
        date = ((datetime.utcfromtimestamp(ts) + timedelta(hours=9)).strftime("%Y-%m-%d")
                if ts else KST_NOW.strftime("%Y-%m-%d"))
        return {
            "price": round(float(price), 2),
            "change": round(float(change), 2),
            "pct": round(float(pct), 2),
            "date": date,
            "currency": m.get("currency", "USD"),
        }
    except Exception as e:
        print(f"[Stock {symbol}] 실패: {e}")
        return None


def fetch_watchlist():
    """관심 종목 리스트 수집."""
    out = []
    for sym, name in WATCHLIST:
        d = fetch_stock(sym)
        out.append({"symbol": sym, "name": name, **(d or {"price": None})})
    return out


def main():
    data = {
        "date": YMD,
        "generated_at_kst": KST_NOW.strftime("%Y-%m-%d %H:%M"),
        "fear_greed": fetch_fear_greed(),
        "vix": fetch_indicator("^VIX", "VIXCLS"),
        "wti": fetch_indicator("CL=F", "DCOILWTICO"),
        "brent": fetch_indicator("BZ=F", "DCOILBRENTEU"),
        "us10y": fetch_indicator("^TNX", "DGS10"),
        "watchlist": fetch_watchlist(),
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{YMD}_지표.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"저장: {out_path}")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
