#!/usr/bin/env nu
#
# het - Hetzner Cloud snapshot workflow manager (Nushell edition)
#
# A tool for managing Hetzner Cloud server snapshots. Designed for workflows
# where you spin up temporary servers, snapshot them when done, and restore
# them later. Snapshots store metadata (original server name, type, location)
# so restores can use the same configuration.
#
# Dependencies: hcloud CLI.

const SCRIPT_VERSION = "0.3.0"
const SCRIPT_DATE = "2025-02-06"

def die [msg: string] {
    error make { msg: $"(ansi red_bold)✗ ($msg)(ansi reset)" }
}

def success [msg: string] {
    print $"(ansi green_bold)✓ ($msg)(ansi reset)"
}

def info [msg: string] {
    print $"(ansi grey)  ($msg)(ansi reset)"
}

def bold [msg: string] {
    print $"(ansi attr_bold)($msg)(ansi reset)"
}

# Run hcloud with -o json and parse the result.
def --wrapped hcloud-json [...args: string]: nothing -> any {
    ^hcloud ...$args -o json | from json
}

# Fetch all servers as structured data.
def get-servers []: nothing -> table {
    hcloud-json server list
}

# Fetch all snapshots as structured data.
def get-snapshots []: nothing -> table {
    hcloud-json image list --type snapshot
}

# Select a server by name or interactively.
def select-server [name?: string]: nothing -> string {
    let servers = get-servers | get name
    if ($servers | is-empty) { die "No servers found." }

    if $name != null {
        if $name not-in $servers { die $"Server '($name)' not found." }
        return $name
    }

    $servers | input list --fuzzy "Select server:"
}

# Select a snapshot by name or interactively.
def select-snapshot [name?: string]: nothing -> string {
    let snapshots = get-snapshots

    if $name != null {
        let found = $snapshots | where description == $name
        if ($found | is-empty) { die $"Snapshot '($name)' not found." }
        return $name
    }

    if ($snapshots | is-empty) { die "No snapshots found." }

    $snapshots | each {|s|
        if ($s.description | is-not-empty) { $s.description } else { $"id:($s.id)" }
    } | input list --fuzzy "Select snapshot:"
}

# Prompt for yes/no confirmation. Returns true if confirmed.
def confirm [prompt: string]: nothing -> bool {
    (["Yes" "No"] | input list $prompt) == "Yes"
}

# Interactively pick a server type, with the default moved to the top.
def pick-server-type [default_type: string]: nothing -> string {
    let types = (hcloud-json server-type list
        | where deprecated == false
        | select name cores memory disk description)

    let display = $types | each {|t|
        let label = [
            ($t.name | fill -w 12),
            ($t.cores | fill -a right -w 5),
            $"($t.memory | fill -a right -w 6) GB",
            $"($t.disk | fill -a right -w 6) GB",
            ($t.description)
        ] | str join
        { value: $t.name, label: $label }
    }

    let ordered = if ($default_type | is-not-empty) {
        let top = $display | where value == $default_type
        let rest = $display | where value != $default_type
        $top | append $rest
    } else {
        $display
    }

    let header = $"NAME         CORES MEMORY     DISK        DESCRIPTION  \(was: ($default_type))"
    let selected_label = $ordered | get label | input list --fuzzy $header
    if ($selected_label | is-empty) { die "Server type is required." }

    $selected_label | split words | first
}

# Interactively pick a location, with the default moved to the top.
def pick-location [default_location: string]: nothing -> string {
    let locations = hcloud-json location list | get name

    let ordered = if ($default_location | is-not-empty) {
        let top = $locations | where $it == $default_location
        let rest = $locations | where $it != $default_location
        $top | append $rest
    } else {
        $locations
    }

    $ordered | input list $"Location \(was: ($default_location)):"
}

# Interactively pick an SSH key, or return empty string.
def pick-ssh-key []: nothing -> string {
    let keys = hcloud-json ssh-key list | get name
    if ($keys | is-empty) { return "" }

    let chosen = ["(none)"] | append $keys | input list "SSH key:"
    if $chosen == "(none)" { "" } else { $chosen }
}

# Create a server from a snapshot image.
def create-server [
    name: string
    type: string
    image_id: int
    location: string
    ssh_key: string
] {
    mut args = [
        server create
            --name $name
            --type $type
            --image ($image_id | into string)
            --location $location
    ]
    if ($ssh_key | is-not-empty) {
        $args = ($args | append [--ssh-key $ssh_key])
    }
    ^hcloud ...$args
}

# Create a snapshot of a server with metadata labels.
def "main snapshot" [
    server?: string  # Server name (interactive if omitted)
] {
    check-deps

    let server = select-server $server
    if ($server | is-empty) { return }

    let server_json = hcloud-json server describe $server
    let server_type = $server_json.server_type.name
    let location = $server_json.datacenter.location.name

    let timestamp = date now | format date "%Y%m%dT%H%M%S"
    let snapshot_name = $"($server)-($timestamp)"

    info $"Creating snapshot '($snapshot_name)'..."
    try {
        (^hcloud server create-image
            --type snapshot
            --description $snapshot_name
            --label $"original-server=($server)"
            --label $"server-type=($server_type)"
            --label $"location=($location)"
            $server)
    } catch {
        die "Failed to create snapshot"
    }

    success $"Snapshot '($snapshot_name)' created"
    info $"Server type: ($server_type)"
    info $"Location: ($location)"
}

# Restore a server from a snapshot.
def "main restore" [
    snapshot?: string   # Snapshot name (interactive if omitted)
    --name (-n): string     # New server name
    --type (-t): string     # Server type (e.g., cx22)
    --location (-l): string # Location (e.g., fsn1)
    --ssh-key (-k): string  # SSH key name
] {
    check-deps

    let snap = select-snapshot $snapshot
    if ($snap | is-empty) { return }

    let snap_row = get-snapshots | where description == $snap | first
    let snap_id = $snap_row.id
    let default_server = $snap_row.labels | get -o "original-server" | default ""
    let default_type = $snap_row.labels | get -o "server-type" | default ""
    let default_location = $snap_row.labels | get -o "location" | default ""

    bold $"Restoring from: ($snap)"
    if ($default_server | is-not-empty) {
        info $"Original: ($default_server) \(($default_type) @ ($default_location))"
    }
    print ""

    # Server name
    let server_name = if $name != null { $name } else {
        input $"Server name [($default_server)]: "
            | str trim
            | if ($in | is-empty) { $default_server } else { $in }
    }
    if ($server_name | is-empty) { die "Server name is required." }

    let exists = try {
        hcloud-json server describe $server_name | ignore; true
    } catch {
        false
    }
    if $exists { die $"Server '($server_name)' already exists." }

    # Server type
    let server_type = if $type != null { $type } else { pick-server-type $default_type }
    if ($server_type | is-empty) { die "Server type is required." }

    # Location
    let location_val = if $location != null { $location } else { pick-location $default_location }
    if ($location_val | is-empty) { die "Location is required." }

    # SSH key
    let ssh_key_val = if $ssh_key != null { $ssh_key } else { pick-ssh-key }

    # Create server
    info $"Creating server '($server_name)'..."
    try {
        create-server $server_name $server_type $snap_id $location_val $ssh_key_val
    } catch {
        die "Failed to create server"
    }

    success $"Server '($server_name)' created"
    info $"Type: ($server_type)"
    info $"Location: ($location_val)"
    if ($ssh_key_val | is-not-empty) { info $"SSH key: ($ssh_key_val)" }

    let ipv4 = (hcloud-json server describe $server_name
        | get -o public_net.ipv4.ip
        | default "")
    if ($ipv4 | is-not-empty) { info $"IPv4: ($ipv4)" }
}

# Destroy a server, optionally creating a snapshot first.
def "main destroy" [
    server?: string      # Server name (interactive if omitted)
    --no-snapshot        # Skip snapshot prompt
] {
    check-deps

    let server = select-server $server
    if ($server | is-empty) { return }

    if not $no_snapshot {
        if (confirm $"Create snapshot of '($server)' before destroying?") {
            main snapshot $server
            print ""
        }
    }

    if not (confirm $"Destroy server '($server)'? This cannot be undone.") {
        info "Aborted."
        return
    }

    info $"Destroying '($server)'..."
    try {
        ^hcloud server delete $server
    } catch {
        die "Failed to destroy server"
    }

    success $"Server '($server)' destroyed"
}

# List all snapshots with metadata.
def "main list" [] {
    check-deps

    let snapshots = get-snapshots

    if ($snapshots | is-empty) {
        info "No snapshots found."
        return
    }

    $snapshots | each {|s|
        let name = if ($s.description | is-not-empty) { $s.description } else { $"id:($s.id)" }
        {
            NAME: ($name | str substring 0..40)
            ID: $s.id
            SIZE: $"(($s | get -o image_size | default 0) | math round --precision 1) GB"
            SERVER: ($s.labels | get -o "original-server" | default "-")
            TYPE: ($s.labels | get -o "server-type" | default "-")
            LOC: ($s.labels | get -o "location" | default "-")
            CREATED: $s.created
        }
    } | table
}

# Delete one or more snapshots.
def "main clean" [
    ...snapshots: string  # Snapshot names (multiselect interactive if omitted)
] {
    check-deps

    let all_snaps = get-snapshots

    let selected = if ($snapshots | is-not-empty) {
        let missing = $snapshots | where {
            |name| $all_snaps | where description == $name | is-empty
        }
        if ($missing | is-not-empty) {
            die $"Snapshot\(s) not found: ($missing | str join ', ')"
        }
        $snapshots
    } else {
        if ($all_snaps | is-empty) { die "No snapshots found." }

        let names = $all_snaps | each {|s|
            if ($s.description | is-not-empty) { $s.description } else { $"id:($s.id)" }
        }

        let chosen = $names
            | input list --multi "Select snapshots (space to select, enter to confirm):"

        if ($chosen | is-empty) {
            info "No snapshots selected."
            return
        }
        $chosen
    }

    # Show what will be deleted
    bold "Snapshots to delete:"
    for s in $selected { info $s }
    print ""

    let count = $selected | length
    if not (confirm $"Delete ($count) snapshot\(s)? This cannot be undone.") {
        info "Aborted."
        return
    }

    for snap_name in $selected {
        let snap_id = $all_snaps
            | where description == $snap_name
            | first
            | get id

        info $"Deleting snapshot '($snap_name)'..."
        try {
            ^hcloud image delete ($snap_id | into string)
        } catch {
            die $"Failed to delete snapshot '($snap_name)'"
        }

        success $"Snapshot '($snap_name)' deleted"
    }
}

# Check that hcloud is available.
def check-deps [] {
    if (which hcloud | is-empty) {
        error make {
            msg: ([
                "Error: 'hcloud' CLI is required but not installed."
                "Install it from: https://github.com/hetznercloud/cli"
            ] | str join "\n")
        }
    }
}

# Hetzner Cloud snapshot workflow manager.
def main [
    --version (-V)  # Show version
] {
    if $version {
        print $"het ($SCRIPT_VERSION) \(($SCRIPT_DATE))"
        return
    }

    check-deps
    help main
}
