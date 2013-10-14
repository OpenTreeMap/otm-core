// Manage panel for image uploading

"use strict";

// For modal dialog on jquery
require('bootstrap');

var $ = require('jquery'),
    Bacon = require('baconjs');

// jQuery-File-Upload and its dependencies
require('jqueryUiWidget');
require('jqueryIframeTransport');
require('jqueryFileUpload');

module.exports.init = function(options) {
    var $panel = $(options.panelId),
        $chooser = $panel.find('.fileChooser'),
        $progressBar = $panel.find('.progress').children().first(),
        $image = $(options.imageElement),
        $error = $(options.error),
        callback,
        finishedStream = new Bacon.EventStream(function(subscribe) {
            callback = subscribe;

            return function() { callback = null; };
        });

    $chooser.fileupload({
        dataType: 'json',
        start: function () {
            $error.hide();
        },
        progressall: function (e, data) {
            var progress = parseInt(data.loaded / data.total * 100, 10);
            $progressBar.width(progress + '%');
        },
        always: function (e, data) {
            $panel.modal('hide');
            $progressBar.width('0%');
        },
        done: function (e, data) {
            if ($image.length > 0) {
                $image.attr('src', data.result.url);
            }

            if (callback) {
                callback(new Bacon.Next(e));
            }
        },
        fail: function (e, data) {
            var json = data.jqXHR.responseJSON,
                message = (json && json.error ? json.error : "Unable to upload image");
            $error.text(message).show();
        }
    });

    return finishedStream;
};
