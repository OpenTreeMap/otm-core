#!/bin/bash
python opentreemap/manage.py collectstatic_js_reverse
npm run build-profile
python opentreemap/manage.py collectstatic --noinput
