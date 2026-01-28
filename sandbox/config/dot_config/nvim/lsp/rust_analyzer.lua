return {
    cmd = { "rust-analyzer" },
    filetypes = { "rust" },
    root_markers = { "Cargo.toml", "rust-project.json" },
    settings = {
        ["rust-analyzer"] = {
            check = {
                command = "clippy",
                features = "all",
            },
        },
    },
}
