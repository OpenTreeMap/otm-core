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
    submitButton: 'button[type="submit"]',
    spinner: '#importer .spinner'
};

function init(options) {
    var url = options.startImportUrl;
    handleForm(dom.treeForm, url);
    handleForm(dom.speciesForm, url);
}

function handleForm(formSelector, url) {
    var $formSelector = $(formSelector),
        $fileChooser = $formSelector.find(dom.fileChooser),
        $submitButton = $formSelector.find(dom.submitButton);

    // Enable submit button when file chosen
    $fileChooser.asEventStream('change')
        .onValue($submitButton, 'prop', 'disabled', false);

    // Submit form, using returned HTML to update tables
    $formSelector.asEventStream('submit')
        .flatMap(startImport)
        .onValue($(dom.container), 'html');

    function startImport(e) {
        var formData = new FormData(e.target);
        e.preventDefault();
        $submitButton.prop('disabled', true);
        $(dom.spinner).show();
        return Bacon.fromPromise($.ajax({
            type: 'POST',
            url: url,
            data: formData,
            contentType: false,
            processData: false
        }));
    }
}

module.exports = {init: init};
