"use strict";

var addMapFeature = require('treemap/addMapFeature');

var manager;

function init(options) {
    manager = addMapFeature.init(options);
}

function activate() {
    if (manager) {
        manager.activate();
    }
}

function deactivate() {
    if (manager) {
        manager.deactivate();
    }
}

module.exports = {
    name: 'addTree',
    init: init,
    activate: activate,
    deactivate: deactivate,
    lockOnActivate: true
};
