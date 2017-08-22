# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.http import Http404

from treemap.models import Tree
from treemap.images import get_image_from_request

from treemap.lib.map_feature import get_map_feature_or_404


def add_tree_photo_helper(request, instance, feature_id, tree_id=None):
    plot = get_map_feature_or_404(feature_id, instance, 'Plot')
    tree_ids = [t.pk for t in plot.tree_set.all()]

    if tree_id and int(tree_id) in tree_ids:
        tree = Tree.objects.get(pk=tree_id)
    elif tree_id is None:
        # See if a tree already exists on this plot
        tree = plot.current_tree()

        if tree is None:
            # A tree doesn't exist, create a new tree create a
            # new tree, and attach it to this plot
            tree = Tree(plot=plot, instance=instance)

            # TODO: it is possible that a user has the ability to
            # 'create tree photos' but not trees. In this case we
            # raise an authorization exception here.
            # It is, however, possible to have both a pending
            # tree and a pending tree photo
            # This will be added later, when auth/admin work
            # correctly with this system
            tree.save_with_user(request.user)

    else:
        # Tree id is invalid or not in this plot
        raise Http404('Tree id %s not found on plot %s'
                      % (tree_id, feature_id))

    #TODO: Auth Error
    data = get_image_from_request(request)
    treephoto = tree.add_photo(data, request.user)

    # We must update a rev so that missing photo searches are up to date
    instance.update_universal_rev()

    return treephoto, tree
