#!/usr/bin/env fish

set -gx DOCKER_HOST "unix:///Users/italo/.colima/default/docker.sock"
python sandbox.py -w ~/dev/fleche rebuild
