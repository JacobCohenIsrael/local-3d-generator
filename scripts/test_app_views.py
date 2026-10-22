"""Hybrid photo selection contract; no model weights loaded."""
import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw, ImageFilter
from app_images import prepare_job, finalize_job
from app_views import (MAX_CANDIDATES, HYBRID_STRATEGY, candidates_for, conditioned_views,
                       image_metrics, select_candidates, select_hybrid, validate_assessment)
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
    return {'name': 'Hybrid test', 'views': {'front': encoded(80, True), 'left': encoded(100),
        'back': encoded(120), 'right': encoded(140)}, 'settings': {'background': 'keep'},
        'extra_views': [{'image': encoded(160), 'name': 'Sharper front'},
                        {'image': encoded(180), 'name': 'Uncertain view'}]}


def observation(direction='front', **kwargs):
    return dict({'direction': direction, 'confidence': .97, 'same_subject': True,
                 'pose_consistent': True, 'usable': True, 'reason': 'Compatible straight-on view'}, **kwargs)


def item(name, quality=.7, **kwargs):
    return dict({'id': name, 'name': name, 'original_sha256': name, 'metrics': {'quality_score': quality}}, **kwargs)


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.root = Path(self.temp.name)
        self.app = Workshop(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_more_than_four_preserved_no_angles_and_provenance_matches(self):
        folder = self.app.jobs / self.app.create(request())
        job = json.loads((folder / 'job.json').read_text())
        self.assertEqual(job['view_strategy'], HYBRID_STRATEGY)
        self.assertTrue(all('azimuth' not in c for c in job['candidates']))
        self.assertEqual(len(list((folder / 'uploads').glob('*.image'))), 6)
        self.assertIsNone(prepare_job(folder))
        with self.assertRaisesRegex(ValueError, 'selection manifest'):
            conditioned_views(folder, job)
        records = json.loads((folder / 'prepared-records.json').read_text())
        selection = finalize_job(folder, records, select_hybrid(records, {
            'extra-01': observation(), 'extra-02': observation('unknown', confidence=.3)}))
        self.assertEqual(selection['selected_count'], 4)
        self.assertFalse(selection['all_uploads_conditioned'])
        self.assertFalse(selection['extra_view_fusion'])
        self.assertEqual(selection['selected']['front'], 'extra-01')
        self.assertIn('uncertain viewpoint', selection['candidates'][-1]['reason'])
        provenance = json.loads((folder / 'prepared/provenance.json').read_text())
        self.assertEqual(provenance['views']['front']['candidate_id'], 'extra-01')
        self.assertEqual(hashlib.sha256((folder / 'prepared/front.png').read_bytes()).hexdigest(),
                         provenance['views']['front']['sha256'])
        self.assertEqual(conditioned_views(folder, job), ['front', 'left', 'back', 'right'])
        self.assertEqual(self.app.list()[0]['selection']['submitted_count'], 6)

    def test_front_required_optional_anchors_do_not_need_vision(self):
        for views in ({'front': encoded()}, {'front': encoded(), 'back': encoded(140)}):
            folder = self.app.jobs / self.app.create({'views': views, 'settings': {'background': 'keep'}})
            selection = prepare_job(folder)
            self.assertEqual(set(selection['selected']), set(views))
            self.assertFalse(selection['vision']['used'])
        with self.assertRaisesRegex(ValueError, 'front'):
            validate_request({'views': {'left': encoded()}})

    def test_sixteen_accepted_seventeenth_rejected(self):
        data = request()
        data['extra_views'] *= 6
        self.assertEqual(len(validate_request(data)[3]), MAX_CANDIDATES)
        data['extra_views'].append({'image': encoded()})
        with self.assertRaisesRegex(ValueError, '16'):
            validate_request(data)

    def test_angles_and_invalid_metadata_rejected(self):
        for value in (0, 90, None):
            data = request()
            data['extra_views'][0]['azimuth'] = value
            with self.assertRaisesRegex(ValueError, 'omit azimuth'):
                validate_request(data)
        for extra in (None, {}, [None], [{'image': encoded(), 'name': 'x' * 81}]):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validate_request(dict(request(), extra_views=extra))
        with self.assertRaisesRegex(ValueError, 'not all-angle fusion'):
            validate_request(dict(request(), view_strategy='fuse_all'))

    def test_combined_bytes_bounded(self):
        with patch('web_app.MAX_TOTAL_BYTES', 20), self.assertRaisesRegex(ValueError, '48 MB'):
            validate_request(request())

    def test_compatible_extra_fills_missing_view_but_anchor_stays(self):
        selection = select_hybrid([item('front'), item('extra-01'), item('extra-02', .75)],
            {'extra-01': observation('back'), 'extra-02': observation('front')})
        self.assertEqual(selection['selected'], {'front': 'front', 'back': 'extra-01'})
        self.assertIn('trusted anchor', selection['candidates'][2]['reason'])

    def test_ambiguity_unsupported_subject_pose_obstruction_skipped(self):
        for changed in ({'direction': 'unknown'}, {'direction': 'unsupported'}, {'confidence': .6},
                        {'same_subject': False}, {'pose_consistent': False}, {'usable': False}):
            with self.subTest(changed=changed):
                assessment = observation('back')
                assessment.update(changed)
                selection = select_hybrid([item('front'), item('extra-01')], {'extra-01': assessment})
                self.assertEqual(selection['selected'], {'front': 'front'})
                self.assertTrue(selection['candidates'][1]['reason'])

    def test_strict_response_validation_and_missing_observations_skip(self):
        for data in (None, {}, observation(confidence=True), observation(confidence=float('nan')),
                     observation(usable='true'), observation('top'), observation(reason='x'*301),
                     dict(observation(), command='run something')):
            with self.subTest(data=data), self.assertRaises(ValueError):
                validate_assessment(data)
        self.assertEqual(select_hybrid([item('front'), item('extra-01')])['selected'], {'front': 'front'})

    def test_duplicate_cannot_establish_another_direction(self):
        selection = select_hybrid([item('front'), item('extra-01', original_sha256='front')],
            {'extra-01': observation('back')})
        self.assertEqual(selection['selected_count'], 1)
        self.assertIn('Duplicate', selection['candidates'][1]['reason'])

    def test_replacement_requires_confidence_and_clear_quality_gain(self):
        for confidence, quality, expected in ((.94, .95, 'front'), (.99, .6, 'front'), (.99, .95, 'extra-01')):
            with self.subTest(confidence=confidence, quality=quality):
                selection = select_hybrid([item('front', .5), item('extra-01', quality)],
                    {'extra-01': observation(confidence=confidence)})
                self.assertEqual(selection['selected']['front'], expected)

    def test_blurred_alternate_scores_lower(self):
        self.assertGreater(image_metrics(Image.open(io.BytesIO(picture())))['quality_score'],
                           image_metrics(Image.open(io.BytesIO(picture(blur=True))))['quality_score'])

    def test_legacy_format_and_manifest_supported(self):
        legacy = {'views': ['front', 'left']}
        self.assertEqual(conditioned_views(self.root, legacy), ['front', 'left'])
        self.assertEqual(len(candidates_for(legacy)), 2)
        (self.root / 'view-selection.json').write_text(json.dumps(select_candidates([
            item('front', azimuth=0), item('left', azimuth=90)])))
        self.assertEqual(conditioned_views(self.root, legacy), ['front', 'left'])

    def test_unusable_required_front_fails_with_audit(self):
        stream = io.BytesIO()
        Image.new('RGBA', (128, 128), (0, 0, 0, 0)).save(stream, format='PNG')
        data = request()
        data['views']['front'] = base64.b64encode(stream.getvalue()).decode()
        folder = self.app.jobs / self.app.create(data)
        with self.assertRaisesRegex(ValueError, 'No usable front'):
            prepare_job(folder)
        self.assertTrue((folder / 'view-selection.json').exists())


if __name__ == '__main__':
    unittest.main()
