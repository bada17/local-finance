# 공시 점검·투명성 지표 — 이 PC 에서 긁고 굽고 올린다. 3월·10월 10일 10시 작업 스케줄러가 부른다.
# 봇(해외 서버)에서 돌리면 국내 누리집 38곳이 막혀 「안 열림」으로 잘못 적혔다(2026-10-15) — 그래서 봇(disclosure.yml)은 지웠다.
#   등록: powershell -File scripts\pc_disclosure.ps1 -등록     손으로: powershell -File scripts\pc_disclosure.ps1
# 기록: %TEMP%\local-finance-disclosure.log
param([switch]$등록)
$repo = Split-Path -Parent $PSScriptRoot
if ($등록) {
  # 3월·10월 10일 10시. 그때 PC 가 꺼져 있었으면 켜질 때 돈다(StartWhenAvailable)
  schtasks /Create /F /TN 'local-finance-disclosure' /SC MONTHLY /M MAR,OCT /D 10 /ST 10:00 /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" | Out-Null
  $s = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 5)
  Set-ScheduledTask -TaskName 'local-finance-disclosure' -Settings $s | Out-Null
  Write-Output '등록함 — 작업 스케줄러 local-finance-disclosure, 3월·10월 10일 10시'
  return
}
Set-Location $repo
Start-Transcript -Path (Join-Path $env:TEMP 'local-finance-disclosure.log') -Append | Out-Null
git pull --rebase -q
# ⚠️ 크롬 스크립트 셋은 같은 포트(9333)를 쓴다 — 한 단계씩 차례로
python scripts/check_disclosure.py
node scripts/recheck_disclosure.js
node scripts/count_clicks.js
node scripts/check_budget_docs.js
python scripts/build_transparency.py
python scripts/build_score.py
git add data/disclosure.json data/disclosure_dom.json data/disclosure_clicks.json data/disclosure_found.json data/disclosure_history.json data/budget_docs.json data/score.json data/score_api.json site/transparency.html site/score.html
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
  git commit -q -m "공시 점검·투명성 지표 $(Get-Date -Format yyyy-MM) (PC)"
  git pull --rebase -q
  git push -q   # push 로 pages.yml 이 저절로 돈다
}
Stop-Transcript | Out-Null
