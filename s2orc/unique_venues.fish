#!/usr/bin/env fish
# Gets the venue of each paper in the gzipped data files and prints the unique ones.
# Files come from the ./download_s2orc.py script
for f in $argv
    gzip -dc $f | jq -r 'map(.venue | ascii_downcase)[]'
end | sort -u
