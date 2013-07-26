#Open Tree Map 2

##Dev requirements
While not necessary to run the application, [Node.js](http://nodejs.org/) and [Grunt](http://gruntjs.com/) are required to build it.

Install node 0.8, and run npm install -g grunt-cli


##JS file structure

All OTM2 javascript files are found in opentreemap/<app>/js/src/

Javscript libraries are in one of 3 places:
  - Libraries that are maintained by their authors on NPM are listed in the package.json and brought in by npm install
  - Libraries that don't pollute the global namespace and put themselves onto modules.exports, but which are not on npm, are in opentreemap/<app>/js/lib/
  - Libraries which pollute the global namespace and/or depend on global variables are in opentreemap/<app>/js/shim/
