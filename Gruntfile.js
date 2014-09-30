"use strict";

var path = require('path');

module.exports = function(grunt) {
    var debug = typeof grunt.option('dev') !== "undefined";
    var noLint = typeof grunt.option('nolint') !== "undefined";

    var appBundlePath = 'treemap/static/js/treemap.js';
    var testBundlePath = 'treemap/static/js/treemap.test.js';

    grunt.loadNpmTasks('grunt-browserify');
    grunt.loadNpmTasks('grunt-contrib-jshint');
    grunt.loadNpmTasks('grunt-contrib-uglify');
    grunt.loadNpmTasks('grunt-sass');
    grunt.loadNpmTasks('grunt-contrib-concat');
    grunt.loadNpmTasks('grunt-contrib-cssmin');
    grunt.loadNpmTasks('grunt-file-creator');
    grunt.loadNpmTasks('grunt-contrib-watch');
    grunt.loadNpmTasks('grunt-shell');

    grunt.file.setBase('opentreemap');

    grunt.registerTask('check', ['jshint']);
    grunt.registerTask('js', debug ? ['browserify', 'file-creator'] : ['browserify', 'uglify']);
    grunt.registerTask('css', debug ? ['sass', 'concat'] : ['sass', 'concat', 'cssmin']);
    grunt.registerTask('default', ['js', 'css']);

    /*
     * Maps all src/*.js files by their Django app name.
     * Makes it easy to use treemap JS modules from other Django apps
     */
    function getSrcAliases() { return getAliases('src'); }
    function getTestAliases() { return getAliases('test'); }
    function getLibAliases() { return getAliases('lib'); }
    function getRegularAliases() {
        return getAliases('src').concat(getAliases('lib'));
    }

    function getAliases(type) {
        if (type !== 'src' && type !== 'test' && type !== 'lib') {
            throw new Error('type argument must be src, test, or lib');
        }
        var files = grunt.file.expand('*/js/' + type + '/*.js');
        return files.map(function(filename) {
            var basename = path.basename(filename, '.js'),
                app = filename.split(path.sep)[0],
                prefix = type === 'src' ? '' : (type + '/');
            return filename + ':' + app + '/' + prefix + basename;
        });
    }

    function getSrcAliasNames() {
        return getAliasNames(getSrcAliases());
    }

    function getLibAliasNames() {
        return getAliasNames(getLibAliases());
    }

    function getRegularAliasNames() {
        return getSrcAliasNames().concat(getLibAliasNames());
    }

    function getTestAliasNames() {
        return getAliasNames(getTestAliases());
    }

    function getAliasNames(aliases) {
        return aliases.map(function(alias){
            return alias.split(':')[1];
        });
    }

    function getAliasFiles(aliases) {
        return aliases.map(function(alias) {
            return alias.split(':')[0];
        });
    }

    grunt.initConfig({
        'file-creator': {
            test: {
                'treemap/static/js/testModules.js': function(fs, fd, done) {
                    fs.writeSync(fd, 'TEST_MODULES = ["' + getTestAliasNames().join('","') + '"];');
                    done();
                }
            }
        },
        watch: {
            js: {
                files: getAliasFiles(getRegularAliases()),
                tasks: noLint ? ['shell:collect_static'] : ['check', 'shell:collect_static']
            },
            css: {
                files: 'treemap/css/sass/**/*.scss',
                tasks: ['shell:collect_static']
            },
            lint: {
                files: [].concat(
                    getAliasFiles(getSrcAliases()),
                    getAliasFiles(getTestAliases())
                ),
                tasks: ['check']
            }
        },
        shell: {
            collect_static: {
                command: 'fab vagrant static:dev'
            }
        },
        browserify: {
            test: {
                src: ['./treemap/js/test/**/*.js'],
                dest: testBundlePath,
                options: {
                    alias: getTestAliases(),
                    external: getRegularAliasNames(),
                    aliasMappings: { // Make libs available to test functions
                        cwd:'treemap/js/lib/',
                        src: ['*.js'],
                        dest: '',
                        ext: '',
                        flatten: true
                    }
                    // setting debug: true causes tests to not be found
                }
            },
            treemap: {
                src: [],
                dest: appBundlePath,
                options: {
                    alias: getRegularAliases(),
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
                        leafletEditablePolyline: {
                            path: './treemap/js/shim/leaflet-editable-polyline.js',
                            exports: null,
                            depends: { leaflet: 'L' }
                        },
                        bloodhound: {
                            path: './treemap/js/shim/bloodhound.js',
                            exports: 'Bloodhound',
                            depends: { jquery: 'jQuery' }
                        },
                        // BEGIN modules which add themselves to the jQuery object
                        typeahead: {
                            path: './treemap/js/shim/typeahead.jquery.js',
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
                        "bootstrap-datepicker": {
                            path: './treemap/js/shim/bootstrap-datepicker.js',
                            exports: null,
                            depends: { jquery: 'jQuery', bootstrap: 'bootstrap' }
                        },
                        "bootstrap-slider": {
                            path: './treemap/js/shim/bootstrap-slider.js',
                            exports: null,
                            depends: { jquery: 'jQuery', bootstrap: 'bootstrap' }
                        },
                        // END modules which add themselves to the jQuery object
                        jscolor: {
                            path: './treemap/js/shim/jscolor.js',
                            exports: null
                        },
                        history: {
                            path: './treemap/js/shim/native.history.js',
                            exports: 'History'
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
            treemap: ['../Gruntfile.js', '*/js/src/**/*.js'],
            tests: getAliasFiles(getTestAliases())
        },
        uglify: {
            options: {
                mangle: {
                    except: ['require', 'google']
                }
            },
            treemap: {
                files: {
                    'treemap/static/js/treemap.min.js': [appBundlePath]
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
                      'treemap/css/vendor/bootstrap-lightbox.css',
                      'treemap/css/vendor/bootstrap-slider.css',
                      'treemap/css/vendor/datepicker.css',
                      'treemap/css/vendor/fontello.css',
                      'treemap/css/vendor/toastr.css',
                      'treemap/css/vendor/leaflet.css',
                      'treemap/css/vendor/leaflet.draw.css'],
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
