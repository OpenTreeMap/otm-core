"use strict";

var commentModeration = require('otm_comments/lib/moderation.js'),
    adminPage = require('manage_treemap/lib/adminPage.js');

var updateStream = commentModeration({container: '#comment-moderation'});
adminPage.init(updateStream);
