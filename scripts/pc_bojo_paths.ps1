# bojo 사업경로 여러 해 수집 — 컴퓨터를 켜고 로그인하면 남은 해를 이어 받는다
# (작업 스케줄러 bojo-paths, 사용자 2026-11-12 「로컬파이낸스 아침마다 돌아가는 봇처럼 컴터 키면 돌리면 되지 않아?」)
# 해마다 data/raw/bojo_paths_<해>.json.gz 가 있으면 끝난 해라 건너뛴다. 없으면 fetch_bojo_paths.py 가 .part.jsonl 에서 이어 받는다.
# 다른 창에서 fetch_bojo_paths 가 이미 돌고 있으면 끝날 때까지 기다린다. 같은 작업이 두 번 뜨지는 않는다(IgnoreNew).
# 차례: 2024 → 2025(어촌신활력 남은 돈 향방) → 2023 → 2022 → 2021 → 2026(진행 중 — 늦게 받을수록 더 차 있다)
# ponytail: 2026 은 중간 자료 — 연말 지나 bojo_paths_2026.json.gz 를 지우면 다음 로그인 때 다시 받는다.
#   등록: powershell -ExecutionPolicy Bypass -File scripts\pc_bojo_paths.ps1 -Register      로그: data\raw\bojo_paths_<해>.log
param([switch]$Register)
$repo = Split-Path -Parent $PSScriptRoot
if ($Register) {
  schtasks /Create /F /TN 'bojo-paths' /SC ONLOGON /TR "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`"" | Out-Null
  $s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 2) -MultipleInstances IgnoreNew
  Set-ScheduledTask -TaskName 'bojo-paths' -Settings $s | Out-Null
  Write-Output 'registered: bojo-paths (at logon)'
  return
}
Set-Location $repo
$running = Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -like '*fetch_bojo_paths.py*' }
if ($running) { Wait-Process -Id $running.ProcessId -ErrorAction SilentlyContinue }
foreach ($y in 2024, 2025, 2023, 2022, 2021, 2026) {
  if (Test-Path "data\raw\bojo_paths_$y.json.gz") { continue }
  python -X utf8 scripts/fetch_bojo_paths.py $y > "data\raw\bojo_paths_$y.log" 2> "data\raw\bojo_paths_$y.err"
}
