# 누리집 게시판 — 봇(해외 서버)이 못 읽은 곳을 이 PC 에서 메운다. 매달 3일 10시 작업 스케줄러가 부른다.
#   등록: powershell -File scripts\pc_fill_boards.ps1 -등록     손으로: powershell -File scripts\pc_fill_boards.ps1
# 봇(boards.yml, 매달 2일 새벽)이 올린 data/board_posts*.json 을 받아 「못 읽은 것」만 다시 보고 올린다.
# 기록: %TEMP%\local-finance-boards.log
param([switch]$등록)
$repo = Split-Path -Parent $PSScriptRoot
if ($등록) {
  # 매달 3일 10시. 그때 PC 가 꺼져 있었으면 켜질 때 돈다(StartWhenAvailable)
  schtasks /Create /F /TN 'local-finance-boards' /SC MONTHLY /D 3 /ST 10:00 /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" | Out-Null
  $s = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 4)
  Set-ScheduledTask -TaskName 'local-finance-boards' -Settings $s | Out-Null
  Write-Output '등록함 — 작업 스케줄러 local-finance-boards, 매달 3일 10시'
  return
}
Set-Location $repo
Start-Transcript -Path (Join-Path $env:TEMP 'local-finance-boards.log') -Append | Out-Null
git pull --rebase -q
if (Test-Path 'data\board_posts.json') {
  node scripts/fetch_boards.js --실패만
  node scripts/fetch_boards.js --의회 --실패만
  git add data/board_posts.json data/board_posts_council.json
  git diff --cached --quiet
  if ($LASTEXITCODE -ne 0) {
    git commit -q -m "누리집 게시판 — 봇이 못 읽은 곳을 PC 에서 메움 $(Get-Date -Format yyyy-MM-dd)"
    git pull --rebase -q
    git push -q
  }
} else { Write-Output '봇 결과가 아직 없다' }
Stop-Transcript | Out-Null
