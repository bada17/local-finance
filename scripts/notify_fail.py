# 봇 실패 알림 — 워크플로 맨 끝 「알림」 작업이 부른다. 실패가 있으면 텔레그램 한 통, 없으면 조용히.
#
#   NEEDS='{"lofin":{"result":"success","outputs":{"steps":"{...}"}}}' python scripts/notify_fail.py
#
# 왜 — continue-on-error 단계는 실패해도 작업이 「초록」이다. 2026-10 에 R2(CLIK 상세)와 사업자번호가
#      그렇게 며칠씩 멈춰 있었는데 아무도 몰랐다. 그래서 작업 결과(needs.*.result)만이 아니라
#      **단계마다의 outcome**(작업 outputs 의 steps — toJSON(steps))까지 본다.
# ⚠️ steps 문맥에는 **id 가 붙은 단계만** 들어간다. 새 단계를 넣으면 id 를 붙일 것.
# 받는 방 — TELEGRAM_CHAT_ID (워크플로에서 TELEGRAM_ALERT_CHAT_ID 가 있으면 그걸 넘긴다).

import json
import os
import sys
import urllib.request


def 실패들(needs):
    틀림 = []
    for 작업, n in needs.items():
        if n.get('result') in ('failure', 'cancelled'):
            틀림.append(f'{작업} — 작업 {n["result"]}')
        try:
            단계 = json.loads((n.get('outputs') or {}).get('steps') or '{}')
        except ValueError:
            단계 = {}
        for 이름, s in 단계.items():
            if s.get('outcome') == 'failure':
                틀림.append(f'{작업} · {이름} — 실패')
    return 틀림


def main():
    틀림 = 실패들(json.loads(os.environ['NEEDS']))
    if not 틀림:
        print('실패 없음')
        return
    e = os.environ
    주소 = f"{e.get('GITHUB_SERVER_URL')}/{e.get('GITHUB_REPOSITORY')}/actions/runs/{e.get('GITHUB_RUN_ID')}"
    글 = f"⚠️ local-finance 봇 — {e.get('GITHUB_WORKFLOW')}\n" + '\n'.join(틀림) + f'\n{주소}'
    print(글)
    token, chat = e.get('TELEGRAM_TOKEN', '').strip(), e.get('TELEGRAM_CHAT_ID', '').strip()
    if not (token and chat):
        sys.exit('텔레그램 열쇠가 없다 — 알림을 못 보냈다')
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage',
        data=json.dumps({'chat_id': chat, 'text': 글, 'disable_web_page_preview': True}).encode(),
        headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req, timeout=30).read()


if __name__ == '__main__':
    if '--시험' in sys.argv:
        d = {'a': {'result': 'success', 'outputs': {'steps': json.dumps({'x': {'outcome': 'failure'}, 'y': {'outcome': 'success'}})}},
             'b': {'result': 'cancelled', 'outputs': {}}, 'c': {'result': 'skipped'}}
        assert 실패들(d) == ['a · x — 실패', 'b — 작업 cancelled'], 실패들(d)
        print('ok')
    else:
        main()
