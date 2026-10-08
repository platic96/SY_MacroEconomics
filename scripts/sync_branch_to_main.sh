#!/usr/bin/env bash
# claude/* 브랜치에 push 된 daily_news 파일을 main 으로 복사한다.
#   - *_카톡용.txt        : 항상 브랜치 것으로 덮어씀 (06:00 루틴 전담 산출물)
#   - 그 외(뉴스요약·지표): main 에 없을 때만 채움 (06:15 / Actions 가 만든 main 파일을 보호)
# PR 을 거치지 않으므로 병합 충돌이 생기지 않는다.
# 사용법: bash scripts/sync_branch_to_main.sh <브랜치명>
set -euo pipefail
BRANCH="${1:?브랜치명이 필요합니다}"

git fetch -q origin main "$BRANCH"
git checkout -q main
git reset -q --hard origin/main

copied=0
while IFS= read -r -d '' f; do
  # 브랜치에서 삭제된 파일은 건너뜀
  git cat-file -e "origin/$BRANCH:$f" 2>/dev/null || continue
  base="$(basename "$f")"
  if [[ "$base" == *_카톡용.txt ]]; then
    git checkout -q "origin/$BRANCH" -- "$f"; copied=$((copied+1)); echo "복사(덮어쓰기): $f"
  elif ! git cat-file -e "origin/main:$f" 2>/dev/null; then
    git checkout -q "origin/$BRANCH" -- "$f"; copied=$((copied+1)); echo "복사(신규): $f"
  else
    echo "건너뜀(main에 이미 있음): $f"
  fi
done < <(git -c core.quotepath=false diff --name-only -z "origin/main...origin/$BRANCH" -- daily_news)

if git diff --cached --quiet; then
  echo "main 에 반영할 변경 없음"; exit 0
fi

git commit -q -m "sync: $BRANCH → main (daily_news $copied개)"
for i in 1 2 3 4 5; do
  if git push -q origin main; then echo "main push 완료"; exit 0; fi
  echo "push 경합 — 재시도 $i/5"; sleep $((i*3))
  git pull -q --rebase origin main
done
echo "main push 실패" >&2; exit 1
