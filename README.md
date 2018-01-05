![OTM2 open source logo](https://opentreemap.github.io/images/logo@2x.png)

[![Code Health](https://landscape.io/github/OpenTreeMap/otm-core/master/landscape.png)](https://landscape.io/github/OpenTreeMap/otm-core/master)
[![Build Status](https://travis-ci.org/OpenTreeMap/otm-core.svg?branch=master)](https://travis-ci.org/OpenTreeMap/otm-core)
[![Coverage Status](https://coveralls.io/repos/OpenTreeMap/otm-core/badge.png)](https://coveralls.io/r/OpenTreeMap/otm-core)

# OpenTreeMap 2

## Questions?

Join the user mailing list and let us know: 
http://groups.google.com/group/opentreemap-user

Or, try our Gitter channel: [![Join the chat at https://gitter.im/OpenTreeMap/otm-core](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/OpenTreeMap/otm-core?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

## Installation

For full installation instructions, see the [Github 
wiki](https://github.com/OpenTreeMap/otm-core/wiki/Installation-Guide).

Alternatively, you can also use the [otm-vagrant 
project](https://github.com/OpenTreeMap/otm-vagrant) to get started. 
While not recommended for production, otm-vagrant greatly simplifies 
getting a development environment for testing and contributing to OTM locally.

### Environment variables
This project requires several environment variables, to provide API keys for several services.

```
ROLLBAR_SERVER_SIDE_ACCESS_TOKEN=....
GOOGLE_MAPS_KEY=...
```
`ROLLBAR_SERVER_SIDE_ACCESS_TOKEN` is a token for [Rollbar](rollbar.com).
`GOOGLE_MAPS_KEY` is a browser key for the Google Maps Javascript API, [which can be obtained here](https://developers.google.com/maps/documentation/javascript/get-api-key).

## Other Repositories

This repository (ie, otm-core) is but one of a few separate repositories 
that together compose the OpenTreeMap project. Others include:

* [otm-tiler](https://github.com/OpenTreeMap/otm-tiler) - map tile 
server based on [Windshaft](https://github.com/CartoDB/Windshaft)
* [otm-ecoservice](https://github.com/OpenTreeMap/otm-ecoservice) - ecosystem 
benefits calculation service
* [otm-ios](https://github.com/OpenTreeMap/otm-ios) - An 
OpenTreeMap client for iOS devices.
* [otm-android](https://github.com/OpenTreeMap/otm-android) - An OpenTreeMap client for Android devices.



### Deprecated Repositories

OpenTreeMap has a long history. These repositories still exist, but are 
deprecated and no development is happening here moving forward.

* [OpenTreeMap](https://github.com/OpenTreeMap/OpenTreeMap) - Otherwise 
known as "OTM1", this is previous generation codebase of OpenTreeMap. It 
has been entirely superceded by this repository and the others 
listed above. However, there are some live tree map sites still running 
on the old OTM1 code, and so we have left it up for archival purposes.

## Developer documentation
 - [Javascript module conventions](doc/js.md)
 - [Python mixins](doc/mixins.md)


## Acknowledgements

This application includes code based on [django-url-tools](https://bitbucket.org/monwara/django-url-tools), Copyright (c) 2013 Monwara LLC.

USDA Grant
---------------
Portions of OpenTreeMap are based upon work supported by the National Institute of Food and Agriculture, U.S. Department of Agriculture, under Agreement No. 2010-33610-20937, 2011-33610-30511, 2011-33610-30862 and 2012-33610-19997 of the Small Business Innovation Research Grants Program. Any opinions, findings, and conclusions, or recommendations expressed on the OpenTreeMap website are those of Azavea and do not necessarily reflect the view of the U.S. Department of Agriculture.
