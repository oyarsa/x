local function setup_lsp_keymaps(bufnr)
    local function map(mode, lhs, rhs, desc)
        vim.keymap.set(mode, lhs, rhs, { buffer = bufnr, desc = desc })
    end

    map("n", "<leader>lk", vim.lsp.buf.hover, "Hover")
    map("n", "gd", vim.lsp.buf.definition, "Go to definition")
    map("n", "gD", vim.lsp.buf.declaration, "Go to declaration")
    map("n", "gi", vim.lsp.buf.implementation, "Go to implementation")
    map("n", "go", vim.lsp.buf.type_definition, "Go to type definition")
    map("n", "gr", vim.lsp.buf.references, "Go to references")
    map("n", "gt", "<C-t>", "Pop tag stack")
    map("n", "<leader>lh", vim.lsp.buf.signature_help, "Signature help")
    map("i", "<A-h>", vim.lsp.buf.signature_help, "Signature help")
    map("n", "<leader>lr", vim.lsp.buf.rename, "Rename")
    map("n", "<leader>la", vim.lsp.buf.code_action, "Code action")

    map("n", "<leader>lf", function()
        vim.lsp.buf.code_action({
            ---@diagnostic disable-next-line: missing-fields
            context = { only = { "source.fixAll" } },
            apply = true,
        })
        vim.cmd.write()
    end, "Fix all code actions")

    -- [d and ]d to previous/next diagnostic are nvim defaults now
end

vim.keymap.set("n", "<leader>ld", vim.diagnostic.open_float, { desc = "Open diagnostic float" })
vim.keymap.set("n", "<leader>lD", vim.diagnostic.setqflist, { desc = "Open diagnostics in quickfix list" })

local function setup_auto_format(bufnr, client)
    if
        not client:supports_method("textDocument/willSaveWaitUntil")
        and client:supports_method("textDocument/formatting")
    then
        vim.api.nvim_create_autocmd("BufWritePre", {
            group = vim.api.nvim_create_augroup("my.lsp", { clear = false }),
            buffer = bufnr,
            callback = function()
                vim.lsp.buf.format({
                    bufnr = bufnr,
                    id = client.id,
                    timeout_ms = 1000,
                })
            end,
        })
    end
end

vim.api.nvim_create_autocmd("LspAttach", {
    callback = function(ev)
        local client = assert(vim.lsp.get_client_by_id(ev.data.client_id))
        setup_lsp_keymaps(ev.buf)
        setup_auto_format(ev.buf, client)
    end,
})

vim.diagnostic.config({
    signs = {
        text = {
            [vim.diagnostic.severity.ERROR] = " ",
            [vim.diagnostic.severity.WARN] = " ",
            [vim.diagnostic.severity.HINT] = " ",
            [vim.diagnostic.severity.INFO] = " ",
        },
    },
})

vim.lsp.config("rust_analyzer", {
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
})

vim.lsp.config("pyright", {
    cmd = { "pyright-langserver", "--stdio" },
    filetypes = { "python" },
    root_markers = { "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "pyrightconfig.json" },
    settings = {
        python = {
            analysis = {
                autoSearchPaths = true,
                useLibraryCodeForTypes = true,
                diagnosticMode = "openFilesOnly",
            },
        },
    },
})

vim.lsp.config("ruff", {
    cmd = { "ruff", "server" },
    filetypes = { "python" },
    root_markers = { "pyproject.toml", "ruff.toml", ".ruff.toml" },
})

vim.lsp.config("ts_ls", {
    cmd = { "typescript-language-server", "--stdio" },
    filetypes = { "javascript", "javascriptreact", "typescript", "typescriptreact" },
    root_markers = { "tsconfig.json", "jsconfig.json", "package.json" },
})

vim.lsp.config("eslint", {
    cmd = { "vscode-eslint-language-server", "--stdio" },
    filetypes = { "javascript", "javascriptreact", "typescript", "typescriptreact" },
    root_markers = { ".eslintrc", ".eslintrc.js", ".eslintrc.json", "eslint.config.js", "eslint.config.mjs" },
    settings = {
        workingDirectories = { mode = "auto" },
    },
})

-- vim.lsp.config("lua_ls", {
--     cmd = { 'lua-language-server' },
--     filetypes = { 'lua' },
--     root_markers = { '.luarc.json', '.luarc.jsonc', '.git' },
-- })

vim.lsp.enable({
    "rust_analyzer",
    "pyright",
    "ruff",
    "ts_ls",
    -- "lua_ls",
    "eslint",
})

-- vim.api.nvim_exec_autocmds("FileType", { buffer = 0 })

-- 1. Define the config in a variable
local lua_opts = {
    cmd = { 'lua-language-server' },
    filetypes = { 'lua' },
    root_markers = { '.luarc.json', '.luarc.jsonc', '.git' },
}

-- 2. Register it with the LSP system (for future buffers)
vim.lsp.config("lua_ls", lua_opts)
vim.lsp.enable("lua_ls")

