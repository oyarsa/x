--------------------------------------------------------------------------------
-- Git hunk
--------------------------------------------------------------------------------
local function parse_diff(diff_output)
    local hunks = {}
    for _, line in ipairs(diff_output) do
        local _, old_count, new_start, new_count =
            line:match('^@@ %-(%d+),?(%d*) %+(%d+),?(%d*) @@')

        if new_start then
            new_start = tonumber(new_start)
            new_count = tonumber(new_count) or 1
            old_count = tonumber(old_count) or 1

            -- Handle deletion at start of file
            if new_start == 0 then
                new_start = 1
                new_count = 1
            end

            local kind
            if old_count == 0 then
                kind = 'Add'
            elseif new_count == 0 then
                kind = 'Delete'
            else
                kind = 'Change'
            end

            table.insert(hunks,
                {
                    start = new_start,
                    count = new_count,
                    kind = kind,
                })
        end
    end
    return hunks
end

local function get_hunks()
    local file = vim.fn.expand('%:p')
    if file == '' then return {} end

    local diff = vim.fn.systemlist({ 'git', 'diff', '--unified=0', '--', file })
    if vim.v.shell_error ~= 0 then return {} end

    return parse_diff(diff)
end

local function next_hunk()
    local hunks = get_hunks()
    local cursor = vim.api.nvim_win_get_cursor(0)[1]

    for _, hunk in ipairs(hunks) do
        if hunk.start > cursor then
            vim.api.nvim_win_set_cursor(0, { hunk.start, 0 })
            return
        end
    end
    if #hunks > 0 then
        vim.api.nvim_win_set_cursor(0, { hunks[1].start, 0 })
    end
end

local function prev_hunk()
    local hunks = get_hunks()
    local cursor = vim.api.nvim_win_get_cursor(0)[1]

    for i = #hunks, 1, -1 do
        if hunks[i].start < cursor then
            vim.api.nvim_win_set_cursor(0, { hunks[i].start, 0 })
            return
        end
    end
    if #hunks > 0 then
        vim.api.nvim_win_set_cursor(0, { hunks[#hunks].start, 0 })
    end
end

vim.keymap.set('n', '<M-c>', next_hunk)
vim.keymap.set('n', '<M-S-c>', prev_hunk)

-- Highlights
vim.api.nvim_set_hl(0, 'GitAddUnstaged', { fg = '#99cc99' })
vim.api.nvim_set_hl(0, 'GitChangeUnstaged', { fg = '#cccc66' })
vim.api.nvim_set_hl(0, 'GitDeleteUnstaged', { fg = '#cc6666' })
vim.api.nvim_set_hl(0, 'GitAddStaged', { fg = '#66cccc' })
vim.api.nvim_set_hl(0, 'GitChangeStaged', { fg = '#6699cc' })
vim.api.nvim_set_hl(0, 'GitDeleteStaged', { fg = '#cc66cc' })

-- Signs
vim.fn.sign_define('GitAddUnstaged', { text = '+', texthl = 'GitAddUnstaged' })
vim.fn.sign_define('GitChangeUnstaged', { text = '~', texthl = 'GitChangeUnstaged' })
vim.fn.sign_define('GitDeleteUnstaged', { text = '_', texthl = 'GitDeleteUnstaged' })
vim.fn.sign_define('GitAddStaged', { text = '+', texthl = 'GitAddStaged' })
vim.fn.sign_define('GitChangeStaged', { text = '~', texthl = 'GitChangeStaged' })
vim.fn.sign_define('GitDeleteStaged', { text = '_', texthl = 'GitDeleteStaged' })

local function update_git_signs()
    local bufnr = vim.api.nvim_get_current_buf()
    local file = vim.fn.expand('%:p')
    if file == '' then return end

    vim.fn.sign_unplace('git_signs', { buffer = bufnr })

    local function place_signs(diff_output, suffix)
        for _, hunk in ipairs(parse_diff(diff_output)) do
            local sign = 'Git' .. hunk.kind .. suffix
            for i = 0, hunk.count - 1 do
                vim.fn.sign_place(0, 'git_signs', sign, bufnr, { lnum = hunk.start + i })
            end
        end
    end

    place_signs(vim.fn.systemlist({ 'git', 'diff', '--unified=0', '--', file }), 'Unstaged')
    place_signs(vim.fn.systemlist({ 'git', 'diff', '--cached', '--unified=0', '--', file }), 'Staged')
end

vim.api.nvim_create_autocmd({ 'BufReadPost', 'BufWritePost' },
    {
        callback = update_git_signs,
    })
