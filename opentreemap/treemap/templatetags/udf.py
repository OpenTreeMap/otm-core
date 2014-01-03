from django import template
from treemap.udf import UserDefinedCollectionValue

register = template.Library()


@register.filter
def collection_values_for_model_id(udfd, model_id):
    if not udfd.iscollection:
        raise ValueError("The specified UserDefinedFieldDefinition"
                         "is not a collection")
    return UserDefinedCollectionValue.objects.filter(field_definition=udfd,
                                                     model_id=model_id)
