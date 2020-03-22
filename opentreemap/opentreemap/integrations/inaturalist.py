from datetime import timedelta

import requests
from django.conf import settings
from django.db import connection
from background_task import background

from treemap.models import INaturalistObservation

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


@background(schedule=timedelta(hours=24))
def sync_identifications_routine():
    """
    This helper function exists to make testing of the routine possible.
    """
    sync_identifications()

def get_o9n(o9n_id):
    token = get_inaturalist_auth_token()
    headers = {'Authorization': 'Bearer {}'.format(token)}

    response = requests.get(
        url="{base_url}/observations/{o9n_id}".format(
            base_url=base_url, o9n_id=o9n_id),
        headers=headers
    )
    import pdb; pdb.set_trace()


def sync_identifications():
    o9n_attr = INaturalistObservation.observation_id.field_name

    o9n_ids = INaturalistObservation.objects.filter(
        is_identified=False).values(o9n_attr)

    for o9n_id in o9n_ids:
        get_o9n(o9n_id[o9n_attr])



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
