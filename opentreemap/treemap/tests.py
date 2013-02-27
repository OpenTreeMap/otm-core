from django.test import TestCase
from treemap.models import Tree, Instance, Plot, User
from treemap.audit import Audit
from django.contrib.gis.geos import Point

class InstanceAndAuth(TestCase):

    def setUp(self):
        p = Point(-8515941.0, 4953519.0)
        self.instance1 = Instance(name='i1',geo_rev=0,center=p)
        self.instance1.save()

        self.instance2 = Instance(name='i2',geo_rev=0,center=p)
        self.instance2.save()

    def test_invalid_instance_returns_404(self):
        response = self.client.get('/%s/' % self.instance1.pk)
        self.assertEqual(response.status_code, 200)

        response = self.client.get('/1000/')
        self.assertEqual(response.status_code, 404)

class AuditTest(TestCase):

    def setUp(self):
        p = Point(-8515941.0, 4953519.0)
        self.instance = Instance(name='i1',geo_rev=0,center=p)
        self.instance.save()

        self.user1 = User(username='joe')
        self.user1.save()

        self.user2 = User(username='amy')
        self.user2.save()

    def assertAuditsEqual(self, exps, acts):
        self.assertEqual(len(exps), len(acts))

        exps = list(exps)
        for act in acts:
            act = act.dict()
            act['created'] = None

            if act in exps:
                exps.remove(act)
            else:
                raise AssertionError('Missing audit record for %s' % act)

    def make_audit(self, pk, field, old, new, action=Audit.Type.Insert, user=None, model=u'Tree'):
        if field:
            field = unicode(field)
        if old:
            old = unicode(old)
        if new:
            new = unicode(new)

        user = user or self.user1

        return { 'model': model,
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
        plot = Plot(geom=p, instance=self.instance, created_by=self.user1)
        plot.save_with_user(self.user1)

        self.assertAuditsEqual([
            self.make_audit(plot.pk, 'id', None, str(plot.pk), model='Plot'),
            self.make_audit(plot.pk, 'instance', None, plot.instance.pk , model='Plot'),
            self.make_audit(plot.pk, 'readonly', None, 'False' , model='Plot'),
            self.make_audit(plot.pk, 'geom', None, str(plot.geom), model='Plot'),
            self.make_audit(plot.pk, 'created_by', None, self.user1.pk, model='Plot')],
                               plot.audits())

        t = Tree(plot=plot, instance=self.instance, readonly=True, created_by=self.user1)

        t.save_with_user(self.user1)

        expected_audits = [
            self.make_audit(t.pk, 'id', None, str(t.pk)),
            self.make_audit(t.pk, 'instance', None, t.instance.pk),
            self.make_audit(t.pk, 'readonly', None, True),
            self.make_audit(t.pk, 'created_by', None, self.user1.pk),
            self.make_audit(t.pk, 'plot', None, plot.pk)]


        self.assertAuditsEqual(expected_audits, t.audits())

        t.readonly = False
        t.save_with_user(self.user2)

        expected_audits.insert(
            0, self.make_audit(t.pk, 'readonly', 'True', 'False',
                               action=Audit.Type.Update, user=self.user2))

        self.assertAuditsEqual(expected_audits, t.audits())

        old_pk = t.pk
        t.delete_with_user(self.user1)

        expected_audits.insert(
            0, self.make_audit(old_pk, None, None, None,
                               action=Audit.Type.Delete, user=self.user1))

        self.assertAuditsEqual(
            expected_audits,
            Audit.audits_for_model('Tree', self.instance, old_pk))
