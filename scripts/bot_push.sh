#!/bin/sh
# 봇이 받은 것을 올린다 — scripts/bot_push.sh "<커밋 글>" <길>...
#
# ⭐ 봇과 사람은 서로 기다리지 않는다(2026-09-30 사용자 — "내가 뭔가를 하는데, 영향을 받으면 안되는데").
#    봇은 **자기 길(data/ 의 수집물)만** 올리고, 올리기 직전에 main 을 받아 그 위에 얹는다.
#    그사이 사람이나 다른 봇 갈래가 먼저 올려 밀리면 다시 받아 다섯 번까지 해 본다.
#    사람은 봇이 돌든 말든 아무 때나 main 에 올리면 된다.
set -e
msg=$1; shift
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add -- "$@"
if git diff --cached --quiet; then echo '새로 받은 것이 없다'; exit 0; fi
git commit -q -m "$msg"
for n in 1 2 3 4 5; do
  git pull -q --rebase && git push -q && exit 0
  git rebase --abort 2>/dev/null || true   # 같은 파일을 사람이 고쳤으면 여기서 계속 막힌다 — 빨갛게 남는다
  echo "밀렸다 — 다시 받아 얹는다 ($n)"; sleep $((n * 5))
done
exit 1
