"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    BU = require('treemap/baconUtils');

var dom = {
    container: '#importer',
    treeForm: '#import-trees-form',
    speciesForm: '#import-species-form',
    fileChooser: 'input[type="file"]',
    importButton: 'button[type="submit"]',
    spinner: '#importer .spinner'
};

function init(options) {
    var url = options.startImportUrl;
    handleForm(dom.treeForm, url);
    handleForm(dom.speciesForm, url);
}

function handleForm(formSelector, url) {
    // Define events on the container so we can replace its contents
    var $container = $(dom.container);

    // Enable import button when file chosen
    $container.asEventStream('change', formSelector + ' ' + dom.fileChooser)
        .onValue(enableImportButton, true);

    // Submit form, using returned HTML to replace page content
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
            url: url,
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
