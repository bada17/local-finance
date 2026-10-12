#!/bin/sh
# Cloudflare R2 와 폴더를 맞춘다 — scripts/r2_sync.sh down|up <로컬폴더> <R2접두어>
#
#   sh scripts/r2_sync.sh down data/clik/상세 clik/상세    R2 → 로컬 (받기 전에, 받은 것을 알려고)
#   sh scripts/r2_sync.sh up   data/clik/상세 clik/상세    로컬 → R2 (받은 뒤에, 새 파일만 올라간다)
#
# 왜 — 저장소가 붓지 않게 큰 원자료는 R2 에 둔다(2026-10-01 사용자 — 시민행동 계정 action@ 의 R2,
#      버킷 local-finance-raw). 저장소에는 .gitignore 로 안 올린다.
# 키 — 깃허브 Secrets R2_ACCOUNT_ID · R2_ACCESS_KEY_ID · R2_SECRET_ACCESS_KEY · R2_BUCKET.
#      **로컬에는 키를 두지 않는다** — 그래서 이건 봇(액션)에서만 돈다. 액션 우분투에는 aws CLI 가 깔려 있다.
# ⚠️ 키가 하나라도 없으면 **실패로 끝낸다.** 조용히 넘어가면 수집기가 「받은 것이 없다」고 보고
#    처음부터 다시 받아 하루 한도를 날린다. 그래서 워크플로는 down 이 성공했을 때만 수집기를 돌린다.
set -e
dir=$1; src=$2; dst=$3
for v in R2_ACCOUNT_ID R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_BUCKET; do
  eval "x=\${$v:-}"; [ -n "$x" ] || { echo "Secret $v 가 없다"; exit 1; }
done
export AWS_ACCESS_KEY_ID=$R2_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY=$R2_SECRET_ACCESS_KEY AWS_DEFAULT_REGION=auto
# 새 aws CLI 는 R2 가 안 받는 체크섬 머리를 붙인다 — 필요할 때만 붙이게
export AWS_REQUEST_CHECKSUM_CALCULATION=when_required AWS_RESPONSE_CHECKSUM_VALIDATION=when_required
ep="https://$R2_ACCOUNT_ID.r2.cloudflarestorage.com"
mkdir -p "$src"
case $dir in
  down) aws s3 sync "s3://$R2_BUCKET/$dst" "$src" --endpoint-url "$ep" --only-show-errors ;;
  up)   aws s3 sync "$src" "s3://$R2_BUCKET/$dst" --endpoint-url "$ep" --only-show-errors ;;
  *) echo "down 또는 up"; exit 1 ;;
esac
echo "R2 $dir — $src ($(ls "$src" | wc -l)개 파일)"
