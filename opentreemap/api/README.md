**NOTE: This is DRAFT documentation and is subject to change.**

# Introduction

TODO

# Terminology

## Instance

A single installation of OpenTreeMap supports an unlimited number of
"maps." To avoid confusion with actual maps displayed on the explore
page the term "instance" is used internally, and in the API.

## Plot

OpenTreeMap tracks the site at which a tree is planted separately from
the tree itself. For street trees, it is not uncommon for a damaged
tree to be removed and a new tree added in its place. The web

application uses the more general "planting site" to refer to the
location where trees are planted. Internally, and in the API, "plot"
is used to refer to these locations.


# API Keys

OpenTreeMap API access keys can be shared between multiple users, or
tied to a specific user. An API key is made up of three parts.

## access_key

This part of the API key is sent in the URL of every request.

## secret_key

This part of the API key is used to sign requests and should never be
shared or stored in an easily accessible location.

## user (optional)

If an API key is assigned to a specific user, requests using that API
key will only have access to data accessible by the assigned user. If
an API key is not assigned to a user, the basic authentication passed
with the request is used to control access to resources.

# Authentication

## Signing requests

The current version of the OpenTreeMap API requires that requests be signed using a keyed-hash
message authentication code (HMAC).

References:

  - [An Objective-C signing example from the OpenTreeMap iOS application](https://github.com/OpenTreeMap/otm-ios/blob/2a316446e19ba8f4852b91e70de542130a80fb05/OpenTreeMap/src/AZ/AZHttpRequest.m#L250)
  - [A Java signing example from the OpenTreeMap Android application](https://github.com/OpenTreeMap/otm-android/blob/864fd695cb453052eca3a1c548041fb1a16d9037/OpenTreeMap/src/main/java/org/azavea/otm/rest/RequestSignature.java)
  - [The Python implementation used by OpenTreeMap to validate signatures](https://docs.python.org/2/library/hmac.html)
  - [The Amazon Web Service implementation, on which the OTM Implementation is based]( http://docs.aws.amazon.com/AmazonSimpleDB/latest/DeveloperGuide/HMACAuth.html)
  - [A technical description of HMAC on Wikipeida](https://en.wikipedia.org/wiki/Hash-based_message_authentication_code)

# Common Request Parameters

All endpoints take the following request parameters (see individual endpoints for examples):

Name | Data Type | Required | Passed In | Description
---- | --------- | -------- | --------- | -----------
`version` | string | yes | URL segment | API version string (e.g. `v3`)
`access_key` | string | yes | query string | API access key
`timestamp` | datetime | yes | query string | Date and time of request, in ISO 8601 format
`signature` | string | yes | query string | Keyed-hash message authentication code

# Users

<a name="get-user-profile"></a>
## Get user profile

Gets the user profile information for the authenticated user.

Definition:

```
GET /api/{version}/user/
```

Example Request:

```
curl -u "auser:apassword"\
     "https://opentreemap.org/api/v3/user?access_key=AN_ACCESS_KEY&timestamp=2015-06-16T17%3A59%3A37&signature=Ybtw...="
```

Example Response:

```
{
  "username": "auser",
  "make_info_public": true,
  "first_name": "A.",
  "last_name": "User",
  "allow_email_contact": true,
  "photo": null,
  "status": "success",
  "is_active": true,
  "thumbnail": null,
  "email": "a@example.com",
  "is_superuser": false,
  "is_staff": false,
  "last_login": "2015-06-16T22:36:57.274Z",
  "organization": "An Organization",
  "id": 1,
  "date_joined": "2013-10-16T22:36:57.274Z"
}
```

## Update user profile

Updates the profile for the authenticated user. This endpoint will
respond with an error if the value of `{user_id}` does not match the
ID of the authenticated user.

Definition:

```
PUT /api/{version}/user/{user_id}/
```

Request Parameters:

Name | Data Type | Required | Passed In | Description
---- | --------- | -------- | --------- | -----------
`user_id` | integer | yes | URL segment | ID of user to update
*(fields)* | JSON | yes | body | Fields to update, see next table

User profile fields:

Name | Data Type | Required | Default | Description
---- | --------- | -------- | ------- | -----------
`username` | string | yes |  | User's username
`password` | string | yes |  | User's password
`email` | string | yes |  | User's email address
`first_name` | string | no | "" | User's first name
`last_name` | string | no | "" | User's last name
`organization` | string | no | "" | User's organization
`make_info_public` | boolean | no | false | Should profile information be visible to other users?
`allow_email_contact` | boolean | no | false | Is this user subscribed to OpenTreeMap email updates?

Example Request:

```
curl -H "Content-Type: application/json"\
     -X PUT\
     -d '{"password": "a_new_password"}'\
     -u "auser:apassword"\
     "https://opentreemap.org/api/v3/user/1/?access_key=AN_ACCESS_KEY&timestamp=2015-06-16T17%3A59%3A37&signature=Ybtw...="
```

Example Response:

The response will be the same as [``GET /api/{version}/user/``](#get-user-profile)

## Update user photo

Updates the profile photo for a user. This endpoint will
respond with an error if the value of `{user_id}` does not match the
ID of the authenticated user.

Definition:

```
PUT /api/{version}/user/{user_id}/photo/
```

Request Parameters:

Name | Data Type | Required | Passed In | Description
---- | --------- | -------- | --------- | -----------
`user_id` | integer | yes | URL segment | ID of user to update
*(none)* | image | yes | body | image data

Example Request:

TODO

Example Response:

TODO


## Send password reset email

Sends an email with a link to the password reset form to the user
associated with the specified email address.

Definition:

```
POST /api/{version}/send-password-reset-email/
```

Request Parameters:

Name | Data Type | Required | Passed In | Description
---- | --------- | -------- | --------- | -----------
`email` | string | yes | body or query string | Email address of account for password reset 

Example Request:

```
curl -X POST\
     -d "email=person@domain.com"\
curl -X POST\
     "https://opentreemap.org/api/v3/send-password-reset-email/?email=auser%40example.com&access_key=AN_ACCESS_KEY&timestamp=2015-06-16T19%3A19%3A38&signature=Igb4axN4ZPspXopKRYJ3rRtRMlCMTnc2n9otUbc0fZI="
```

Example Responses:

```
{"status": "success"}
```

```
{"status": "failure", "message": "Email address not found."}
```

# Instances

## Get nearby instances

Gets instances closest to the specified location,
sorted in ascending order by distance, as well as all the instances of
which the authenticated user is a member.

The location should be specified as latitude,longitude (e.g. `39.727,-75.123`)

Definition:

```
GET /api/{version}/locations/{lat,lng}/instances/?max={max}
```

Request Parameters:

Name | Data Type | Required | Passed In | Description
---- | --------- | -------- | --------- | -----------
`lat,lng` | comma-separated floats | yes | URL segment | Location (latitude, longitude) for instance search
`max` | integer | yes | query string | Maximum number of instances to return (1-500)
`distance` | integer | yes | query string | Return instances within this distance (in meters) of given location

Example Request:

```
curl "https://opentreemap.org/api/v3/locations/39.727,-75.123/instances/instances?max=5&distance=320000.0&access_key=AN_ACCESS_KEY&timestamp=2015-06-16T19%3A48%3A05&signature=ybtw..."
```

Example Response:

```
{
  "nearby": [
    {
      "geoRevHash": "476734c0c78845d9b0040125d4ccce4c",
      "eco": {
        "benefits": [
          {
            "keys": [
              "energy",
              "stormwater",
              "airquality",
              "co2",
              "co2storage"
            ],
            "model": "plot",
            "label": "Tree Benefits"
          }
        ],
        "supportsEcoBenefits": true
      },
      "extent_radius": 183887.03722814,
      "name": "An Instance",
      "extent": {
        "min_lat": 38.449602363274,
        "min_lng": -76.136580304206,
        "max_lat": 40.608802912468,
        "max_lng": -74.382754265662
      },
      "distance": 0,
      "url": "aninstance",
      "id": 119,
      "center": {
        "lat": 40.014616288549,
        "lng": -75.163950920105
      }
    }
  ],
  "personal": [{ ...instance details... }]
}
```

## Get all instances

Get all publicly accessible instances.

Definition:

```
GET /api/{version}/instances/
```

Example Request:

```
curl "https://opentreemap.org/api/v3/instances/?access_key=AN_ACCESS_KEY&timestamp=2015-06-16T19%3A48%3A05&signature=ybtw..."
```

Example Response:

```
[
  {
    "geoRevHash": "476734c0c78845d9b0040125d4ccce4c",
    "eco": {
      "benefits": [
        {
          "keys": [
            "energy",
            "stormwater",
            "airquality",
            "co2",
            "co2storage"
          ],
          "model": "plot",
          "label": "Tree Benefits"
        }
      ],
      "supportsEcoBenefits": true
    },
    "extent_radius": 183887.03722814,
    "name": "An Instance",
    "extent": {
      "min_lat": 38.449602363274,
      "min_lng": -76.136580304206,
      "max_lat": 40.608802912468,
      "max_lng": -74.382754265662
    },
    "distance": 0,
    "url": "aninstance",
    "id": 119,
    "center": {
      "lat": 40.014616288549,
      "lng": -75.163950920105
    }
  },
  { ...instance 2 details ...}
]
```

## Get an instance

Get the full details of an instance.

Definition:

```
GET /api/{version}/instance/{instance_url_name}/
```

Request Parameters:

Name | Data Type | Required | Passed In | Description
---- | --------- | -------- | --------- | -----------
`instance_url_name` | string | yes | URL segment | Short name of instance

Example Request:

```
curl "https://opentreemap.org/api/v3/instance/myinstance?access_key=AN_ACCESS_KEY&timestamp=2015-06-16T19%3A48%3A05&signature=ybtw...""
```

Example Response:

```
{
  "eco": {
    "benefits": [
      {
        "keys": [
          "energy",
          "stormwater",
          "airquality",
          "co2",
          "co2storage"
        ],
        "model": "plot",
        "label": "Tree Benefits"
      }
    ],
    "supportsEcoBenefits": true
  },
  "extent": {
    "min_lat": 39.613625125147,
    "min_lng": -75.607540238938,
    "max_lat": 40.302188623454,
    "max_lng": -74.709224954819
  },
  "meta_perms": {
    "can_edit_tree": true,
    "can_add_tree": true,
    "can_edit_tree_photo": true
  },
  "config": {

  },
  "id": 251,
  "center": {
    "lat": 39.95877353707,
    "lng": -75.158382596879
  },
  "date_format": "MMM d, yyyy",
  "search": {
    "missing": [
      {
        "identifier": "species.id",
        "label": "Missing Species"
      },
      {
        "identifier": "tree.diameter",
        "label": "Missing Diameter"
      },
      {
        "identifier": "mapFeaturePhoto.id",
        "label": "Missing Photo"
      }
    ],
    "standard": [
      {
        "search_type": "SPECIES",
        "identifier": "species.id",
        "label": "Species"
      },
      {
        "search_type": "RANGE",
        "identifier": "tree.diameter",
        "label": "Diameter"
      },
      {
        "search_type": "RANGE",
        "identifier": "tree.height",
        "label": "Height"
      }
    ]
  },
  "extent_radius": 70710.678118654,
  "name": "My Instance",
  "field_key_groups": [
    {
      "header": "Tree Information",
      "field_keys": [
        "tree.species",
        "tree.diameter",
        "tree.height",
        "tree.date_planted"
      ]
    },
    {
      "header": "Planting Site Information",
      "field_keys": [
        "plot.width",
        "plot.length"
      ]
    },
    {
      "sort_key": "Date",
      "header": "Stewardship",
      "collection_udf_keys": [
        "plot.udf:Stewardship",
        "tree.udf:Stewardship"
      ]
    }
  ],
  "url": "myinstance",
  "fields": {
    "tree.diameter": {
      "digits": 1,
      "display_name": "Diameter",
      "is_collection": false,
      "data_type": "float",
      "can_write": true,
      "units": "in",
      "field_key": "tree.diameter",
      "field_name": "diameter",
      "canonical_units_factor": 1,
      "choices": [

      ]
    },
    "plot.length": {
      "digits": 1,
      "display_name": "Length",
      "is_collection": false,
      "data_type": "float",
      "can_write": true,
      "units": "in",
      "field_key": "plot.length",
      "field_name": "length",
      "canonical_units_factor": 1,
      "choices": [

      ]
    },
    ... more fields ...
  },
  "geoRevHash": "c4ca4238a0b923820dcc509a6f75849b",
  "short_date_format": "MM\/dd\/yyyy"
}
```


# Plots

## Create a new plot and tree

Add a plot to an instance and optionally create an associated tree. The body of your request must be a JSON object that, at a minimum, describes the point at which
the plot is located.

```
{
  "plot": {
    "geom": {
      "srid": 4326,
      "x": latitude in decimal degrees
      "y": longitude in decimal degrees
    }
  }
}
```

Definition:

```
POST /api/{version}/{`instance_url_name`}/plots/
```

Request Parameters:

Name | Data Type | Required | Passed In | Description
---- | --------- | -------- | --------- | -----------
`instance_url_name` | string | yes | URL segment | Short name of instance
`plot` | JSON | yes | body | Plot fields to update, see table below
`tree` | JSON | yes | body | Tree fields to update, see table below

<a name="plot-fields"></a>
Plot fields:

Name | Data Type | Required | Default | Description
---- | --------- | -------- | ------- | -----------
`geom` | JSON | yes | | Plot location
`geom.srid` | integer | no | 3857 | SRID of coordinate system (e.g. 3857 for Web Mercator, 4326 for lat/long)
`geom.x` | float | yes | | X coordinate of location (in SRID-specific units)
`geom.y` | float | yes | | Y coordinate of location (in SRID-specific units)
`length` | float | no | null | Length of plot bed (in instance-specific units)
`width` | float | no | null | Width of plot bed (in instance-specific units)
`address_street` | string | no | "" | Number and street of nearest address
`address_city` | string | no | "" | City name
`address_zip` | string | no | "" | Postal code
`owner_orig_id` | string | no | "" | ID of plot in an external system
`udf:Stewardship` | JSON | no | [] | List of stewardship actions
`udf:Stewardship.Action` | string | yes | | Action performed, from instance-specific choices
`udf:Stewardship.Date` | date | yes | | Date performed (YYYY-MM-DD)
`udf:<customFieldName>` | *(varies)* | no | | Instance-specific custom field 

<a name="tree-fields"></a>
Tree fields:

Name | Data Type | Required | Default | Description
---- | --------- | -------- | ------- | -----------
`species` | integer | no | null | Internal ID of this tree's species
`diameter` | float | no | null | Tree diameter at breast height (instance-specific units)
`height` | float | no | null | Tree height (in instance-specific units)
`canopy_height` | float | no | null | Canopy height (in instance-specific units)
`date_planted` | date | no | null | Date tree planted (YYYY-MM-DD)
`date_removed` | date | no | null | Date tree removed (YYYY-MM-DD) 
`udf:Stewardship` | JSON | no | [ ] | List of stewardship actions
`udf:Stewardship.Action` | string | yes | | Action performed, from instance-specific choices
`udf:Stewardship.Date` | date | yes | | Date performed (YYYY-MM-DD)
`udf:<customFieldName>` | *(varies)* | no | | Instance-specific custom field 

Example Request:

```
curl -H "Content-Type: application/json"\
     -X POST\
     -d '{"plot": {"geom": {"srid": 4326, "x": -75.15653, "y": 39.97426}, "width": 10}, "tree": {"height": 10}}'\
     "https://opentreemap.org/api/v3/instance/myinstance/plots/?access_key=AN_ACCESS_KEY&timestamp=2015-06-16T19%3A48%3A05&signature=ybtw..."
```

Example Response:

```
{
  "favorited": false,
  "progress_messages": [
    "Add the diameter",
    "Add the species",
    "Add a photo"
  ],
  "share": {
    "url": "https:\/\/opentreemap.org\/api\/v3\/instance\/myinstance\/features/1/",
    "image": "https:\/\/opentreemap.org\/static\/img\/tree.png",
    "description": "This Missing Species is mapped on My Instance",
    "title": "Missing Species on My Instance"
  },
  "photos": [],
  "latest_update": {
    "model_id": 494685,
    "action": 1,
    "previous_value": null,
    "requires_auth": false,
    "user_id": 1,
    "created": "2015-06-16 00:45:17.916506+00:00",
    "instance_id": 251,
    "field": "height",
    "current_value": "10.0",
    "model": "Tree",
    "ref": null
  },
  "upload_photo_endpoint": "\/myinstance\/plots\/673099\/tree\/494685\/photo",
  "photo_upload_share_text": "I added a photo of this planting site!",
  "has_tree": true,
  "plot": {
    "address_city": null,
    "feature_type": "Plot",
    "width": 10,
    "owner_orig_id": null,
    "readonly": false,
    "updated_at": "2015-06-16T00:45:17.838Z",
    "instance": 251,
    "mapfeature_ptr": 673099,
    "geom": {
      "y": 39.97426,
      "x": -75.15653,
      "srid": 4326
    },
    "length": null,
    "udf:Stewardship": [],
    "address_street": null,
    "id": 673099,
    "address_zip": null
  },
  "recent_activity": [
    [
      {
        "username": "auser",
        "id": 1
      },
      "2015-06-16T00:45:17.916Z",
      [
        {
          "model_id": 494685,
          "action": 1,
          "previous_value": null,
          "requires_auth": false,
          "user_id": 1,
          "created": "2015-06-16 00:45:17.916506+00:00",
          "instance_id": 251,
          "field": "height",
          "current_value": "10.0",
          "model": "Tree",
          "ref": null
        },
        {
          "model_id": 494685,
          "action": 1,
          "previous_value": null,
          "requires_auth": false,
          "user_id": 1,
          "created": "2015-06-16 00:45:17.916470+00:00",
          "instance_id": 251,
          "field": "id",
          "current_value": "494685",
          "model": "Tree",
          "ref": null
        },
        {
          "model_id": 494685,
          "action": 1,
          "previous_value": null,
          "requires_auth": false,
          "user_id": 1,
          "created": "2015-06-16 00:45:17.916434+00:00",
          "instance_id": 251,
          "field": "readonly",
          "current_value": "False",
          "model": "Tree",
          "ref": null
        },
        {
          "model_id": 494685,
          "action": 1,
          "previous_value": null,
          "requires_auth": false,
          "user_id": 1,
          "created": "2015-06-16 00:45:17.916376+00:00",
          "instance_id": 251,
          "field": "plot",
          "current_value": "673099",
          "model": "Tree",
          "ref": null
        },
        {
          "model_id": 673099,
          "action": 1,
          "previous_value": null,
          "requires_auth": false,
          "user_id": 1,
          "created": "2015-06-16 00:45:17.722707+00:00",
          "instance_id": 251,
          "field": "id",
          "current_value": "673099",
          "model": "Plot",
          "ref": null
        }
      ]
    ]
  ],
  "feature_type": "Plot",
  "title": "Missing Species",
  "tree": {
    "plot": 673099,
    "diameter": null,
    "date_planted": null,
    "readonly": false,
    "canopy_height": null,
    "id": 494685,
    "instance": 251,
    "udf:Stewardship": [],
    "date_removed": null,
    "height": 10,
    "species": null
  },
  "feature": {
    "address_city": null,
    "feature_type": "Plot",
    "width": 10,
    "owner_orig_id": null,
    "readonly": false,
    "updated_at": "2015-06-16T00:45:17.838Z",
    "instance": 251,
    "mapfeature_ptr": 673099,
    "geom": {
      "y": 39.97426,
      "x": -75.15653,
      "srid": 4326
    },
    "length": null,
    "udf:Stewardship": [],
    "address_street": null,
    "id": 673099,
    "address_zip": null
  },
  "progress_percent": 25,
  "address_full": "",
  "geoRevHash": "e4da3b7fbbce2345d7772b0674a318d5"
}
```

<a name="get-a-plot-and-the-current-tree"></a>
## Get a plot and its current tree

Get data for a plot and the tree planted in the plot.

Definition:

```
GET /api/{version}/instance/{`instance_url_name`}/plots/{plot_id}/
```

Request Parameters:

Name | Data Type | Required | Passed In | Description
---- | --------- | -------- | --------- | -----------
`instance_url_name` | string | yes | URL segment | Short name of instance
`plot_id` | integer | yes | URL segment | ID of desired plot

Example Request:

```
curl "https://opentreemap.org/api/v3/instance/myinstance/plots/1/?access_key=AN_ACCESS_KEY&timestamp=2015-06-16T19%3A48%3A05&signature=ybtw..."
```

Example Response:

```
{
  "favorited": false,
  "recent_activity": [],
  "benefits_total_currency": 2.05154669748,
  "feature_type": "Plot",
  "title": "Coast live oak",
  "tree": {
    "plot": 1,
    "diameter": 3,
    "date_planted": null,
    "readonly": false,
    "canopy_height": null,
    "id": 344761,
    "instance": 1,
    "udf:Stewardship": [],
    "date_removed": null,
    "height": 7,
    "species": {
      "flowering_period": "",
      "max_diameter": 200,
      "fall_conspicuous": false,
      "is_native": true,
      "scientific_name": "Quercus agrifolia",
      "otm_code": "QUAG",
      "plant_guide_url": "",
      "max_height": 800,
      "species": "agrifolia",
      "instance": 1,
      "palatable_human": false,
      "fruit_or_nut_period": "",
      "flower_conspicuous": false,
      "common_name": "Coast live oak",
      "has_wildlife_value": true,
      "fact_sheet_url": "",
      "genus": "Quercus",
      "cultivar": "",
      "id": 1,
      "other_part_of_name": ""
    },
  },
  "progress_messages": [
    "Add a photo"
  ],
  "basis": {
    "plot": {
      "n_objects_discarded": 0,
      "n_objects_used": 1
    }
  }
  "feature": {
    "address_city": "",
    "feature_type": "Plot",
    "width": null,
    "readonly": false,
    "updated_at": "2014-11-25T22:52:20.895Z",
    "instance": 1,
    "mapfeature_ptr": 1,
    "geom": {
      "y": 34.013166237,
      "x": -118.391855216,
      "srid": 4326
    },
    "length": null,
    "udf:Stewardship": [],
    "address_street": "",
    "id": 1,
    "address_zip": null
  },
  "progress_percent": 75,
  "address_full": "",
  "photos": [
    {
      "raw": {
        "mapfeaturephoto_ptr": 1,
        "image": "trees\/2015\/06\/16\/473190-344761-62907476367de8ec1e80aa163c18a368.png",
        "tree": 1,
        "thumbnail": "trees_thumbs\/2015\/06\/16\/thumb-473190-344761-62907476367de8ec1e80aa163c18a368.png",
        "instance": 1,
        "id": 1,
        "map_feature": 1
      },
      "absolute_detail_url": "https:\/\/opentreemap.org\/myinstance\/features\/1\/photo\/1\/detail",
      "mapfeaturephoto_ptr": 1,
      "image": "\/media\/trees\/2015\/06\/16\/473190-344761-62907476367de8ec1e80aa163c18a368.png",
      "tree": 344761,
      "thumbnail": "\/media\/trees_thumbs\/2015\/06\/16\/thumb-473190-344761-62907476367de8ec1e80aa163c18a368.png",
      "instance": 21,
      "detail_url": "\/latreemap\/features\/1\/photo\/1\/detail",
      "id": 1,
      "map_feature": 1,
      "absolute_image": "https:\/\/opentreemap.org:\/media\/trees\/2015\/06\/16\/473190-344761-62907476367de8ec1e80aa163c18a368.png"
    }
  ],
  "plot": {
    "udf:Tree Location": null,
    "address_city": "",
    "feature_type": "Plot",
    "width": null,
    "owner_orig_id": "",
    "readonly": false,
    "updated_at": "2014-11-25T22:52:20.895Z",
    "instance": 1,
    "mapfeature_ptr": 1,
    "geom": {
      "y": 34.013166237,
      "x": -118.391855216,
      "srid": 4326
    },
    "length": null,
    "udf:Stewardship": [],
    "address_street": "",
    "id": 1,
    "address_zip": null
  },
  "currency_symbol": "$",
  "latest_update": null,
  "benefits": {
    "plot": {
      "co2storage": {
        "name": "co2storage",
        "value": "16.2",
        "label": "Carbon dioxide stored to date",
        "currency": 0.169575,
        "currency_saved": "$0",
        "unit": "lbs",
        "unit-name": "eco"
      },
      "energy": {
        "name": "energy",
        "value": "4.6",
        "label": "Energy conserved",
        "currency": 0.7830235,
        "currency_saved": "$0",
        "unit": "kwh\/year",
        "unit-name": "eco"
      },
      "co2": {
        "name": "co2",
        "value": "17.6",
        "label": "Carbon dioxide removed",
        "currency": 0.18518808,
        "currency_saved": "$0",
        "unit": "lbs\/year",
        "unit-name": "eco"
      },
      "airquality": {
        "name": "airquality",
        "value": "-0.0",
        "label": "Air quality improved",
        "currency": 0.30616439788,
        "currency_saved": "$0",
        "unit": "lbs\/year",
        "unit-name": "eco"
      },
      "stormwater": {
        "name": "stormwater",
        "value": "60.8",
        "label": "Stormwater filtered",
        "currency": 0.6075957196,
        "currency_saved": "$0",
        "unit": "gal\/year",
        "unit-name": "eco"
      }
    }
  },
  "upload_photo_endpoint": "\/myinstance\/plots\/1\/tree\/1\/photo",
  "has_tree": true
}
```


## Update a plot and/or tree

Update an existing plot and/or tree. The `PUT` verb is used for this
request, but this endpoint behaves more like a `PATCH` request in that
omitted fields will not be modified. You
can update a single field value by passing a single JSON-encoded
key-value pair.

Definition:

```
PUT /api/{version}/instance/{`instance_url_name`}/plots/{plot_id}/
```

Request Parameters:

Name | Data Type | Required | Passed In | Description
---- | --------- | -------- | --------- | -----------
`instance_url_name` | string | yes | URL segment | Short name of instance
`plot_id` | integer | yes | URL segment | ID of plot to update
`plot` | JSON | no | body | [Plot fields to update](#plot-fields)
`tree` | JSON | no | body | [Tree fields to update](#tree-fields)

Example Request:

```
curl -H "Content-Type: application/json"\
     -X PUT\
     -d '{"plot": {"width": 4.2}}'\
     "https://opentreemap.org/api/v3/instance/myinstance/plots/1/?access_key=AN_ACCESS_KEY&timestamp=2015-06-16T19%3A48%3A05&signature=ybtw..."
```


Example Response:

The response will be the same as [``GET /api/{version}/instance/{`instance_url_name`}/plots/{plot_id}/``](#get-a-plot-and-the-current-tree)

## Delete a plot

Delete an existing plot, and its tree (if present).

Definition:

```
DELETE /api/{version}/instance/{`instance_url_name`}/plots/{plot_id}/
```

Request Parameters:

Name | Data Type | Required | Passed In | Description
---- | --------- | -------- | --------- | -----------
`instance_url_name` | string | yes | URL segment | Short name of instance
`plot_id` | integer | yes | URL segment | ID of plot to delete

Example Request:

```
curl -X DELETE\
     -u "auser:apassword"\
     "https://opentreemap.org/api/v3/instance/myinstance/plots/1/?access_key=AN_ACCESS_KEY&timestamp=2015-06-16T19%3A48%3A05&signature=ybtw..."
```

Example Response:

```
{"ok": True}
```

## Delete a tree

Delete an existing tree, but leave the plot in which it is planted.

Definition:

```
DELETE /api/{version}/instance/{`instance_url_name`}/plots/{plot_id}/tree/
```

Request Parameters:

Name | Data Type | Required | Passed In | Description
---- | --------- | -------- | --------- | -----------
`instance_url_name` | string | yes | URL segment | Short name of instance
`plot_id` | integer | yes | URL segment | ID of plot whose tree should be deleted

Example Request:

```
curl -X DELETE\
     -u "auser:apassword"\
     "https://opentreemap.org/api/v3/instance/myinstance/plots/1/tree/?access_key=AN_ACCESS_KEY&timestamp=2015-06-16T19%3A48%3A05&signature=ybtw.."
```


Example Response:

```
{"ok": True}
```

## Add a photo to a tree

Definition:

```
POST /api/{version}/instance/{`instance_url_name`}/plots/{plot_id}/tree/photo/
```

Request Parameters:

Name | Data Type | Required | Passed In | Description
---- | --------- | -------- | --------- | -----------
`instance_url_name` | string | yes | URL segment | Short name of instance
`plot_id` | integer | yes | URL segment | ID of plot whose tree has been photographed
*(none)* | image | yes | body | image data

Example Request:

TODO

Example Response:

TODO

## Get nearby plots

Gets the plots closest to the specified location,
sorted in ascending order by distance.

The location should be specified as latitude,longitude (e.g. `-75.123,39.727`)

Definition:

```
GET /api/{version}/instance/{`instance_url_name`}/location/{lat,lng}/plots/?max_plots={max_plots}
```

Request Parameters:

Name | Data Type | Required | Passed In | Description
---- | --------- | -------- | --------- | -----------
`instance_url_name` | string | yes | URL segment | Short name of instance
`lat,lng` | comma-separated floats | yes | URL segment | Location (latitude, longitude) for plot search
`max_plots` | integer | yes | query string | Maximum number of plots to return (1-500)

Example Request:

```
curl "https://opentreemap.org/api/v3/instance/myinstance/locations/33.997392,-118.085103/plots?max_plots=2&access_key=AN_ACCESS_KEY&timestamp=2015-06-16T21%3A36%3A41&signature=ybtw..."
```

Example Response:

```
[
  { ...full plot and tree detail 1... },
  { ...full plot and tree detail 2... }
]
```

Each plot returned will have the same schema as [``GET /api/{version}/instance/{`instance_url_name`}/plots/{plot_id}/``](#get-a-plot-and-the-current-tree)


# Species

# Get all species

Get all tree species defined for the specified instance.

Definition:

```
GET /api/{version}/instance/{`instance_url_name`}/species/
```

Request Parameters:

Name | Data Type | Required | Passed In | Description
---- | --------- | -------- | --------- | -----------
`instance_url_name` | string | yes | URL segment | Short name of instance

Example Request:

```
curl "https://opentreemap.org/api/v3/instance/myinstance/species/?access_key=AN_ACCESS_KEY&timestamp=2015-06-16T21%3A36%3A41&signature=ybtw...""
```

Example Response:

```
[
  {
    "scientific_name": "Aucuba",
    "value": "Acuba [Aucuba]",
    "id": 143493,
    "tokens": [
      "Acuba",
      "Aucuba"
    ],
    "common_name": "Acuba",
    "genus": "Aucuba",
    "cultivar": "",
    "species": ""
  },
  { ...next species...}
]
```
