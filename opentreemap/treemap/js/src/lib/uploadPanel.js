// Manage panel for file uploading
"use strict";

var $ = require('jquery'),
    toastr = require('toastr'),
    Bacon = require('baconjs'),
    U = require('treemap/lib/utility.js'),
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

        $chooser = $panel.find('.fileChooser'),
        $progressBar = $panel.find('.progress').children().first(),
        callback,
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

            if (callback) {
                // Downstream users will be opening modals, which leads to
                // style errors if that is done before a modal closes
                $panel.one('hidden.bs.modal', function() {
                    callback(new Bacon.Next({event: e, data: data}));
                });
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
