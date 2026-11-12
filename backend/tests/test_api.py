"""Contract tests use the supplied files and a fake adapter only inside tests."""
import copy
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.main import app, load_saved, solver_lock
from app.models import OptimizationResult


class APITests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_all_saved_results_preserve_original_payload(self):
        import json
        from app.main import DATA
        for n in (8, 12, 16):
            original = json.loads((DATA / f'result_sector_{n}.json').read_text())
            response = self.client.get(f'/results/sector_{n}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), original)

    def test_saved_totals_match_camera_selection(self):
        for n in (8, 12, 16):
            d = load_saved(f'sector_{n}')
            by_id = {c.id: c for c in d.candidates}
            for name, s in d.solutions.items():
                chosen = [by_id[i] for i in s.selected]
                self.assertAlmostEqual(sum(c.cost for c in chosen), s.cost)
                self.assertAlmostEqual(sum(c.power_w for c in chosen), s.power_w)
                covered = sum(bool(set(z.covered_by) & set(s.selected)) for z in d.zones)
                self.assertAlmostEqual(covered / len(d.zones) * 100, s.coverage_pct, places=1)

    def test_live_requires_real_adapter(self):
        with patch('app.main.get_solver', return_value=None):
            r = self.client.post('/optimize', json={'instance': 'sector_12', 'p': 2, 'lambda': 2})
        self.assertEqual(r.status_code, 503)

    def test_live_forwards_region_and_parameters(self):
        output = load_saved('sector_12').model_dump(mode='json',exclude_unset=True)
        bounds = [-73.988, 40.751, -73.980, 40.756]
        with patch('app.main.get_solver') as get:
            get.return_value.return_value = output
            r = self.client.post('/optimize', json={'instance': 'sector_12', 'p': 3, 'lambda': 4.5, 'bbox': bounds})
            get.return_value.assert_called_once_with(instance='sector_12', bbox=bounds, p=3, lambda_=4.5)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), output)

    def test_legacy_request_uses_saved_bbox(self):
        with patch('app.main.get_solver') as get:
            get.return_value.return_value = load_saved('sector_8').model_dump(mode='json',exclude_unset=True)
            r = self.client.post('/optimize', json={'instance': 'sector_8', 'p': 2, 'lambda': 2})
            self.assertEqual(get.return_value.call_args.kwargs['bbox'], list(load_saved('sector_8').sector.bbox))
        self.assertEqual(r.status_code, 200)

    def test_invalid_requests_rejected(self):
        for payload in [{'instance':'../../etc/passwd'}, {'p':0}, {'p':2.5}, {'lambda':0}, {'bbox':[1,2,0,3]}, {'bbox':[0,0,1,90]}, {'bbox':[1,2,3]}, {'surprise':True}]:
            self.assertEqual(self.client.post('/optimize', json=payload).status_code, 422)
        self.assertEqual(self.client.get('/results/not_an_instance').status_code,422)

    def test_bad_solver_payload_and_pipeline_failure(self):
        with patch('app.main.get_solver') as get:
            get.return_value.return_value = {'broken':True}
            self.assertEqual(self.client.post('/optimize',json={}).status_code,502)
            get.return_value.side_effect = RuntimeError('private server detail')
            response=self.client.post('/optimize',json={})
            self.assertEqual(response.status_code,500)
            self.assertNotIn('private server detail',response.text)
        self.assertFalse(solver_lock.locked())

    def test_busy_solver(self):
        with patch('app.main.get_solver',return_value=lambda **kw: None):
            solver_lock.acquire()
            try:
                self.assertEqual(self.client.post('/optimize',json={}).status_code,429)
            finally:
                solver_lock.release()

    def test_invalid_camera_reference(self):
        d=load_saved('sector_8').model_dump(mode='json',exclude_unset=True)
        bad=copy.deepcopy(d);bad['solutions']['qaoa']['selected'][0]=999
        with self.assertRaises(ValidationError): OptimizationResult.model_validate(bad)
        bad=copy.deepcopy(d);bad['candidates'][0]['fov_polygon']=[[999,40]]*3
        with self.assertRaises(ValidationError): OptimizationResult.model_validate(bad)

    def test_health_and_cors(self):
        self.assertEqual(self.client.get('/health').status_code,200)
        r=self.client.options('/optimize',headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.headers['access-control-allow-origin'],'http://localhost:5173')

if __name__ == '__main__': unittest.main()
