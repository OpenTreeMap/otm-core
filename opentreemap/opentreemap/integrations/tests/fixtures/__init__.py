import copy
import json

# API reference: https://www.inaturalist.org/pages/api+reference#get-observations-id
with open('opentreemap/integrations/tests/fixtures/observation.json') as json_file:
    _o9n = json.loads(json_file.read())


def get_inaturalist_o9n(o9n_id=None):
    o9n_copy = copy.deepcopy(_o9n)

    if o9n_id:
        o9n_copy['id'] = o9n_id

    return o9n_copy
