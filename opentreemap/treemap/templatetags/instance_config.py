from django import template

register = template.Library()


def _get_color_from_config(config, name):
    color = config.get(name)
    if color:
        return '#' + color
    else:
        return ''


@register.filter
def primary_color(config):
    return _get_color_from_config(config,
                                  "scss_variables.primary-color")


@register.filter
def secondary_color(config):
    return _get_color_from_config(config,
                                  "scss_variables.secondary-color")
