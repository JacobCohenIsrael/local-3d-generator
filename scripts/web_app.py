"""Loopback-only local 3D workshop. Standard-library HTTP, SQLite durable queue."""
import argparse
import base64
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import threading
import time
from urllib.parse import urlparse
import uuid

from PIL import Image
from filelock import FileLock
from native_process import OwnedProcess
from runtime_paths import project_python, asset_root

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ('front', 'left', 'back', 'right')
MAX_FILE = 12 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000
ASSETS = {'fbx': ('asset/asset.fbx', 'application/octet-stream'),
          'glb': ('asset/asset.glb', 'model/gltf-binary'),
          'blend': ('asset/asset.blend', 'application/octet-stream'),
          'preview': ('asset/preview.png', 'image/png'),
          'package': ('asset/unity-package.zip', 'application/zip'),
          'report': ('report.json', 'application/json'),
          'color': ('asset/textures/basecolor.png','image/png'),
          'coverage': ('asset/textures/coverage.png','image/png'),
          'material': ('asset/material-manifest.json','application/json')}


def validate_request(data):
    if not isinstance(data, dict):
        raise ValueError('Expected a job object')
    name = data.get('name', 'Untitled model')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValueError('Use a model name between 1 and 100 characters')
    settings = data.get('settings', {})
    if not isinstance(settings, dict):
        raise ValueError('Invalid settings')
    settings = {'quality': settings.get('quality', 'balanced'), 'background': settings.get('background', 'object'),
        'planner': settings.get('planner', 'preset'), 'max_attempts': settings.get('max_attempts', 2),
        'triangles': settings.get('triangles', 50000), 'height': settings.get('height', 1.8),
        'allow_flat': settings.get('allow_flat', False),
        'texture': settings.get('texture','none'), 'texture_size':settings.get('texture_size',1024)}
    for key, values in {'quality': ('balanced', 'detailed'), 'background': ('object', 'person', 'keep'),
                        'planner': ('preset', 'strata'), 'texture':('none','photo_basecolor')}.items():
        if settings[key] not in values:
            raise ValueError(f'Invalid {key}')
    if type(settings['texture_size']) is not int or settings['texture_size'] not in (512,1024):
        raise ValueError('Invalid texture size')
    for key, low, high in (('max_attempts', 1, 2), ('triangles', 5000, 200000)):
        if type(settings[key]) is not int or not low <= settings[key] <= high:
            raise ValueError(f'Invalid {key}')
    if type(settings['height']) not in (int, float) or not .1 <= settings['height'] <= 20:
        raise ValueError('Height must be between 0.1 and 20 meters')
    if type(settings['allow_flat']) is not bool:
        raise ValueError('Invalid flat-object option')
    supplied = data.get('views')
    if not isinstance(supplied, dict) or not supplied or set(supplied) - set(VIEWS) or 'front' not in supplied:
        raise ValueError('Upload a front view; use only front, left, back and right labels')
    views = {}
    for name_key, encoded in supplied.items():
        if not isinstance(encoded, str) or len(encoded) > MAX_FILE * 4 // 3 + 4:
            raise ValueError('Each image must be smaller than 12 MB')
        content = base64.b64decode(encoded, validate=True)
        if not content or len(content) > MAX_FILE:
            raise ValueError('Each image must be smaller than 12 MB')
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in ('JPEG', 'PNG', 'WEBP') or min(image.size) < 64 or image.width * image.height > 20_000_000:
                raise ValueError('Use JPEG, PNG or WebP images, at least 64 pixels wide and tall, under 20 megapixels')
            image.verify()
        views[name_key] = content
    return name.strip(), settings, views


class Workshop:
    def __init__(self, root=ROOT):
        self.root = root
        self.jobs = root / 'outputs/web-jobs'
        self.jobs.mkdir(parents=True, exist_ok=True)
        self.db_path = root / 'work/web-jobs.sqlite3'
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(32)
        self.stop = threading.Event()
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, name TEXT, state TEXT, created REAL, error TEXT)')
            db.execute("UPDATE jobs SET state='interrupted', error='App stopped during generation. Submit a new job to try again.' WHERE state='running'")

    def db(self):
        return sqlite3.connect(self.db_path, timeout=15)

    def create(self, data):
        name, settings, views = validate_request(data)
        with self.db() as db:
            if db.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0] >= 10:
                raise ValueError('Queue is full (10 jobs). Wait for a job to finish.')
        job_id = uuid.uuid4().hex
        folder = self.jobs / job_id
        (folder / 'uploads').mkdir(parents=True)
        for view, content in views.items():
            (folder / 'uploads' / f'{view}.image').write_bytes(content)
        created = time.time()
        job = {'id': job_id, 'name': name, 'settings': settings, 'views': [v for v in VIEWS if v in views],
               'created_at': created, 'created_utc': datetime.now(timezone.utc).isoformat()}
        (folder / 'job.json').write_text(json.dumps(job, indent=2))
        with self.db() as db:
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,NULL)', (job_id, name, 'queued', created))
        return job_id

    def list(self):
        with self.db() as db:
            records = db.execute('SELECT id,name,state,created,error FROM jobs ORDER BY created DESC LIMIT 100').fetchall()
        result = []
        for job_id, name, state, created, error in records:
            folder = self.jobs / job_id
            item = {'id': job_id, 'name': name, 'state': state, 'created_at': created, 'error': error}
            for filename, key in [('progress.json', 'progress'), ('report.json', 'report'), ('job.json', 'job')]:
                try:
                    item[key] = json.loads((folder / filename).read_text())
                except (FileNotFoundError, json.JSONDecodeError, PermissionError):
                    pass
            item['downloads'] = [key for key, (path, _) in ASSETS.items() if (folder / path).is_file()]
            result.append(item)
        return result

    def cancel(self, job_id):
        with self.db() as db:
            row = db.execute('SELECT state FROM jobs WHERE id=?', (job_id,)).fetchone()
            if not row:
                raise ValueError('Job not found')
            if row[0] == 'queued':
                db.execute("UPDATE jobs SET state='cancelled' WHERE id=?", (job_id,))
            elif row[0] == 'running':
                (self.jobs / job_id / 'CANCEL').touch()

    def worker(self):
        while not self.stop.wait(.5):
            with self.db() as db:
                row = db.execute("SELECT id FROM jobs WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
                if row:
                    # BEGIN IMMEDIATE serializes cancellation against the claim.
                    changed = db.execute("UPDATE jobs SET state='running' WHERE id=? AND state='queued'", row).rowcount
            if not row or not changed:
                continue
            job_id = row[0]
            folder = self.jobs / job_id
            try:
                owned = OwnedProcess([str(project_python(ROOT)), '-B',
                    str(ROOT / 'scripts/app_pipeline.py'), '--job-dir', str(folder)],
                    folder / 'pipeline.log', cwd=str(ROOT))
                try:
                    code = owned.wait(3600, cancel=folder / 'CANCEL')
                finally:
                    owned.close()
                if code:
                    try:
                        message = json.loads((folder / 'progress.json').read_text())['message']
                    except (OSError, ValueError):
                        message = 'Generation stopped unexpectedly; see local pipeline.log'
                    raise RuntimeError(message)
                state, error = 'completed', None
            except BaseException as exc:
                state = 'cancelled' if (folder / 'CANCEL').exists() else 'failed'
                error = str(exc)[-2000:]
            with self.db() as db:
                db.execute('UPDATE jobs SET state=?,error=? WHERE id=?', (state, error, job_id))


def handler(workshop, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def allowed(self):
            return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}')

        def send(self, status, content, content_type='application/json', filename=None):
            if isinstance(content, (dict, list)):
                content = json.dumps(content).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            # Three.js fetches embedded GLB image blobs via ImageBitmapLoader.
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; connect-src 'self' blob:; object-src 'none'; frame-ancestors 'none'")
            if filename:
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            if not self.allowed():
                return self.send(403, {'error': 'Local access only'})
            path = urlparse(self.path).path
            if path == '/api/jobs':
                return self.send(200, workshop.list())
            if path == '/api/health':
                return self.send(200, {'ready': True, 'mode': 'local', 'version': 2,'photo_baking':True,
                    'multiview_ready': (asset_root(ROOT) / 'models/hunyuan3d-2mv/hunyuan3d-dit-v2-mv/model.fp16.safetensors').is_file(),
                    'single_view_ready': (asset_root(ROOT) / 'models/hunyuan3d-2.1/hunyuan3d-dit-v2-1/model.fp16.ckpt').is_file()})
            if path in ('/api/demo/front', '/api/demo/left', '/api/demo/back'):
                demo = asset_root(ROOT) / 'work/vendor/Hunyuan3D-2/assets/example_mv_images/1' / (path.rsplit('/', 1)[1] + '.png')
                if demo.is_file():
                    return self.send(200, demo.read_bytes(), 'image/png')
                return self.send(404, {'error': 'Example images are not installed'})
            match = re.fullmatch(r'/api/jobs/([a-f0-9]{32})/(files|views)/([a-z]+)', path)
            if match:
                job_id, category, key = match.groups()
                folder = workshop.jobs / job_id
                if category == 'files' and key in ASSETS:
                    name, mime = ASSETS[key]
                    file = folder / name
                    if file.is_file():
                        return self.send(200, file.read_bytes(), mime,
                            file.name if key in ('fbx', 'blend', 'package', 'report') else None)
                elif category == 'views' and key in VIEWS:
                    file = folder / 'prepared' / f'{key}.png'
                    if file.is_file():
                        return self.send(200, file.read_bytes(), 'image/png')
                return self.send(404, {'error': 'File not available'})
            relative = 'index.html' if path == '/' else path.lstrip('/')
            file = (ROOT / 'web' / relative).resolve()
            if not file.is_relative_to((ROOT / 'web').resolve()) or not file.is_file():
                return self.send(404, {'error': 'Not found'})
            content = file.read_bytes()
            if relative == 'index.html':
                content = content.replace(b'__APP_TOKEN__', workshop.token.encode())
            return self.send(200, content, mimetypes.guess_type(file)[0] or 'application/octet-stream')

        def do_POST(self):
            if not self.allowed() or self.headers.get('X-Local3D-Token') != workshop.token:
                return self.send(403, {'error': 'Reload this local app before submitting'})
            origin = self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{port}', f'http://localhost:{port}'):
                return self.send(403, {'error': 'Cross-origin request blocked'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 68 * 1024 * 1024:
                    return self.send(413, {'error': 'Upload too large'})
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise ValueError('Expected JSON upload')
                data = json.loads(self.rfile.read(length))
                if self.path == '/api/jobs':
                    return self.send(201, {'id': workshop.create(data)})
                match = re.fullmatch(r'/api/jobs/([a-f0-9]{32})/cancel', self.path)
                if match:
                    workshop.cancel(match[1])
                    return self.send(200, {'ok': True})
                return self.send(404, {'error': 'Not found'})
            except (ValueError, OSError, Image.DecompressionBombError) as error:
                return self.send(400, {'error': str(error)})

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    with FileLock(str(ROOT / 'work/web-app.lock'), timeout=0):
        workshop = Workshop()
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(workshop, args.port))
        server.daemon_threads = True
        server.timeout = 1
        threading.Thread(target=workshop.worker, daemon=True).start()
        print(f'Local 3D Generator: http://127.0.0.1:{args.port}', flush=True)
        try:
            server.serve_forever()
        finally:
            workshop.stop.set()
            server.server_close()


if __name__ == '__main__':
    main()
