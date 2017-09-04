"use strict";

var $ = require('jquery'),
    BU = require('treemap/lib/baconUtils.js'),
    url = require('url'),
    U = require('treemap/lib/utility.js'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    reverse = require('reverse'),
    config = require('treemap/lib/config.js'),

    START_URL_ATTR = 'data-export-start-url',
    ENABLE_EXPORT_SELECTOR = '[' + START_URL_ATTR + ']',
    PANEL_SELECTOR = '#export-panel',
    PREP_LABEL_SELECTOR = PANEL_SELECTOR + " .prep-msg",
    ERROR_LABEL_SELECTOR = PANEL_SELECTOR + " .error-msg",
    BUTTON_SELECTOR = PANEL_SELECTOR + " * [data-dismiss]",
    CANCEL_BUTTON_SELECTOR = PANEL_SELECTOR + " .dismiss-cancel",
    OK_BUTTON_SELECTOR = PANEL_SELECTOR + " .dismiss-ok",

    // While there is an active job id, query the
    // check exporter end-point
    DEFAULT_INTERVAL = 2000, // 2s

    _activeJob = null,
    jobManager = {
        stop: function () { _activeJob = null; },
        start: function (jobId) { _activeJob = jobId; },
        isCurrent: function (jobId) { return _activeJob === jobId; }
    };

////////////////////////////////////////
// ajax / job mgmt
////////////////////////////////////////

function getQueryStringObject () {
    var query = url.parse(window.location.href, true).query;
    return {
        q: query.q || '',
        show: query.show || ''
    };
}

function isComplete (resp) { return resp.status === 'COMPLETE'; }
function isFailed (resp) { return !_.includes(['COMPLETE', 'PENDING'], resp.status); }
function startFailed(resp) { return resp.start_status === 'ERROR'; }

function getJobStartStream () {
    // Some exportable links are added to the page dynamically with AJAX
    // Rather than explicitly re-initing this module each time that happens,
    // we use a single delegated event on 'body'
    return $('body').asEventStream('click', ENABLE_EXPORT_SELECTOR)
        .flatMap(function(e) {
            var elementStartUrl = $(e.target).attr(START_URL_ATTR),
                queryStringObject = getQueryStringObject();

            return Bacon.fromPromise($.ajax({
                method: 'GET',
                url: elementStartUrl,
                contentType: 'application/json',
                data: queryStringObject
            }));
        });
}

function makeJobCheckStream (attrStream) {
    function poll (jobId) {
        jobManager.start(jobId);
        var url = reverse.check_export({
            instance_url_name: config.instance.url_name,
            job_id: jobId
        });
        return Bacon.fromPoll(DEFAULT_INTERVAL, function() {
            return jobManager.isCurrent(jobId) ?
                BU.jsonRequest('GET', url)() : new Bacon.End();
        });
    }
    // because poll has a type of (a -> Stream a) and
    // so does Bacon.fromPromise which is called implicitly,
    // this stream has to be unboxed twice to produce a flat
    // stream of json responses.
    return attrStream.flatMap(poll).flatMap(_.identity);
}

////////////////////////////////////////
// ui
////////////////////////////////////////


function getDisplayManager (defaultErrorMessage) {
    var $panel = $(PANEL_SELECTOR),
        $prepLabel = $(PREP_LABEL_SELECTOR),
        $errorLabel = $(ERROR_LABEL_SELECTOR),
        $cancel = $(CANCEL_BUTTON_SELECTOR),
        $ok = $(OK_BUTTON_SELECTOR);

    function hideInnerElements() {
        $prepLabel.hide();
        $errorLabel.hide();
        $cancel.hide();
        $ok.hide();
    }

    function wait() {
        hideInnerElements();
        $prepLabel.show();
        $cancel.show();
        $panel.modal('show');
    }
    function dismiss() {
        hideInnerElements();
        $panel.modal('hide');
    }
    function fail(msg) {
        if (msg === null || msg === '' || !_.isString(msg)) {
            msg = defaultErrorMessage;
        }
        hideInnerElements();
        $errorLabel.html(msg);
        $errorLabel.show();
        $ok.show();
        $panel.modal('show');
    }

    return {wait: wait,
            dismiss: dismiss,
            fail: fail};
}

exports.run = function (options) {
    var startStream = getJobStartStream(),
        defaultErrorMessage = $(ERROR_LABEL_SELECTOR).html(),
        displayManager = getDisplayManager(defaultErrorMessage),
        cancelStream = $(BUTTON_SELECTOR).asEventStream('click'),
        checkStream = makeJobCheckStream(startStream.map('.job_id')),
        fileUrlStream = checkStream.filter(isComplete).map('.url'),
        failureMessageStream = Bacon.mergeAll(
                checkStream.filter(isFailed), startStream.filter(startFailed))
            .map('.message'),
        normalExitStream = Bacon.mergeAll(cancelStream, fileUrlStream),
        exitStream = Bacon.mergeAll(normalExitStream, failureMessageStream),
        globalStream = Bacon.mergeAll(exitStream, checkStream, startStream);

    // start waiting when a job is initiated
    startStream.onValue(displayManager.wait);

    // handle errors
    globalStream.onError(jobManager.stop);
    globalStream.onError(displayManager.fail);
    failureMessageStream.onValue(displayManager.fail);

    // normal exit cleanup
    normalExitStream.onValue(displayManager.dismiss);
    fileUrlStream.onValue(function (url) { window.location.href = url; });
    exitStream.onValue(jobManager.stop);
};
