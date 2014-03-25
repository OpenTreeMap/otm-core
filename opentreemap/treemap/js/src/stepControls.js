"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    U = require('treemap/utility');

module.exports = {
    init: function ($container) {
        var $steps = U.$find('.add-step', $container),
            maxStepNumber = $steps.length - 1,
            $nextButtons = U.$find('.next', $steps),
            $prevButtons = U.$find('.previous', $steps),
            stepChangeStartStream = Bacon.mergeAll(
                $nextButtons.asEventStream('click')
                    .filter(isEnabled)
                    .map(getNextStepNumber),
                $prevButtons.asEventStream('click')
                    .filter(isEnabled)
                    .map(getPrevStepNumber)
            ),
            stepChangeCompleteStream = $steps.asEventStream('transitionend webkitTransitionEnd')
                .filter(function (e) {
                    return $(e.target).hasClass('active');
                })
                .map(function (e) {
                    return $(e.target).index();
                });

        stepChangeStartStream.onValue(showStep);

        function isEnabled(e) {
            return !$(e.target).closest('li').hasClass('disabled');
        }

        function getNextStepNumber(e) {
            return getStepNumber(e.target, function (n) { return n + 1; });
        }

        function getPrevStepNumber(e) {
            return getStepNumber(e.target, function (n) { return n - 1; });
        }

        function getStepNumber(button, getNextInSequence) {
            var stepNumber = $(button).closest('.add-step').index();
            do {
                stepNumber = getNextInSequence(stepNumber);
            } while ($steps.eq(stepNumber).hasClass('inactive'));
            return stepNumber;
        }

        function showStep(stepNumber) {
            if (stepNumber <= maxStepNumber) {
                $steps.removeClass('active next prev');
                $steps.eq(stepNumber).addClass('active');
                for (var i = 0; i < stepNumber; i++) {
                    $steps.eq(i).addClass('prev');
                }
                for (var i = maxStepNumber; i > stepNumber; i--) {
                    $steps.eq(i).addClass('next');
                }
            }
        }

        function activateStep(stepNumber, shouldActivate) {
            // Assumes that the current step is earlier than stepNumber
            var $step = $steps.eq(stepNumber);
            $step.removeClass('inactive next');
            if (shouldActivate) {
                $step.addClass('next')
            } else {
                $step.addClass('inactive')
            }
        }

        function enableNext(stepNumber, shouldEnable) {
            var $next = $nextButtons.eq(stepNumber);
            if (shouldEnable) {
                $next.removeClass('disabled');
            } else {
                $next.addClass('disabled');
            }
        }

        return {
            maxStepNumber: maxStepNumber,
            stepChangeStartStream: stepChangeStartStream,
            stepChangeCompleteStream: stepChangeCompleteStream,
            allDoneStream: $nextButtons.last().asEventStream('click'),
            showStep: showStep,
            activateStep: activateStep,
            enableNext: enableNext
        };
    }
};
