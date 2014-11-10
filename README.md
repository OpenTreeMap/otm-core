![OTM2 open source logo](https://opentreemap.github.io/images/logo@2x.png)

[![Code Health](https://landscape.io/github/OpenTreeMap/OTM2/master/landscape.png)](https://landscape.io/github/OpenTreeMap/OTM2/master)
[![Build Status](https://travis-ci.org/OpenTreeMap/OTM2.svg?branch=master)](https://travis-ci.org/OpenTreeMap/OTM2)
[![Coverage Status](https://coveralls.io/repos/OpenTreeMap/OTM2/badge.png)](https://coveralls.io/r/OpenTreeMap/OTM2)

#OpenTreeMap 2

##Questions?

Join the user mailing list and let us know: 
http://groups.google.com/group/opentreemap-user

Or, try the IRC channel at #opentreemap on freenode.net.

##Installation

For full installation instructions, see the [Github 
wiki](https://github.com/OpenTreeMap/OTM2/wiki/Installation-Guide).

Alternatively, you can also use the [otm2-vagrant 
project](https://github.com/OpenTreeMap/otm2-vagrant) to get started. 
While not recommended for production, otm2-vagrant greatly simplifies 
getting a development environment for testing and contributing to OTM2 locally.

##Other Repositories

This repository (ie, OTM2) is but one of a few separate repositories 
that together compose the OpenTreeMap project. Others include:

* [otm2-tiler](https://github.com/OpenTreeMap/otm2-tiler) - map tile 
server based on [Windshaft](https://github.com/CartoDB/Windshaft)
* [ecobenefits](https://github.com/OpenTreeMap/ecobenefits) - ecosystem 
benefits calculation service
* [OpenTreeMap-iOS](https://github.com/OpenTreeMap/OpenTreeMap-iOS) - An 
OpenTreeMap client for iOS devices.
* [OpenTreeMap-Android](https://github.com/OpenTreeMap/OpenTreeMap-Android) - An OpenTreeMap client for Android devices.

###Deprecated Repositories

OpenTreeMap has a long history. These repositories still exist, but are 
deprecated and no development is happening here moving forward.

* [OpenTreeMap](https://github.com/OpenTreeMap/OpenTreeMap) - Otherwise 
known as "OTM1", this is previous generation codebase of OpenTreeMap. It 
has been entirely superceded by this OTM2 repository and the others 
listed above. However, there are some live tree map sites still running 
on the old OTM1 code, and so we have left it up for archival purposes.

##JS file structure

All OTM2 javascript files are found in opentreemap/*/js/src/

Javscript libraries are in one of 4 places:
  - Libraries that are maintained by their authors on NPM are listed in the package.json and brought in by npm install
  - Libraries that don't pollute the global namespace and put themselves onto modules.exports, but which are not on npm, are in `opentreemap/*/js/lib/`
  - Libraries which pollute the global namespace and/or depend on global variables are in `opentreemap/*/js/shim/`
    * When adding a JS library which needs shimming, don't forget to add it to the shim section of the [Gruntfile](Gruntfile.js)
  - Libraries which require being downloaded from the vendor's servers (such as the Google Maps API) are included directly in a `<script>` tag on the page and then manually shimmed with a wrapper file in `opentreemap/*/js/lib/`

USDA Grant
---------------
Portions of OpenTreeMap are based upon work supported by the National Institute of Food and Agriculture, U.S. Department of Agriculture, under Agreement No. 2010-33610-20937, 2011-33610-30511, 2011-33610-30862 and 2012-33610-19997 of the Small Business Innovation Research Grants Program. Any opinions, findings, and conclusions, or recommendations expressed on the OpenTreeMap website are those of Azavea and do not necessarily reflect the view of the U.S. Department of Agriculture.
