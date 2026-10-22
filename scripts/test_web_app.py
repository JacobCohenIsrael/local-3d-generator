"""HTTP boundary and durable queue checks; no inference needed."""
import base64
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

from PIL import Image
from web_app import Workshop, handler, validate_request
from native_process import OwnedProcess


def request_data():
    stream = io.BytesIO()
    Image.new('RGBA', (64, 64), (100, 150, 80, 255)).save(stream, format='PNG')
    return {'name': 'A model', 'views': {'front': base64.b64encode(stream.getvalue()).decode()}}


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'work')
        self.root = Path(self.temporary.name)
        self.app = Workshop(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def test_queue_persists_and_cancel_is_terminal(self):
        job_id = self.app.create(request_data())
        self.assertEqual(Workshop(self.root).list()[0]['state'], 'queued')
        self.app.cancel(job_id)
        self.assertEqual(Workshop(self.root).list()[0]['state'], 'cancelled')

    def test_restart_marks_inflight_interrupted_without_retry(self):
        job_id = self.app.create(request_data())
        with self.app.db() as db:
            db.execute("UPDATE jobs SET state='running' WHERE id=?", (job_id,))
        recovered = Workshop(self.root).list()[0]
        self.assertEqual(recovered['state'], 'interrupted')
        self.assertIn('Submit a new job', recovered['error'])

    def test_running_cancellation_stops_owned_tree(self):
        job_id = self.app.create(request_data())
        created = []
        def launch(command, log, **kwargs):
            process = OwnedProcess([sys.executable, '-B', '-c', 'import time; time.sleep(60)'], log)
            created.append(process)
            return process
        with patch('web_app.OwnedProcess', side_effect=launch):
            worker = threading.Thread(target=self.app.worker)
            worker.start()
            try:
                deadline = time.monotonic() + 8
                while not created and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertTrue(created)
                self.app.cancel(job_id)
                while self.app.list()[0]['state'] == 'running' and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertEqual(self.app.list()[0]['state'], 'cancelled')
                self.assertTrue(created[0].shutdown_confirmed)
            finally:
                self.app.stop.set()
                worker.join(10)

    def test_crash_does_not_trigger_inference_restart(self):
        self.app.create(request_data())
        created = []
        def launch(command, log, **kwargs):
            process = OwnedProcess([sys.executable, '-B', '-c', 'raise SystemExit(2)'], log)
            created.append(process)
            return process
        with patch('web_app.OwnedProcess', side_effect=launch):
            worker = threading.Thread(target=self.app.worker)
            worker.start()
            try:
                deadline = time.monotonic() + 8
                while self.app.list()[0]['state'] not in ('failed', 'completed') and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertEqual(self.app.list()[0]['state'], 'failed')
                self.assertEqual(len(created), 1)
                self.assertTrue(created[0].shutdown_confirmed)
            finally:
                self.app.stop.set()
                worker.join(10)

    def test_rejects_invalid_views_and_settings(self):
        for data in [dict(request_data(), views={'../secret':'x'}),
                     dict(request_data(), views={'left':'x'}),
                     dict(request_data(), views={'front':'not an image'}),
                     dict(request_data(), settings={'height':float('nan')}),
                     dict(request_data(), settings={'max_attempts':100}),
                     dict(request_data(), settings={'triangles':True})]:
            with self.subTest(data=data), self.assertRaises((ValueError, OSError)):
                validate_request(data)

    def test_http_csrf_host_origin_and_file_boundary(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.app, 0))
        port = server.server_address[1]
        server.RequestHandlerClass = handler(self.app, port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{port}'
        def rejected(path, headers, status, body=None):
            with self.assertRaises(HTTPError) as raised:
                urlopen(Request(url+path, data=body, headers=headers))
            self.assertEqual(raised.exception.code, status)
            raised.exception.close()
        try:
            with urlopen(url+'/api/health') as health:
                # Embedded GLB textures use a local blob fetch, not a remote URL.
                self.assertIn("connect-src 'self' blob:",health.headers['Content-Security-Policy'])
            body = json.dumps(request_data()).encode()
            rejected('/api/jobs', {'Content-Type':'application/json'}, 403, body)
            rejected('/api/jobs', {'Content-Type':'application/json','X-Local3D-Token':self.app.token,
                                 'Origin':'https://other.example'}, 403, body)
            rejected('/api/health', {'Host':'evil.example'}, 403)
            rejected('/../AGENT.md', {}, 404)
            response = urlopen(Request(url+'/api/jobs', data=body, headers={
                'Content-Type':'application/json','X-Local3D-Token':self.app.token,'Origin':url}))
            self.assertEqual(response.status, 201)
            response.close()
            from test_app_views import request
            from app_images import prepare_job, finalize_job
            from app_views import select_hybrid
            from test_app_views import observation
            job_id = self.app.create(request())
            folder = self.app.jobs / job_id
            prepare_job(folder)
            records = json.loads((folder / 'prepared-records.json').read_text())
            finalize_job(folder, records, select_hybrid(records, {'extra-01': observation()}))
            with urlopen(url+f'/api/jobs/{job_id}/files/selection') as response:
                self.assertEqual(json.load(response)['submitted_count'],6)
                self.assertIn('attachment',response.headers['Content-Disposition'])
            with urlopen(url+f'/api/jobs/{job_id}/candidates/extra-01') as response:
                self.assertEqual(response.headers['Content-Type'],'image/png')
            for key in ('front', 'extra-01'):
                with urlopen(url+f'/api/jobs/{job_id}/uploads/{key}') as response:
                    self.assertEqual(response.headers['Content-Type'], 'image/png')
                    self.assertEqual(response.read(), (folder / 'uploads' / f'{key}.image').read_bytes())
            # A file alone is insufficient: replay only exposes registered uploads.
            (folder / 'uploads/extra-99.image').write_bytes((folder / 'uploads/front.image').read_bytes())
            rejected(f'/api/jobs/{job_id}/uploads/extra-99', {}, 404)
            rejected(f'/api/jobs/{job_id}/uploads/../../job.json', {}, 404)
            rejected(f'/api/jobs/{job_id}/uploads/front', {'Host':'evil.example'}, 403)
            (folder / 'uploads/extra-01.image').unlink()
            rejected(f'/api/jobs/{job_id}/uploads/extra-01', {}, 404)
            for fmt, mime in [('JPEG', 'image/jpeg'), ('WEBP', 'image/webp')]:
                with self.subTest(format=fmt):
                    image = io.BytesIO()
                    Image.new('RGB', (64, 64), (25, 80, 130)).save(image, format=fmt)
                    data = request_data()
                    data['views']['front'] = base64.b64encode(image.getvalue()).decode()
                    replay_id = self.app.create(data)
                    metadata = self.app.jobs / replay_id / 'job.json'
                    legacy = json.loads(metadata.read_text())
                    del legacy['candidates']
                    metadata.write_text(json.dumps(legacy))
                    with urlopen(url+f'/api/jobs/{replay_id}/uploads/front') as response:
                        self.assertEqual(response.headers['Content-Type'], mime)
                        self.assertEqual(response.read(), image.getvalue())
            rejected(f'/api/jobs/{job_id}/candidates/extra-99',{},404)
            rejected(f'/api/jobs/{job_id}/candidates/../../job.json',{},404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
