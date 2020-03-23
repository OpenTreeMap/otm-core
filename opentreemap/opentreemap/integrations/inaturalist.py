import dateutil.parser
from datetime import timedelta

import requests
from django.conf import settings
from django.db import connection

from treemap.models import INaturalistObservation, Species

base_url = "https://www.inaturalist.org"


def get_inaturalist_auth_token():

    payload = {
        'client_id': settings.INATURALIST_APP_ID,
        'client_secret': settings.INATURALIST_APP_SECRET,
        'grant_type': 'password',
        'username': settings.USERNAME,
        'password': settings.PASSWORD
    }

    r = requests.post(
        url="{base_url}/oauth/token".format(base_url=base_url),
        data=payload
    )
    token = r.json()['access_token']
    return token


def create_observation(token, latitude, longitude):

    headers = {'Authorization': 'Bearer {}'.format(token)}
    params = {'observation': {
        'observed_on_string': datetime.datetime.now().isoformat(),
        'latitude': latitude,
        'longitude': longitude
    }
    }

    response = requests.post(
        url="{base_url}/observations.json".format(base_url=base_url),
        json=params,
        headers=headers
    )

    return response.json()[0]


def add_photo_to_observation(token, observation_id, photo):

    headers = {'Authorization': 'Bearer {}'.format(token)}
    data = {'observation_photo[observation_id]': observation_id}
    file_data = {'file': photo.image.file.file}

    requests.post(
        url="{base_url}/observation_photos".format(base_url=base_url),
        headers=headers,
        data=data,
        files=file_data
    )


def sync_identifications():
    """
    Goes through all unidentified observations and updates them with taxonomy on iNaturalist
    """
    o9n_models = INaturalistObservation.objects.filter(is_identified=False)

    for o9n_model in o9n_models:
        taxonomy = get_o9n(o9n_model.observation_id).get('taxon')
        if taxonomy:
            _set_identification(o9n_model, taxonomy)


def get_o9n(o9n_id):
    """
    Retrieve iNaturalist observation by ID
    API docs: https://www.inaturalist.org/pages/api+reference#get-observations-id
    :param o9n_id: observation ID
    :return: observation JSON as a dict
    """
    return requests.get(
        url="{base_url}/observations/{o9n_id}.json".format(
            base_url=base_url, o9n_id=o9n_id)
    ).json()


def _set_identification(o9n_model, taxon):
    o9n_model.tree.species = Species(common_name=taxon['common_name']['name'])
    o9n_model.identified_at = dateutil.parser.parse(taxon['updated_at'])
    o9n_model.is_identified = True
    o9n_model.save()


def get_features_for_inaturalist():
    """
    Get all the features that have a label and can be submitted to iNaturalist
    """
    query = """
        SELECT  photo.id, photo.map_feature_id, photo.instance_id
        FROM    treemap_mapfeaturephoto photo
        JOIN    treemap_mapfeaturephotolabel label on label.map_feature_photo_id = photo.id
        LEFT JOIN treemap_inaturalistobservation inat on inat.map_feature_id = photo.map_feature_id
        where   1=1
        and     inat.id is null
        group by photo.id, photo.map_feature_id, photo.instance_id
        having sum(case when label.name = 'shape' then 1 else 0 end) > 0
        and sum(case when label.name = 'bark'  then 1 else 0 end) > 0
        and sum(case when label.name = 'leaf'  then 1 else 0 end) > 0
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        results = cursor.fetchall()

    return [{'photo_id': r[0],
             'feature_id': r[1],
             'instance_id': r[2]}
            for r in results]
