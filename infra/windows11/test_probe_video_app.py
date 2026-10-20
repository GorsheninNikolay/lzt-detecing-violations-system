"""Offline checks for receipt durability and unknown paid-submit reconciliation."""
import hashlib
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import probe_video_app as probe


class AcceptanceTests(unittest.TestCase):
    def test_private_receipt_and_timezone_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'receipt.json'
            probe.save(path,{'private':'retained'})
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            self.assertEqual(json.loads(path.read_text()),{'private':'retained'})
        original = {'catalog_work_id':'work','start_at':'2026-10-20T03:00:00+03:00','end_at':'2026-10-21T03:00:00+03:00',
                    'state':'active','stage_key':'excavation','expected_equipment':['excavator'],
                    'allowed_equipment':[],'excluded_equipment':[]}
        stored = {k:v for k,v in original.items() if k not in ('start_at','end_at')}
        stored.update(starts_at='2026-10-20T00:00:00+00:00',ends_at='2026-10-21T00:00:00+00:00')
        probe.assert_plan({'revision_number':1,'entries':[stored]},{'expected_revision':0,'entries':[original]})

    def test_unknown_submit_reuses_key_and_known_job_skips_post(self):
        payload = b'video-result-'*10
        shared = {'keys':[],'unknown':True}
        plan = {'revision_number':1,'revision_id':'plan','entries':[]}
        job = {'state':'succeeded','device':{'actual_device':'cuda:0','weights':[
                    {'id':'apoce','sha256':'a'*64},{'id':'kaggle','sha256':'b'*64}]},
               'context':{'plan_revision_id':'plan'},'media_kind':'video',
               'result':{'processed_frame_count':3,'selected_frames':[{}, {}, {}],
                         'explanation_state':'succeeded','assessment':{'summary':'test'},
                         'video_url':'/api/video-runs/job/media','sha256':hashlib.sha256(payload).hexdigest(),'size':len(payload)}}
        class FakeClient:
            outsider = False
            def __init__(self,*args): pass
            def login(self,credentials):
                self.outsider = credentials['email']=='outsider'
                return 'outsider' if self.outsider else 'owner'
            def json(self,path,method='GET',body=None,**kwargs):
                if path == '/api/health/ready': return {'ready':True}
                if path.startswith('/api/zones/zone/plan'): return plan
                if path.startswith('/api/runs/video?'):
                    shared['keys'].append(kwargs['headers']['Idempotency-Key'])
                    if shared['unknown']:
                        shared['unknown'] = False
                        raise TimeoutError('accepted but response lost')
                    return {'run_id':'job'}
                if path in ('/api/video-runs/job','/api/runs/job'): return job
                raise AssertionError(path)
            def call(self,path,headers=None,allowed=(200,)):
                if self.outsider:
                    assert allowed == (404,)
                    return b'',404,{}
                if headers and headers.get('Range'):
                    return payload[:32],206,{'Content-Range':f'bytes 0-31/{len(payload)}'}
                return payload,200,{}
        metadata = {'streams':[{'codec_type':'video','codec_name':'h264','nb_read_frames':3,'width':160,'height':96},
                                {'codec_type':'audio'}],'format':{'duration':0.6}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clip = root/'source.mp4'
            clip.write_bytes(b'stable-source')
            receipt = {'base':'http://example.test','origin':'http://example.test',
                'credentials':{'email':'owner'},'outsider_credentials':{'email':'outsider'},
                'project_id':'project','zone_id':'zone','plan_body':{'expected_revision':0,'entries':[]},
                'plan_revision_id':'plan','clip_path':str(clip),'clip_sha256':hashlib.sha256(clip.read_bytes()).hexdigest(),
                'result_path':str(root/'result.mp4'),'request_context':{'plan_revision_id':'plan'},
                'video_key':'fixed-key','checks':{}}
            persisted = []
            def persist(): persisted.append(json.loads(json.dumps(receipt)))
            args = SimpleNamespace(timeout=1,expect_device='cuda:0')
            with patch.object(probe,'Client',FakeClient),patch.object(probe,'probe',lambda path:metadata):
                with self.assertRaises(TimeoutError):
                    probe.acceptance(args,receipt,persist)
                self.assertTrue(persisted[-1]['video_submission_started'])
                self.assertEqual(persisted[-1]['video_key'],'fixed-key')
                self.assertNotIn('run_id',receipt)
                probe.acceptance(args,receipt,persist)
                self.assertEqual(receipt['run_id'],'job')
                probe.acceptance(args,receipt,persist)
            self.assertEqual(shared['keys'],['fixed-key','fixed-key'])
            self.assertEqual(receipt['status'],'passed')


if __name__ == '__main__':
    unittest.main()
