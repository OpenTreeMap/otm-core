"use strict";

var $ = require('jquery'),
    toastr = require('toastr'),
    reverse = require('reverse'),
    config = require('treemap/lib/config.js');

var dom = {
    delete: '#delete-object',
    deleteConfirm: '#delete-confirm',
    deleteCancel: '#delete-cancel',
    deleteConfirmationBox: '#delete-confirmation-box',
    spinner: '.spinner'
};

exports.init = function(options) {
    options = options || {};

    $(dom.deleteConfirm).click(function () {
        var deleteUrl = options.deleteUrl || document.URL,
            successUrl = options.successUrl || reverse.map(config.instance.url_name);
        $(dom.spinner).show();
        $.ajax({
            url: deleteUrl,
            type: 'DELETE',
            success: function () {
                window.location = successUrl;
            },
            error: function () {
                toastr.error("Cannot delete");
            }
        });
    });

    $(dom.deleteCancel).click(function () {
        $(dom.deleteConfirmationBox).hide();
    });
    $(dom.delete).click(function () {
        $(dom.deleteConfirmationBox).show();
    });
};
