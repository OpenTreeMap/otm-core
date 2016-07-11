Javascript conventions
======

We use Common.js style Javascript modules, bundled together into different files using [Webpack](https://webpack.github.io/).
There is generally one JS "entry" bundle per page, as well as a common bundle that contains frequently used modules and runs code needed for every page.

##JS file structure

All Javascript source files are found in `opentreemap/*/js/src/`.  Entry modules are in the root of the `src/` directory, while non-entry modules are in `src/lib/`

Javscript libraries are in one of 4 places:
  - Libraries that are maintained by their authors on NPM are listed in the package.json and brought in by npm install
  - Libraries that use a module system like Common.js, AMD, UMD, or similar, are located in `assets/js/vendor/`
  - Libraries which pollute the global namespace and/or depend on global variables are in `assets/js/shim/`
    * When adding a JS library which needs shimming, don't forget to add it to the shim section of the [Webpack configuration](webpack.common.config.js)
  - Libraries which require being downloaded from the vendor's servers (such as the Google Maps API) are included directly in a `<script>` tag on the page and then manually shimmed with a wrapper file in `assets/js/vendor/`
