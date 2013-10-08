from django.utils.translation import ugettext as trans

_benefit_labels = {
    'energy':     trans('Energy'),
    'stormwater': trans('Stormwater'),
    'co2':        trans('Carbon Dioxide'),
    'airquality': trans('Air Quality')
}


def get_label(benefit_name):
    if benefit_name in _benefit_labels:
        return _benefit_labels[benefit_name]
    else:
        raise Exception("Unexpected benefit name: " + benefit_name)
