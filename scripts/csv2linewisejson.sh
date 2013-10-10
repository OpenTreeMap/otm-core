#!/bin/bash
# usage: pipe in a csv, get linewise json on stdout
# requires csvkit - http://csvkit.readthedocs.org/en/latest/

csvjson < /dev/stdin | sed 's/\[/\[\n/g' | sed 's/}, /},\n/g' | sed 's/\]/\n\]/g'
