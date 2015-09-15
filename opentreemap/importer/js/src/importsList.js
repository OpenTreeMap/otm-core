/*global FormData*/
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
    unitSection: '#importer-tree-units',
    // TODO:  when we figure out what actions we
    // will support besides viewing status, break
    // this up into different selectors.
    viewStatusLink: 'td a',
    spinner: '#importer .spinner',
    importsFinished: 'input[name="imports-finished"]'
};

var REFRESH_INTERVAL = 5 * 1000;

function init(options) {
    var $container = $(dom.container),
        tablesUpdatedBus = new Bacon.Bus(),
        viewStatusStream = BU.reloadContainerOnClick($container, dom.viewStatusLink),

        containerUpdateStream = Bacon.mergeAll(
            handleForm($container, dom.treeForm, options.startImportUrl),
            handleForm($container, dom.speciesForm, options.startImportUrl),
            statusView.init($container, viewStatusStream),
            viewStatusStream
        );


    // When the whole container updates, or
    // when the tables have just been updated,
    // wait a bit and
    // trigger a refresh if any imports aren't finished.
    Bacon.mergeAll(
            containerUpdateStream,
            tablesUpdatedBus)
        .throttle(REFRESH_INTERVAL)
        .onValue(updateTablesIfImportsNotFinished, options.refreshImportsUrl, tablesUpdatedBus);
}

function handleForm($container, formSelector, startImportUrl) {
    // Define events on the container so we can replace its contents
    $container.asEventStream('change', formSelector + ' ' + dom.fileChooser)
        .onValue(enableImportUI, true);

    var importStartStream = $container.asEventStream('submit', formSelector)
        .flatMap(startImport)
        .doAction($container, 'html');

    function startImport(e) {
        var formData = new FormData(e.target);
        e.preventDefault();
        enableImportUI(false);
        $(dom.spinner).show();
        return Bacon.fromPromise($.ajax({
            type: 'POST',
            url: startImportUrl,
            data: formData,
            contentType: false,
            processData: false
        }));
    }

    function enableImportUI(shouldEnable) {
        var $importButton = $(formSelector).find(dom.importButton),
            $unitSection = $(dom.unitSection);

        if (shouldEnable) {
            $importButton.prop('disabled', false);
            if (formSelector === dom.treeForm) {
                $unitSection.show();
            }
        } else {
            $importButton.prop('disabled', true);
            $unitSection.hide();
        }
    }

    return importStartStream;
}

function updateTablesIfImportsNotFinished(url, tablesUpdatedBus) {
    // If some imports aren't finished we reload the tables,
    // and push to the "tablesUpdatedBus" so we'll be called again.
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
