#!/usr/bin/env nu

def main [repo: string = "."] {
    cd $repo

    git log --date=short --format='%ad %H'
    | lines
    | parse "{day} {commit}"
    | uniq-by day
    | sort-by day
    | reduce -f { prev: 0, rows: [] } {|row, acc|
        let go_files = git ls-tree -r --name-only $row.commit
            | lines
            | where { str ends-with ".go" }
        let count = if ($go_files | is-empty) { 0 } else {
            git archive $row.commit -- ...$go_files | tar -xO
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
}
