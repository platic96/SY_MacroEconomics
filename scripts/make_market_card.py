# -*- coding: utf-8 -*-
"""오늘의 시장 한 장 — daily_news/{YMD}_지표.json → daily_news/{YMD}_시장한장.png
숫자는 JSON 값만 사용(없으면 '조회 실패'). 1080x1350 세로형(블로그·인스타 공용), 폰에서 읽히는 글자 크기.
사용: python scripts/make_market_card.py [YYMMDD]   (생략 시 KST 오늘)
"""
import json, sys, os, datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch, Rectangle

for f in ('NanumGothic', 'Malgun Gothic', 'Noto Sans CJK KR', 'AppleGothic'):
    if any(f == x.name for x in fm.fontManager.ttflist):
        plt.rcParams['font.family'] = f
        break
plt.rcParams['axes.unicode_minus'] = False

NAVY, GOLD, RED, GREEN, GRAY, INK = '#1F3864', '#C9A14A', '#C0392B', '#3F7A2A', '#6B7380', '#1E2533'
ALIAS = {'IRE': '아이렌 2배 ETF', 'DRAM': '메모리 ETF', '442580.KS': 'HBM반도체 ETF'}
FG_KO = [(25, '극단적 공포', '#B03A2E'), (45, '공포', '#E07B39'), (56, '중립', '#9A9A9A'), (75, '탐욕', '#7FA33A'), (101, '극단적 탐욕', '#3F7A2A')]


def fg_label(s):
    for hi, name, col in FG_KO:
        if s < hi:
            return name, col
    return FG_KO[-1][1], FG_KO[-1][2]


def vix_label(v):
    return '매우 평온' if v < 15 else '평온' if v < 20 else '경계' if v < 30 else '불안'


def val(d, k):
    x = d.get(k) or {}
    return x.get('value') if isinstance(x, dict) else None


def main():
    ymd = sys.argv[1] if len(sys.argv) > 1 else (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime('%y%m%d')
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'daily_news')
    src = os.path.join(base, f'{ymd}_지표.json')
    if not os.path.exists(src):
        print('지표 JSON 없음 — 그림 생략:', src); return
    d = json.load(open(src, encoding='utf-8'))
    full = f'20{ymd[:2]}.{ymd[2:4]}.{ymd[4:]}'
    # 표시: 2026.11.24.(화) KST 05:40 기준 — 시각은 지표를 실제로 수집한 시각(generated_at_kst)
    stamp = full + ' 기준'
    try:
        dt = datetime.datetime.strptime(d.get('generated_at_kst', ''), '%Y-%m-%d %H:%M')
        stamp = dt.strftime('%Y.%m.%d.') + '(' + '월화수목금토일'[dt.weekday()] + ') KST ' + dt.strftime('%H:%M') + ' 기준'
    except Exception:
        pass

    fig = plt.figure(figsize=(10.8, 13.5), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1080); ax.set_ylim(1350, 0); ax.axis('off')
    ax.add_patch(Rectangle((0, 0), 1080, 14, color=GOLD))
    ax.text(70, 95, '오늘의 시장 한 장', fontsize=46, fontweight='bold', color=NAVY, va='center')
    ax.text(70, 160, stamp, fontsize=30, color=GRAY, va='center')

    # 공포·탐욕 게이지
    fg = d.get('fear_greed') or {}
    score = fg.get('score')
    ax.text(70, 245, '공포·탐욕 지수', fontsize=32, fontweight='bold', color=INK, va='center')
    gx, gy, gw, gh = 70, 290, 940, 40
    lo = 0
    for hi, name, col in FG_KO:
        ax.add_patch(Rectangle((gx + gw * lo / 100, gy), gw * (min(hi, 100) - lo) / 100, gh, color=col, alpha=.85))
        lo = min(hi, 100)
    for t in (0, 25, 50, 75, 100):
        ax.text(gx + gw * t / 100, gy + gh + 34, str(t), fontsize=24, color=GRAY, ha='center', va='center')
    if score is not None:
        name, col = fg_label(score)
        x = gx + gw * score / 100
        ax.plot([x, x], [gy - 18, gy + gh + 8], color=INK, lw=5)
        ax.text(1010, 245, f'{score}  {name}', fontsize=36, fontweight='bold', color=col, ha='right', va='center')
    else:
        ax.text(1010, 245, '조회 실패', fontsize=32, color=GRAY, ha='right', va='center')

    # 지표 타일 3개
    tiles = []
    v = val(d, 'vix'); tiles.append(('VIX(변동성)', f'{v:.1f}' if v is not None else '조회 실패', vix_label(v) if v is not None else ''))
    v = val(d, 'us10y'); tiles.append(('미 10년물 금리', f'{v:.2f}%' if v is not None else '조회 실패', ''))
    w, b = val(d, 'wti'), val(d, 'brent')
    tiles.append(('WTI 유가', f'${w:.1f}' if w is not None else '조회 실패', f'브렌트 ${b:.1f}' if b is not None else ''))
    for i, (k, vv, sub) in enumerate(tiles):
        x0 = 70 + i * 320
        ax.add_patch(FancyBboxPatch((x0, 420), 300, 190, boxstyle='round,pad=0,rounding_size=18', fc='#F2F4F8', ec='none'))
        ax.text(x0 + 24, 462, k, fontsize=26, color=GRAY, va='center')
        ax.text(x0 + 24, 528, vv, fontsize=44, fontweight='bold', color=NAVY, va='center')
        if sub:
            ax.text(x0 + 24, 583, sub, fontsize=26, color=INK, va='center')

    # 주요 지수·코인·종목 등락 막대 (JSON 'card' 순서 그대로, 없으면 watchlist)
    card = d.get('card')
    if card:
        ax.text(70, 670, '주요 지수·코인·종목 등락', fontsize=32, fontweight='bold', color=INK, va='center')
        ax.text(1010, 670, '지수·종목 전일 종가 / 코인 아침 시세', fontsize=20, color=GRAY, ha='right', va='center')
        wl = [x for x in card if x.get('pct') is not None]
    else:
        ax.text(70, 670, '관심 종목 등락 (전일 종가 기준)', fontsize=32, fontweight='bold', color=INK, va='center')
        wl = [x for x in (d.get('watchlist') or []) if x.get('pct') is not None]
        wl.sort(key=lambda x: x['pct'], reverse=True)
    wl = wl[:8]

    def label(x):
        if not card:
            nm = ALIAS.get(x.get('symbol'), x['name'])
            return nm if len(nm) <= 11 else (x.get('symbol') or nm[:10])
        p = x.get('price')
        ps = (f'{p:,.0f}' if p >= 1000 else f'{p:,.2f}') if p is not None else '?'
        return f"{x['name']} ({x.get('unit', '')}{ps})"

    if wl:
        m = max(abs(x['pct']) for x in wl) or 1
        rows = len(wl); rh = min(70, 500 / rows); y0 = 720
        zx = 640 if card else (560 if any(x['pct'] < 0 for x in wl) else 380)
        right = 1010 - zx; left = zx - 400
        for i, x in enumerate(wl):
            y = y0 + i * rh + rh / 2
            ax.text(70, y, label(x), fontsize=27 if card else 28, color=INK, va='center')
            p = x['pct']; col = GREEN if p >= 0 else RED
            if p >= 0:
                L = (right - 175) * abs(p) / m
                ax.add_patch(Rectangle((zx, y - rh * .3), max(L, 3), rh * .6, color=col))
                ax.text(zx + L + 12, y, f'▲{p:.1f}%', fontsize=28, fontweight='bold', color=col, va='center')
            else:
                L = min((right - 175) * abs(p) / m, 120)
                ax.add_patch(Rectangle((zx - L, y - rh * .3), max(L, 3), rh * .6, color=col))
                ax.text(zx + 12, y, f'▼{abs(p):.1f}%', fontsize=28, fontweight='bold', color=col, va='center')
        ax.plot([zx, zx], [y0, y0 + rows * rh], color='#999', lw=2)
    else:
        ax.text(70, 760, '등락 데이터 조회 실패', fontsize=30, color=GRAY)

    ax.text(70, 1262, '자료: CNN 공포·탐욕, Yahoo Finance (자동 수집) · 투자 권유 아님', fontsize=22, color=GRAY, va='center')
    ax.add_patch(Rectangle((0, 1290), 1080, 60, color=NAVY))
    ax.text(1010, 1320, '지뜽', fontsize=32, fontweight='bold', color='white', ha='right', va='center')
    out = os.path.join(base, f'{ymd}_시장한장.png')
    fig.savefig(out, dpi=100, metadata={'Software': None})
    print('saved', out)


if __name__ == '__main__':
    main()
