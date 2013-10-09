from django.utils.translation import ugettext as trans

_benefit_labels = {
    # Translators: 'Energy' is the name of an eco benefit
    'energy':     trans('Energy'),
    # Translators: 'Stormwater' is the name of an eco benefit
    'stormwater': trans('Stormwater'),
    # Translators: 'Carbon Dioxide' is the name of an eco benefit
    'co2':        trans('Carbon Dioxide'),
    # Translators: 'Air Quality' is the name of an eco benefit
    'airquality': trans('Air Quality')
}


def get_benefit_label(benefit_name):
    return _benefit_labels[benefit_name]
