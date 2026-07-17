"""
매일 시장 지표 4종을 받아 daily_news/{YMD}_지표.json 으로 저장한다.
- Fear & Greed : CNN 비공식 API (requests + 브라우저 헤더 → 봇차단 우회)
- VIX/WTI/Brent/10Y : FRED (미 세인트루이스 연준, 서버 친화적·차단 없음, 무료키 필요)

노션 루틴은 이 JSON을 GitHub raw로 읽기만 한다(API 직접 호출 X → 차단 문제 원천 제거).
FRED_API_KEY 가 없으면 시장지표는 null 로 남고 F&G만 채워진다.
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

CNN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://edition.cnn.com/markets/fear-and-greed",
    "Origin": "https://edition.cnn.com",
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


def fetch_fred(series_id):
    """FRED 최신 관측치(전일 종가) 반환. 키 없거나 실패 시 None."""
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
                return {"value": float(obs["value"]), "date": obs["date"]}
        return None
    except Exception as e:
        print(f"[FRED {series_id}] 실패: {e}")
        return None


def main():
    data = {
        "date": YMD,
        "generated_at_kst": KST_NOW.strftime("%Y-%m-%d %H:%M"),
        "fear_greed": fetch_fear_greed(),      # {score, rating} or None
        "vix": fetch_fred("VIXCLS"),           # {value, date} or None
        "wti": fetch_fred("DCOILWTICO"),       # 서부텍사스유
        "brent": fetch_fred("DCOILBRENTEU"),   # 브렌트유
        "us10y": fetch_fred("DGS10"),          # 미 10년물 국채금리(%)
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{YMD}_지표.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"저장: {out_path}")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
