"""CPU-only checks for extra-photo validation, selection and model inputs."""
import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw, ImageFilter
from app_images import prepare_job
from app_views import MAX_CANDIDATES, candidates_for, conditioned_views, image_metrics, select_candidates
from web_app import Workshop, validate_request

ROOT = Path(__file__).resolve().parents[1]


def picture(tint=100, blur=False):
    image = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 20, 220, 240), fill=(tint, 110, 160, 255))
    for x in range(40, 210, 8):
        draw.line((x, 30, x, 230), fill=(245, 180, 70, 255), width=3)
    if blur:
        image = image.filter(ImageFilter.GaussianBlur(4))
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return stream.getvalue()


def encoded(tint=100, blur=False):
    return base64.b64encode(picture(tint, blur)).decode()


def request():
    return {'name': 'Extra view test', 'views': {'front': encoded(80, True), 'left': encoded(100),
        'back': encoded(120), 'right': encoded(140)}, 'settings': {'background': 'keep'},
        'extra_views': [{'image': encoded(160), 'azimuth': 0, 'name': 'Sharper front'},
                        {'image': encoded(180), 'azimuth': 45, 'name': 'Diagonal'}]}


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.root = Path(self.temp.name)
        self.app = Workshop(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_more_than_four_preserved_and_selection_matches_provenance(self):
        job_id = self.app.create(request())
        folder = self.app.jobs / job_id
        job = json.loads((folder / 'job.json').read_text())
        self.assertEqual(len(job['candidates']), 6)
        self.assertEqual(len(list((folder / 'uploads').glob('*.image'))), 6)
        selection = prepare_job(folder)
        self.assertEqual(selection['submitted_count'], 6)
        self.assertEqual(selection['selected_count'], 4)
        self.assertFalse(selection['all_uploads_conditioned'])
        self.assertFalse(selection['extra_view_fusion'])
        self.assertEqual(selection['selected']['front'], 'extra-01')
        diagonal = next(c for c in selection['candidates'] if c['id'] == 'extra-02')
        self.assertEqual(diagonal['status'], 'not_selected')
        self.assertIn('selection window', diagonal['reason'])
        provenance = json.loads((folder / 'prepared/provenance.json').read_text())
        self.assertEqual(provenance['views']['front']['candidate_id'], 'extra-01')
        self.assertEqual(hashlib.sha256((folder / 'prepared/front.png').read_bytes()).hexdigest(),
                         provenance['views']['front']['sha256'])
        self.assertEqual(conditioned_views(folder, job), ['front', 'left', 'back', 'right'])
        self.assertEqual(self.app.list()[0]['selection']['submitted_count'], 6)

    def test_sixteen_accepted_seventeenth_rejected(self):
        data = request()
        data['extra_views'] = data['extra_views'] * 6
        self.assertEqual(len(validate_request(data)[3]), MAX_CANDIDATES)
        data['extra_views'].append({'image': encoded(), 'azimuth': 0})
        with self.assertRaisesRegex(ValueError, '16'):
            validate_request(data)

    def test_invalid_metadata_and_all_angle_fusion_rejected(self):
        for angle in (float('nan'), float('inf'), True, -1, 360, '90', None):
            data = request()
            data['extra_views'][0]['azimuth'] = angle
            with self.subTest(angle=angle), self.assertRaises(ValueError):
                validate_request(data)
        for extra in (None, {}, [None], [{'image': encoded(), 'azimuth': 0, 'name': 'x' * 81}]):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validate_request(dict(request(), extra_views=extra))
        with self.assertRaisesRegex(ValueError, 'not all-angle fusion'):
            validate_request(dict(request(), view_strategy='fuse_all'))

    def test_combined_bytes_bounded(self):
        from unittest.mock import patch
        with patch('web_app.MAX_TOTAL_BYTES', 20), self.assertRaisesRegex(ValueError, '48 MB'):
            validate_request(request())

    def test_duplicate_image_not_counted_as_another_direction(self):
        items = [{'id': name, 'name': name, 'azimuth': angle, 'original_sha256': 'same',
                  'metrics': {'quality_score': 1}} for name, angle in [('front', 0), ('left', 90)]]
        selection = select_candidates(items)
        self.assertEqual(selection['selected_count'], 1)
        self.assertIn('Duplicate', selection['candidates'][1]['reason'])

    def test_angle_wraparound_and_determinism(self):
        item = {'id': 'extra-01', 'name': 'Near front', 'azimuth': 355,
                'original_sha256': 'unique', 'metrics': {'quality_score': .9}}
        first = select_candidates([item])
        self.assertEqual(first, select_candidates([item]))
        self.assertEqual(first['selected'], {'front': 'extra-01'})
        self.assertEqual(first['candidates'][0]['angular_error_degrees'], 5)

    def test_blurred_alternate_scores_lower(self):
        sharp = image_metrics(Image.open(io.BytesIO(picture())))
        blurry = image_metrics(Image.open(io.BytesIO(picture(blur=True))))
        self.assertGreater(sharp['quality_score'], blurry['quality_score'])

    def test_original_format_still_supported_missing_new_manifest_fails_closed(self):
        legacy = {'views': ['front', 'left']}
        self.assertEqual(conditioned_views(self.root, legacy), ['front', 'left'])
        self.assertEqual(len(candidates_for(legacy)), 2)
        with self.assertRaisesRegex(ValueError, 'selection manifest'):
            conditioned_views(self.root, {'views': ['front'], 'candidates': [{'id': 'front'}]})

    def test_unusable_front_can_be_replaced_and_all_empty_fails_with_audit(self):
        stream = io.BytesIO()
        Image.new('RGBA', (128, 128), (0, 0, 0, 0)).save(stream, format='PNG')
        data = request()
        data['views']['front'] = base64.b64encode(stream.getvalue()).decode()
        job_id = self.app.create(data)
        selection = prepare_job(self.app.jobs / job_id)
        self.assertEqual(selection['selected']['front'], 'extra-01')
        front = next(c for c in selection['candidates'] if c['id'] == 'front')
        self.assertIn('foreground', front['reason'])
        data = {'name': 'Empty', 'views': {'front': data['views']['front']}, 'settings': {'background':'keep'}}
        job_id = self.app.create(data)
        folder = self.app.jobs / job_id
        with self.assertRaisesRegex(ValueError, 'No usable front'):
            prepare_job(folder)
        self.assertTrue((folder / 'view-selection.json').exists())


if __name__ == '__main__':
    unittest.main()
