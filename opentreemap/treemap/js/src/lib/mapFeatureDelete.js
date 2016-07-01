"use strict";

var $ = require('jquery'),
    toastr = require('toastr');

exports.init = function(options) {
    var config = options.config,
        controls = options.deleteControls,
        $delete = $(controls.delete),
        $deleteConfirm = $(controls.deleteConfirm),
        $deleteCancel = $(controls.deleteCancel),
        $deleteConfirmationBox = $(controls.deleteConfirmationBox),

        resetUIState = function () {
            if (options.resetUIState) {
                options.resetUIState();
            }
            $deleteConfirmationBox.hide();
        },

        getUrls = options.getUrls || function () {
            return {deleteUrl: document.URL,
                    afterDeleteUrl: config.instance.mapUrl};
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
