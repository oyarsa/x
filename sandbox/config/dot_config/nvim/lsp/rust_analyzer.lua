-- Check if a file is part of the Rust stdlib, cargo registry, or git dependencies.
-- When navigating to definition in these locations, we want to reuse an existing
-- rust-analyzer instance rather than spawning a new one.
local function is_library(fname)
    local user_home = vim.fs.normalize(vim.env.HOME)

    -- Cargo stores downloaded crates in these locations
    local cargo_home = os.getenv("CARGO_HOME") or user_home .. "/.cargo"
    local registry = cargo_home .. "/registry/src"   -- crates.io dependencies
    local git_registry = cargo_home .. "/git/checkouts" -- git dependencies

    -- Rustup stores toolchain files (stdlib source) here
    local rustup_home = os.getenv("RUSTUP_HOME") or user_home .. "/.rustup"
    local toolchains = rustup_home .. "/toolchains"

    for _, item in ipairs({ toolchains, registry, git_registry }) do
        if vim.fs.relpath(item, fname) then
            -- File is inside a library path, reuse the most recent rust-analyzer client
            local clients = vim.lsp.get_clients({ name = "rust_analyzer" })
            return #clients > 0 and clients[#clients].config.root_dir or nil
        end
    end
end

return {
    cmd = { "rust-analyzer" },
    filetypes = { "rust" },

    -- Custom root detection to properly handle:
    -- 1. Library files (stdlib, dependencies) - reuse existing client
    -- 2. Cargo workspaces - find the actual workspace root, not just nearest Cargo.toml
    -- 3. Standalone files - fall back to .git directory
    root_dir = function(bufnr, on_dir)
        local fname = vim.api.nvim_buf_get_name(bufnr)

        -- For library files, reuse an existing rust-analyzer instance
        local reused_dir = is_library(fname)
        if reused_dir then
            on_dir(reused_dir)
            return
        end

        local cargo_crate_dir = vim.fs.root(fname, { "Cargo.toml" })

        -- No Cargo.toml found - try rust-project.json or fall back to .git directory
        if cargo_crate_dir == nil then
            on_dir(
                vim.fs.root(fname, { "rust-project.json" })
                or vim.fs.dirname(vim.fs.find(".git", { path = fname, upward = true })[1])
            )
            return
        end

        -- Found a Cargo.toml - use `cargo metadata` to find the workspace root.
        -- This ensures rust-analyzer sees the entire workspace in a monorepo,
        -- not just the individual crate.
        local cmd = {
            "cargo",
            "metadata",
            "--no-deps",
            "--format-version",
            "1",
            "--manifest-path",
            cargo_crate_dir .. "/Cargo.toml",
        }

        vim.system(cmd, { text = true }, function(output)
            if output.code == 0 and output.stdout then
                local result = vim.json.decode(output.stdout)
                if result["workspace_root"] then
                    on_dir(vim.fs.normalize(result["workspace_root"]))
                    return
                end
            end
            -- Fallback to the crate directory if cargo metadata fails
            on_dir(cargo_crate_dir)
        end)
    end,

    capabilities = {
        experimental = {
            -- Send status as LSP notifications instead of window/showMessage popups.
            -- This prevents the "Failed to discover workspace" warning from appearing
            -- as an intrusive message when opening standalone Rust files.
            serverStatusNotification = true,
        },
    },

    before_init = function(init_params, config)
        -- rust-analyzer reads some settings from initializationOptions rather than
        -- the standard settings object. Copy our settings there to ensure they're applied.
        if config.settings and config.settings["rust-analyzer"] then
            init_params.initializationOptions = config.settings["rust-analyzer"]
        end
    end,

    settings = {
        ["rust-analyzer"] = {
            check = {
                -- Run clippy instead of cargo check for better lints
                command = "clippy",
                -- Check all features to catch feature-gated issues
                features = "all",
            },
        },
    },
}
