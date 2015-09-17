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
    hasPendingImports: '.has-pending-imports',
    tableRefreshUrl: ' .refresh-url',
    pagingContainer: '.import-table .pagination',
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
            tableRefreshedBus
        );

    // Handle paging
    $container.asEventStream('click', dom.pagingButtons)
        .doAction('.preventDefault')
        .onValue(function (e) {
            var button = e.currentTarget,
                url = button.href,
                $table = $(button).closest(dom.tableContainer);
            $table.load(url, function () {
                refreshTableIfNeeded($table, tableRefreshedBus);
            });
        });

    // Trigger a refresh if there are pending imports
    refreshNeededStream
        .throttle(REFRESH_INTERVAL)
        .onValue(refreshTablesIfImportsPending, tableRefreshedBus);
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

function refreshTablesIfImportsPending(tableRefreshedBus) {
    refreshIfPending($(dom.activeTreesTable));
    refreshIfPending($(dom.activeSpeciesTable));

    function refreshIfPending($table) {
        if (needsRefresh($table)) {
            // Table's active page has pending imports, so refetch
            var url = getRefreshUrl($table);
            $.ajax(url).done(function (html) {
                var refreshUrl = getRefreshUrl($table);
                if (url === refreshUrl) {
                    // Page we fetched is still visible, so update it
                    $table.html(html);
                }
                refreshTableIfNeeded($table, tableRefreshedBus);
            });
        }
    }

    function getRefreshUrl($table) {
        return $table.find(dom.tableRefreshUrl).val();
    }
}

function refreshTableIfNeeded($table, tableRefreshedBus) {
    if (needsRefresh($table)) {
        // Page has pending imports, so make sure we're called again
        tableRefreshedBus.push();
    }
}

function needsRefresh($table) {
    var hasPending = $table.find(dom.hasPendingImports).val();
    return (hasPending === "True");
}

module.exports = {init: init};
