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
    tableContainer: '.import-table',
    treeForm: '#import-trees-form',
    speciesForm: '#import-species-form',
    fileChooser: 'input[type="file"]',
    importButton: 'button[type="submit"]',
    unitSection: '#importer-tree-units',
    activeTreesTable: '#activeTrees',
    activeSpeciesTable: '#activeSpecies',
    activeTreesPending: '#activeTrees-has-pending',
    activeSpeciesPending: '#activeSpecies-has-pending',
    pagingButtons: '.import-table .pagination li a',
    viewStatusLink: '.js-view',
    spinner: '#importer .spinner',
    importsFinished: 'input[name="imports-finished"]'
};

var REFRESH_INTERVAL = 5 * 1000;

function init(options) {
    var $container = $(dom.container),
        tableRefreshedBus = new Bacon.Bus(),
        viewStatusStream = BU.reloadContainerOnClick($container, dom.viewStatusLink),

        refreshNeededStream = Bacon.mergeAll(
            handleForm($container, dom.treeForm, options.startImportUrl, dom.activeTreesTable),
            handleForm($container, dom.speciesForm, options.startImportUrl, dom.activeSpeciesTable),
            statusView.init($container, viewStatusStream),
            viewStatusStream,
            tableRefreshedBus
        );

    // Handle paging
    $container.asEventStream('click', dom.pagingButtons)
        .doAction('.preventDefault')
        .onValue(function (e) {
            var button = e.currentTarget,
                url = button.href,
                $tableContainer = $(button).closest(dom.tableContainer);
            $tableContainer.load(url);
        });

    // Trigger a refresh if there are pending imports
    refreshNeededStream
        .throttle(REFRESH_INTERVAL)
        .onValue(updateTablesIfImportsPending, options, tableRefreshedBus);
}

function handleForm($container, formSelector, startImportUrl, tableSelector) {
    // Define events on the container so we can replace its contents
    $container.asEventStream('change', formSelector + ' ' + dom.fileChooser)
        .onValue(enableImportUI, true);

    var importStartStream = $container.asEventStream('submit', formSelector)
        .flatMap(startImport)
        .doAction(function (html) {
            $(tableSelector).html(html);
            $(dom.spinner).hide();
        });

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

function updateTablesIfImportsPending(options, tableRefreshedBus) {
    updateIfPending(dom.activeTreesTable, dom.activeTreesPending, options.refreshTreeImportsUrl);
    updateIfPending(dom.activeSpeciesTable, dom.activeSpeciesPending, options.refreshSpeciesImportsUrl);

    function updateIfPending(table, pending, url) {
        // If the table has pending imports, reload it
        // and push to the "tableRefreshedBus" so we'll be called again.
        if ($(pending).val() === 'True') {
            $(table).load(url,
                function (response, status, xhr) {
                    if (status !== "error") {
                        tableRefreshedBus.push();
                    }
                });
        }
    }
}

module.exports = {init: init};
