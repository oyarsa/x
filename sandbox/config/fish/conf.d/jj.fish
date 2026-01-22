function jl1 --wraps='jj log -T builtin_log_oneline --no-graph' --description 'alias jl1 jj log -T builtin_log_oneline --no-graph'
    jj log -T builtin_log_oneline --no-graph -r '::@' $argv
end

function jen --wraps='jj next --edit' --description 'alias jen jj next --edit'
    jj next --edit $argv
end

function jgm --wraps='jj bookmark set -r @- && jj git push' --description 'alias jgm jj bookmark set -r @- master && jj git push'
    jj bookmark set -r @- master && jj git push $argv
end

function js --wraps='jj split' --description 'alias js jj split'
    jj split $argv
end

function jlf --wraps='jj log -T builtin_log_compact_full_description' --wraps='jj log -r "::@" -T builtin_log_compact_full_description' --description 'alias jlf jj log -r "::@" -T builtin_log_compact_full_description'
    jj log -r "::@" -T builtin_log_compact_full_description $argv
end

function jet --wraps=jj\ edit\ -r\ \'visible_heads\(\)\' --wraps='jj edit -r visible_heads' --description 'alias jj edit -r visible_heads'
    jj edit -r 'visible_heads()' $argv
end

function jci --wraps='jj commit -i' --description 'alias jci jj commit -i'
    jj commit -i $argv
end

function jco --wraps='jj commit' --description 'alias jco jj commit'
    jj commit $argv
end

function jep --wraps='jj prev --edit' --description 'alias jep jj prev --edit'
    jj prev --edit $argv
end
function jlaf --wraps="jj log" --description "alias jlaf jj log -r all full"
    jj log -T builtin_log_compact_full_description -r 'all()' $argv
end

function jla --wraps="jj log" --description "alias jla jj log -r all"
    jj log -r 'all()' $argv
end

function jl --wraps='jj log -n10' --description 'alias jl jj log -n10'
    jj log -n10 $argv
end

function jdd --wraps='jj diff' --description 'alias jdd jj diff [more]'
    jj diff --name-only | fzf \
        --multi \
        --preview 'jj diff --color=always {} | delta' \
        --preview-window=right:70% \
        --bind 'ctrl-d:preview-half-page-down,ctrl-u:preview-half-page-up' \
        --bind 'ctrl-s:execute-silent(jj squash {+})+reload(jj diff --name-only)'
end

function jnm --wraps='jj new trunk()' --description 'Create new change on top of trunk'
    jj new 'trunk()'
end

function jlm --wraps="jj log -r 'master::@'" --description "alias jlm jj log -r 'master::@'"
    jj log -r 'master::@' $argv
end

function jll --wraps='jj log -T builtin_log_compact_full_description' --wraps='jj log' --description 'alias jll jj log -r "::@"'
    jj log -r '::@' $argv
end

function jpr --wraps="jj git fetch && jj new 'trunk()' && jj log" --description "alias jpr jj git fetch && jj new 'trunk()' && jj log"
    # Update local copy after merging a PR in remote.
    # Assumes that the local copy hasn't changed. If it did, use
    # `jup`.
    jj git fetch && jj new 'trunk()' && jj log $argv
end

function jgp --wraps='jj git push' --description 'alias jgp jj git push'
    jj git push $argv
end

function jsq --wraps='jj squash' --description 'alias jsq jj squash'
    jj squash $argv
end

function jna --wraps='jj new -A' --description 'alias jna jj new -A [@]'
    set -f args $argv
    test (count $args) -eq 0 && set args @
    jj new -A $args
end

function jnb --wraps='jj new -B' --description 'alias jnb jj new -B [@]'
    set -f args $argv
    test (count $args) -eq 0 && set args @
    jj new -B $args
end

function jblamefull --wraps='jj file annotate --config templates.annotate_commit_summary=annotate_commit_summary_full' --description='alias jj file annotate --config templates.annotate_commit_summary=annotate_commit_summary_full'
    jj file annotate --config 'templates.annotate_commit_summary="annotate_commit_summary_full"' $argv
end

function jgf --wraps='jj git fetch' --description 'alias jgf jj git fetch'
    jj git fetch $argv

    printf "\n"
    jj log -n5 --no-pager && echo && jj status $argv
end

function jc --wraps='jj describe' --wraps='jj commit' --description 'alias jc jj describe'
    jj describe $argv
end

function jn --wraps='jj new' --description 'alias jn jj new'
    jj new $argv
end

function jdu --wraps='jj diff -r @-' --description 'alias jdu jj diff -r @-'
    jj diff -r @- $argv
end

function jd --wraps='jj diff' --description 'alias jd jj diff'
    jj diff $argv
end

function je --wraps='jj edit' --description 'alias je jj edit'
    jj edit $argv
end

function jbu --description 'alias jbu jj bookmark set -r @-'
    jj bookmark set -r @- $argv
end

function jblame --wraps='jj file annotate' --description 'alias jblame jj file annotate'
    jj file annotate $argv
end

function jsearch --wraps='jj log -r \'description("0.26")\' -T builtin_log_compact_full_description' --wraps='jj log -r \'description("$argv")\' -T builtin_log_compact_full_description' --description 'alias jsearch jj log -r \'description("$argv")\' -T builtin_log_compact_full_description'
    jj log -r "description(\"$argv\")" -T builtin_log_compact_full_description
end

function jcu --wraps='jj describe -r @-' --description 'alias jcu jj describe -r @-'
    jj describe -r @- $argv
end

function jtp --wraps='jj tug && jgp' --description 'alias jtp jj tug && jgp'
    jj tug && jgp $argv
end

function jde --wraps="nvim (jj diff --summary | cut -d' ' -f2)" --description "alias jde nvim (jj diff --summary | cut -d' ' -f2)"
    nvim (jj diff --summary | cut -d' ' -f2) $argv
end
