"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    BU = require('treemap/baconUtils'),
    statusView = require('importer/status');

var dom = {
    container: '#importer',
    treeForm: '#import-trees-form',
    speciesForm: '#import-species-form',
    fileChooser: 'input[type="file"]',
    importButton: 'button[type="submit"]',
    actionLink: 'td a',
    spinner: '#importer .spinner'
};

function init(options) {
    // Define events on the container so we can replace its contents
    var $container = $(dom.container);

    statusView.init($container);

    handleForm($container, dom.treeForm, options);
    handleForm($container, dom.speciesForm, options);

    BU.reloadContainerOnClick($container, dom.actionLink);
}

function handleForm($container, formSelector, options) {
    $container.asEventStream('change', formSelector + ' ' + dom.fileChooser)
        .onValue(enableImportButton, true);

    $container.asEventStream('submit', formSelector)
        .flatMap(startImport)
        .onValue($container, 'html');

    function startImport(e) {
        var formData = new FormData(e.target);
        e.preventDefault();
        enableImportButton(false);
        $(dom.spinner).show();
        return Bacon.fromPromise($.ajax({
            type: 'POST',
            url: options.startImportUrl,
            data: formData,
            contentType: false,
            processData: false
        }));
    }

    function enableImportButton(shouldEnable) {
        $(formSelector)
            .find(dom.importButton)
            .prop('disabled', !shouldEnable);
    }
}

module.exports = {init: init};
