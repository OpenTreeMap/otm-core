module.exports = function(grunt) {
    "use strict";

    var debug = typeof grunt.option('dev') !== "undefined";

    grunt.loadNpmTasks('grunt-browserify');
    grunt.loadNpmTasks('grunt-contrib-jshint');
    grunt.loadNpmTasks('grunt-contrib-uglify');
    grunt.loadNpmTasks('grunt-sass');
    grunt.loadNpmTasks('grunt-contrib-concat');
    grunt.loadNpmTasks('grunt-contrib-cssmin');
    grunt.file.setBase('opentreemap');

    grunt.registerTask('check', ['jshint']);
    grunt.registerTask('js', debug ? ['browserify'] : ['browserify', 'uglify']);
    grunt.registerTask('css', debug ? ['sass', 'concat'] : ['sass', 'concat', 'cssmin']);
    grunt.registerTask('default', ['js', 'css']);

    /*
     * Reads the extra.json file which should be a dictionary
     * where the keys are the require.js alias and the values
     * are the path to a file, relative to `opentreemap`
     */
    function getAliases() {
        var aliases = ['treemap/js/src/alerts.js:alerts',
                       'treemap/js/src/baconUtils.js:BaconUtils',
                       'treemap/js/src/buttonEnabler.js:buttonEnabler',
                       'treemap/js/src/csrf.js:csrf',
                       'treemap/js/src/export.js:export',
                       'treemap/js/src/geocoder.js:geocoder',
                       'treemap/js/src/geocoderUi.js:geocoderUi',
                       'treemap/js/src/imageUploadPanel.js:imageUploadPanel',
                       'treemap/js/src/inlineEditForm.js:inlineEditForm',
                       'treemap/js/src/map.js:map',
                       'treemap/js/src/mapManager.js:mapManager',
                       'treemap/js/src/photoReview.js:photoReview',
                       'treemap/js/src/plot.js:plot',
                       'treemap/js/src/searchBar.js:searchBar',
                       'treemap/js/src/user.js:user',
                       'treemap/js/src/utility.js:utility'];

        var extras = require('./extra.json');
        for (var alias in extras) {
            var filepath = extras[alias];
            if (grunt.file.exists(filepath)) {
                aliases.push(filepath + ':' + alias);
            }
        }
        return aliases;
    }

    grunt.initConfig({
        browserify: {
            treemap: {
                src: [],
                dest: 'treemap/static/js/treemap.js',
                options: {
                    alias: getAliases(),
                    aliasMappings: {
                        cwd:'treemap/js/lib/',
                        src: ['*.js'],
                        dest: '',
                        ext: '',
                        flatten: true
                    },
                    noParse: grunt.file.expand('*/js/lib/*.js'),
                    shim: {
                        leafletgoogle: {
                            path: './treemap/js/shim/leaflet.google.js',
                            exports: null,
                            depends: { leaflet: 'L' }
                        },
                        leafletbing: {
                            path: './treemap/js/shim/leaflet.bing.js',
                            exports: null,
                            depends: { leaflet: 'L' }
                        },
                        utfgrid: {
                            path: './treemap/js/shim/leaflet.utfgrid.js',
                            exports: null,
                            depends: { leaflet: 'L' }
                        },
                        // BEGIN modules which add themselves to the jQuery object
                        typeahead: {
                            path: './treemap/js/shim/typeahead.js',
                            exports: null,
                            depends: { jquery: 'jQuery' }
                        },
                        bootstrap: {
                            path: './treemap/js/shim/bootstrap.js',
                            exports: null,
                            depends: { jquery: 'jQuery' }
                        },
                        jqueryFileUpload: {
                            path: './treemap/js/shim/jquery.fileupload.js',
                            exports: null,
                            depends: { jquery: 'jQuery' }
                        },
                        jqueryIframeTransport: {
                            path: './treemap/js/shim/jquery.iframe-transport.js',
                            exports: null,
                            depends: { jquery: 'jQuery' }
                        },
                        jqueryUiWidget: {
                            path: './treemap/js/shim/jquery.ui.widget.js',
                            exports: null,
                            depends: { jquery: 'jQuery' }
                        },
                        // END modules which add themselves to the jQuery object
                        jscolor: {
                            path: './treemap/js/shim/jscolor.js',
                            exports: null
                        },
                        // Bootstrap-datepicker puts itself onto the jQuery object
                        "bootstrap-datepicker": {
                            path: './treemap/js/shim/bootstrap-datepicker.js',
                            exports: null,
                            depends: { jquery: 'jQuery', bootstrap: 'bootstrap' }
                        }
                    },
                    debug: debug
                }
            }
        },
        jshint: {
            options: {
                jshintrc: "../.jshintrc"
            },
            treemap: ['../Gruntfile.js', '*/js/src/**/*.js']
        },
        uglify: {
            options: {
                mangle: {
                    except: ['require', 'google']
                }
            },
            treemap: {
                files: {
                    'treemap/static/js/treemap.min.js': ['treemap/static/js/treemap.js']
                }
            }
        },
        sass: {
            treemap: {
                options: {
                    includePaths: ['treemap/css/sass/']
                },
                files: {
                    'treemap/static/css/main.css': 'treemap/css/sass/main.scss'
                }
            }
        },
        concat: {
            treemap: {
                src: ['treemap/css/vendor/bootstrap.css',
                      'treemap/css/vendor/bootstrap-responsive.css',
                      'treemap/css/vendor/datepicker.css',
                      'treemap/css/vendor/fontello.css',
                      'treemap/css/vendor/toastr.css',
                      'treemap/css/vendor/leaflet.css'],
                dest: 'treemap/static/css/vendor.css'
            }
        },
        cssmin: {
            treemap: {
                files: {
                    'treemap/static/css/vendor.min.css': ['treemap/static/css/vendor.css'],
                    'treemap/static/css/main.min.css': ['treemap/static/css/main.css']
                }
            }
        }
    });
};
