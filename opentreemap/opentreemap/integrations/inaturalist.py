import csv
from collections import Counter
import dateutil.parser
import datetime
import time
import logging

from celery import shared_task, chord
import requests
from django.conf import settings
from django.db import connection
from django.core.cache import cache

from treemap.models import INaturalistObservation, Species, MapFeaturePhotoLabel, INaturalistPhoto
from treemap.lib.map_feature import get_map_feature_or_404

base_url = settings.INATURALIST_URL


def get_inaturalist_auth_token():

    payload = {
        'client_id': settings.INATURALIST_APP_ID,
        'client_secret': settings.INATURALIST_APP_SECRET,
        'grant_type': 'password',
        'username': settings.INATURALIST_USERNAME,
        'password': settings.INATURALIST_PASSWORD
    }

    r = requests.post(
        url="{base_url}/oauth/token".format(base_url=base_url),
        data=payload
    )
    token = r.json()['access_token']
    return token


def set_observation_to_captive(token, observation_id):
    metric = 'wild'

    headers = {'Authorization': 'Bearer {}'.format(token)}
    params = {
        'id': observation_id,
        'metric': metric,
        'agree': 'false'
    }

    response = requests.post(
        url="{base_url}/observations/{observation_id}/quality/{metric}".format(
            base_url=base_url,
            observation_id=observation_id,
            metric=metric),
        json=params,
        headers=headers
    )

    return response.ok


def create_observation(token, latitude, longitude, species):

    headers = {'Authorization': 'Bearer {}'.format(token)}
    params = {'observation': {
        'observed_on_string': datetime.datetime.now().isoformat(),
        'latitude': latitude,
        'longitude': longitude,
        'species_guess': species
    }
    }

    response = requests.post(
        url="{base_url}/observations.json".format(base_url=base_url),
        json=params,
        headers=headers
    )

    observation = response.json()[0]

    set_observation_to_captive(token, observation['id'])

    return observation


def add_photo_to_observation(token, observation_id, photo):

    headers = {'Authorization': 'Bearer {}'.format(token)}
    data = {'observation_photo[observation_id]': observation_id}
    file_data = {'file': photo.image.file.file}

    response = requests.post(
        url="{base_url}/observation_photos".format(base_url=base_url),
        headers=headers,
        data=data,
        files=file_data
    )
    return response.json()


def get_majority_identification(identifications):
    """
    Find the majority of an identification
    """
    _identifications = [{
        'user': identification['user']['login'],
        'taxon_id': identification['taxon']['id'],
        'taxon': identification['taxon']['name']
    } for identification in identifications]

    most_common = Counter([i['taxon'] for i in _identifications]).most_common()
    (taxon, count) = most_common[0] if most_common else ('', 0)

    users = [i['user'] for i in _identifications if i['taxon'] == taxon]

    return {
        'taxon': taxon,
        'users': ','.join(users),
        'total_count': len(_identifications),
        'count': count
    }


def is_species_match(taxon_otm, taxon_inaturalist):
    """
    Tons of weird mismatches, so we need a mapping
    """
    taxon_inaturalist_map = {
        'prunus × yedoensis': 'prunus yedoensis'
    }
    _taxon_inaturalist = taxon_inaturalist_map.get(taxon_inaturalist, taxon_inaturalist)
    return taxon_otm in _taxon_inaturalist or _taxon_inaturalist in taxon_otm


def sync_identifications():
    """
    Goes through all unidentified observations and updates them with taxonomy on iNaturalist
    """
    o9n_models = INaturalistObservation.objects.filter(is_identified=False)

    observations = get_all_observations([o.observation_id for o in o9n_models])
    id_info = []

    for o9n_model in o9n_models:
        observation = observations.get(o9n_model.observation_id)
        if not observation:
            continue

        identifications = observation['identifications']
        identification_majority = get_majority_identification(identifications)
        if not o9n_model.tree or not o9n_model.tree.species:
            continue

        taxon_otm = o9n_model.tree.species.scientific_name

        species_match = is_species_match(taxon_otm.lower(), identification_majority['taxon'].lower())

        try:
            id_info.append({
                'map_feature_id': o9n_model.map_feature.id,
                'tree_id': o9n_model.tree.id,
                'matches': species_match,
                'species_otm': taxon_otm,
                'species_inaturalist': identification_majority['taxon'],
                'users_majority': identification_majority['users'],
                'sjc_in_majority': 'sustainablejc' in identification_majority['users'],
                'count_identification': len(identifications),
                'count_most_votes': identification_majority['total_count'],
                'num_identification_agreements_inat': observation['num_identification_agreements'],
                'num_identification_disagreements_inat': observation['num_identification_disagreements'],
                'identifications_most_disagree_inat': observation['identifications_most_disagree'],
                'taxons_inaturalist': ','.join([i['taxon']['name'] for i in identifications])
            })
        except Exception as e:
            continue

        #_set_identification(o9n_model, taxonomy)

    with open('inaturalist_compare.csv', 'w') as csvfile:
        fieldnames = id_info[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(id_info)


def get_all_observations(observation_ids):
    """
    Retrieve iNaturalist observation by ID
    SWAGGER docs: https://api.inaturalist.org/v1

    We want to retrieve all observations that have at least two observations in agreement

    :param o9n_id: observation ID
    :return: observation JSON as a dict
    """
    identifications = {}
    page = 1
    per_page = 100
    base_url = 'https://api.inaturalist.org/v1'
    for observation_batch in [observation_ids[x:x+per_page] for x in range(0, len(observation_ids), per_page)]:
        data = requests.get(
            url="{base_url}/observations/{ids}".format(
                base_url=base_url,
                ids=','.join([str(o) for o in observation_batch])),
        ).json()

        if (not data):
            break

        results = data['results']
        for result in results:
            try:
                identifications[result['id']] = {
                    'identifications': result['identifications'],
                    'num_identification_agreements': result['num_identification_agreements'],
                    'num_identification_disagreements': result['num_identification_disagreements'],
                    'identifications_most_disagree': result['identifications_most_disagree']
                }
            except Exception as e:
                pass

        time.sleep(5)

    return identifications


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
    o9n_model.tree.species = Species(common_name=taxon['taxon']['common_name']['name'])
    o9n_model.identified_at = dateutil.parser.parse(taxon['updated_at'])
    o9n_model.is_identified = True
    o9n_model.save()


def get_features_for_inaturalist(tree_id=None):
    """
    Get all the features that have a label and can be submitted to iNaturalist
    """
    tree_filter_clause = "1=1"
    if tree_id:
        tree_filter_clause = "t.id = {}".format(tree_id)

    query = """
        SELECT  photo.map_feature_id, photo.instance_id, t.id as tree_id
        FROM    treemap_mapfeaturephoto photo
        JOIN    treemap_mapfeaturephotolabel label on label.map_feature_photo_id = photo.id
        JOIN    treemap_tree t on t.plot_id = photo.map_feature_id
        LEFT JOIN treemap_inaturalistobservation inat on inat.map_feature_id = photo.map_feature_id
        where   1=1
        and     inat.id is null

         -- these could be empty tree pits
        and     t.species_id is not null

        -- we also cannot get the species to dead trees
        and     coalesce(t.udfs -> 'Condition', '') != 'Dead'

        -- if we should filter a specific tree, do it here
        and     {}

        group by photo.map_feature_id, photo.instance_id, t.id
        having sum(case when label.name = 'shape' then 1 else 0 end) > 0
        and sum(case when label.name = 'bark'  then 1 else 0 end) > 0
        and sum(case when label.name = 'leaf'  then 1 else 0 end) > 0
    """.format(tree_filter_clause)

    with connection.cursor() as cursor:
        # FIXME use parameters for a tree id
        cursor.execute(query)
        results = cursor.fetchall()

    return [{'feature_id': r[0],
             'instance_id': r[1],
             'tree_id': r[2]}
            for r in results]


@shared_task()
def create_observations(instance, tree_id=None):
    logger = logging.getLogger('iNaturalist')
    logger.info('Creating observations')

    features = get_features_for_inaturalist(tree_id)
    if not features:
        return

    token = get_inaturalist_auth_token()

    for feature in features:
        feature = get_map_feature_or_404(feature['feature_id'], instance)
        tree = feature.safe_get_current_tree()

        if not tree:
            continue

        photos = tree.photos().prefetch_related('mapfeaturephotolabel_set').all()
        if len(photos) != 3:
            continue

        # we want to submit the leaf first, so sort by leaf
        photos = sorted(photos, key=lambda x: 0 if x.has_label('leaf') else 1)
        (longitude, latitude) = feature.latlon.coords

        # create the observation
        _observation = create_observation(
            token,
            latitude,
            longitude,
            tree.species.common_name
        )
        observation = INaturalistObservation(
            observation_id=_observation['id'],
            map_feature=feature,
            tree=tree,
            submitted_at=datetime.datetime.now()
        )
        observation.save()

        for photo in photos:
            time.sleep(10)
            photo_info = add_photo_to_observation(token, _observation['id'], photo)

            photo_observation = INaturalistPhoto(
                tree_photo=photo,
                observation=observation,
                inaturalist_photo_id=photo_info['photo_id']
            )
            photo_observation.save()

        # let's not get rate limited
        time.sleep(30)

    logger.info('Finished creating observations')
