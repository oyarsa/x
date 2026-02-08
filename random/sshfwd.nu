#!/usr/bin/env nu

def socket-dir []: nothing -> string {
    let dir = $"($env.HOME)/.local/share/sshfwd"
    mkdir $dir
    $dir
}

def get-socket [host: string]: nothing -> string {
    $"(socket-dir)/($host).sock"
}

def get-ports-file [host: string]: nothing -> string {
    $"(socket-dir)/($host).ports"
}

# Stop running background tunnel
def "main stop" [
    host: string  # SSH host or alias
] {
    let socket = (get-socket $host)

    if ($socket | path exists) {
        ssh -S $socket -O exit $host
        rm -f (get-ports-file $host)
        print $"Stopped tunnel to ($host)."
    } else {
        print $"No active tunnel to ($host)."
    }
}

# List running tunnels
def "main ls" [] {
    glob $"(socket-dir)/*.sock" | each { |sock|
        let host = $sock | path parse | get stem
        let check = ssh -S $sock -O check $host | complete

        if $check.exit_code == 0 {
            let ports_file = get-ports-file $host
            let ports = if ($ports_file | path exists) {
                open $ports_file | str trim
            } else {
                "?"
            }
            { host: $host, ports: $ports }
        } else {
            # Stale socket, clean up
            rm -f $sock (get-ports-file $host)
            null
        }
    } | compact
}

# Forward ports over SSH with optional background mode and clean stop
def "main start" [
    host: string          # SSH host or alias
    ...ports: int         # Ports to forward
    --expose              # Bind to 0.0.0.0 so others on your network can connect
] {
    let socket = (get-socket $host)

    if ($ports | is-empty) {
        error make { msg: "At least one port is required" }
    }

    let bind = if $expose { "0.0.0.0" } else { "localhost" }
    let forwards = $ports | each { |p| [-L $"($bind):($p):localhost:($p)"] } | flatten

    # Save port info for ls
    let ports_str = $ports | str join ", "
    $ports_str | save -f (get-ports-file $host)

    let expose_note = if $expose { " (exposed to network)" } else { "" }
    print $"Forwarding ports ($ports_str) to ($host)($expose_note)"
    ssh ...$forwards -S $socket -M $host -N -f

    print "Running in the background. Stop with:"
    print
    print $"    sshfwd stop ($host)"
}

def main [] {
    help main
}
