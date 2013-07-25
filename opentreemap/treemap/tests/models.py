from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


from django.test import TestCase
from django.contrib.gis.geos import Point

from treemap.models import Tree, Instance, Plot, FieldPermission, Species
from treemap.tests import make_loaded_role, make_instance_and_basic_user


class HashModelTest(TestCase):
    def setUp(self):
        self.instance, self.user = make_instance_and_basic_user()
        permissions = (
            ('Plot', 'geom', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'width', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'length', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'address_street', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'plot', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'readonly', FieldPermission.WRITE_DIRECTLY))

        self.user.roles.add(
            make_loaded_role(self.instance, "custom", 0, permissions))

        self.p1 = Point(-8515941.0, 4953519.0)
        self.p2 = Point(-7615441.0, 5953519.0)

    def test_changing_fields_changes_hash(self):
        plot = Plot(geom=self.p1, instance=self.instance)
        plot.save_with_user(self.user)

        #
        # Make sure regular field updates change the hash
        #
        h1 = plot.hash
        plot.width = 44
        plot.save_with_user(self.user)
        h2 = plot.hash

        self.assertNotEqual(h1, h2, "Hashes should change")

        h1 = plot.hash
        plot.address_street = "test"
        plot.save_with_user(self.user)
        h2 = plot.hash

        self.assertNotEqual(h1, h2, "Hashes should change")

        #
        # Verify adding a new tree updates the plot hash
        #

        h1 = plot.hash
        tree = Tree(plot=plot,
                    instance=self.instance,
                    readonly=False)
        tree.save_with_user(self.user)
        h2 = plot.hash

        self.assertNotEqual(h1, h2, "Hashes should change")

        #
        # Verify that updating a tree related to a plot also
        # changes the plot hash
        #

        h1 = plot.hash
        tree.readonly = True
        tree.save_with_user(self.user)

        h2 = plot.hash

        self.assertNotEqual(h1, h2, "Hashes should change")


class GeoRevIncr(TestCase):
    def setUp(self):
        self.p1 = Point(-8515941.0, 4953519.0)
        self.p2 = Point(-7615441.0, 5953519.0)
        self.instance, self.user = make_instance_and_basic_user()

        permissions = (
            ('Plot', 'geom', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'width', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'length', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'address_street', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'address_city', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'address_zip', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'import_event', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'owner_orig_id', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'readonly', FieldPermission.WRITE_DIRECTLY))

        self.user.roles.add(
            make_loaded_role(self.instance, "custom", 0, permissions))

    def hash_and_rev(self):
        i = Instance.objects.get(pk=self.instance.pk)
        return [i.geo_rev_hash, i.geo_rev]

    def test_changing_geometry_updates_counter(self):
        rev1h, rev1 = self.hash_and_rev()

        # Create
        plot1 = Plot(geom=self.p1, instance=self.instance)

        plot1.save_with_user(self.user)

        rev2h, rev2 = self.hash_and_rev()

        self.assertNotEqual(rev1h, rev2h)
        self.assertEqual(rev1 + 1, rev2)

        plot2 = Plot(geom=self.p2, instance=self.instance)

        plot2.save_with_user(self.user)

        rev3h, rev3 = self.hash_and_rev()

        self.assertNotEqual(rev2h, rev3h)
        self.assertEqual(rev2 + 1, rev3)

        # Update
        plot2.geom = self.p1
        plot2.save_with_user(self.user)

        rev4h, rev4 = self.hash_and_rev()

        self.assertNotEqual(rev3h, rev4h)
        self.assertEqual(rev3 + 1, rev4)

        # Delete
        plot2.delete_with_user(self.user)

        rev5h, rev5 = self.hash_and_rev()

        self.assertNotEqual(rev4h, rev5h)
        self.assertEqual(rev4 + 1, rev5)


class SpeciesModelTests(TestCase):
    def test_scientific_name_genus(self):
        s = Species(genus='Ulmus')
        self.assertEquals(s.scientific_name, 'Ulmus')

    def test_scientific_name_genus_species(self):
        s = Species(genus='Ulmus', species='rubra')
        self.assertEquals(s.scientific_name, 'Ulmus rubra')

    def test_scientific_name_genus_cultivar(self):
        s = Species(genus='Ulmus', cultivar_name='Columella')
        self.assertEquals(s.scientific_name, "Ulmus 'Columella'")

    def test_scientific_name_all(self):
        s = Species(genus='Ulmus', species='rubra', cultivar_name='Columella')
        self.assertEquals(s.scientific_name, "Ulmus rubra 'Columella'")
