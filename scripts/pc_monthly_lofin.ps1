# 지방재정365 달마다 받기 — 이 PC 에서 돈다. 작업 스케줄러 local-finance-monthly 가 매달 1일 9시 30분에 부른다(꺼져 있었으면 켜질 때).
# 왜 — 2026-11-10 부터 지방재정365 가 깃허브(해외) 서버 접속을 막는다(pc_daily_lofin.ps1 과 같은 까닭).
#   monthly.yml 에서 지방재정365 를 부르던 다섯 단계(지표·5년 추이·세입 43종·재료표 12종·진행 중인 사업)를 옮겼다(그쪽은 if: false).
#   받은 것을 올린 뒤 monthly.yml 을 부른다 — 달마다 굽기의 예약은 지웠다(PC 가 받기 전에 구우면 지난달 자료로 굽는다).
#   결과는 data/pc_monthly.json — 봇 지킴이가 1일 오후 2시 뒤로 이번 달 기록이 없거나 실패면 텔레그램.
#   등록: powershell -ExecutionPolicy Bypass -File scripts\pc_monthly_lofin.ps1 -Register     손으로: powershell -File scripts\pc_monthly_lofin.ps1
# 기록: %TEMP%\local-finance-monthly.log
param([switch]$Register)
$repo = Split-Path -Parent $PSScriptRoot
if ($Register) {
  schtasks /Create /F /TN 'local-finance-monthly' /SC MONTHLY /D 1 /ST 09:30 /TR "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`"" | Out-Null
  $s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 4)
  Set-ScheduledTask -TaskName 'local-finance-monthly' -Settings $s | Out-Null
  Write-Output 'registered: local-finance-monthly, day 1 09:30'
  return
}
Set-Location $repo
Start-Transcript -Path (Join-Path $env:TEMP 'local-finance-monthly.log') -Append | Out-Null
$env:PYTHONIOENCODING = 'utf-8'
$sh = Join-Path $env:ProgramFiles 'Git\bin\bash.exe'
# PC 가 꺼져 있다 켜지면 날마다 수집과 같이 뜬다 — 같은 폴더에서 같이 올리면 부딪히니 그쪽이 끝나길 기다린다
while ((Get-ScheduledTask -TaskName 'local-finance-daily' -ErrorAction SilentlyContinue).State -eq 'Running') { Start-Sleep 60 }
$결과 = [ordered]@{ '날' = (Get-Date -Format 'yyyy-MM-dd'); '시작' = (Get-Date -Format 'HH:mm') }
# 파이썬 출력을 PowerShell 로 한 번 거쳐야 기록(Transcript)에 남는다
function 돌려($이름, [scriptblock]$일) { & $일 2>&1 | ForEach-Object { "$_" } | Out-Host; $결과[$이름] = $LASTEXITCODE; Write-Output "▶ $이름 → $LASTEXITCODE" }

git -c rebase.autoStash=true pull --rebase -q
Set-Location (Join-Path $repo 'scripts')   # monthly.yml 과 같게 scripts 안에서 돈다
돌려 '지표 받기' { python fetch_indicators.py }
돌려 '5년 추이 받기' { python fetch_series.py }
돌려 '세입 43종 받기' { python fetch_revenue.py }
돌려 '재료표 12종 받기' { python fetch_items.py }
돌려 '진행 중인 사업 받기' { python build_ongoing.py --all }
Set-Location $repo
$결과['끝'] = (Get-Date -Format 'HH:mm')
[IO.File]::WriteAllText((Join-Path $repo 'data\pc_monthly.json'), ($결과 | ConvertTo-Json), (New-Object Text.UTF8Encoding $false))
& $sh scripts/bot_push.sh "달마다 받기(PC) · 지방재정365 $($결과['날'])" data/indicators data/series.json data/revenue data/items site/data/ongoing data/pc_monthly.json
$결과['올리기'] = $LASTEXITCODE
# 받기가 일부 실패해도 굽는다 — 실패한 것은 지난달 자료가 그대로 쓰인다(전과 같다)
gh workflow run monthly.yml --ref main
Write-Output "▶ 달마다 굽기 부름 → $LASTEXITCODE"
Stop-Transcript | Out-Null
