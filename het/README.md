# het

Hetzner Cloud snapshot workflow manager.

A CLI tool for managing Hetzner Cloud server snapshots. Designed for workflows where you
spin up temporary servers, snapshot them when done, and restore them later.

## Features

- **Snapshot with metadata**: Snapshots automatically store the original server name,
  type, and location as labels
- **Easy restore**: Restore a server from a snapshot with the original configuration
  pre-filled
- **Interactive selection**: All commands support interactive fuzzy-finding when
  arguments are omitted
- **Batch cleanup**: Delete multiple snapshots at once with multiselect

## Requirements

- [fish shell](https://fishshell.com/)
- [hcloud](https://github.com/hetznercloud/cli) - Hetzner Cloud CLI (must be configured
  with your API token)
- [gum](https://github.com/charmbracelet/gum) - Terminal UI components
- [jq](https://jqlang.github.io/jq/) - JSON processor

## Installation

Copy `het.fish` somewhere in your PATH and make it executable:

```sh
$ cp het.fish ~/.local/bin/het chmod +x ~/.local/bin/het
```

## Usage

```sh
# Create a snapshot of a server
$ het snapshot myserver

# List all snapshots
$ het list

# Restore a server from a snapshot (interactive prompts for name, type, location)
$ het restore myserver-20250131T120000

# Destroy a server (prompts to create snapshot first)
$ het destroy myserver

# Delete snapshots (interactive multiselect)
$ het clean

# Delete specific snapshots
$ het clean myserver-20250131T120000 myserver-20250130T090000
```

All commands accept `--help` for usage information.

## How it works

When you create a snapshot, het stores metadata as image labels:
- `original-server`: The server name
- `server-type`: The server type (e.g., cx22)
- `location`: The datacenter location (e.g., fsn1)

When restoring, these labels pre-populate the prompts so you can quickly recreate the
server with the same configuration, or change any values as needed.
