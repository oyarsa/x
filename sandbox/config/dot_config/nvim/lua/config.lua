-- Completion: C-n triggers omni completion, noselect by default
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
-- LSP
--------------------------------------------------------------------------------
require("lsp")
