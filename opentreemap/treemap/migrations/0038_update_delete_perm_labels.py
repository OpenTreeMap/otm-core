# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

CODENAME_LABELS = {
    "delete_plot": {
        "new": "Can delete any planting site",
        "old": "Can delete planting site",
    },
    "delete_tree": {"new": "Can delete any tree", "old": "Can delete tree"},
    "delete_treephoto": {
        "new": "Can delete any tree photo",
        "old": "Can delete tree photo",
    },
    "delete_bioswale": {"new": "Can delete any bioswale", "old": "Can delete bioswale"},
    "delete_bioswalephoto": {
        "new": "Can delete any bioswale photo",
        "old": "Can delete bioswale photo",
    },
    "delete_rainbarrel": {
        "new": "Can delete any rain barrel",
        "old": "Can delete rain barrel",
    },
    "delete_rainbarrelphoto": {
        "new": "Can delete any rain barrel photo",
        "old": "Can delete rain barrel photo",
    },
    "delete_raingarden": {
        "new": "Can delete any rain garden",
        "old": "Can delete rain garden",
    },
    "delete_raingardenphoto": {
        "new": "Can delete any rain garden photo",
        "old": "Can delete rain garden photo",
    },
    "delete_rainbarrella": {
        "new": "Can delete any rain barrel la",
        "old": "Can delete rain barrel la",
    },
    "delete_rainbarrellaphoto": {
        "new": "Can delete any rain barrel la photo",
        "old": "Can delete rain barrel la photo",
    },
    "delete_raingardenla": {
        "new": "Can delete any rain garden la",
        "old": "Can delete rain garden la",
    },
    "delete_raingardenlaphoto": {
        "new": "Can delete any rain garden la photo",
        "old": "Can delete rain garden la photo",
    },
    "delete_turfconcretegardenla": {
        "new": "Can delete any turf concrete garden la",
        "old": "Can delete turf concrete garden la",
    },
    "delete_turfconcretegardenlaphoto": {
        "new": "Can delete any turf concrete garden la photo",
        "old": "Can delete turf concrete garden la photo",
    },
}


def change_labels(apps, codename_labels, label_key):
    Permission = apps.get_model("auth", "Permission")
    for codename in codename_labels:
        perm = Permission.objects.filter(codename=codename)
        perm.update(name=codename_labels[codename][label_key])


def fix_labels(apps, schema_editor):
    change_labels(apps, CODENAME_LABELS, "new")


def revert_labels(apps, schema_editor):
    change_labels(apps, CODENAME_LABELS, "old")


class Migration(migrations.Migration):

    dependencies = [
        ("treemap", "0037_fix_plot_add_delete_permission_labels"),
    ]

    operations = [
        migrations.RunPython(fix_labels, revert_labels),
    ]
