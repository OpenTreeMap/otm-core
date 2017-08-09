"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    R = require('ramda');

var dom = {
    dialog: '#detailsDialog',
    labTitle: '#detailsDialog .modal-title',
    btnOk: '#detailsDialog .ok',
    txtName: '#edit-plan-name',
    txtDescription: '#edit-plan-description',
    radPublic: '#detailsDialog input[name=isPublic]'
};

module.exports = {
    init: init,
    show: show
};

function init() {
    var planDetailsStream = $(dom.btnOk)
            .asEventStream('click')
            .map(function () {
                return {
                    operation: $(dom.btnOk).data('operation'),
                    name: $(dom.txtName).val().trim(),
                    description: $(dom.txtDescription).val().trim(),
                    isPublished: $(dom.radPublic + ':checked').val() === 'true'
                };
            }),
        closeStream = $(dom.dialog).asEventStream('hide.bs.modal'),
        cancelStream = Bacon.when(
            [closeStream, planDetailsStream], R.always(false),
            [closeStream], R.always(true)
        ).filter(_.identity);

    return {
        planDetailsStream: planDetailsStream,
        cancelStream: cancelStream
    };
}

function show(options) {
    var details = options.details;
    $(dom.txtName).val(details.name);
    $(dom.txtDescription).val(details.description);
    $(dom.radPublic).val(details.isPublished ? ['true'] : ['false']);
    $(dom.labTitle).html(options.title);
    $(dom.btnOk)
        .html(options.btnOkLabel)
        .data('operation', options.operation);
    $(dom.dialog).modal('show');
}

