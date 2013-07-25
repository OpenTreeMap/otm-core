#Open Tree Map 2

##JS file structure

All OTM2 javascript files are found in opentreemap/<app>/js/src/

Javscript libraries are in one of 3 places:
  - Libraries that are maintained by their authors on NPM are listed in the package.json and brought in by npm install
  - Libraries that don't pollute the global namespace and put themselves onto modules.exports, but which are not on npm, are in opentreemap/<app>/js/lib/
  - Libraries which pollute the global namespace and/or depend on global variables are in opentreemap/<app>/js/shim/
