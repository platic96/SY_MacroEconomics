"""
매일 시장 지표를 노션 「투자일기」 DB에 밀어 넣는다.

- 오늘 행이 없으면 만들고, 있으면 지표/Market 두 칸만 갱신한다(중복 생성 방지).
- 사용자가 직접 쓰는 항목(NEWS·시장분위기·M-E 차이·내 감정·자신감·Action·
  해야할 일, 복기 3종)은 절대 건드리지 않는다.
- 종이 양식처럼 한 칸에 여러 값을 · 로 이어 붙인다.

    1 지표    F&G 67 (Greed) · VIX 14.51 (-2.31%) · WTI 81.71 (+0.54%) /
              브렌트 87.28 (+0.41%) · 미10년 4.64% (+0.30%)
    3 Market  나스닥 26,803 (+0.83%) · S&P500 7,799 (+0.52%) · …

- 등락률은 야후의 전일 종가(chartPreviousClose) 기준이라 시세와 함께 직접 받는다.
  F&G 만 CNN 값이므로 fetch_indicators.py 가 만든 JSON에서 읽는다.

필요 환경변수: NOTION_TOKEN (노션 통합 토큰)
"""
import os
import json
from datetime import datetime, timedelta

import requests

DATABASE_ID = "aa307c5e-725e-4869-802c-a35950a70432"   # 노션 「투자일기」

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_DIR = os.path.join(REPO_ROOT, "daily_news")

KST_NOW = datetime.utcnow() + timedelta(hours=9)
YMD = KST_NOW.strftime("%y%m%d")
ISO = KST_NOW.strftime("%Y-%m-%d")
WEEKDAY = ["월", "화", "수", "목", "금", "토", "일"][KST_NOW.weekday()]
# 예: 2026.08.14 (금)  — 문자 정렬해도 날짜순이 유지된다.
TITLE = f"{KST_NOW.strftime('%Y.%m.%d')} ({WEEKDAY})"

# 미국 종가는 KST 기준 다음 날 새벽에 확정된다.
#   미 월 종가 → 한국 화요일 / … / 미 금 종가 → 한국 토요일
# 따라서 한국 일요일(미 토)·월요일(미 일)에는 새로 받을 종가가 없다.
SKIP_WEEKDAYS = {6, 0}          # 일, 월 (Python: 월=0 … 일=6)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
YAHOO_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://finance.yahoo.com/",
    "Origin": "https://finance.yahoo.com",
}

# 1 지표 — VIX·유가·금리 (F&G 는 CNN 이라 JSON 에서 읽음)
INDICATORS = [
    ("VIX", "^VIX"),
    ("WTI", "CL=F"),
    ("브렌트", "BZ=F"),
    ("미10년", "^TNX"),
]

# 3 Market — 사진 순서 + SOXX·DRAM 추가. 마지막 값은 단위.
#   지수는 포인트라 단위가 없고, 주식·ETF·원자재는 $, 환율은 원.
MARKET = [
    ("나스닥", "^IXIC", ""),
    ("S&P500", "^GSPC", ""),
    ("비트코인", "BTC-USD", "$"),
    ("달러원", "KRW=X", "원"),
    ("이더리움", "ETH-USD", "$"),
    ("금", "GC=F", "$"),
    ("SOXX", "SOXX", "$"),        # iShares 반도체 ETF
    ("DRAM", "DRAM", "$"),        # Roundhill 메모리 ETF
    ("IREN", "IREN", "$"),
    ("RKLB", "RKLB", "$"),
]


def notion_headers():
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise SystemExit("[중단] NOTION_TOKEN 환경변수가 없습니다.")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def num(value):
    """1234.5 → '1,235' / 작은 값은 소수점 유지."""
    if value is None:
        return None
    return f"{value:,.0f}" if abs(value) >= 1000 else f"{value:,.2f}".rstrip("0").rstrip(".")


def fetch_quote(symbol):
    """(현재가, 전일대비 %, 전일대비 변화량) — 실패 시 (None, None, None).

    변화량은 금리처럼 bp 로 표기해야 하는 값에 쓴다.
    """
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            headers=YAHOO_HEADERS, timeout=20,
        )
        r.raise_for_status()
        m = r.json()["chart"]["result"][0]["meta"]
        price = m.get("regularMarketPrice")
        if price is None:
            return None, None, None
        prev = m.get("chartPreviousClose") or m.get("previousClose")
        if not prev:
            return round(float(price), 2), None, None
        change = float(price) - float(prev)
        pct = change / float(prev) * 100
        return round(float(price), 2), round(pct, 2), round(change, 4)
    except Exception as e:
        print(f"[야후 {symbol}] 실패: {e}")
        return None, None, None


def us_last_trading_date():
    """미국 증시 마지막 거래일(ET). 실패 시 None.

    미 증시 마감 16:00 ET = 20~21시 UTC 라서, 체결 시각의 UTC 날짜가
    곧 그날의 거래일이 된다.
    """
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/^GSPC",
            headers=YAHOO_HEADERS, timeout=20,
        )
        r.raise_for_status()
        ts = r.json()["chart"]["result"][0]["meta"].get("regularMarketTime")
        return datetime.utcfromtimestamp(ts).date() if ts else None
    except Exception as e:
        print(f"[거래일 확인] 실패: {e}")
        return None


def is_us_holiday():
    """평일인데 미 증시가 안 열렸으면 (거래일, True). 정상이면 (거래일, False)."""
    traded = us_last_trading_date()
    expected = (KST_NOW - timedelta(days=1)).date()
    return traded, bool(traded and traded != expected)


def load_indicators():
    """fetch_indicators.py 가 만든 오늘자 JSON. 없으면 빈 dict."""
    path = os.path.join(JSON_DIR, f"{YMD}_지표.json")
    if not os.path.exists(path):
        print(f"[경고] {path} 없음 — F&G 는 건너뜁니다.")
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt(name, price, pct, unit=""):
    """'SOXX $550.74 (+0.76%)' 형태. 값이 없으면 None.

    unit 은 '$'(앞에 붙임) / '원'·'%'(뒤에 붙임) / ''(지수라 단위 없음).
    """
    if price is None:
        return None
    value = f"${num(price)}" if unit == "$" else f"{num(price)}{unit}"
    text = f"{name} {value}"
    if pct is not None:
        text += f" ({pct:+.2f}%)"
    return text


def build_지표(data):
    parts = []

    # F&G — CNN 값. score 와 rating(Greed / Extreme Fear 등)을 함께 표기
    fg = data.get("fear_greed") or {}
    score, rating = fg.get("score"), fg.get("rating")
    if score is not None:
        label = f" ({rating.title()})" if rating else ""
        parts.append(f"F&G {score:.0f}{label}")

    quotes = {name: fetch_quote(sym) for name, sym in INDICATORS}

    vix, vix_pct, _ = quotes["VIX"]
    if vix is not None:
        parts.append(fmt("VIX", vix, vix_pct))

    # WTI 와 브렌트는 한 덩어리로 묶는다
    wti, wti_pct, _ = quotes["WTI"]
    brent, brent_pct, _ = quotes["브렌트"]
    oil = [s for s in (fmt("WTI", wti, wti_pct, "$"),
                       fmt("브렌트", brent, brent_pct, "$")) if s]
    if oil:
        parts.append(" / ".join(oil))

    # 미10년은 금리라 % 가 아니라 bp(베이시스포인트)로 표기한다. 1bp = 0.01%p
    y, _, y_chg = quotes["미10년"]
    if y is not None:
        bp = f" ({y_chg * 100:+.0f}bp)" if y_chg is not None else ""
        parts.append(f"미10년 {num(y)}%{bp}")

    return " · ".join(parts)


def build_market():
    parts = []
    for name, sym, unit in MARKET:
        price, pct, _ = fetch_quote(sym)
        line = fmt(name, price, pct, unit)
        if line:
            parts.append(line)
    return " · ".join(parts)


def find_today_page(headers):
    """오늘 날짜 행이 이미 있으면 그 page_id 반환."""
    r = requests.post(
        f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
        headers=headers,
        json={"filter": {"property": "0 날짜", "date": {"equals": ISO}}, "page_size": 1},
        timeout=20,
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    return results[0]["id"] if results else None


def text_prop(value):
    return {"rich_text": [{"text": {"content": value}}]}


def main():
    # 한국 일·월요일 = 미국 토·일 → 새로 받을 종가가 없으므로 행을 만들지 않는다.
    if KST_NOW.weekday() in SKIP_WEEKDAYS:
        print(f"[건너뜀] {TITLE} — {WEEKDAY}요일은 미국 증시 종가가 새로 나오지 않음")
        return

    traded, holiday = is_us_holiday()
    title = f"{TITLE} 휴장" if holiday else TITLE
    if holiday:
        print(f"[휴장] 미 증시 마지막 거래일 {traded} — 직전 종가로 행을 만듭니다.")

    headers = notion_headers()

    지표 = build_지표(load_indicators())
    market = build_market()

    if not 지표 and not market:
        raise SystemExit("[중단] 채울 수 있는 값이 하나도 없습니다.")

    props = {}
    if 지표:
        props["1 지표"] = text_prop(지표)
    if market:
        props["3 Market"] = text_prop(market)

    page_id = find_today_page(headers)
    if page_id:
        # 이미 있는 행 — 두 칸만 덮어쓴다. 사용자가 쓴 글은 건드리지 않는다.
        r = requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=headers, json={"properties": props}, timeout=20,
        )
        action = "갱신"
    else:
        props["제목"] = {"title": [{"text": {"content": title}}]}
        props["0 날짜"] = {"date": {"start": ISO}}
        r = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json={"parent": {"database_id": DATABASE_ID}, "properties": props},
            timeout=20,
        )
        action = "생성"

    if not r.ok:
        raise SystemExit(f"[실패] 노션 {action} 오류 {r.status_code}: {r.text[:300]}")

    print(f"[완료] {title} {action}")
    print(f"  1 지표   : {지표}")
    print(f"  3 Market : {market}")


if __name__ == "__main__":
    main()
