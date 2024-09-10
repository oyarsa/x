#!/usr/bin/env fish
# Gets the venue of each paper in the gzipped data files and prints the unique ones.
# Files come from the ./download_s2orc.py script, saved in the `data` directory.
fd -HI -ejson.gz . data -x sh -c 'gzip -dc {} |  jq -r \'map(.venue)[]\'' |
    string trim | string lower | sort -u
