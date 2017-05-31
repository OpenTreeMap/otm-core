"use strict";

var adminPage = require('manage_treemap/lib/adminPage.js');

var updateStream = require('manage_treemap/lib/photoReview.js').init({
       tab: 'a[href="#photo-review"]',
       container: '#photo-review',
   });
adminPage.init(updateStream);
