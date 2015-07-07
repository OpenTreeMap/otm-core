"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    U = require('treemap/utility');

exports.init = function(options) {
    var config = options.config,
        controls = options.deleteControls,
        $delete = $(controls.delete),
        $deleteConfirm = $(controls.deleteConfirm),
        $deleteCancel = $(controls.deleteCancel),
        $deleteConfirmationBox = $(controls.deleteConfirmationBox),
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
                getPlotUrlFromTreeUrl = _.compose(U.removeLastUrlSegment,
                                                  U.removeLastUrlSegment),
                currentlyOnTreeUrl = (_.contains(
                    U.getUrlSegments(document.URL), "trees")),
                deleteUrl,
                afterDeleteUrl;

            if (currentlyOnTreeUrl &&
                treeId !== '') {
                // use this same url to delete the tree
                deleteUrl = document.URL;
                afterDeleteUrl = getPlotUrlFromTreeUrl(document.URL);
            } else if (treeId === '') {
                deleteUrl = document.URL;
                afterDeleteUrl = config.instance.mapUrl;
            } else {
                deleteUrl = 'trees/' + treeId + '/';
                afterDeleteUrl = document.URL;
            }

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
