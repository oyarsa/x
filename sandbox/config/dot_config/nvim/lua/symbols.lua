--------------------------------------------------------------------------------
-- Symbol picker: navigate to symbols using LSP + fzf
--------------------------------------------------------------------------------

-- LSP symbol kind numbers (from LSP spec)
local Kind = {
    File = 1,
    Module = 2,
    Namespace = 3,
    Package = 4,
    Class = 5,
    Method = 6,
    Property = 7,
    Field = 8,
    Constructor = 9,
    Enum = 10,
    Interface = 11,
    Function = 12,
    Variable = 13,
    Constant = 14,
    String = 15,
    Number = 16,
    Boolean = 17,
    Array = 18,
    Object = 19,
    Key = 20,
    Null = 21,
    EnumMember = 22,
    Struct = 23,
    Event = 24,
    Operator = 25,
    TypeParameter = 26,
}

-- ANSI color codes
local colors = {
    reset = "\27[0m",
    dim = "\27[2m",
    yellow = "\27[33m",
    blue = "\27[34m",
    magenta = "\27[35m",
    cyan = "\27[36m",
    green = "\27[32m",
    red = "\27[31m",
}

-- Abbreviated display names and colors for symbol kinds
-- Lowercase = common, Uppercase = secondary (same letter, different meaning)
local kind_info = {
    [Kind.Class] = { abbrev = "c", color = colors.yellow },
    [Kind.Constructor] = { abbrev = "C", color = colors.magenta },
    [Kind.Method] = { abbrev = "m", color = colors.magenta },
    [Kind.Module] = { abbrev = "M", color = colors.blue },
    [Kind.Function] = { abbrev = "f", color = colors.green },
    [Kind.Field] = { abbrev = "F", color = colors.cyan },
    [Kind.Property] = { abbrev = "p", color = colors.cyan },
    [Kind.Package] = { abbrev = "P", color = colors.blue },
    [Kind.Enum] = { abbrev = "e", color = colors.yellow },
    [Kind.EnumMember] = { abbrev = "E", color = colors.cyan },
    [Kind.Struct] = { abbrev = "s", color = colors.yellow },
    [Kind.String] = { abbrev = "S", color = colors.cyan },
    [Kind.Namespace] = { abbrev = "n", color = colors.blue },
    [Kind.Number] = { abbrev = "N", color = colors.cyan },
    [Kind.Object] = { abbrev = "o", color = colors.cyan },
    [Kind.Operator] = { abbrev = "O", color = colors.cyan },
    [Kind.Constant] = { abbrev = "k", color = colors.red },
    [Kind.Key] = { abbrev = "K", color = colors.cyan },
    [Kind.Variable] = { abbrev = "v", color = colors.cyan },
    [Kind.Interface] = { abbrev = "i", color = colors.yellow },
    [Kind.Array] = { abbrev = "a", color = colors.cyan },
    [Kind.Boolean] = { abbrev = "b", color = colors.cyan },
    [Kind.TypeParameter] = { abbrev = "t", color = colors.blue },
    [Kind.Event] = { abbrev = "W", color = colors.magenta },
    [Kind.File] = { abbrev = "L", color = colors.cyan },
    [Kind.Null] = { abbrev = "X", color = colors.cyan },
}

-- Container kinds that can have nested members we want to show
local container_kinds = {
    [Kind.Class] = true,
    [Kind.Struct] = true,
    [Kind.Enum] = true,
    [Kind.Interface] = true,
    [Kind.Module] = true,
    [Kind.Namespace] = true,
}

--------------------------------------------------------------------------------
-- Shared utilities
--------------------------------------------------------------------------------

-- Format colored badge for a symbol kind: [k]
local function format_badge(kind)
    local info = kind_info[kind] or { abbrev = "?", color = colors.reset }
    return string.format("%s[%s]%s", info.color, info.abbrev, colors.reset)
end

-- Get responsive preview position
local function get_preview_position()
    return vim.o.columns > 120 and "right:50%" or "bottom:50%"
end

-- Check if any LSP client has the given capability
local function has_lsp_capability(bufnr, capability)
    local clients = vim.lsp.get_clients({ bufnr = bufnr })
    for _, client in ipairs(clients) do
        if client.server_capabilities[capability] then
            return true
        end
    end
    return false
end

-- Calculate max width of a field across all items
local function calc_max_width(items, get_width)
    local max_width = 0
    for _, item in ipairs(items) do
        local width = get_width(item)
        if width > max_width then
            max_width = width
        end
    end
    return max_width
end

-- Run fzf picker with common options
local function run_fzf(opts)
    local preview_pos = get_preview_position()
    local fzf_options = {
        "--ansi",
        "--layout=reverse",
        "--delimiter='\t'",
        "--with-nth=2..",
        "--preview-window=" .. preview_pos .. ":+{1}-/2",
    }

    if opts.prompt then
        table.insert(fzf_options, "--prompt")
        table.insert(fzf_options, "'" .. opts.prompt .. "> '")
    end
    if opts.no_sort then
        table.insert(fzf_options, "--no-sort")
        table.insert(fzf_options, "--tiebreak=index")
    end
    if opts.preview_cmd then
        table.insert(fzf_options, "--preview")
        table.insert(fzf_options, vim.fn.shellescape(opts.preview_cmd))
    end

    vim.fn["fzf#run"]({
        source = opts.lines,
        sink = opts.sink,
        options = table.concat(fzf_options, " "),
        window = { width = 0.95, height = 0.9, border = "rounded" },
    })
end

--------------------------------------------------------------------------------
-- Document Symbol Picker (current file)
--------------------------------------------------------------------------------

-- Collect top-level symbols and first-level members of containers.
-- Skips local variables and deeply nested symbols.
local function collect_document_symbols(symbols, result, parent_is_container)
    result = result or {}

    for _, symbol in ipairs(symbols) do
        local range = symbol.location and symbol.location.range
            or symbol.selectionRange
            or symbol.range
        local lnum = range.start.line + 1
        local col = range.start.character + 1
        local is_container = container_kinds[symbol.kind]

        local include = false
        if parent_is_container then
            include = symbol.kind ~= Kind.Variable
        else
            include = symbol.kind ~= Kind.Variable
                or symbol.kind == Kind.Constant
        end

        if include then
            table.insert(result, {
                name = symbol.name,
                kind = symbol.kind,
                lnum = lnum,
                col = col,
                nested = parent_is_container,
            })
        end

        if is_container and symbol.children and not parent_is_container then
            collect_document_symbols(symbol.children, result, true)
        end
    end

    return result
end

-- Calculate display width of document symbol entry
local function document_symbol_width(sym)
    local indent_width = sym.nested and 2 or 0
    local info = kind_info[sym.kind] or { abbrev = "?" }
    local badge_width = 2 + #info.abbrev
    return indent_width + badge_width + 1 + #sym.name
end

-- Format document symbol for fzf: "lnum\t[k] name    signature"
local function format_document_symbol(sym, buf_lines, col_width)
    local indent = sym.nested and "  " or ""
    local badge = format_badge(sym.kind)
    local first_col = string.format("%s%s %s", indent, badge, sym.name)

    local visible_width = document_symbol_width(sym)
    local padding = string.rep(" ", col_width - visible_width + 2)

    local signature = (buf_lines[sym.lnum] or ""):gsub("^%s+", "")

    return string.format("%d\t%s%s%s", sym.lnum, first_col, padding, signature)
end

local function DocumentSymbolPicker()
    local bufnr = vim.api.nvim_get_current_buf()
    local filepath = vim.api.nvim_buf_get_name(bufnr)

    if not has_lsp_capability(bufnr, "documentSymbolProvider") then
        vim.notify("No LSP with document symbol support", vim.log.levels.WARN)
        return
    end

    local params = { textDocument = vim.lsp.util.make_text_document_params() }

    local method = "textDocument/documentSymbol"
    vim.lsp.buf_request(bufnr, method, params, function(err, result)
        if err then
            vim.notify("LSP error: " .. tostring(err), vim.log.levels.ERROR)
            return
        end
        if not result or #result == 0 then
            vim.notify("No symbols found", vim.log.levels.INFO)
            return
        end

        -- Get syntax-highlighted lines using bat
        local bat_cmd = string.format(
            "bat --color=always --style=plain %s",
            vim.fn.shellescape(filepath)
        )
        local highlighted = vim.fn.systemlist(bat_cmd)
        local buf_lines = #highlighted > 0
            and highlighted
            or vim.api.nvim_buf_get_lines(bufnr, 0, -1, false)

        local symbols = collect_document_symbols(result)
        local max_width = calc_max_width(symbols, document_symbol_width)

        local lines = {}
        for _, sym in ipairs(symbols) do
            local formatted = format_document_symbol(sym, buf_lines, max_width)
            table.insert(lines, formatted)
        end

        local preview_cmd = string.format(
            "bat --color=always --style=numbers --highlight-line {1} %s",
            vim.fn.shellescape(filepath)
        )

        run_fzf({
            lines = lines,
            prompt = "Symbol",
            no_sort = true,
            preview_cmd = preview_cmd,
            sink = function(line)
                local lnum = tonumber(line:match("^(%d+)\t"))
                if lnum then
                    vim.api.nvim_win_set_cursor(0, { lnum, 0 })
                    vim.cmd("normal! zz")
                end
            end,
        })
    end)
end

vim.keymap.set("n", "<leader>fs", DocumentSymbolPicker, {
    desc = "Find symbol in buffer",
})

--------------------------------------------------------------------------------
-- Workspace Symbol Picker (all files)
--------------------------------------------------------------------------------

-- Format workspace symbol for fzf: "filepath:lnum\t[k] name    file:line"
local function format_workspace_symbol(sym, max_name_width)
    local badge = format_badge(sym.kind)
    local padding = string.rep(" ", max_name_width - #sym.name + 2)
    local rel_path = vim.fn.fnamemodify(sym.filepath, ":.")
    local location = string.format(
        "%s%s:%d%s",
        colors.dim, rel_path, sym.lnum, colors.reset
    )

    return string.format(
        "%s:%d\t%s %s%s%s",
        sym.filepath, sym.lnum, badge, sym.name, padding, location
    )
end

local function WorkspaceSymbolPicker()
    local bufnr = vim.api.nvim_get_current_buf()

    if not has_lsp_capability(bufnr, "workspaceSymbolProvider") then
        vim.notify("No LSP with workspace symbol support", vim.log.levels.WARN)
        return
    end

    vim.ui.input({ prompt = "Workspace symbol: " }, function(query)
        if not query or query == "" then
            return
        end

        local params = { query = query }
        vim.lsp.buf_request(bufnr, "workspace/symbol", params, function(err, result)
            if err then
                vim.notify("LSP error: " .. tostring(err), vim.log.levels.ERROR)
                return
            end
            if not result or #result == 0 then
                vim.notify("No symbols found", vim.log.levels.INFO)
                return
            end

            local symbols = {}
            for _, sym in ipairs(result) do
                local filepath = vim.uri_to_fname(sym.location.uri)
                local range = sym.location.range
                table.insert(symbols, {
                    name = sym.name,
                    kind = sym.kind,
                    filepath = filepath,
                    lnum = range.start.line + 1,
                    col = range.start.character + 1,
                })
            end

            local function get_name_width(s)
                return #s.name
            end
            local max_name_width = calc_max_width(symbols, get_name_width)

            local lines = {}
            for _, sym in ipairs(symbols) do
                local formatted = format_workspace_symbol(sym, max_name_width)
                table.insert(lines, formatted)
            end

            local preview_cmd = "bat --color=always --style=numbers"
                .. " --highlight-line $(echo {1} | cut -d: -f2)"
                .. " $(echo {1} | cut -d: -f1)"

            run_fzf({
                lines = lines,
                prompt = "Workspace Symbol",
                preview_cmd = preview_cmd,
                sink = function(line)
                    local filepath, lnum = line:match("^(.+):(%d+)\t")
                    lnum = tonumber(lnum)
                    if filepath and lnum then
                        vim.cmd("edit " .. vim.fn.fnameescape(filepath))
                        vim.api.nvim_win_set_cursor(0, { lnum, 0 })
                        vim.cmd("normal! zz")
                    end
                end,
            })
        end)
    end)
end

vim.keymap.set("n", "<leader>fw", WorkspaceSymbolPicker, {
    desc = "Find symbol in workspace",
})
