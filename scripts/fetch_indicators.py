"""
매일 시장 지표 5종을 받아 daily_news/{YMD}_지표.json 으로 저장한다.

- Fear & Greed : CNN 비공식 API (requests + 브라우저 헤더 → 봇차단 우회)
- VIX/WTI/Brent/10Y : ① 야후 파이낸스(실시간) 우선 → ② 실패 시 FRED(무료키, 며칠 지연) 대체

노션 루틴은 이 JSON을 GitHub raw로 읽기만 한다(API 직접 호출 X → 차단 문제 원천 제거).
FRED_API_KEY 가 없어도 야후가 되면 값이 채워진다.
"""
import os
import json
from datetime import datetime, timedelta

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO_ROOT, "daily_news")

# 파일명 날짜: 생성 시점 KST 기준 (generate_news.py 와 동일 규칙)
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
                "sort_order": "desc", "limit": 5,  # 최근 5개 중 값 있는 첫 관측치
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


def main():
    data = {
        "date": YMD,
        "generated_at_kst": KST_NOW.strftime("%Y-%m-%d %H:%M"),
        "fear_greed": fetch_fear_greed(),                      # {score, rating}
        "vix": fetch_indicator("^VIX", "VIXCLS"),              # {value, date, source}
        "wti": fetch_indicator("CL=F", "DCOILWTICO"),          # 서부텍사스유
        "brent": fetch_indicator("BZ=F", "DCOILBRENTEU"),      # 브렌트유
        "us10y": fetch_indicator("^TNX", "DGS10"),             # 미 10년물 국채금리(%)
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{YMD}_지표.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"저장: {out_path}")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
