// Manage panel for file uploading
"use strict";

var $ = require('jquery'),
    toastr = require('toastr'),
    Bacon = require('baconjs'),
    U = require('treemap/lib/utility.js'),
    reverse = require('reverse'),
    _ = require('lodash'),
    config = require('treemap/lib/config.js');

// For modal dialog on jquery
require('bootstrap');

// jQuery-File-Upload and its dependencies
require('jqueryIframeTransport');
require('jqueryFileUpload');


module.exports.init = function(options) {
    options = options || {};
    var $panel = $(options.panelId || '#upload-panel'),
        $image = $(options.imageElement),
        $error = $(options.error || '.js-upload-error'),
        dataType = options.dataType || 'json',
        addMapFeatureBus = options.addMapFeatureBus,

        $chooser = $panel.find('.fileChooser'),
        $progressBar = $panel.find('.progress').children().first(),
        callback,
        unsubscribeFromAdd = $.noop,
        finishedStream = new Bacon.EventStream(function(subscribe) {
            callback = subscribe;

            return function() {
                callback = null;
            };
        });

    var fileupload = $chooser.fileupload({
        dataType: dataType,
        start: function () {
            $error.hide();
        },
        add: function(e, data) {
            unsubscribeFromAdd();

            // keep track of this for visibility

            var input = $(this).closest(".fileChooser");
            var row = $(input.data('row-id'));

            // once we finish adding the tree, we can use that
            // result to send the photo and label
            unsubscribeFromAdd = addMapFeatureBus.onValue(function (result) {
                var label = input.data('label');

                // either we have an empty site, so we want to use the empty site photo
                // or we don't have an empty site and we want every other photo
                var isEmptySite = !result.feature.has_tree;

                var callback_data = {};

                var url = null;
                if (isEmptySite && label == 'empty site') {

                    url = reverse.Urls.add_photo_to_map_feature({
                        instance_url_name: config.instance.url_name,
                        feature_id: result.featureId,
                    });
                    callback_data['feature_id'] = result.featureId;

                } else if (!isEmptySite && label != 'empty site') {

                    url = reverse.Urls.add_photo_to_tree_with_label({
                        instance_url_name: config.instance.url_name,
                        feature_id: result.featureId,
                        tree_id: result.treeId
                    });
                    callback_data['feature_id'] = result.featureId;
                    callback_data['tree_id'] = result.treeId;
                }
                // this handles the case of a tree photo that might accidentally be added
                // on an empty site
                else {
                    return;
                }

                data.formData = {'label': label}
                data.url = url;

                // push to the stream once this is done uploading
                callback_data['label'] = label;
                data.submit().done(function(e) {
                    callback(new Bacon.Next(callback_data));
                });
            });
            row.addClass('bg-success')

            $(input.data('checkbox-id')).prop('checked', true);
            $panel.modal('hide');
        },
        progressall: function (e, data) {
            var progress = parseInt(data.loaded / data.total * 100, 10);
            $progressBar.width(progress + '%');
        },
        always: function (e, data) {
            $progressBar.width('0%');
        },
        done: function (e, data) {
            $panel.modal('hide');
            if ($image.length > 0) {
                $image.attr('src', data.result.url);
            }

            // clear everything
            var input = $(this).closest(".fileChooser");
            var row = $(input.data('row-id'));
            row.removeClass('bg-success')

            $(input.data('checkbox-id')).prop('checked', false);
            data.files = [];
            unsubscribeFromAdd();

            if (callback) {
                // Downstream users will be opening modals, which leads to
                // style errors if that is done before a modal closes
                //callback(new Bacon.Next({event: e, data: data}));
                //$panel.one('hidden.bs.modal', function() {
                //    callback(new Bacon.Next({event: e, data: data}));
                //});
            }
        },
        fail: function (e, data) {
            // If the datatype is not JSON we expect the endpoint to return
            // error messages inside the HTML fragment it gives back
            if (dataType == 'json') {
                var json = data.jqXHR.responseJSON,
                    message;

                if (json && json.error) {
                    U.warnDeprecatedErrorMessage(json);
                    message = json.error;
                } else if (json && json.globalErrors) {
                    message = json.globalErrors.join(',');
                } else {
                    message = "Upload failed";
                }
                $error.text(message).show();
            }
        }
    });

    fileupload.on('fileuploadadd', function(e, data) {
        data.process(function() {
            var defer = $.Deferred();
            _.each(data.files, function(file) {
                if (file.size >= options.maxImageSize) {
                    var mb = options.maxImageSize / 1024 / 1024,
                        message = config.trans.fileExceedsMaximumFileSize
                            .replace('{0}', file.name)
                            .replace('{1}', mb + ' MB');
                    toastr.error(message);
                    defer.reject([data]);
                }
            });
            defer.resolve([data]);
            return defer.promise();
        });
    });

    $panel.on('hidden.bs.modal', function() {
        $error.hide();
    });

    return finishedStream;
};
