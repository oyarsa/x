function fish_user_key_bindings
    fzf_key_bindings
    bind alt-l __list_current_token
    bind alt-j __jj
    bind alt-g __gg
    # Override fifc Tab binding
    bind \t complete
end
