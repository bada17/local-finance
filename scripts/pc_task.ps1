# PC 예약 작업 공통 — 창 없이 걸기, 오늘 몫이 끝났나. pc_*.ps1 이 불러 쓴다(. pc_task.ps1).
# 왜 — 윈도우 11 은 「-WindowStyle Hidden」이어도 터미널 창이 뜨고, 그 창이 닫히면 작업이 0xC000013A 로 죽는다
#   (2026-11-17·19·24·25 날마다 수집, 11-25 시험 작업으로 재현). conhost --headless 는 창이 아예 없다.
# ⚠️ 창이 없으면 출력을 받을 데가 없어 bash 가 echo 부터 1 로 끝난다(11-20 에 이것 때문에 실패) — 그래서 cmd 로 모두 파일에 보낸다.
#   파일로 보내면 파이썬이 cp949 로 찍다 죽으므로 PYTHONIOENCODING 도 같이 준다.
# 시험: powershell -ExecutionPolicy Bypass -File scripts\pc_task.ps1 -Test
param([switch]$Test)

function 창없이($이름, $파일, $인자 = '') {
  $안 = "set PYTHONIOENCODING=utf-8&& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $파일 $인자 > %TEMP%\$이름.out.log 2>&1 < NUL"
  Set-ScheduledTask -TaskName $이름 -Action (New-ScheduledTaskAction -Execute 'conhost.exe' -Argument "--headless cmd.exe /d /c `"$안`"") | Out-Null
}

# 「받기」·「부탁」이 든 칸이 모두 0 이거나 true 인가(봇 지킴이와 같은 잣대)
# ⚠️ PowerShell 은 $false -eq 0 도 1 -eq $true 도 참이라 꼴부터 가른다
function 다받았나($기록, $오늘) {
  if (-not $기록 -or $기록.'날' -ne $오늘 -or -not $기록.'끝') { return $false }
  foreach ($칸 in $기록.PSObject.Properties) {
    if ($칸.Name -notmatch '받기|부탁') { continue }
    $됨 = if ($칸.Value -is [bool]) { $칸.Value } else { "$($칸.Value)" -eq '0' }
    if (-not $됨) { return $false }
  }
  return $true
}

if ($Test) {
  $좋음 = '{"날":"2026-11-25","R2 내려받기":true,"받기":0,"R2 올리기 부탁":0,"끝":"10:00"}'
  $경우 = @(
    @($좋음, '2026-11-25', $true), @($좋음, '2026-11-26', $false),
    @($좋음.Replace('true', 'false'), '2026-11-25', $false), @($좋음.Replace('"받기":0', '"받기":1'), '2026-11-25', $false),
    @($좋음.Replace('부탁":0', '부탁":1'), '2026-11-25', $false), @($좋음.Replace(',"끝":"10:00"', ''), '2026-11-25', $false), @('', '2026-11-25', $false))
  foreach ($c in $경우) { if ((다받았나 ($c[0] | ConvertFrom-Json) $c[1]) -ne $c[2]) { throw "틀림: $($c[0]) $($c[1])" } }
  Write-Output 'ok'
}
