-- Alias :W to :w
vim.api.nvim_create_user_command("W", "w", {})

--------------------------------------------------------------------------------
-- Completion: C-n triggers omni completion, noselect by default
--------------------------------------------------------------------------------
vim.opt.completeopt = { "menu", "menuone", "noselect" }

vim.keymap.set("i", "<C-n>", function()
    if vim.fn.pumvisible() == 1 then
        return "<C-n>"
    elseif vim.bo.omnifunc ~= "" then
        return "<C-x><C-o>"
    else
        return "<C-x><C-n>"
    end
end, { expr = true })

--------------------------------------------------------------------------------
-- vim-unimpaired: quickfix navigation
--------------------------------------------------------------------------------
vim.keymap.set("n", "[q", "<Cmd>cprev<CR>", { desc = "Previous quickfix" })
vim.keymap.set("n", "]q", "<Cmd>cnext<CR>", { desc = "Next quickfix" })
vim.keymap.set("n", "[Q", "<Cmd>cfirst<CR>", { desc = "First quickfix" })
vim.keymap.set("n", "]Q", "<Cmd>clast<CR>", { desc = "Last quickfix" })

-- vim-unimpaired: yo toggles
vim.keymap.set("n", "yow", "<Cmd>set wrap!<CR>", { desc = "Toggle wrap" })
vim.keymap.set("n", "yon", function()
    if vim.wo.number then
        vim.wo.number = false
        vim.wo.relativenumber = false
    else
        vim.wo.number = true
        vim.wo.relativenumber = true
    end
end, { desc = "Toggle number + relativenumber" })
vim.keymap.set('n', 'yoq', function()
    if vim.fn.getqflist({ winid = 0 }).winid ~= 0 then
        vim.cmd('cclose')
    else
        vim.cmd('copen')
    end
end, { desc = "Toggle quickfix list" })

--------------------------------------------------------------------------------
-- vim-rsi: readline bindings in insert and command mode
--------------------------------------------------------------------------------
-- Insert mode
vim.keymap.set("i", "<C-a>", "<Home>")
vim.keymap.set("i", "<C-e>", "<End>")
vim.keymap.set("i", "<C-d>", "<Del>")

-- Command mode
vim.keymap.set("c", "<C-a>", "<Home>")
vim.keymap.set("c", "<C-e>", "<End>")
vim.keymap.set("c", "<C-d>", "<Del>")

--------------------------------------------------------------------------------
-- bufremove: delete buffer without closing window
--------------------------------------------------------------------------------
local function bufremove()
    local buf = vim.api.nvim_get_current_buf()
    local bufs = vim.tbl_filter(function(b)
        return vim.bo[b].buflisted
    end, vim.api.nvim_list_bufs())

    -- Switch to another buffer first
    if #bufs > 1 then
        vim.cmd("bprev")
    else
        vim.cmd("enew")
    end
    -- Delete the original buffer
    if vim.api.nvim_buf_is_valid(buf) then
        vim.api.nvim_buf_delete(buf, { force = false })
    end
end

vim.keymap.set("n", "<leader>q", bufremove, { desc = "Delete buffer (keep window)" })

--------------------------------------------------------------------------------
-- trailspace: highlight trailing whitespace
--------------------------------------------------------------------------------
vim.api.nvim_set_hl(0, "TrailingWhitespace", { bg = "#5f0000" })

local trailspace_group = vim.api.nvim_create_augroup("trailspace", { clear = true })
vim.api.nvim_create_autocmd({ "BufWinEnter", "InsertLeave" }, {
    group = trailspace_group,
    callback = function()
        if vim.bo.buftype == "" then
            vim.fn.matchadd("TrailingWhitespace", [[\s\+$]])
        end
    end,
})
-- Don't show trailing space while typing in insert mode
vim.api.nvim_create_autocmd("InsertEnter", {
    group = trailspace_group,
    callback = function()
        vim.fn.clearmatches()
    end,
})

--------------------------------------------------------------------------------
-- FZF and Grep
--------------------------------------------------------------------------------

-- fzf setup (apt files installation dir)
vim.opt.rtp:append('/usr/share/doc/fzf/examples')

-- <leader>ff Open fzf window to search files with preview
vim.keymap.set('n', '<leader>ff', ':Files<CR>', { desc = "Fuzzy find files" })
vim.api.nvim_create_user_command('Files',
    function()
        vim.fn['fzf#run']({
            source = 'fd --type f',
            sink = 'e',
            options = '--preview "bat --color=always {}" --preview-window=right:60%',
        })
    end, {})

-- <leader>fg Grep and show quickfix list
vim.keymap.set('n', '<leader>fg', ':Grep<CR>', { desc = "Grep and show quickfix list" })
vim.api.nvim_create_user_command('Grep', function()
    vim.fn.inputsave()
    local pattern = vim.fn.input('Rg: ')
    vim.fn.inputrestore()
    if pattern ~= '' then
        vim.cmd('silent grep ' .. vim.fn.shellescape(pattern))
        vim.cmd('copen')
        vim.cmd('wincmd p')
    end
end, {})

-- <leader>f/ Search in current buffer and show quickfix list
vim.keymap.set('n', '<leader>f/', ':Search ',
    { desc = "Search current buffer and show quickfix list" })
vim.api.nvim_create_user_command('Search', function(opts)
    vim.cmd('vimgrep /' .. opts.args .. '/ %')
    vim.cmd('copen')
end, { nargs = 1 })

--------------------------------------------------------------------------------
-- Popup terminal
--------------------------------------------------------------------------------

local function TogglePopupTerminal()
    local buf = vim.g.popup_term_buf
    local win = vim.g.popup_term_win

    -- If window exists and is valid, close it
    if win and vim.api.nvim_win_is_valid(win) then
        vim.api.nvim_win_hide(win)
        vim.g.popup_term_win = nil
        return
    end

    -- Create buffer if needed
    if not buf or not vim.api.nvim_buf_is_valid(buf) then
        buf = vim.api.nvim_create_buf(false, true)
        vim.g.popup_term_buf = buf
    end

    -- Calculate dimensions (80% of editor)
    local width = math.floor(vim.o.columns * 0.8)
    local height = math.floor(vim.o.lines * 0.8)
    local row = math.floor((vim.o.lines - height) / 2)
    local col = math.floor((vim.o.columns - width) / 2)

    -- Open floating window
    win = vim.api.nvim_open_win(buf, true, {
        relative = 'editor',
        width = width,
        height = height,
        row = row,
        col = col,
        border = 'single',
    })
    vim.g.popup_term_win = win

    -- Style the window
    vim.api.nvim_set_hl(0, 'PopupTermBorder', { fg = '#000000' })
    vim.wo[win].winhl = 'Normal:Normal,FloatBorder:PopupTermBorder'

    -- Start terminal if buffer is empty
    if vim.bo[buf].buftype ~= 'terminal' then
        vim.cmd('terminal')
        vim.bo[buf].buflisted = false -- Keep it hidden from buffer list
        vim.keymap.set('t', '<leader>tt', TogglePopupTerminal, { buffer = buf })
    end

    vim.cmd('startinsert')
end

vim.keymap.set('n', '<leader>tt', TogglePopupTerminal)

--------------------------------------------------------------------------------
-- Tabline
--------------------------------------------------------------------------------

vim.o.showtabline = 2

function BufferLine()
    local parts = {}
    local current = vim.api.nvim_get_current_buf()

    for _, bufnr in ipairs(vim.api.nvim_list_bufs()) do
        if vim.bo[bufnr].buflisted then
            local path = vim.fn.fnamemodify(vim.api.nvim_buf_get_name(bufnr), ':.')
            local name

            if path == '' then
                name = '[No Name]'
            else
                -- Split path and abbreviate directories
                local segments = vim.split(path, '/', { plain = true })
                if #segments > 1 then
                    for i = 1, #segments - 1 do
                        segments[i] = segments[i]:sub(1, 1)
                    end
                end
                name = table.concat(segments, '/')
            end

            if vim.bo[bufnr].modified then
                name = name .. ' [+]'
            end

            local hl = bufnr == current and '%#TabLineSel#' or '%#TabLine#'
            table.insert(parts, hl .. ' ' .. bufnr .. ':' .. name .. ' ')
        end
    end

    return table.concat(parts) .. '%#TabLineFill#'
end

vim.o.tabline = '%!v:lua.BufferLine()'

--------------------------------------------------------------------------------
-- Buffer picker
--------------------------------------------------------------------------------

local function BufferPick()
    local buffers = {}
    for _, bufnr in ipairs(vim.api.nvim_list_bufs()) do
        if vim.bo[bufnr].buflisted then
            local name = vim.fn.fnamemodify(vim.api.nvim_buf_get_name(bufnr), ':.')
            if name == '' then
                name = '[No Name]'
            end
            table.insert(buffers, bufnr .. ':' .. name)
        end
    end

    vim.fn['fzf#run']({
        source = buffers,
        ['sink*'] = function(lines)
            if #lines < 2 then return end
            local key = lines[1]
            local selection = lines[2]
            local bufnr = tonumber(selection:match('^(%d+):'))

            if key == 'ctrl-d' then
                vim.api.nvim_buf_delete(bufnr, {})
                vim.defer_fn(BufferPick, 0)
            else
                vim.api.nvim_set_current_buf(bufnr)
            end
        end,
        options = '--prompt "Buffer> " --expect=ctrl-d',
        window = { width = 0.6, height = 0.4, border = 'rounded' },
    })
end

vim.keymap.set('n', '<leader>w', BufferPick)

--------------------------------------------------------------------------------
-- Filetype column ruler
--------------------------------------------------------------------------------
local colorcolumn_by_ft = {
    python = "89",
    jjdescription = "73",
    lua = "81",
    rust = "101",
}

vim.api.nvim_create_autocmd("FileType", {
    callback = function()
        local cc = colorcolumn_by_ft[vim.bo.filetype]
        vim.wo.colorcolumn = cc or ""
    end,
})
vim.api.nvim_set_hl(0, 'ColorColumn', { bg = '#4a4a4a' })
