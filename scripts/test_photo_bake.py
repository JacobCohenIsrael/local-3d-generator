"""Photo projection correctness, provenance and unknown-surface behavior."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
from photo_bake import bake
from photo_projection import camera_basis, depth_buffer, triangle_pixels, fit_camera, project, sample_view, extend_surface_colors
from web_app import validate_request
from test_web_app import request_data


class PhotoBakeTests(unittest.TestCase):
    def test_tiny_source_keeps_visible_sloped_surface_but_rejects_hidden_points(self):
        vertices = np.array([[-1,1,-1],[1,-1,-1],[1,-1,1],[-1,1,1]],np.float32)
        faces = np.array([[0,1,2],[0,2,3]])
        points = np.array([[x,-x,0] for x in (.005,.02,-.005,-.02)],np.float32)
        normals = np.tile(np.array([1,-1,0])/np.sqrt(2),(len(points),1))
        camera = {'basis':camera_basis('front',0),'center':[0,0],'scale':16,
            'photo_center':[32,32],'silhouette_iou':1}
        rgba = np.ones((64,64,4),np.float32)
        rgb,weight = sample_view(points,normals,vertices,faces,rgba,camera)
        self.assertTrue((weight>0).all(),'Coarse source-sized depth must not remove a visible sloped surface')
        hidden = points+np.array([0,.15,0])
        _,hidden_weight = sample_view(hidden,normals,vertices,faces,rgba,camera)
        self.assertTrue((hidden_weight==0).all(),'Increasing depth resolution must not paint hidden geometry')
        self.assertTrue(np.allclose(rgb,1))

    def test_elevated_view_can_fit_above_old_twenty_degree_limit(self):
        vertices = np.array([[x,y,z] for z in (-.15,.15) for y in (-1.5,1.5) for x in (-1,1)])
        faces = np.array([[0,1,3],[0,3,2],[4,6,7],[4,7,5],[0,4,5],[0,5,1],
            [2,3,7],[2,7,6],[0,2,6],[0,6,4],[1,5,7],[1,7,3]])
        camera = {'basis':camera_basis('front',40),'center':[0,0],'scale':10,'photo_center':[32,32]}
        alpha = np.isfinite(depth_buffer(project(vertices,camera),faces,64,64)).astype(np.float32)
        fitted = fit_camera(vertices,faces,alpha,'front')
        self.assertGreaterEqual(fitted['elevation'],30)
        self.assertGreater(fitted['silhouette_iou'],.85)

    def test_color_extension_uses_3d_distance_and_preserves_observed_colors(self):
        points = np.array([[0,0,0],[10,0,0],[.1,0,0],[9.9,0,0]])
        colors = np.array([[1,0,0],[0,0,1],[.5,.5,.5],[.5,.5,.5]],np.float32)
        covered = np.array([True,True,False,False])
        extended = extend_surface_colors(points,colors,covered)
        self.assertTrue(np.array_equal(extended[covered],colors[covered]))
        self.assertTrue(np.array_equal(extended[2],colors[0]))
        self.assertTrue(np.array_equal(extended[3],colors[1]))
        self.assertTrue(np.array_equal(covered,[True,True,False,False]))

    def test_selected_extras_supply_bake_views_and_can_replace_front(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root/'work') as directory:
            folder = Path(directory)
            prepared = folder/'prepared'
            prepared.mkdir()
            provenance = {'views':{}}
            for view,candidate,color in [('front','extra-01',(0,255,0,255)),('back','extra-02',(0,0,255,255))]:
                path = prepared/f'{view}.png'
                Image.new('RGBA',(64,64),color).save(path)
                provenance['views'][view] = {'candidate_id':candidate,'original_sha256':candidate+'-original',
                    'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            (prepared/'provenance.json').write_text(json.dumps(provenance))
            # Only front was labelled, but vision replaced it and filled back.
            (folder/'job.json').write_text(json.dumps({'views':['front'],
                'candidates':[{'id':key} for key in ('front','extra-01','extra-02')]}))
            (folder/'view-selection.json').write_text(json.dumps({'strategy':'hybrid_vision_v1',
                'selected':{'front':'extra-01','back':'extra-02'}}))
            vertices = np.array([[-1,0,-1],[1,0,-1],[1,0,1],[-1,0,1]],np.float32)
            faces = np.array([[0,1,2],[0,2,3]]*2)
            uv = np.array([[[.05,.05],[.45,.05],[.45,.95]],[[.05,.05],[.45,.95],[.05,.95]],
                [[.55,.05],[.95,.05],[.95,.95]],[[.55,.05],[.95,.95],[.55,.95]]],np.float32)
            normals = np.array([[[0,-1,0]]*3]*2+[[[0,1,0]]*3]*2,np.float32)
            np.savez(folder/'geometry.npz',vertices=vertices,faces=faces,uv=uv,normals=normals)
            with contextlib.redirect_stdout(io.StringIO()):
                report = bake(folder,folder/'geometry.npz',folder/'texture',64)
            atlas = np.asarray(Image.open(folder/'texture/basecolor.png'))
            self.assertEqual(report['views_used'],['front','back'])
            self.assertEqual(report['views']['front']['candidate_id'],'extra-01')
            self.assertEqual(report['views']['back']['candidate_id'],'extra-02')
            self.assertTrue(np.allclose(atlas[32,16],[0,255,0],atol=2))
            self.assertTrue(np.allclose(atlas[32,48],[0,0,255],atol=2))

    def test_small_silhouette_gain_does_not_tilt_cardinal_camera(self):
        alpha = np.zeros((64,64),np.float32)
        alpha[4:60,12:52] = 1
        level = alpha.copy()
        level[32,32] = 0
        silhouettes = [level,alpha,*[np.zeros_like(alpha)]*5]
        depths = [np.where(mask>0,0,-np.inf) for mask in silhouettes]
        vertices = np.array([[-1,0,-1],[1,0,-1],[1,0,1],[-1,0,1]])
        with patch('photo_projection.depth_buffer',side_effect=depths):
            camera = fit_camera(vertices,np.array([[0,1,2],[0,2,3]]),alpha,'front')
        self.assertEqual(camera['elevation'],0)
        self.assertGreater(camera['silhouette_iou'],.98)

    def test_competing_photos_do_not_blend_into_ghost_colors(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root/'work') as directory:
            folder = Path(directory)
            (folder/'prepared').mkdir()
            provenance = {'views':{}}
            for view,color in [('front',(255,0,0,255)),('left',(0,0,255,255))]:
                path = folder/'prepared'/f'{view}.png'
                Image.new('RGBA',(64,64),color).save(path)
                provenance['views'][view] = {'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            (folder/'prepared/provenance.json').write_text(json.dumps(provenance))
            (folder/'job.json').write_text(json.dumps({'views':['front','left']}))
            vertices = np.array([[-1,-1,-1],[1,1,-1],[1,1,1],[-1,-1,1]],np.float32)
            faces = np.array([[0,1,2],[0,2,3]])
            uv = np.array([[[.05,.05],[.95,.05],[.95,.95]],[[.05,.05],[.95,.95],[.05,.95]]],np.float32)
            normals = np.tile(np.array([1,-1,0])/np.sqrt(2),(2,3,1))
            np.savez(folder/'geometry.npz',vertices=vertices,faces=faces,uv=uv,normals=normals)
            with contextlib.redirect_stdout(io.StringIO()):
                report = bake(folder,folder/'geometry.npz',folder/'texture',64)
            atlas = np.asarray(Image.open(folder/'texture/basecolor.png'))
            covered = np.asarray(Image.open(folder/'texture/coverage.png'))>0
            colors = atlas[covered]
            # Averaging these inconsistent photos would create purple double
            # details. Every selected texel must retain exactly one source color.
            self.assertTrue(np.all((colors[:,0]>250) ^ (colors[:,2]>250)))
            self.assertTrue(np.all(np.minimum(colors[:,0],colors[:,2])<3))
            self.assertGreater(report['views']['front']['contributing_texels'],0)
            self.assertGreater(report['views']['left']['contributing_texels'],0)

    def test_depth_buffer_prefers_front_surface(self):
        xy = np.array([[0,0],[8,0],[0,8]],np.float32)
        vertices = np.vstack([np.column_stack([xy,np.zeros(3)]),np.column_stack([xy,np.ones(3)])])
        depth = depth_buffer(vertices,np.array([[0,1,2],[3,4,5]]),8,8)
        self.assertAlmostEqual(float(depth[1,1]),1)
        self.assertFalse(np.isfinite(depth[7,7]))

    def test_cardinal_views_have_consistent_handedness(self):
        for view in ('front','left','back','right'):
            right,up,direction = camera_basis(view,10)
            self.assertTrue(np.allclose(np.cross(direction,right),up))
            self.assertAlmostEqual(float(np.dot(right,direction)),0)
        self.assertTrue(np.allclose(camera_basis('front',0)[2],[0,-1,0]))
        self.assertTrue(np.allclose(camera_basis('left',0)[2],[1,0,0]))

    def test_degenerate_uv_triangle_has_no_pixels(self):
        self.assertIsNone(triangle_pixels(np.zeros((3,2)),64,64))

    def test_texture_settings_are_bounded(self):
        for settings in ({'texture':'execute-something'},{'texture_size':8192},{'texture_size':True},
                         {'texture_fill':'invented-mode'}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                validate_request(dict(request_data(),settings=settings))
        _,settings,_,_ = validate_request(dict(request_data(),settings={'texture':'photo_basecolor','texture_size':512}))
        self.assertEqual(settings['texture'],'photo_basecolor')

    def test_back_facing_surface_stays_neutral_not_inpainted(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root/'work') as directory:
            folder = Path(directory)
            prepared = folder/'prepared'
            prepared.mkdir()
            Image.new('RGBA',(64,64),(255,0,0,255)).save(prepared/'front.png')
            sha = hashlib.sha256((prepared/'front.png').read_bytes()).hexdigest()
            (prepared/'provenance.json').write_text(json.dumps({'views':{'front':{'sha256':sha}}}))
            (folder/'job.json').write_text(json.dumps({'views':['front']}))
            vertices = np.array([[-1,0,-1],[1,0,-1],[1,0,1],[-1,0,1]],np.float32)
            faces = np.array([[0,1,2],[0,2,3]]*2)
            uv = np.array([[[.05,.05],[.45,.05],[.45,.95]],[[.05,.05],[.45,.95],[.05,.95]],
                [[.55,.05],[.95,.05],[.95,.95]],[[.55,.05],[.95,.95],[.55,.95]]],np.float32)
            normals = np.array([[[0,-1,0]]*3]*2+[[[0,1,0]]*3]*2,np.float32)
            np.savez(folder/'geometry.npz',vertices=vertices,faces=faces,uv=uv,normals=normals)
            with contextlib.redirect_stdout(io.StringIO()):
                report = bake(folder,folder/'geometry.npz',folder/'texture',64)
            atlas = np.asarray(Image.open(folder/'texture/basecolor.png'))
            coverage = np.asarray(Image.open(folder/'texture/coverage.png'))
            self.assertTrue(np.allclose(atlas[32,16],[255,0,0],atol=2))
            self.assertTrue(np.allclose(atlas[32,48],[128,128,128],atol=1))
            self.assertEqual(coverage[32,48],0)
            self.assertAlmostEqual(report['coverage_fraction'],.5,delta=.08)
            self.assertFalse(report['generated_or_inpainted_pixels'])
            # Estimated fill is opt-in and cannot inflate photo coverage.
            with contextlib.redirect_stdout(io.StringIO()):
                filled = bake(folder,folder/'geometry.npz',folder/'filled',64,'nearest_surface')
            filled_atlas = np.asarray(Image.open(folder/'filled/basecolor.png'))
            inferred = np.asarray(Image.open(folder/'filled/inferred.png'))
            self.assertEqual(filled['coverage_fraction'],report['coverage_fraction'])
            self.assertAlmostEqual(filled['inferred_fraction'],1-report['coverage_fraction'])
            self.assertTrue(np.array_equal(filled_atlas[coverage>0],atlas[coverage>0]))
            self.assertTrue(np.allclose(filled_atlas[32,48],[255,0,0],atol=2))
            self.assertEqual(inferred[32,16],0)
            self.assertEqual(inferred[32,48],255)
            self.assertFalse(filled['neural_paint_used'])
            # A changed reference is rejected rather than painted silently.
            Image.new('RGBA',(64,64),(0,255,0,255)).save(prepared/'front.png')
            with self.assertRaisesRegex(ValueError,'integrity'):
                bake(folder,folder/'geometry.npz',folder/'tampered',64)


if __name__=='__main__':
    unittest.main()
