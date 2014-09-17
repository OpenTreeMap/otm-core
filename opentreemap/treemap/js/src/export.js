"use strict";

var $ = require('jquery'),
    BU = require('treemap/baconUtils'),
    url = require('url'),
    U = require('treemap/utility'),
    _ = require('lodash'),
    Bacon = require('baconjs'),

    START_URL_ATTR = 'data-export-start-url',
    ENABLE_EXPORT_SELECTOR = '[' + START_URL_ATTR + ']',
    PANEL_SELECTOR = '#export-panel',
    CANCEL_SELECTOR = PANEL_SELECTOR + " * [data-dismiss]",

    // While there is an active job id, query the
    // check exporter end-point
    DEFAULT_INTERVAL = 2000, // 2s

    _activeJob = null,
    jobManager = {
        stop: function () { _activeJob = null; },
        start: function (jobId) { _activeJob = jobId; },
        isCurrent: function (jobId) { return _activeJob === jobId; }
    },

    config;

////////////////////////////////////////
// ajax / job mgmt
////////////////////////////////////////

function getQueryStringObject () {
    return {q: url.parse(window.location.href, true).query.q || '' };
}

function isComplete (resp) { return resp.status === 'COMPLETE'; }
function isFailed (resp) { return !_.contains(['COMPLETE', 'PENDING'], resp.status); }

function getJobStartStream (element) {
    var $element = $(element),
        elementStartUrl = $element.attr(START_URL_ATTR);
    return $element.asEventStream('click')
        .map(getQueryStringObject)
        .flatMap(BU.jsonRequest('GET', elementStartUrl));
}

function makeJobCheckStream (attrStream) {
    function poll (jobId) {
        jobManager.start(jobId);
        var url = config.exportCheckUrl + '/' + jobId + '/';
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


var RadioGroup = function(elementMap) {
    // Given a map of logical names to jquery elements
    // (such as {e1: $(...), e2: $(...)})
    //
    // return a new RadioGroup with a single method
    // show(name) that will hide all elements except
    // name
    this.show = function(elementToShow) {
        _.each(elementMap, function($thing, name) {
            if (name === elementToShow) {
                $thing.show();
            } else {
                $thing.hide();
            }
        });
    };
};

function getDisplayManager () {
    var $panel = $(PANEL_SELECTOR),
        messageRadioGroup = new RadioGroup({
            prep: $panel.find('.prep-msg'),
            err: $panel.find('.error-msg')
        }),

        dismissRadioGroup = new RadioGroup({
            cancel: $panel.find('.dismiss-cancel'),
            ok: $panel.find('.dismiss-ok')
        });

    function wait() {
        messageRadioGroup.show('prep');
        dismissRadioGroup.show('cancel');
        $panel.modal('show');
    }
    function dismiss() {
        messageRadioGroup.show('prep');
        dismissRadioGroup.show('cancel');
        $panel.modal('hide');
    }
    function error() {
        messageRadioGroup.show('err');
        dismissRadioGroup.show('ok');
        $panel.modal('show');
    }
    function fail(msg) {
        // Error response or something we can't handle
        if (msg === null || msg === '') {
            error();
        } else {
            dismissRadioGroup.show('ok');
            $panel.find('.modal-body').html(msg);
            $panel.modal('show');
        }
    }

    return {wait: wait,
            dismiss: dismiss,
            error: error,
            fail: fail};
}

exports.run = function (options) {
    config = options.config;

    var startStreams = _.map($(ENABLE_EXPORT_SELECTOR), getJobStartStream),
        startStream = Bacon.mergeAll(startStreams),
        displayManager = getDisplayManager(),
        cancelStream = $(CANCEL_SELECTOR).asEventStream('click'),
        checkStream = makeJobCheckStream(startStream.map('.job_id')),
        fileUrlStream = checkStream.filter(isComplete).map('.url'),
        checkFailureMessageStream = checkStream.filter(isFailed).map('.message'),
        normalExitStream = Bacon.mergeAll(cancelStream, fileUrlStream),
        exitStream = Bacon.mergeAll(normalExitStream, checkFailureMessageStream),
        globalStream = Bacon.mergeAll(exitStream, checkStream, startStream);

    // pass server failure message through to UI
    startStream.onError(displayManager.error);

    // start waiting when a job is initiated
    startStream.onValue(displayManager.wait);

    // an error can result from a generic javascript error
    // or a specific error condition returned by the server
    checkStream.onError(displayManager.error);
    checkFailureMessageStream.onValue(displayManager.fail);

    fileUrlStream.onValue(function (url) { window.location.href = url; });

    // dismiss the display manager when there's no error
    // to leave in the modal for acknowledgement
    normalExitStream.onValue(displayManager.dismiss);

    // clear the active job and stop polling if an error occurs
    // or a finish condition occurs
    exitStream.onValue(jobManager.stop);
    globalStream.onError(jobManager.stop);
};
