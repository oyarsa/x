#!/usr/bin/env nu

# List all executables in PATH with modified and created dates,
# sorted by modified date.
def main [
    --last: int              # Show N newest (default 25)
    --first: int             # Show N oldest
    --all                    # Show all executables
    --exclude (-E): string   # Exclude paths containing patterns, comma-separated
] {
    let executables = (
        $env.PATH
        | where { $in | path exists }
        | each {|dir|
            try {
                ls --long $dir | where type == file
            } catch {
                []
            }
        }
        | flatten
        | where mode =~ 'x'
        | insert resolved { $in.name | path expand }
        | uniq-by resolved
        | reject resolved
        | if ($exclude | is-not-empty) {
            where {|row|
                $exclude | split row "," | all {|pat|
                    not ($row.name | str contains $pat)
                }
            }
        } else {
            $in
        }
        | sort-by modified
    )

    if ($executables | is-empty) {
        print -e "No executables found in PATH"
        return
    }

    let result = if $all {
        $executables
    } else if $first != null {
        $executables | first $first
    } else {
        $executables
        | last ($last | default 25)
        | reverse
    }

    $result | select name modified created
}
