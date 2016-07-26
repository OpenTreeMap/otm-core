"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    U = require('treemap/lib/utility.js');

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
                }),
            doneClickedStream = $nextButtons.last()
                .asEventStream('click')
                .filter(isEnabled);

        stepChangeStartStream.onValue(showStep);
        doneClickedStream.onValue(function () {
            enableNext(maxStepNumber, false); // prevent double-submit
        });

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
                var i;
                for (i = 0; i < stepNumber; i++) {
                    $steps.eq(i).addClass('prev');
                }
                for (i = maxStepNumber; i > stepNumber; i--) {
                    $steps.eq(i).addClass('next');
                }
            }
            if (stepNumber === maxStepNumber) {
                // Enable "Done" button (possibly disabled by an earlier click)
                enableNext(maxStepNumber, true);
            }
        }

        function activateStep(stepNumber, shouldActivate) {
            // Assumes that the current step is earlier than stepNumber
            var $step = $steps.eq(stepNumber);
            $step.removeClass('inactive next');
            if (shouldActivate) {
                $step.addClass('next');
            } else {
                $step.addClass('inactive');
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

        function getStepNumberForElement(element) {
            var $step = $(_.find($steps, function(step) {
                return $.contains(step, element);
            }));
            if ($step.length > 0) {
                return $step.index();
            } else {
                return maxStepNumber;
            }
        }

        return {
            initialMaxStepNumber: maxStepNumber,
            maxStepNumber: maxStepNumber,
            stepChangeStartStream: stepChangeStartStream,
            stepChangeCompleteStream: stepChangeCompleteStream,
            allDoneStream: doneClickedStream,
            showStep: showStep,
            activateStep: activateStep,
            enableNext: enableNext,
            getStepNumberForElement: getStepNumberForElement
        };
    }
};
