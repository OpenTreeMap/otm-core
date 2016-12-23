"use strict";

// This entry module is loaded in 'base.html' and is used to load JS that
// should run on every page on the site

require("../../../../assets/css/sass/main.scss");
require("autotrack");
require("treemap/lib/buttonEnabler.js").run();
require("treemap/lib/export.js").run();

// Polyfill for String.startsWith(), not supported in IE 11
if (!String.prototype.startsWith) {
    String.prototype.startsWith = function (searchString, position) {
        position = position || 0;
        return this.indexOf(searchString, position) === position;
    };
}
