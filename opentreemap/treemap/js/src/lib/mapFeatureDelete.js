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
};

exports.init = function(options) {
    options = options || {};
    var $delete = $(dom.delete),
        $deleteConfirm = $(dom.deleteConfirm),
        $deleteCancel = $(dom.deleteCancel),
        $deleteConfirmationBox = $(dom.deleteConfirmationBox),

        resetUIState = function () {
            if (options.resetUIState) {
                options.resetUIState();
            }
            $deleteConfirmationBox.hide();
        },

        getUrls = options.getUrls || function () {
            return {deleteUrl: document.URL,
                    afterDeleteUrl: reverse.map(config.instance.url_name)};
        };

    $deleteConfirm.click(function () {
        var urls = getUrls();
        $.ajax({
            url: urls.deleteUrl,
            type: 'DELETE',
            success: function () {
                window.location = urls.afterDeleteUrl;
            },
            error: function () {
                toastr.error("Cannot delete");
            }
        });
    });

    $deleteCancel.click(resetUIState);
    $delete.click(function () { 
        resetUIState();
        $deleteConfirmationBox.show(); 
    });
};
