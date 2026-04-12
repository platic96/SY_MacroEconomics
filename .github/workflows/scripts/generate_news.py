import os
import requests
from datetime import datetime, timedelta
import anthropic


def fetch_news():
    api_key = os.environ['NEWS_API_KEY']

    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    today = datetime.utcnow().strftime('%Y-%m-%d')

    url = 'https://newsapi.org/v2/everything'
    params = {
        'q': 'bloomberg OR "wall street" OR "federal reserve" OR "stock market" OR inflation OR economy',
        'from': yesterday,
        'to': today,
        'language': 'en',
        'sortBy': 'publishedAt',
        'pageSize': 20,
        'apiKey': api_key
    }

    response = requests.get(url, params=params)
    data = response.json()

    if data.get('status') != 'ok':
        print(f"NewsAPI 오류: {data}")
        return []

    return data.get('articles', [])


def summarize_news(articles):
    client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

    articles_text = ""
    for i, article in enumerate(articles[:15], 1):
        articles_text += f"{i}. **{article['title']}**\n"
        if article.get('description'):
            articles_text += f"   {article['description']}\n"
        articles_text += f"   출처: {article['source']['name']}\n\n"

    kst_now = datetime.utcnow() + timedelta(hours=9)
    today_str = kst_now.strftime('%Y년 %m월 %d일')

    prompt = f"""다음은 오늘 Bloomberg과 Wall Street 주요 금융 매체의 최신 뉴스 기사들입니다.

{articles_text}

위 기사들을 바탕으로 한국어로 상세한 마크다운 뉴스 요약을 작성해주세요.

반드시 아래 형식을 따라주세요:

# 📰 Bloomberg & Wall Street 주요 뉴스 요약
**기준일시:** {today_str} 08:30 KST

---

[주요 섹션별 요약 - 최대 5~6개 섹션, 각 섹션은 ## 제목 사용, 핵심 내용 불릿 포인트로 정리]

---

## 핵심 요약

> [전체 내용 1~2문장 요약]

---

## 주요 출처
[기사 제목과 출처 목록]"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text


def main():
    print("뉴스 수집 중...")
    articles = fetch_news()
    print(f"{len(articles)}개 기사 수집 완료")

    if not articles:
        print("수집된 기사가 없습니다. 종료합니다.")
        return

    print("Claude로 요약 중...")
    summary = summarize_news(articles)

    kst_now = datetime.utcnow() + timedelta(hours=9)
    today = kst_now.strftime('%y%m%d')
    filename = f"daily_news/{today}_뉴스요약.md"

    os.makedirs('daily_news', exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(summary)

    print(f"파일 저장 완료: {filename}")


if __name__ == '__main__':
    main()
