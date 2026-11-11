# 지방재정365 날마다 수집 — 이 PC 에서 돈다. 작업 스케줄러 local-finance-daily 가 매일 9시에 부른다(꺼져 있었으면 켜질 때).
# 왜 — 2026-11-10 부터 지방재정365 가 깃허브(해외) 서버 접속을 막는다(응답 없음, 이 PC 에선 0.2초). 사용자 11-11 「우리 pc에서 돌리고」.
#   daily.yml 의 lofin·review 갈래를 그대로 옮겼다(그쪽은 if: false). 계약 원본은 R2 에 있는데 이 PC 키는 읽기 전용이라
#   바뀐 파일을 임시 릴리스 contracts-pc 에 <날>.tar.gz 로 붙이고 r2-move.yml 을 부른다(봇이 올리고 견주고 지운다).
#   결과는 data/pc_daily.json 에 남기고 올린다 — 봇 지킴이가 오후 2시에 보고 없거나 실패면 텔레그램(이 PC 엔 텔레그램 키가 없다).
#   등록: powershell -File scripts\pc_daily_lofin.ps1 -등록     손으로: powershell -File scripts\pc_daily_lofin.ps1
# 기록: %TEMP%\local-finance-daily.log
param([switch]$등록)
$repo = Split-Path -Parent $PSScriptRoot
if ($등록) {
  schtasks /Create /F /TN 'local-finance-daily' /SC DAILY /ST 09:00 /TR "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`"" | Out-Null
  # 전원과 상관없이 돈다(2026-11-04 사용자 — 게시판 작업과 같게)
  $s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 4)
  Set-ScheduledTask -TaskName 'local-finance-daily' -Settings $s | Out-Null
  Write-Output '등록함 — 작업 스케줄러 local-finance-daily, 매일 9시'
  return
}
Set-Location $repo
Start-Transcript -Path (Join-Path $env:TEMP 'local-finance-daily.log') -Append | Out-Null
$env:PYTHONIOENCODING = 'utf-8'
$sh = Join-Path $env:ProgramFiles 'Git\bin\bash.exe'
$결과 = [ordered]@{ '날' = (Get-Date -Format 'yyyy-MM-dd'); '시작' = (Get-Date -Format 'HH:mm') }
function 돌려($이름, [scriptblock]$일) { & $일; $결과[$이름] = $LASTEXITCODE; Write-Output "▶ $이름 → $LASTEXITCODE" }

git -c rebase.autoStash=true pull --rebase -q
# ⚠️ 내려받기가 안 되면 받지 않는다 — 「받은 것이 없다」로 보고 처음부터 다시 받아 하루 한도를 날린다
& $sh scripts/r2_sync.sh down data/contracts 최근계약
$결과['R2 내려받기'] = ($LASTEXITCODE -eq 0) -and (@(Get-ChildItem data/contracts -File).Count -gt 1000)
$표 = Get-Date
if ($결과['R2 내려받기']) {
  돌려 '받기' { python scripts/collect_daily.py }
  돌려 '이어 받기' { python scripts/backfill_contracts.py --limit 30 }
  돌려 '다시 받기' { python -u scripts/refresh_contracts.py --분 60 }
}
돌려 '투자심사' { python scripts/fetch_review.py }

$바뀐 = @(Get-ChildItem data/contracts -File | Where-Object { $_.LastWriteTime -gt $표 })
$결과['바뀐 계약 원본'] = $바뀐.Count
if ($바뀐.Count) {
  $tar = Join-Path $env:TEMP "$(Get-Date -Format yyyyMMdd).tar.gz"
  tar -czf $tar -C data/contracts @($바뀐.Name)
  gh release view contracts-pc 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { gh release upload contracts-pc $tar --clobber }   # 전날 것이 아직 안 옮겨졌으면 같이 간다
  else { gh release create contracts-pc $tar --draft --title 'R2 로 옮길 것(잠깐)' --notes '봇(r2-move)이 옮기고 지운다' }
  gh workflow run r2-move.yml --ref main
  $결과['R2 올리기 부탁'] = $LASTEXITCODE
}
$결과['끝'] = (Get-Date -Format 'HH:mm')
[IO.File]::WriteAllText((Join-Path $repo 'data\pc_daily.json'), ($결과 | ConvertTo-Json), (New-Object Text.UTF8Encoding $false))
& $sh scripts/bot_push.sh "날마다 수집(PC) · 지방재정365 $($결과['날'])" data/contracts_late data/spending data/review.json site/review data/pc_daily.json
Stop-Transcript | Out-Null
