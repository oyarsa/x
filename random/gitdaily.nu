#!/usr/bin/env nu

def main [
    repo: string = "."
    --pattern (-P): string  # regex to filter files (e.g. '\.go$'). Default: all git-tracked files
    --first: int         # only include the first N days
    --last: int          # only include the last N days
] {
    cd $repo

    let days = git log --date=short --format='%ad %H'
        | lines
        | parse "{day} {commit}"
        | uniq-by day
        | sort-by day

    let days = if $first != null { $days | first $first } else { $days }
    let days = if $last != null { $days | last ($last + 1) } else { $days }

    $days
    | reduce -f { prev: 0, rows: [] } {|row, acc|
        let files = git ls-tree -r --name-only $row.commit | lines
        let files = if $pattern != null {
            $files | where {|f| $f =~ $pattern }
        } else { $files }
        let count = if ($files | is-empty) { 0 } else {
            git archive $row.commit -- ...$files | tar -xO
            | lines
            | where { str trim | is-not-empty }
            | length
        }
        let diff = $count - $acc.prev
        {
            prev: $count
            rows: ($acc.rows | append {
                day: $row.day
                lines: $count
                diff: $"(if $diff >= 0 { '+' })($diff)"
            })
        }
    }
    | get rows
    | if $last != null { skip 1 } else { $in }
}
