"use strict";

var $ = require('jquery'),
    _ = require('underscore'),

exports.init = function(options) {
    var config = options.config,
        $delete = $(options.delete),
        $deleteConfirm = $(options.deleteConfirm),
        $deleteCancel = $(options.deleteCancel),
        $deleteConfirmationBox = $(options.deleteConfirmationBox),
        plotId = $('div[data-field="plot.id"]').attr('data-value'),

        // tree id is the sole datapoint used to determine the state
        // of the plot to be acted upon. this information is used for:
        // * deciding which warning message to show
        // * The url to post a delete verb to
        // * the url to redirect to
        getTreeId = function () {
            return $(options.treeIdColumn).attr('data-tree-id');
        },
        
        // query whether a tree exists and
        // show or hide the plot/tree warning
        // finally, hide the whole containing box
        resetUIState = function () {
            if (getTreeId() === '') {
                $('#delete-plot-warning').show();
                $('#delete-tree-warning').hide();
            } else {
                $('#delete-tree-warning').show();
                $('#delete-plot-warning').hide();
            }
            $deleteConfirmationBox.hide();
        },

        // sends the appropriate deletion request to the server based on
        // the treeId value, then redirects to the correct page after
        // receiving a response. Tree deletions redirect back to plot detail,
        // plot deletions redirect to the map page.
        executeServerDelete = function () {
            var treeId = getTreeId(),
                deleteUrlBase = '',
                deleteUrl = treeId === '' ? deleteUrlBase :
                    deleteUrlBase + 'trees/' + treeId + '/',
                afterDeleteUrl = treeId === '' ? config.instance.mapUrl : '';

            $.ajax({
                url: deleteUrl,
                type: 'DELETE',
                success: function () {
                    window.location = afterDeleteUrl; 
                }
            });
        };

    // events
    $deleteConfirm.click(executeServerDelete);
    $deleteCancel.click(resetUIState);
    $delete.click(function () { 
        resetUIState();
        $deleteConfirmationBox.show(); 
    });
};
