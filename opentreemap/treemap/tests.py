from django.test import TestCase
from treemap.models import Tree, Instance
from treemap.audit import Audit
from django.contrib.gis.geos import Point

class AuditTest(TestCase):

    def setUp(self):
        p = Point(-8515941.0, 4953519.0)
        self.instance = Instance(name='i1',geo_rev=0,center=p)
        self.instance.save()

        self.user = 1

    def assertAuditsEqual(self, exps, acts):
        self.assertEqual(len(exps), len(acts))

        for [exp,act] in zip(exps, acts):
            act = act.dict()
            act['created'] = None
            self.assertEqual(exp, act)

    def make_audit(self, pk, field, old, new, action=Audit.Type.Insert, user=None):
        if field:
            field = unicode(field)
        if old:
            old = unicode(old)
        if new:
            new = unicode(new)

        user = user or self.user

        return { 'model': u'Tree',
                 'model_id': pk,
                 'instance_id': self.instance,
                 'field': field,
                 'previous_value': old,
                 'current_value': new,
                 'user_id': user,
                 'action': action,
                 'requires_auth': False,
                 'ref_id': None,
                 'created': None }

    def test_basic_audit(self):
        p = Point(-8515222.0, 4953200.0)
        t = Tree(geom=p, instance=self.instance, owner='joe')

        t.save_with_user(self.user)

        expected_audits = [
            self.make_audit(t.pk, 'id', None, str(t.pk)),
            self.make_audit(t.pk, 'geom', None, str(t.geom)),
            self.make_audit(t.pk, 'instance', None, t.instance.pk),
            self.make_audit(t.pk, 'owner', None, t.owner)]


        self.assertAuditsEqual(expected_audits, t.audits())

        t.owner = 'sally'
        t.save_with_user(2)

        expected_audits.insert(
            0, self.make_audit(t.pk, 'owner', 'joe', t.owner,
                               action=Audit.Type.Update, user=2))

        self.assertAuditsEqual(expected_audits, t.audits())

        old_pk = t.pk
        t.delete_with_user(4)

        expected_audits.insert(
            0, self.make_audit(old_pk, None, None, None,
                               action=Audit.Type.Delete, user=4))

        self.assertAuditsEqual(
            expected_audits,
            Audit.audits_for_model('Tree', self.instance, old_pk))
