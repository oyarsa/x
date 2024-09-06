#!/usr/bin/env fish

if test (count $argv) -ne 1
    echo "Usage: $(basename (status -f)) <url>"
    exit 1
end

set url $argv[1]
curl -s $url | python titles.py | glow -p
