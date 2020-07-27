# OTM API Documentation

**Table of Contents**

- [Concepts](#concepts)
- [Endpoints](#endpoints)
    - [Status](#status)
    - [Version](#version)
    - [User](#user)
    - [Instance](#instance)
    - [Plot and Tree](#plot-and-tree)
- [HMAC](#hmac)

## Concepts

OpenTreeMap hosts data for many distinct groups. The API refers to these as instances. Instances are completely separate from each other. The same user can access data from different instances, but no data is passed between instances.

Plot and tree are separate resources. The plot represents the physical location of a street tree and has a latitude and longitude. A tree has a species and diameter and must be associated with a plot. A plot may have no tree, or a single tree. A plot may be associated with multiple tree records over time (when trees die and are replanted, for instance), but only one at a time.

The OTM API was developed to provide the data required by the native OTM mobile applications. The current version is not designed as a general purpose API and does not have all the conveniences of a general purpose API (for example, errors responses are not serialized as JSON).

All requests to the OTM API must be signed with HMAC. See the HMAC section of this document for details.

## Endpoints

### Status

`GET /`

Get the status of the API.

Returns an array JSON objects.

```js
[
    {
        "api_version": "v4",
        "message": "",
        "status": "online"
    }
]
```

### Version

`GET /version`

Get the current version of the API.

Returns a JSON object.

```js
{
    "api_version": "v4",
    "otm_version": "dev"
}
```

### User

`GET /user/`

Get the profile details of the currently authenticated user.

Returns a JSON object.

```js
{
    "date_joined": "2020-01-14T22:35:49.958Z",
    "id": 1,
    "organization": "Example Organization",
    "last_login": null,
    "is_staff": false,
    "is_superuser": false,
    "email": "info@example.com",
    "thumbnail": null,
    "is_active": true,
    "status": "success",
    "photo": null,
    "allow_email_contact": false,
    "last_name": "Person",
    "first_name": "Demo",
    "make_info_public": false,
    "username": "demoperson"
}
```

---

`PUT /user/{id}`

Update the profile details of a user. A user may update their profile and only their profile.

Returns a the full, updated profile details of the specified user as a JSON object.

```js
{
    "date_joined": "2020-01-14T22:35:49.958Z",
    "id": 1,
    "organization": "Example Organization",
    "last_login": null,
    "is_staff": false,
    "is_superuser": false,
    "email": "info@example.com",
    "thumbnail": null,
    "is_active": true,
    "status": "success",
    "photo": null,
    "allow_email_contact": false,
    "last_name": "Person",
    "first_name": "Demo",
    "make_info_public": false,
    "username": "demoperson"
}
```

---

`POST /user/{id}/photo`

Upload a profile photo for a user.

Returns a JSON object.

```js
{
    "url": "https://photopath/thumbnail.jpg"
}
```

---

`POST /send-password-reset-email`

Start the password reset process by sending an email.

Query parameters:

- `email` (required) - The email address of a registered user.

Returns a JSON object

```js
{
    "status": "success"
}
```

### Instance

`GET /instances`

Get a list of publicly accessible instances.

Returns an array of JSON objects

```js
[
    {
        "center": {
            "lng": -112.12762796884756,
            "lat": 33.58432998116328
        },
        "id": 2,
        "url": "apidemo",
        "universalRevHash": "c81e728d9d4c2f636f067f89cc14862c",
        "name": "API Demo",
        "extent_radius": 70710.67811865476,
        "extent": {
            "max_lng": -111.67847032678779,
            "max_lat": 33.957698113234656,
            "min_lng": -112.57678561090732,
            "min_lat": 33.209339275354175
        },
        "eco": {
            "supportsEcoBenefits": true,
            "benefits": [
                {
                    "label": "Tree Benefits",
                    "model": "plot",
                    "keys": [
                        "energy",
                        "stormwater",
                        "airquality",
                        "co2",
                        "co2storage"
                    ]
                }
            ]
        },
        "geoRevHash": "c81e728d9d4c2f636f067f89cc14862c"
    }
]
```
---

`GET /locations/{latitude},{longitude}/instances`

Get the instances which the current user has contributed to and instances within a specified distance of the specified point.

Query parameters:

- `distance` - The maximum allowable distance in meters from the specified point. Default is 100,000.
- `max` - The maximum number of results to return. Default is 10. Maximum is 500.

Returns a JSON object with 2 arrays. The nearby array contains instances within the specified distance to the specified point. The personal array contains instances to which the current user has contributed.

```js
{
    "nearby": [
      {
            "center": {
                "lng": -112.12762796884756,
                "lat": 33.58432998116328
            },
            "id": 1,
            "url": "demo1",
            "distance": 0.0016223018867653424,
            "universalRevHash": "c81e728d9d4c2f636f067f89cc14862c",
            "name": "Demo Instance 1",
            "extent_radius": 70710.67811865476,
            "extent": {
                "max_lng": -111.67847032678779,
                "max_lat": 33.957698113234656,
                "min_lng": -112.57678561090732,
                "min_lat": 33.209339275354175
            },
            "eco": {
                "supportsEcoBenefits": true,
                "benefits": [
                    {
                        "label": "Tree Benefits",
                        "model": "plot",
                        "keys": [
                            "energy",
                            "stormwater",
                            "airquality",
                            "co2",
                            "co2storage"
                        ]
                    }
                ]
            },
            "geoRevHash": "abce728d9d4c2f636f067f89cc14862c"
        }
    ],
    "personal": [
        {
            "center": {
                "lng": -112.12762796884756,
                "lat": 33.58432998116328
            },
            "id": 2,
            "url": "demo2",
            "distance": 0.0016223018867653424,
            "universalRevHash": "c81e728d9d4c2f636f067f89cc14862c",
            "name": "Demo Instance 2",
            "extent_radius": 70710.67811865476,
            "extent": {
                "max_lng": -111.67847032678779,
                "max_lat": 33.957698113234656,
                "min_lng": -112.57678561090732,
                "min_lat": 33.209339275354175
            },
            "eco": {
                "supportsEcoBenefits": true,
                "benefits": [
                    {
                        "label": "Tree Benefits",
                        "model": "plot",
                        "keys": [
                            "energy",
                            "stormwater",
                            "airquality",
                            "co2",
                            "co2storage"
                        ]
                    }
                ]
            },
            "geoRevHash": "c81e728d9d4c2f636f067f89cc14862c"
        }
    ]
}
```

---

`GET /instance/{instance-url-name}`

Get the details of the specified instance.

Returns a JSON object.

```js
{
    "short_date_format": "MM/dd/yyyy",
    "geoRevHash": "c81e728d9d4c2f636f067f89cc14862c",
    "fields": {
        "species.palatable_human": {
            "choices": [],
            "canonical_units_factor": 1.0,
            "field_name": "palatable_human",
            "field_key": "species.palatable_human",
            "units": "",
            "can_write": true,
            "data_type": "bool",
            "is_collection": false,
            "display_name": "Edible",
            "digits": ""
        },
        "plot.geom": {
            "choices": [],
            "canonical_units_factor": 1.0,
            "field_name": "geom",
            "field_key": "plot.geom",
            "units": "",
            "can_write": true,
            "data_type": "point",
            "is_collection": false,
            "display_name": "Geom",
            "digits": ""
        },
        "tree.date_removed": {
            "choices": [],
            "canonical_units_factor": 1.0,
            "field_name": "date_removed",
            "field_key": "tree.date_removed",
            "units": "",
            "can_write": true,
            "data_type": "date",
            "is_collection": false,
            "display_name": "Date Removed",
            "digits": ""
        },
        "species.max_height": {
            "choices": [],
            "canonical_units_factor": 1.0,
            "field_name": "max_height",
            "field_key": "species.max_height",
            "units": "",
            "can_write": true,
            "data_type": "int",
            "is_collection": false,
            "display_name": "Max Height",
            "digits": ""
        },
        "plot.udf:Stewardship": {
            "choices": [],
            "canonical_units_factor": 1.0,
            "field_name": "udf:Stewardship",
            "field_key": "plot.udf:Stewardship",
            "units": "",
            "can_write": true,
            "data_type": [
                {
                    "choices": [
                        "Enlarged",
                        "Changed to Include a Guard",
                        "Changed to Remove a Guard",
                        "Filled with Herbaceous Plantings"
                    ],
                    "name": "Action",
                    "type": "choice"
                },
                {
                    "name": "Date",
                    "type": "date"
                }
            ],
            "is_collection": true,
            "display_name": "Stewardship",
            "digits": ""
        },
        "species.fact_sheet_url": {
            "choices": [],
            "canonical_units_factor": 1.0,
            "field_name": "fact_sheet_url",
            "field_key": "species.fact_sheet_url",
            "units": "",
            "can_write": true,
            "data_type": "string",
            "is_collection": false,
            "display_name": "Fact Sheet Url",
            "digits": ""
        },
    },
    "url": "jw-2020-07-23",
    "field_key_groups": [
        {
            "field_keys": [
                "tree.species",
                "tree.diameter",
                "tree.height",
                "tree.date_planted"
            ],
            "model": "tree",
            "header": "Tree Information"
        },
        {
            "field_keys": [
                "plot.width",
                "plot.length"
            ],
            "model": "plot",
            "header": "Planting Site Information"
        },
        {
            "collection_udf_keys": [
                "plot.udf:Stewardship",
                "tree.udf:Stewardship"
            ],
            "header": "Stewardship",
            "sort_key": "Date"
        }
    ],
    "name": "jw-2020-07-23",
    "extent_radius": 70710.67811865476,
    "search": {
        "missing": [
            {
                "label": "Show Missing Species",
                "identifier": "species.id"
            },
            {
                "label": "Show Missing Tree Diameter",
                "identifier": "tree.diameter"
            },
            {
                "label": "Show Missing Photos",
                "identifier": "mapFeaturePhoto.id"
            }
        ],
        "standard": [
            {
                "label": "Species",
                "identifier": "species.id",
                "search_type": "SPECIES"
            },
            {
                "label": "Tree Diameter",
                "identifier": "tree.diameter",
                "search_type": "RANGE"
            },
            {
                "label": "Tree Height",
                "identifier": "tree.height",
                "search_type": "RANGE"
            }
        ]
    },
    "date_format": "MMM d, yyyy",
    "center": {
        "lng": -112.12762796884756,
        "lat": 33.58432998116328
    },
    "id": 2,
    "config": {
    },
    "meta_perms": {
        "can_edit_tree_photo": true,
        "can_add_tree": true,
        "can_edit_tree": true
    },
    "extent": {
        "max_lng": -111.67847032678779,
        "max_lat": 33.957698113234656,
        "min_lng": -112.57678561090732,
        "min_lat": 33.209339275354175
    },
    "eco": {
        "supportsEcoBenefits": true,
        "benefits": [
            {
                "label": "Tree Benefits",
                "model": "plot",
                "keys": [
                    "energy",
                    "stormwater",
                    "airquality",
                    "co2",
                    "co2storage"
                ]
            }
        ]
    }
}
```

---

`GET /instance/{instance-url-name}/species`

Get the list of tree species for the specified instance.

```js
[
    {
        "other_part_of_name": "",
        "species": "",
        "cultivar": "",
        "genus": "Acacia",
        "common_name": "Acacia",
        "tokens": [
            "Acacia"
        ],
        "id": 267,
        "value": "Acacia [Acacia]",
        "scientific_name": "Acacia"
    },
    {
        "other_part_of_name": "",
        "species": "eldarica",
        "cultivar": "",
        "genus": "Pinus",
        "common_name": "Afghan pine",
        "tokens": [
            "Pinus",
            "eldarica",
            "Afghan",
            "pine"
        ],
        "id": 372,
        "value": "Afghan pine [Pinus eldarica]",
        "scientific_name": "Pinus eldarica"
    }
]
```

---

`GET /instance/{instance-url-name}/users.csv`

`GET /instance/{instance-url-name}/users.json`

Return the list of users who have contributed data to the specified instance in CSV or JSON format.

### Plot and Tree

`GET  /instance/{instance-url-name}/locations/{latitude},{longitude}/plots`

Get a list of plots within the specified instance near the specified point.

Query parameters:

- `max_plots` - The maximum number of results to return. Default is 1. Maximum is 500.
- `distance` - The maximum distance in meters from the specified location. Default is 100.

Returns an array of JSON objects

```js
[
    {
        "has_tree": false,
        "photo_upload_share_text": "I added a photo of this planting site!",
        "upload_photo_endpoint": "/demo/plots/2/photo",
        "latest_update": {
            "ref": null,
            "model": "Plot",
            "current_value": "",
            "field": "address_zip",
            "instance_id": 2,
            "created": "2020-07-27 17:02:29.393934+00:00",
            "user_id": 1,
            "requires_auth": false,
            "previous_value": null,
            "action": 1,
            "model_id": 2
        },
        "external_link": null,
        "plot": {
            "address_zip": "",
            "id": 2,
            "address_street": "",
            "udf:Stewardship": [],
            "length": null,
            "feature_type": "Plot",
            "geom": {
                "srid": 4326,
                "x": -112.09487915039062,
                "y": 33.51620936110904
            },
            "mapfeature_ptr": 2,
            "udfs": {
            },
            "instance": 2,
            "updated_at": "2020-07-27T17:02:29.354Z",
            "readonly": false,
            "hide_at_zoom": null,
            "owner_orig_id": null,
            "width": null,
            "updated_by": 1,
            "address_city": ""
        },
        "photos": null,
        "address_full": "",
        "progress_percent": 25,
        "feature": {
            "address_zip": "",
            "id": 2,
            "address_street": "",
            "udf:Stewardship": [],
            "length": null,
            "feature_type": "Plot",
            "geom": {
                "srid": 4326,
                "x": -112.09487915039062,
                "y": 33.51620936110904
            },
            "mapfeature_ptr": 2,
            "udfs": {
            },
            "instance": 2,
            "updated_at": "2020-07-27T17:02:29.354Z",
            "readonly": false,
            "hide_at_zoom": null,
            "owner_orig_id": null,
            "width": null,
            "updated_by": 1,
            "address_city": ""
        },
        "share": {
            "title": "Empty Planting Site on Demo Instance",
            "description": "This Empty Planting Site is mapped on Demo Instance",
            "image": "http://mediapath/static/img/otmLogo126.png",
            "url": "http://www.opentreemap.org/demo/features/2/"
        },
        "progress_messages": [
            "Add a tree",
            "Add the diameter",
            "Add the species",
            "Add a photo"
        ],
        "tree": {
            "species": null,
            "height": null,
            "date_removed": null,
            "udf:Stewardship": [],
            "udfs": {
            },
            "instance": 2,
            "id": null,
            "canopy_height": null,
            "readonly": false,
            "date_planted": null,
            "diameter": null,
            "plot": 2
        },
        "title": "Empty Planting Site",
        "feature_type": "Plot",
        "recent_activity": [
            [
                {
                    "id": 1,
                    "username": "demouser"
                },
                "2020-07-27T17:02:29.393Z",
                [
                    {
                        "ref": null,
                        "model": "Plot",
                        "current_value": "",
                        "field": "address_zip",
                        "instance_id": 2,
                        "created": "2020-07-27 17:02:29.393934+00:00",
                        "user_id": 1,
                        "requires_auth": false,
                        "previous_value": null,
                        "action": 1,
                        "model_id": 2
                    },
                    {
                        "ref": null,
                        "model": "Plot",
                        "current_value": "2",
                        "field": "id",
                        "instance_id": 2,
                        "created": "2020-07-27 17:02:29.393903+00:00",
                        "user_id": 1,
                        "requires_auth": false,
                        "previous_value": null,
                        "action": 1,
                        "model_id": 2
                    },
                    {
                        "ref": null,
                        "model": "Plot",
                        "current_value": "",
                        "field": "address_street",
                        "instance_id": 2,
                        "created": "2020-07-27 17:02:29.393869+00:00",
                        "user_id": 1,
                        "requires_auth": false,
                        "previous_value": null,
                        "action": 1,
                        "model_id": 2
                    },
                    {
                        "ref": null,
                        "model": "Plot",
                        "current_value": "SRID=3857;POINT (-12478344.86755503 3964024.286869242)",
                        "field": "geom",
                        "instance_id": 2,
                        "created": "2020-07-27 17:02:29.393834+00:00",
                        "user_id": 1,
                        "requires_auth": false,
                        "previous_value": null,
                        "action": 1,
                        "model_id": 2
                    },
                    {
                        "ref": null,
                        "model": "Plot",
                        "current_value": "False",
                        "field": "readonly",
                        "instance_id": 2,
                        "created": "2020-07-27 17:02:29.393701+00:00",
                        "user_id": 1,
                        "requires_auth": false,
                        "previous_value": null,
                        "action": 1,
                        "model_id": 2
                    }
                ]
            ]
        ],
        "favorited": false
    }
]
```

---

`POST /instance/{instance-url-name}/plots`

Create a new plot, and optionally tree, in the specified instance.

The `POST` body is a JSON object

```js
{
    "tree": {
        "diameter": 12
    },
    "plot": {
        "geom": {
            "srid": 4326,
            "y": 33.5162,
            "x": -112.0948
        }
    }
}
```

Returns a JSON object

```js
{
    "has_tree": true,
    "photo_upload_share_text": "I added a photo of this planting site!",
    "upload_photo_endpoint": "/demo/plots/4/tree/1/photo",
    "geoRevHash": "a87ff679a2f3e71d9181a67b7542122c",
    "latest_update": {
        "ref": null,
        "model": "Tree",
        "current_value": "12.0",
        "field": "diameter",
        "instance_id": 2,
        "created": "2020-07-27 20:22:32.086498+00:00",
        "user_id": 1,
        "requires_auth": false,
        "previous_value": null,
        "action": 1,
        "model_id": 1
    },
    "external_link": null,
    "plot": {
        "address_zip": null,
        "id": 4,
        "address_street": null,
        "udf:Stewardship": [],
        "length": null,
        "feature_type": "Plot",
        "geom": {
            "srid": 4326,
            "x": -112.09479999999999,
            "y": 33.5162
        },
        "mapfeature_ptr": 4,
        "udfs": {
        },
        "instance": 2,
        "updated_at": "2020-07-27T20:22:32.058Z",
        "readonly": false,
        "hide_at_zoom": null,
        "owner_orig_id": null,
        "width": null,
        "updated_by": 1,
        "address_city": null
    },
    "photos": [],
    "address_full": "",
    "progress_percent": 50,
    "feature": {
        "address_zip": null,
        "id": 4,
        "address_street": null,
        "udf:Stewardship": [],
        "length": null,
        "feature_type": "Plot",
        "geom": {
            "srid": 4326,
            "x": -112.09479999999999,
            "y": 33.5162
        },
        "mapfeature_ptr": 4,
        "udfs": {
        },
        "instance": 2,
        "updated_at": "2020-07-27T20:22:32.058Z",
        "readonly": false,
        "hide_at_zoom": null,
        "owner_orig_id": null,
        "width": null,
        "updated_by": 1,
        "address_city": null
    },
    "share": {
        "title": "Missing Species on Demo Instance",
        "description": "This Missing Species is mapped on Demo Intance",
        "image": "https://www.opentreemap.org/static/img/tree.png",
        "url": "https://www.opentreemap.org/demo/features/4/"
    },
    "progress_messages": [
        "Add the species",
        "Add a photo"
    ],
    "tree": {
        "species": null,
        "height": null,
        "date_removed": null,
        "udf:Stewardship": [],
        "udfs": {
        },
        "instance": 2,
        "id": 1,
        "canopy_height": null,
        "readonly": false,
        "date_planted": null,
        "diameter": 12.0,
        "plot": 4
    },
    "title": "Missing Species",
    "feature_type": "Plot",
    "recent_activity": [
        [
            {
                "id": 1,
                "username": "demouser"
            },
            "2020-07-27T20:22:32.086Z",
            [
                {
                    "ref": null,
                    "model": "Tree",
                    "current_value": "12.0",
                    "field": "diameter",
                    "instance_id": 2,
                    "created": "2020-07-27 20:22:32.086498+00:00",
                    "user_id": 1,
                    "requires_auth": false,
                    "previous_value": null,
                    "action": 1,
                    "model_id": 1
                },
            ]
        ]
    ],
    "favorited": false
}
```

---

`GET /instance/{instance-url-name}/plots/{plot-id}`

Get the details of the specified plot, possibly including tree details.

Returns a JSON object

```js
{
    "has_tree": true,
    "photo_upload_share_text": "I added a photo of this planting site!",
    "upload_photo_endpoint": "/demo/plots/4/tree/1/photo",
    "geoRevHash": "a87ff679a2f3e71d9181a67b7542122c",
    "latest_update": {
        "ref": null,
        "model": "Tree",
        "current_value": "12.0",
        "field": "diameter",
        "instance_id": 2,
        "created": "2020-07-27 20:22:32.086498+00:00",
        "user_id": 1,
        "requires_auth": false,
        "previous_value": null,
        "action": 1,
        "model_id": 1
    },
    "external_link": null,
    "plot": {
        "address_zip": null,
        "id": 4,
        "address_street": null,
        "udf:Stewardship": [],
        "length": null,
        "feature_type": "Plot",
        "geom": {
            "srid": 4326,
            "x": -112.09479999999999,
            "y": 33.5162
        },
        "mapfeature_ptr": 4,
        "udfs": {
        },
        "instance": 2,
        "updated_at": "2020-07-27T20:22:32.058Z",
        "readonly": false,
        "hide_at_zoom": null,
        "owner_orig_id": null,
        "width": null,
        "updated_by": 1,
        "address_city": null
    },
    "photos": [],
    "address_full": "",
    "progress_percent": 50,
    "feature": {
        "address_zip": null,
        "id": 4,
        "address_street": null,
        "udf:Stewardship": [],
        "length": null,
        "feature_type": "Plot",
        "geom": {
            "srid": 4326,
            "x": -112.09479999999999,
            "y": 33.5162
        },
        "mapfeature_ptr": 4,
        "udfs": {
        },
        "instance": 2,
        "updated_at": "2020-07-27T20:22:32.058Z",
        "readonly": false,
        "hide_at_zoom": null,
        "owner_orig_id": null,
        "width": null,
        "updated_by": 1,
        "address_city": null
    },
    "share": {
        "title": "Missing Species on Demo Instance",
        "description": "This Missing Species is mapped on Demo Intance",
        "image": "https://www.opentreemap.org/static/img/tree.png",
        "url": "https://www.opentreemap.org/demo/features/4/"
    },
    "progress_messages": [
        "Add the species",
        "Add a photo"
    ],
    "tree": {
        "species": null,
        "height": null,
        "date_removed": null,
        "udf:Stewardship": [],
        "udfs": {
        },
        "instance": 2,
        "id": 1,
        "canopy_height": null,
        "readonly": false,
        "date_planted": null,
        "diameter": 12.0,
        "plot": 4
    },
    "title": "Missing Species",
    "feature_type": "Plot",
    "recent_activity": [
        [
            {
                "id": 1,
                "username": "demouser"
            },
            "2020-07-27T20:22:32.086Z",
            [
                {
                    "ref": null,
                    "model": "Tree",
                    "current_value": "12.0",
                    "field": "diameter",
                    "instance_id": 2,
                    "created": "2020-07-27 20:22:32.086498+00:00",
                    "user_id": 1,
                    "requires_auth": false,
                    "previous_value": null,
                    "action": 1,
                    "model_id": 1
                },
            ]
        ]
    ],
    "favorited": false
}
```

---

`PUT /instance/{instance-url-name}/plots/{plot-id}`

Update the data for the specified plot and optionally tree.

The request body should be a JSON formatted object

```js
{
    "tree": {
        "height": 42
    }
}
```

Returns a JSON object

```js
{
    "has_tree": true,
    "photo_upload_share_text": "I added a photo of this planting site!",
    "upload_photo_endpoint": "/demo/plots/4/tree/1/photo",
    "geoRevHash": "a87ff679a2f3e71d9181a67b7542122c",
    "latest_update": {
        "ref": null,
        "model": "Tree",
        "current_value": "12.0",
        "field": "diameter",
        "instance_id": 2,
        "created": "2020-07-27 20:22:32.086498+00:00",
        "user_id": 1,
        "requires_auth": false,
        "previous_value": null,
        "action": 1,
        "model_id": 1
    },
    "external_link": null,
    "plot": {
        "address_zip": null,
        "id": 4,
        "address_street": null,
        "udf:Stewardship": [],
        "length": null,
        "feature_type": "Plot",
        "geom": {
            "srid": 4326,
            "x": -112.09479999999999,
            "y": 33.5162
        },
        "mapfeature_ptr": 4,
        "udfs": {
        },
        "instance": 2,
        "updated_at": "2020-07-27T20:22:32.058Z",
        "readonly": false,
        "hide_at_zoom": null,
        "owner_orig_id": null,
        "width": null,
        "updated_by": 1,
        "address_city": null
    },
    "photos": [],
    "address_full": "",
    "progress_percent": 50,
    "feature": {
        "address_zip": null,
        "id": 4,
        "address_street": null,
        "udf:Stewardship": [],
        "length": null,
        "feature_type": "Plot",
        "geom": {
            "srid": 4326,
            "x": -112.09479999999999,
            "y": 33.5162
        },
        "mapfeature_ptr": 4,
        "udfs": {
        },
        "instance": 2,
        "updated_at": "2020-07-27T20:22:32.058Z",
        "readonly": false,
        "hide_at_zoom": null,
        "owner_orig_id": null,
        "width": null,
        "updated_by": 1,
        "address_city": null
    },
    "share": {
        "title": "Missing Species on Demo Instance",
        "description": "This Missing Species is mapped on Demo Intance",
        "image": "https://www.opentreemap.org/static/img/tree.png",
        "url": "https://www.opentreemap.org/demo/features/4/"
    },
    "progress_messages": [
        "Add the species",
        "Add a photo"
    ],
    "tree": {
        "species": null,
        "height": 42.0,
        "date_removed": null,
        "udf:Stewardship": [],
        "udfs": {
        },
        "instance": 2,
        "id": 1,
        "canopy_height": null,
        "readonly": false,
        "date_planted": null,
        "diameter": 12.0,
        "plot": 4
    },
    "title": "Missing Species",
    "feature_type": "Plot",
    "recent_activity": [
        [
            {
                "id": 1,
                "username": "demouser"
            },
            "2020-07-27T20:22:32.086Z",
            [
                {
                    "ref": null,
                    "model": "Tree",
                    "current_value": "42.0",
                    "field": "height",
                    "instance_id": 2,
                    "created": "2020-07-27 20:22:32.086498+00:00",
                    "user_id": 1,
                    "requires_auth": false,
                    "previous_value": null,
                    "action": 1,
                    "model_id": 1
                },
            ]
        ]
    ],
    "favorited": false
}
```

---

`POST /instance/{instance-url-name}/plots/{plot-id}/tree/photo`

Upload a photo of the current tree associated with the specified plot.

The request body should be an image file in a format supported by [Pillow](https://pypi.org/project/Pillow/) 

Returns a JSON object representing the photo.

### HMAC

All OTM API requests must be signed using
[HMAC](https://enwikipediaorg/wiki/HMAC). The server-side HMAC implementation is based on the [`hmac` package included with Python](https://docs.python.org/3/library/hmac.html)

The [`hmaccurl.py`](../scripts/hmaccurl.py) command line tool is an example of
how API requests can be signed with HMAC. It is a Python script that wraps the
`curl` command and adds the required HMAC signature and timestamp query string
arguments. This command line tool can be used as-is to make requests to the API
or can be embedded in a larger Python application.

Signing a request requires an `ACCESS_KEY` and `SECRET_KEY` that match an
`APIAccessCredential` saved to the database. If you are running your own
installation of OTM you can use `APIAccessCredential.create()` in the Django
shell to create a new pair of keys. If you are accessing a hosted version of OTM
contact the hosting provider to obtain a key pair.

The optional `user` attribute on `APIAccessCredential` controls whether all requests
using that key pair will automatically assume the identity of that user. If
`user` is `None` then requests that require authentication will also need to
include an HTTP basic authentication header containing the username and
password. For example, the native mobile apps use a single key pair for API
access and pass the credentials of the individual user via basic authentication.

As additional reference, these are sections of the OTM code related to HMAC signing.

```python
def sign_request(request, cred=None):
    if cred is None:
        cred = APIAccessCredential.create()

    nowstr = datetime.datetime.now().strftime(SIG_TIMESTAMP_FORMAT)

    request.GET = request.GET.copy()
    request.GET['timestamp'] = nowstr
    request.GET['access_key'] = cred.access_key

    sig = get_signature_for_request(request, cred.secret_key)
    request.GET['signature'] = sig

    return request
```
https://github.com/OpenTreeMap/otm-core/blob/053e5c17322719a80ee93c190c05df285890bc58/opentreemap/api/tests.py#L65-L78

```python
def get_signature_for_request(request, secret_key):
    """
    Generate a signature for the given request

    Based on AWS signatures:
    http://docs.aws.amazon.com/AmazonSimpleDB/latest/DeveloperGuide/HMACAuth.html
    """
    httpverb = request.method
    hostheader = request.META.get('HTTP_HOST', '').lower()

    request_uri = request.path

    # This used to use request.REQUEST, but after some testing and analysis it
    # seems that both iOS & Android always pass named parameters in the query
    # string, even for non-GET requests
    params = sorted(request.GET.iteritems(), key=lambda a: a[0])

    paramstr = '&'.join(['%s=%s' % (k, urllib.quote_plus(str(v)))
                         for (k, v) in params
                         if k.lower() != "signature"])

    sign_string = '\n'.join([httpverb, hostheader, request_uri, paramstr])

    # Sometimes reeading from body fails, so try reading as a file-like
    try:
        body_encoded = base64.b64encode(request.body)
    except:
        body_encoded = base64.b64encode(request.read())

    if body_encoded:
        sign_string += body_encoded

    sig = base64.b64encode(
        hmac.new(secret_key, sign_string, hashlib.sha256).digest())

    return sig
```
https://github.com/OpenTreeMap/otm-core/blob/053e5c17322719a80ee93c190c05df285890bc58/opentreemap/api/auth.py#L16-L52

```python
def _check_signature(view_f, require_login):
    _bad_request = HttpResponseBadRequest('Invalid signature')
    _missing_request = HttpResponseBadRequest('Missing signature or timestamp')

    @wraps(view_f)
    def wrapperf(request, *args, **kwargs):
        # Request must have signature and access_key
        # parameters
        sig = request.GET.get('signature')

        if not sig:
            sig = request.META.get('HTTP_X_SIGNATURE')

        if not sig:
            return _missing_request

        # Signature may have had "+" changed to spaces so change them
        # back
        sig = sig.replace(' ', '+')

        timestamp = request.GET.get('timestamp')
        if not timestamp:
            return _missing_request

        try:
            timestamp = datetime.datetime.strptime(
                timestamp, SIG_TIMESTAMP_FORMAT)

            expires = timestamp + datetime.timedelta(minutes=15)

            if expires < datetime.datetime.now():
                return _bad_request

        except ValueError:
            return _missing_request

        if not sig:
            return _missing_request

        key = request.GET.get('access_key')

        if not key:
            return _bad_request

        try:
            cred = APIAccessCredential.objects.get(access_key=key)
        except APIAccessCredential.DoesNotExist:
            return _bad_request

        if not cred.enabled:
            return create_401unauthorized()

        signed = get_signature_for_request(request, cred.secret_key)

        if len(signed) != len(sig):
            return _bad_request

        # Don't bail early
        matches = 0
        for (c1, c2) in zip(sig, signed):
            matches = (ord(c1) ^ ord(c2)) | matches

        if matches == 0:
            if cred.user:
                user = cred.user
            else:
                user = parse_user_from_request(request)

            if require_login:
                if user is None or user.is_anonymous():
                    return create_401unauthorized()

            if user is None:
                user = AnonymousUser()

            request.user = user
            return view_f(request, *args, **kwargs)

        else:
            return _bad_request

    return wrapperf
```
https://github.com/OpenTreeMap/otm-core/blob/053e5c17322719a80ee93c190c05df285890bc58/opentreemap/api/decorators.py#L31-L112
