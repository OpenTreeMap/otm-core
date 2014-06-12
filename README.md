#OpenTreeMap 2

##Dev requirements
While not necessary to run the application, [Node.js](http://nodejs.org/) and [Grunt](http://gruntjs.com/) are required to build it.

Install node 0.8, and run:
```
npm install -g grunt-cli
```


##JS file structure

All OTM2 javascript files are found in opentreemap/*/js/src/

Javscript libraries are in one of 4 places:
  - Libraries that are maintained by their authors on NPM are listed in the package.json and brought in by npm install
  - Libraries that don't pollute the global namespace and put themselves onto modules.exports, but which are not on npm, are in `opentreemap/*/js/lib/`
  - Libraries which pollute the global namespace and/or depend on global variables are in `opentreemap/*/js/shim/`
    * When adding a JS library which needs shimming, don't forget to add it to the shim section of the [Gruntfile](Gruntfile.js)
  - Libraries which require being downloaded from the vendor's servers (such as the Google Maps API) are included directly in a `<script>` tag on the page and then manually shimmed with a wrapper file in `opentreemap/*/js/lib/`

USDA Grant! YAY!
---------------
Portions of OpenTreeMap are based upon work supported by the National Institute of Food and Agriculture, U.S. Department of Agriculture, under Agreement No. 2010-33610-20937, 2011-33610-30511, 2011-33610-30862 and 2012-33610-19997 of the Small Business Innovation Research Grants Program. Any opinions, findings, and conclusions, or recommendations expressed on the OpenTreeMap website are those of Azavea and do not necessarily reflect the view of the U.S. Department of Agriculture.
