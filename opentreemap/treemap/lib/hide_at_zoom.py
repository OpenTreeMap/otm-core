# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from math import floor

from django.db import connection

from treemap.models import MapFeature

GRID_PIXELS = 2
MAX_ZOOM = 14
MIN_ZOOM = 0

# When viewing a zoomed-out tree map, multiple plots in a local area are
# rendered on top of one another. We set MapFeature.hide_at_zoom so the tiler
# can render just one plot in such cases, speeding up tile creation for maps
# with many plots.
#
# At each zoom level Z we find groups of plots located in the same cell of
# a grid (cell size GRID_PIXELS), and set hide_at_zoom = Z for all but one
# plot in each group.
#
# A larger cell size gives more speedup, but if it's too large the tree dots
# start showing the grid pattern. GRID_PIXELS = 2 is the sweet spot for our
# current tree dot size of 5 pixels.


def recompute_hide_at_zoom(instance, verbose=False):
    # TODO: skip if geo_rev hasn't changed
    if verbose:
        print('\nUpdating instance %s' % instance.url_name)

    MapFeature.objects.all() \
        .filter(instance=instance) \
        .update(hide_at_zoom=None)

    _print_summary(instance, MAX_ZOOM + 1, verbose)
    for zoom in range(MAX_ZOOM, MIN_ZOOM - 1, -1):
        grid_size_wm = _get_grid_size_wm(GRID_PIXELS, zoom)
        with connection.cursor() as cursor:
            cursor.execute(_SQL_RECOMPUTE, {
                'instance_id': instance.id,
                'grid_size': grid_size_wm,
                'zoom': zoom
            })
        _print_summary(instance, zoom, verbose)

    instance.update_geo_rev()


def _print_summary(instance, zoom, verbose):
    if verbose:
        features = MapFeature.objects.filter(instance=instance,
                                             hide_at_zoom=None)
        print("{1:>2}  {0:>7}".format(features.count(), zoom))


def _get_grid_size_wm(grid_pixels, zoom):
    wm_world_width = 40075016.6856
    tile_size = 256
    wm_units_per_pixel = wm_world_width / (tile_size * pow(2, zoom))
    grid_size_wm = grid_pixels * wm_units_per_pixel
    return grid_size_wm


# Notes:
# 1) Ignore non-plots. They aren't numerous, and it simplifies
#    both the tiler and opt-out of green infrastructure types.
# 2) Not using ST_SnapToGrid because results were not consistent across runs.

_SQL_RECOMPUTE = """
    WITH featuresToHide AS (
        WITH mapfeature AS (
            /* Get all plots in instance with hide_at_zoom not set */
             SELECT f.id, f.the_geom_webmercator
             FROM treemap_mapfeature f
             INNER JOIN treemap_instance i ON f.instance_id=i.id
             WHERE i.id=%(instance_id)s
               AND f.feature_type='Plot'
               AND f.hide_at_zoom IS NULL
        )
        SELECT mapfeature.id FROM mapfeature
        LEFT OUTER JOIN
            /* Choose one feature from each grid cell */
            (SELECT DISTINCT ON (geom)
                id,
                ST_MakePoint(floor(ST_X(the_geom_webmercator) / %(grid_size)s),
                             floor(ST_Y(the_geom_webmercator) / %(grid_size)s))
                    AS geom
              FROM mapfeature
            ) AS distinctRows
            ON mapfeature.id = distinctRows.id
        /* Now get the features NOT chosen */
        WHERE distinctRows.id IS NULL
    )
    UPDATE treemap_mapfeature f
    SET hide_at_zoom = %(zoom)s
    FROM featuresToHide
    WHERE f.id = featuresToHide.id;
    """


def update_hide_at_zoom_after_delete(feature):
    if feature.feature_type == 'Plot':
        _reveal_a_hidden_plot(
            feature.instance, feature.geom, feature.hide_at_zoom)


def update_hide_at_zoom_after_move(feature, user, point_old):
    # For simplicity treat a move as an add and a delete.
    # This means slightly more rendering than would be optimal, but
    # plots aren't moved often and we'll re-optimize nightly.
    # For the "add" we show the plot at all zoom levels (by clearing its
    # hide_at_zoom). For the "delete" we reveal a plot hidden by the old
    # position to prevent holes in the canopy.
    if feature.feature_type == 'Plot':
        hide_at_zoom_old = feature.hide_at_zoom
        feature.hide_at_zoom = None
        feature.save_with_user(user)

        _reveal_a_hidden_plot(feature.instance, point_old, hide_at_zoom_old)


def _reveal_a_hidden_plot(instance, point, hide_at_zoom):
    min_zoom = MIN_ZOOM - 1 if hide_at_zoom is None else hide_at_zoom

    for zoom in range(MAX_ZOOM, min_zoom, -1):
        grid_size_wm = _get_grid_size_wm(GRID_PIXELS, zoom)
        # Plot that disappeared was visible at this zoom level.
        # Reveal a hidden plot if there's one in this cell.
        with connection.cursor() as cursor:
            cursor.execute(_SQL_REVEAL, {
                'instance_id': instance.id,
                'grid_size': grid_size_wm,
                'zoom': zoom,
                'hide_at_zoom': hide_at_zoom,
                'cell_x': floor(point.x / grid_size_wm),
                'cell_y': floor(point.y / grid_size_wm),
            })
            result = cursor.fetchone()
            if result is not None:
                # Found one. Its hide_at_zoom has been lowered so it will fill
                # the hole left by the old plot.
                return


_SQL_REVEAL = """
    UPDATE treemap_mapfeature f
    SET hide_at_zoom = %(hide_at_zoom)s
    FROM (
         SELECT f.id
         FROM treemap_mapfeature f
         INNER JOIN treemap_instance i ON f.instance_id=i.id
         WHERE i.id = %(instance_id)s
           AND f.feature_type = 'Plot'
           AND f.hide_at_zoom >= %(zoom)s
           AND floor(ST_X(the_geom_webmercator) / %(grid_size)s) = %(cell_x)s
           AND floor(ST_Y(the_geom_webmercator) / %(grid_size)s) = %(cell_y)s
         LIMIT 1
         ) feature_to_reveal
    WHERE f.id = feature_to_reveal.id
    RETURNING feature_to_reveal.id;
    """
