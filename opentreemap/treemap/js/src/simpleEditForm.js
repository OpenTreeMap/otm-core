"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    R = require('ramda'),
    BU = require('treemap/baconUtils'),
    U = require('treemap/utility'),
    _ = require('lodash'),
    moment = require('moment'),
    FH = require('treemap/fieldHelpers'),
    console = require('console-browserify'),
    editableForm = require('treemap/editableForm'),

    eventsLandingInEditMode = [editableForm.editStartAction, 'save:error'],
    eventsLandingInDisplayMode = ['save:ok', 'cancel'];

exports.init = function(options) {
    var $edit = $(options.edit),
        $save = $(options.save),
        $cancel = $(options.cancel),
        displayFields = options.displayFields || '[data-class="display"]',
        editFields = options.editFields || '[data-class="edit"]',
        saveStream = options.saveStream,

        editStream = $edit.asEventStream('click').map(editableForm.editStartAction),
        cancelStream = $cancel.asEventStream('click').map('cancel'),
        actionStream = new Bacon.Bus(),

        editForm = editableForm.init(options),

        saveOkStream = saveStream.map('save:ok'),
        saveErrorStream = saveStream.mapError('save:error');

    // Merge the major streams on the page together so that it can centrally
    // manage the cleanup of ui forms after the change in run mode
    actionStream.plug(editStream);
    actionStream.plug(saveOkStream);
    actionStream.plug(cancelStream);
    actionStream.onValue(editForm.hideAndShowElements, editFields, eventsLandingInEditMode);
    actionStream.onValue(editForm.hideAndShowElements, displayFields, eventsLandingInDisplayMode);

    saveOkStream.onValue(editForm.formFieldsToDisplayValues);

    editStream.onValue(editForm.displayValuesToFormFields);
};
