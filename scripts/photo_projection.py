"""CPU orthographic photo projection and visibility-aware UV rasterization."""
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

AZIMUTHS = {'front': 0, 'left': 90, 'back': 180, 'right': 270}


def triangle_pixels(points, width, height):
    """Pixel-center barycentrics; returns rows, columns and weights."""
    low = np.maximum(np.floor(points.min(axis=0) - .5).astype(int), 0)
    high = np.minimum(np.ceil(points.max(axis=0) - .5).astype(int), [width-1, height-1])
    if np.any(low > high):
        return None
    a, b, c = points
    denominator = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
    if abs(denominator) < 1e-10:
        return None
    yy, xx = np.mgrid[low[1]:high[1]+1, low[0]:high[0]+1]
    x, y = xx+.5, yy+.5
    w0 = ((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/denominator
    w1 = ((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/denominator
    w2 = 1-w0-w1
    inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
    if not inside.any():
        return None
    return yy[inside], xx[inside], np.stack([w0[inside], w1[inside], w2[inside]], axis=1)


def depth_buffer(projected, faces, width, height):
    depth = np.full((height, width), -np.inf, dtype=np.float32)
    for face in faces:
        triangle = projected[face]
        pixels = triangle_pixels(triangle[:, :2], width, height)
        if pixels is not None:
            yy, xx, bary = pixels
            z = bary @ triangle[:, 2]
            depth[yy, xx] = np.maximum(depth[yy, xx], z)
    return depth


def camera_basis(view, elevation):
    a, e = np.deg2rad([AZIMUTHS[view], elevation])
    right = np.array([np.cos(a), np.sin(a), 0.])
    direction = np.array([np.sin(a)*np.cos(e), -np.cos(a)*np.cos(e), np.sin(e)])
    up = np.cross(direction, right)
    return right, up, direction


def project(vertices, camera, resolution_scale=1):
    right, up, direction = np.asarray(camera['basis'])
    xy = np.column_stack([(vertices@right-camera['center'][0])*camera['scale']+camera['photo_center'][0],
        camera['photo_center'][1]-(vertices@up-camera['center'][1])*camera['scale']])
    return np.column_stack([xy*resolution_scale, vertices@direction])


def fit_camera(vertices, faces, alpha, view, elevations=(0,10,20,30,40,50,60)):
    """Fit cardinal orthographic silhouette; scores do not establish calibration."""
    height, width = alpha.shape
    fy, fx = np.nonzero(alpha > .5)
    if not len(fx):
        raise ValueError(f'{view} has no opaque foreground')
    box = [int(fx.min()), int(fy.min()), int(fx.max()+1), int(fy.max()+1)]
    ratio = min(1., 192/max(height, width))
    rh, rw = max(1, round(height*ratio)), max(1, round(width*ratio))
    target = ndimage.zoom(alpha, (rh/height, rw/width), order=0) > .5
    yy, xx = np.indices((rh, rw))
    best_score, best = -1., None
    for elevation in elevations:
        right, up, direction = camera_basis(view, elevation)
        u, v = vertices@right, vertices@up
        camera = {'basis': [right.tolist(), up.tolist(), direction.tolist()],
            'center': [float((u.min()+u.max())/2), float((v.min()+v.max())/2)],
            'scale': (box[3]-box[1])/max(float(np.ptp(v)), 1e-8),
            'photo_center': [(box[0]+box[2])/2, (box[1]+box[3])/2], 'elevation': elevation}
        silhouette = np.isfinite(depth_buffer(project(vertices, camera, ratio), faces, rw, rh))
        cx, cy = np.array(camera['photo_center'])*ratio
        # Small bounded 2D fit; no arbitrary pose solve or image synthesis.
        for factor in (.95, 1., 1.05):
            for dx in (-.025, 0, .025):
                for dy in (-.025, 0, .025):
                    sx = np.rint((xx-cx-dx*(box[2]-box[0])*ratio)/factor+cx).astype(int)
                    sy = np.rint((yy-cy-dy*(box[3]-box[1])*ratio)/factor+cy).astype(int)
                    valid = (sx >= 0) & (sx < rw) & (sy >= 0) & (sy < rh)
                    candidate = np.zeros_like(silhouette)
                    candidate[valid] = silhouette[sy[valid], sx[valid]]
                    score = np.count_nonzero(candidate & target)/max(1, np.count_nonzero(candidate | target))
                    # Labelled cardinal views usually have level cameras. A
                    # tiny silhouette gain must not tilt facial features away
                    # from the sculpted eyes/mouth. Require a meaningful gain.
                    objective = score-.002*abs(elevation)
                    if objective > best_score:
                        best_score = objective
                        best = dict(camera, scale=camera['scale']*factor,
                            photo_center=[camera['photo_center'][0]+dx*(box[2]-box[0]),
                                          camera['photo_center'][1]+dy*(box[3]-box[1])],
                            silhouette_iou=float(score),fit_objective=float(objective))
    best['elevation_penalty_per_degree'] = .002
    best['fit_model'] = 'cardinal orthographic, elevation + bounded scale/translation'
    return best


def atlas_surface(vertices, faces, corner_uv, corner_normals, size):
    points = np.zeros((size, size, 3), np.float32)
    normals = np.zeros_like(points)
    valid = np.zeros((size, size), bool)
    for index, face in enumerate(faces):
        uv = corner_uv[index]
        screen = np.column_stack([uv[:, 0]*size, (1-uv[:, 1])*size])
        pixels = triangle_pixels(screen, size, size)
        if pixels is not None:
            yy, xx, bary = pixels
            points[yy, xx] = bary @ vertices[face]
            normals[yy, xx] = bary @ corner_normals[index]
            valid[yy, xx] = True
    normals /= np.maximum(np.linalg.norm(normals, axis=2, keepdims=True), 1e-8)
    return points[valid], normals[valid], valid


def srgb_to_linear(rgb):
    return np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)


def linear_to_srgb(rgb):
    rgb = np.clip(rgb, 0, 1)
    return np.where(rgb <= .0031308, rgb*12.92, 1.055*rgb**(1/2.4)-.055)


def sample_view(points, normals, vertices, faces, rgba, camera):
    height, width = rgba.shape[:2]
    coordinates = project(points, camera)
    x, y, z = coordinates.T
    # Visibility is a geometry calculation. A tiny sprite must not reduce its
    # depth buffer to a few dozen pixels and reject valid sloped surfaces.
    # Color is still sampled from the original pixels below.
    ratio = 512/max(height, width)
    rw, rh = max(1, round(width*ratio)), max(1, round(height*ratio))
    depth = depth_buffer(project(vertices, camera, ratio), faces, rw, rh)
    ix = np.clip((x*ratio).astype(int), 0, rw-1)
    iy = np.clip((y*ratio).astype(int), 0, rh-1)
    front = np.maximum(normals @ np.asarray(camera['basis'][2]), 0)
    tolerance = max(float(np.max(np.ptp(vertices, axis=0)))*.012, 1e-6)
    visible = (x >= 0) & (x < width) & (y >= 0) & (y < height) & (front > .12)
    visible &= np.isfinite(depth[iy, ix]) & (np.abs(z-depth[iy, ix]) < tolerance)
    alpha = ndimage.map_coordinates(rgba[:, :, 3], [y-.5, x-.5], order=1, mode='constant', cval=0)
    edge_distance = ndimage.distance_transform_edt(rgba[:, :, 3] > .9)
    edge = ndimage.map_coordinates(edge_distance, [y-.5, x-.5], order=1, mode='constant', cval=0)
    weight = visible * (alpha > .9) * np.minimum(edge/3, 1) * front**4 * camera['silhouette_iou']**2
    rgb = np.column_stack([ndimage.map_coordinates(srgb_to_linear(rgba[:, :, channel]),
        [y-.5, x-.5], order=1, mode='constant', cval=0) for channel in range(3)])
    return rgb, weight


def extend_surface_colors(points, colors, covered):
    """Estimate unknown colors from nearest observed 3D surface positions.

    No UV-space dilation across unrelated islands; observed pixels stay exact.
    This extrapolates color only, and must never increase measured photo coverage.
    """
    if not covered.any():
        raise ValueError('Color extension needs observed surface samples')
    result = colors.copy()
    unknown = ~covered
    if unknown.any():
        _, nearest = cKDTree(points[covered]).query(points[unknown],workers=1)
        result[unknown] = colors[covered][nearest]
    return result
