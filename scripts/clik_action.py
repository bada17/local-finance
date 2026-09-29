"""Actions에서만 쓰는 표본 호출 예약. 키를 내려받거나 출력하지 않는다."""
import base64
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.parse

from probe_clik_topic import BudgetClient, ROOT, check_output


def reserve(state, day, run_id, calls=40, cushion=20):
    result = copy.deepcopy(state)
    records = result.setdefault('내부표본호출', {})
    used = result.setdefault('날짜별호출', {}).get(day, 0)
    if run_id in records or used + calls > 1000 - cushion:
        raise ValueError('이미 실행한 작업이거나 호출 예비 몫이 부족합니다.')
    result['날짜별호출'][day] = used + calls
    records[run_id] = {'날짜': day, '예약': calls, '시작장부': used, '상태': '예약'}
    return result


def settle(state, run_id, used):
    result = copy.deepcopy(state)
    record = result.get('내부표본호출', {}).get(run_id)
    if not record or record['상태'] != '예약' or not 0 <= used <= record['예약']:
        raise ValueError('예약을 확인할 수 없어 장부에서 차감하지 않습니다.')
    day = record['날짜']
    if result['날짜별호출'].get(day, 0) < record['시작장부'] + record['예약']:
        raise ValueError('장부가 이전으로 돌아가 있어 차감하지 않습니다.')
    result['날짜별호출'][day] -= record['예약'] - used
    record.update({'실호출': used, '상태': '정산'})
    return result


def github(args, payload=None):
    process = subprocess.run(['gh', 'api', *args],
                             input=json.dumps(payload) if payload is not None else None,
                             capture_output=True, text=True)
    if process.returncode:
        raise RuntimeError('GitHub 장부 요청 실패; 응답 내용은 출력하지 않습니다.')
    return json.loads(process.stdout)


def read_remote(endpoint):
    obj = github([endpoint + '?ref=main'])
    return json.loads(base64.b64decode(obj['content'])), obj['sha']


def write_remote(endpoint, state, sha, message):
    content = base64.b64encode(json.dumps(state, ensure_ascii=False, indent=1).encode()).decode()
    github(['--method', 'PUT', endpoint, '--input', '-'],
           {'branch': 'main', 'sha': sha, 'message': message, 'content': content})


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true' or not os.environ.get('CLIK_KEY'):
        raise RuntimeError('GitHub Actions의 CLIK_KEY가 필요합니다.')
    out = check_output(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    day, run_id = BudgetClient.today(), os.environ['GITHUB_RUN_ID']
    endpoint = 'repos/' + os.environ['GITHUB_REPOSITORY'] + '/contents/' + urllib.parse.quote('data/clik/상태.json')
    state, sha = read_remote(endpoint)
    reserved = reserve(state, day, run_id)
    write_remote(endpoint, reserved, sha, 'CLIK 내부 표본 호출 40회 예약 ' + run_id)
    # 예약 전 값으로 시작한다. 중단돼도 원격 예약은 남아 초과 호출을 막는다.
    local = ROOT / 'data/clik/상태.json'
    local.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding='utf-8')
    try:
        with (out / 'probe.log').open('w', encoding='utf-8') as log:
            process = subprocess.run([sys.executable, str(ROOT/'scripts/probe_clik_topic.py'),
                                      '--out', str(out), '--limit', '40', '--reserve', '20',
                                      '--sample', '24', '--pages', '6'], stdout=log, stderr=log)
        if process.returncode:
            raise RuntimeError('표본 실행 실패; 암호화된 내부 로그를 확인하세요.')
    finally:
        after = json.loads(local.read_text(encoding='utf-8'))
        # 날짜가 넘어갔으면 자동 환급하지 않는다.
        if BudgetClient.today() == day:
            used = after['날짜별호출'].get(day, 0) - state['날짜별호출'].get(day, 0)
            current, current_sha = read_remote(endpoint)
            final = settle(current, run_id, used)
            write_remote(endpoint, final, current_sha, 'CLIK 내부 표본 호출 정산 ' + run_id)
            (out/'ledger.json').write_text(json.dumps(final, ensure_ascii=False, indent=1), encoding='utf-8')
            print(f'CLIK 표본 호출 {used}회; 장부 정산 완료.')
        # 공급자 응답에 키가 반사돼도 산출물에는 보관하지 않는다.
        key = os.environ['CLIK_KEY']
        for path in out.rglob('*'):
            if path.is_file():
                value = path.read_text(encoding='utf-8')
                path.write_text(value.replace(key, '[REDACTED]'), encoding='utf-8')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit('표본 Actions 실행 중단: ' + type(exc).__name__) from None
