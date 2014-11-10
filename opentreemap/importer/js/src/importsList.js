"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    BU = require('treemap/baconUtils'),
    R = require('ramda'),
    statusView = require('importer/status');

var dom = {
    container: '#importer',
    tablesContainer: '#import-tables',
    treeForm: '#import-trees-form',
    speciesForm: '#import-species-form',
    fileChooser: 'input[type="file"]',
    importButton: 'button[type="submit"]',
    actionLink: 'td a',
    spinner: '#importer .spinner',
    importsFinished: 'input[name="importsFinished"]'
};

var REFRESH_INTERVAL = 5 * 1000;

function init(options) {
    var $container = $(dom.container),
        iAmVisibleProperty = options.iAmVisibleProperty,
        tablesUpdatedBus = new Bacon.Bus();

    statusView.init($container);

    handleForm($container, dom.treeForm, options.startImportUrl, tablesUpdatedBus);
    handleForm($container, dom.speciesForm, options.startImportUrl, tablesUpdatedBus);

    BU.reloadContainerOnClick($container, dom.actionLink);

    // When I become visible, or
    // when the tables have just been updated and I am visible,
    // wait a bit and
    // trigger a refresh if any imports aren't finished.
    Bacon.mergeAll(
            iAmVisibleProperty.changes().filter(R.eq(true)),
            tablesUpdatedBus.filter(iAmVisibleProperty))
        .throttle(REFRESH_INTERVAL)
        .onValue(updateTablesIfImportsNotFinished, options.refreshImportsUrl, tablesUpdatedBus);
}

function handleForm($container, formSelector, startImportUrl, tablesUpdatedBus) {
    // Define events on the container so we can replace its contents
    $container.asEventStream('change', formSelector + ' ' + dom.fileChooser)
        .onValue(enableImportButton, true);

    $container.asEventStream('submit', formSelector)
        .flatMap(startImport)
        .doAction($container, 'html')
        .onValue(tablesUpdatedBus, 'push');

    function startImport(e) {
        var formData = new FormData(e.target);
        e.preventDefault();
        enableImportButton(false);
        $(dom.spinner).show();
        return Bacon.fromPromise($.ajax({
            type: 'POST',
            url: startImportUrl,
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

function updateTablesIfImportsNotFinished(url, tablesUpdatedBus) {
    if ($(dom.importsFinished).val() === 'False') {
        $(dom.tablesContainer).load(url,
            function (response, status, xhr) {
                if (status !== "error") {
                    tablesUpdatedBus.push();
                }
            });
    }
}

module.exports = {init: init};
