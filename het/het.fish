#!/usr/bin/env fish
#
# Hetzner Cloud snapshot workflow manager.
#
# Commands:
#   snapshot <server>  - Create a snapshot of a server
#   restore <snapshot> - Restore a server from a snapshot
#   destroy <server>   - Destroy a server (optionally snapshot first)
#   clean <snapshot>   - Delete a snapshot
#   list               - List all snapshots with metadata

set -g script_name (basename (status filename))
set -g script_version "0.2.0"
set -g script_date 2025-01-31

function die
    gum style --foreground 196 --bold "✗ $argv"
    exit 1
end

function success
    gum style --foreground 82 --bold "✓ $argv"
end

function info
    gum style --foreground 245 "  $argv"
end

function get_server_names
    hcloud server list -o json | jq -r '.[].name'
end

function get_snapshot_names
    hcloud image list --type snapshot -o json | jq -r '.[].description // "id:\(.[].id)"'
end

function select_server
    set -l name $argv[1]
    if test -n "$name"
        if not hcloud server describe "$name" -o json >/dev/null 2>&1
            die "Server '$name' not found."
        end
        echo $name
        return
    end

    set -l servers (get_server_names)
    if test -z "$servers"
        die "No servers found."
    end
    printf '%s\n' $servers | gum filter --placeholder "Select server..."
end

function select_snapshot
    set -l name $argv[1]
    if test -n "$name"
        set -l id (hcloud image list --type snapshot -o json | jq -r ".[] | select(.description == \"$name\") | .id")
        if test -z "$id"
            die "Snapshot '$name' not found."
        end
        echo $name
        return
    end

    set -l snapshots (get_snapshot_names)
    if test -z "$snapshots"
        die "No snapshots found."
    end
    printf '%s\n' $snapshots | gum filter --placeholder "Select snapshot..."
end

function cmd_snapshot
    set -l server (select_server $argv[1])
    or return 1
    test -z "$server"; and return 1

    set -l server_json (hcloud server describe "$server" -o json)
    set -l server_type (echo $server_json | jq -r '.server_type.name')
    set -l location (echo $server_json | jq -r '.datacenter.location.name')

    set -l timestamp (date -u +%Y%m%dT%H%M%S%3N)
    set -l snapshot_name "$server-$timestamp"

    info "Creating snapshot '$snapshot_name'..."
    hcloud server create-image \
        --type snapshot \
        --description "$snapshot_name" \
        --label "original-server=$server" \
        --label "server-type=$server_type" \
        --label "location=$location" \
        "$server"
    or die "Failed to create snapshot"

    success "Snapshot '$snapshot_name' created"
    info "Server type: $server_type"
    info "Location: $location"
end

function cmd_restore
    argparse 'n/name=' 't/type=' 'l/location=' 'k/ssh-key=' -- $argv
    or return 1

    set -l snapshot (select_snapshot $argv[1])
    or return 1
    test -z "$snapshot"; and return 1

    set -l snapshot_json (hcloud image list --type snapshot -o json | jq -r ".[] | select(.description == \"$snapshot\")")
    set -l snapshot_id (echo $snapshot_json | jq -r '.id')
    set -l default_server (echo $snapshot_json | jq -r '.labels["original-server"] // ""')
    set -l default_type (echo $snapshot_json | jq -r '.labels["server-type"] // ""')
    set -l default_location (echo $snapshot_json | jq -r '.labels["location"] // ""')

    gum style --bold "Restoring from: $snapshot"
    if test -n "$default_server"
        info "Original: $default_server ($default_type @ $default_location)"
    end
    echo

    # Server name
    set -l server_name $_flag_name
    if test -z "$server_name"
        set server_name (gum input --prompt "Server name: " --value "$default_server")
    end
    test -z "$server_name"; and die "Server name is required."

    if hcloud server describe "$server_name" >/dev/null 2>&1
        die "Server '$server_name' already exists."
    end

    # Server type
    set -l server_type $_flag_type
    if test -z "$server_type"
        set -l types_json (hcloud server-type list -o json)
        set -l header (printf "%-12s %5s %8s %8s %s" NAME CORES MEMORY DISK DESCRIPTION)
        set -l types_table (echo $types_json | jq -r '.[] | "\(.name)|\(.cores)|\(.memory)|\(.disk)|\(.description)"' | while read -l line
            set -l parts (string split '|' $line)
            printf "%-12s %5s %6s GB %6s GB %s\n" $parts[1] $parts[2] $parts[3] $parts[4] $parts[5]
        end)
        # Move default type to top if set
        if test -n "$default_type"
            set -l default_line (printf '%s\n' $types_table | string match -e "$default_type")
            set -l other_lines (printf '%s\n' $types_table | string match -v -e "$default_type")
            set types_table $default_line $other_lines
        end
        set -l selected (printf '%s\n' $types_table | gum filter --header "$header" --placeholder "Server type (was: $default_type)...")
        set server_type (echo $selected | awk '{print $1}')
    end
    test -z "$server_type"; and die "Server type is required."

    # Location
    set -l location $_flag_location
    if test -z "$location"
        set -l locations (hcloud location list -o json | jq -r '.[].name')
        if test -n "$default_location"
            set locations $default_location (string match -v $default_location -- $locations)
        end
        set location (printf '%s\n' $locations | gum choose --header "Location (was: $default_location)")
    end
    test -z "$location"; and die "Location is required."

    # SSH key
    set -l ssh_key $_flag_ssh_key
    if test -z "$ssh_key"
        set -l keys (hcloud ssh-key list -o json | jq -r '.[].name')
        if test -n "$keys"
            set keys "(none)" $keys
            set ssh_key (printf '%s\n' $keys | gum choose --header "SSH key")
            test "$ssh_key" = "(none)"; and set ssh_key ""
        end
    end

    # Create server
    info "Creating server '$server_name'..."
    set -l cmd hcloud server create \
        --name "$server_name" \
        --type "$server_type" \
        --image "$snapshot_id" \
        --location "$location"
    if test -n "$ssh_key"
        set cmd $cmd --ssh-key "$ssh_key"
    end

    $cmd
    or die "Failed to create server"

    success "Server '$server_name' created"
    info "Type: $server_type"
    info "Location: $location"
    if test -n "$ssh_key"
        info "SSH key: $ssh_key"
    end

    set -l ipv4 (hcloud server describe "$server_name" -o json | jq -r '.public_net.ipv4.ip // empty')
    if test -n "$ipv4"
        info "IPv4: $ipv4"
    end
end

function cmd_destroy
    argparse no-snapshot -- $argv
    or return 1

    set -l server (select_server $argv[1])
    or return 1
    test -z "$server"; and return 1

    if not set -q _flag_no_snapshot
        if gum confirm "Create snapshot of '$server' before destroying?"
            cmd_snapshot "$server"
            or begin
                die "Snapshot failed. Aborting."
            end
            echo
        end
    end

    if not gum confirm "Destroy server '$server'? This cannot be undone."
        info "Aborted."
        return 0
    end

    info "Destroying '$server'..."
    hcloud server delete "$server"
    or die "Failed to destroy server"

    success "Server '$server' destroyed"
end

function cmd_list
    set -l snapshots (hcloud image list --type snapshot -o json)

    if test (echo $snapshots | jq 'length') -eq 0
        info "No snapshots found."
        return 0
    end

    printf "%-40s %8s %10s %-15s %-10s %-8s %-12s\n" NAME ID SIZE SERVER TYPE LOC CREATED | gum style --bold
    gum style --foreground 240 (string repeat -n 110 ─)

    echo $snapshots | jq -r '.[] | [
        (.description // "id:\(.id)")[:40],
        (.id | tostring),
        "\(.image_size // 0 | . * 10 | round / 10) GB",
        (.labels["original-server"] // "-")[:15],
        (.labels["server-type"] // "-")[:10],
        (.labels["location"] // "-")[:8],
        (.created // "-")[:10]
    ] | @tsv' | while read -l name id size server type loc created
        printf "%-40s %8s %10s %-15s %-10s %-8s %-12s\n" $name $id $size $server $type $loc $created
    end
end

function cmd_clean
    set -l snapshot (select_snapshot $argv[1])
    or return 1
    test -z "$snapshot"; and return 1

    set -l snapshot_id (hcloud image list --type snapshot -o json | jq -r ".[] | select(.description == \"$snapshot\") | .id")

    if not gum confirm "Delete snapshot '$snapshot'? This cannot be undone."
        info "Aborted."
        return 0
    end

    info "Deleting snapshot '$snapshot'..."
    hcloud image delete "$snapshot_id"
    or die "Failed to delete snapshot"

    success "Snapshot '$snapshot' deleted"
end

function show_help
    echo "Hetzner Cloud snapshot workflow manager."
    echo
    echo "Usage: $script_name <command> [args]"
    echo
    echo "Commands:"
    echo "  snapshot [server]  - Create a snapshot of a server"
    echo "  restore [snapshot] - Restore a server from a snapshot"
    echo "  destroy [server]   - Destroy a server"
    echo "  clean [snapshot]   - Delete a snapshot"
    echo "  list               - List all snapshots"
    echo
    echo "Options:"
    echo "  -h, --help         - Show this help message"
    echo "  -V, --version      - Show version"
    echo
    echo "Run '$script_name <command> --help' for command-specific help."
end

function show_help_snapshot
    echo "Create a snapshot of a server."
    echo
    echo "Usage: $script_name snapshot [server]"
    echo
    echo "Arguments:"
    echo "  server  - Server name (interactive if omitted)"
end

function show_help_restore
    echo "Restore a server from a snapshot."
    echo
    echo "Usage: $script_name restore [snapshot] [options]"
    echo
    echo "Arguments:"
    echo "  snapshot            - Snapshot name (interactive if omitted)"
    echo
    echo "Options:"
    echo "  -n, --name <name>   - New server name"
    echo "  -t, --type <type>   - Server type (e.g., cx22)"
    echo "  -l, --location <loc> - Location (e.g., fsn1)"
    echo "  -k, --ssh-key <key> - SSH key name"
end

function show_help_destroy
    echo "Destroy a server, optionally creating a snapshot first."
    echo
    echo "Usage: $script_name destroy [server] [options]"
    echo
    echo "Arguments:"
    echo "  server              - Server name (interactive if omitted)"
    echo
    echo "Options:"
    echo "  --no-snapshot       - Skip snapshot prompt"
end

function show_help_list
    echo "List all snapshots with metadata."
    echo
    echo "Usage: $script_name list"
end

function show_help_clean
    echo "Delete a snapshot."
    echo
    echo "Usage: $script_name clean [snapshot]"
    echo
    echo "Arguments:"
    echo "  snapshot  - Snapshot name (interactive if omitted)"
end

function main
    # Check dependencies
    if not command -q gum
        echo "Error: 'gum' is required but not installed." >&2
        echo "Install it from: https://github.com/charmbracelet/gum" >&2
        exit 1
    end

    if not command -q hcloud
        echo "Error: 'hcloud' CLI is required but not installed." >&2
        echo "Install it from: https://github.com/hetznercloud/cli" >&2
        exit 1
    end

    if not command -q jq
        echo "Error: 'jq' is required but not installed." >&2
        echo "Install if from: apt, homebrew, mise, asdf, etc."
        exit 1
    end

    argparse -i h/help V/version -- $argv

    if set -q _flag_version
        echo "$script_name $script_version ($script_date)"
        exit 0
    end

    if set -q _flag_help; or test (count $argv) -eq 0
        show_help
        exit 0
    end

    set -l cmd $argv[1]
    set -e argv[1]

    # Check for help on subcommands
    if contains -- -h $argv; or contains -- --help $argv
        switch $cmd
            case snapshot
                show_help_snapshot
            case restore
                show_help_restore
            case destroy
                show_help_destroy
            case clean
                show_help_clean
            case list
                show_help_list
            case '*'
                die "Unknown command: $cmd"
        end
        exit 0
    end

    switch $cmd
        case snapshot
            cmd_snapshot $argv
        case restore
            cmd_restore $argv
        case destroy
            cmd_destroy $argv
        case clean
            cmd_clean $argv
        case list
            cmd_list $argv
        case '*'
            die "Unknown command: $cmd"
    end
end

main $argv
