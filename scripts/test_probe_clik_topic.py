import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from probe_clik_topic import BudgetClient, extract_mentions, check_output, sample_rows


class TopicTest(unittest.TestCase):
    def test_speaker_context_and_spacing(self):
        html='<p>○위원장 홍길동</p><p>다음 안건입니다.</p><p>○관광과장 김가람</p><p>여수 세계 섬 박람회 준비 예산을 설명드립니다.</p><script>여수세계섬박람회</script>'
        mentions=extract_mentions(html,'여수세계섬박람회')
        self.assertEqual(len(mentions),1)
        self.assertEqual(mentions[0]['발언자표기'],'관광과장 김가람')
        self.assertIn('준비 예산',mentions[0]['문맥'])

    def test_no_speaker_is_not_invented(self):
        self.assertEqual(extract_mentions('<p>여수세계섬박람회</p>','여수세계섬박람회')[0]['발언자표기'],'미확인')
        self.assertEqual(extract_mentions('<p>다른 박람회</p>','여수세계섬박람회'),[])

    def test_failed_network_attempt_still_charged(self):
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder)/'state.json';state.write_text('{"갈래":{"보존":1},"날짜별호출":{}}',encoding='utf-8')
            client=BudgetClient('secret',state,limit=1,reserve=0)
            with patch('probe_clik_topic.urllib.request.urlopen',side_effect=TimeoutError):
                with self.assertRaises(RuntimeError):client.call({'displayType':'list'})
            d=json.loads(state.read_text(encoding='utf-8'))
            self.assertEqual(sum(d['날짜별호출'].values()),1)
            self.assertEqual(d['갈래'],{'보존':1})
            with self.assertRaises(RuntimeError):client.call({'displayType':'list'})
            self.assertEqual(sum(json.loads(state.read_text(encoding='utf-8'))['날짜별호출'].values()),1)

    def test_reserve_stops_before_api(self):
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder)/'state.json'
            client=BudgetClient('secret',state,limit=10,reserve=20)
            state.write_text(json.dumps({'날짜별호출':{client.today():980}}),encoding='utf-8')
            with patch('probe_clik_topic.urllib.request.urlopen') as call:
                with self.assertRaises(RuntimeError):client.call({})
                call.assert_not_called()

    def test_output_never_inside_repo(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'repo';root.mkdir()
            with self.assertRaises(ValueError):check_output(root/'hidden',root)
            self.assertEqual(check_output(Path(folder)/'private',root),Path(folder)/'private')

    def test_sample_spreads_across_councils_and_years(self):
        rows=[{'DOCID':f'C{i}','RASMBLY_ID':str(i%3),'MTG_DE':str(2020+i%2)+'0101'} for i in range(20)]
        sample=sample_rows(rows,6)
        self.assertEqual(len({(r['RASMBLY_ID'],r['MTG_DE'][:4]) for r in sample}),6)


if __name__=='__main__':unittest.main()
