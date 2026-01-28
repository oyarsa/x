-- Melange colorscheme - standalone single-file version
-- From https://github.com/savq/melange-nvim
-- Copyright (c) 2021 Sergio Alejandro Vargas
-- SPDX-License-Identifier: MIT

vim.cmd 'highlight clear'
vim.cmd 'syntax reset'
vim.g.colors_name = 'melange'

local a, b, c, d

if vim.opt.background:get() == 'light' then
    a = {
        bg    = "#F1F1F1",
        float = "#E9E1DB",
        sel   = "#D9D3CE",
        ui    = "#A98A78",
        com   = "#7D6658",
        fg    = "#54433A",
    }
    b = {
        red     = "#BF0021",
        yellow  = "#A06D00",
        green   = "#3A684A",
        cyan    = "#3D6568",
        blue    = "#465AA4",
        magenta = "#904180",
    }
    c = {
        red     = "#C77B8B",
        yellow  = "#BC5C00",
        green   = "#6E9B72",
        cyan    = "#739797",
        blue    = "#7892BD",
        magenta = "#BE79BB",
    }
    d = {
        red     = "#F1DEDF",
        yellow  = "#CCA478",
        green   = "#D0E9D1",
        cyan    = "#CDE8E7",
        blue    = "#E0E2E8",
        magenta = "#E8E0E8",
    }
else
    a = {
        bg    = "#292522",
        float = "#34302C",
        sel   = "#403A36",
        ui    = "#867462",
        com   = "#C1A78E",
        fg    = "#ECE1D7",
    }
    b = {
        red     = "#D47766",
        yellow  = "#EBC06D",
        green   = "#85B695",
        cyan    = "#89B3B6",
        blue    = "#A3A9CE",
        magenta = "#CF9BC2",
    }
    c = {
        red     = "#BD8183",
        yellow  = "#E49B5D",
        green   = "#78997A",
        cyan    = "#7B9695",
        blue    = "#7F91B2",
        magenta = "#B380B0",
    }
    d = {
        red     = "#7D2A2F",
        yellow  = "#8B7449",
        green   = "#233524",
        cyan    = "#253333",
        blue    = "#273142",
        magenta = "#422741",
    }
end

local bold, italic, underline, undercurl, strikethrough
if vim.g.melange_enable_font_variants == true or vim.g.melange_enable_font_variants == nil then
    bold = true
    italic = true
    underline = true
    undercurl = true
    strikethrough = true
elseif type(vim.g.melange_enable_font_variants) == 'table' then
    bold = vim.g.melange_enable_font_variants.bold
    italic = vim.g.melange_enable_font_variants.italic
    underline = vim.g.melange_enable_font_variants.underline
    undercurl = vim.g.melange_enable_font_variants.undercurl
    strikethrough = vim.g.melange_enable_font_variants.strikethrough
end

for name, attrs in pairs {
    -- :help highlight-default
    Normal = { fg = a.fg, bg = a.bg },
    NormalFloat = { bg = a.float },
    FloatTitle = { fg = c.yellow, bg = a.float },
    FloatFooter = { fg = c.yellow, bg = a.float },
    ColorColumn = { bg = a.float },
    CursorColumn = 'ColorColumn',
    CursorLine = 'ColorColumn',
    WinSeparator = { fg = a.ui },
    LineNr = { fg = a.ui },
    CursorLineNr = { fg = c.yellow },
    Folded = { fg = a.com, bg = d.cyan },
    FoldColumn = 'LineNr',
    SignColumn = 'LineNr',
    Pmenu = 'NormalFloat',
    PmenuSel = { bg = a.sel },
    PmenuThumb = 'PmenuSel',
    PmenuMatch = { fg = b.yellow, bold = bold },
    PmenuMatchSel = { reverse = true },
    ComplMatchIns = { fg = a.com },
    WildMenu = 'NormalFloat',
    StatusLine = 'NormalFloat',
    StatusLineNC = { fg = a.com, bg = a.float },
    TabLine = 'StatusLineNC',
    TabLineFill = 'StatusLine',
    TabLineSel = { bg = a.float, bold = bold },
    CurSearch = { fg = a.bg, bg = b.yellow, bold = bold },
    MatchParen = 'Substitute',
    Search = { fg = a.bg, bg = d.yellow, bold = bold },
    Substitute = { bg = d.red, bold = bold },
    Visual = { bg = a.sel },
    Conceal = { fg = a.com },
    Whitespace = { fg = a.ui },
    NonText = 'Whitespace',
    SpecialKey = 'Whitespace',
    Directory = { fg = c.green },
    Title = { fg = c.yellow, bold = bold },
    ErrorMsg = { bg = d.red },
    ModeMsg = { fg = a.com },
    MoreMsg = { fg = c.green, bold = bold },
    WarningMsg = { fg = c.red },
    Question = 'MoreMsg',
    QuickFixLine = 'PmenuMatch',
    qfFileName = 'Directory',

    -- :help :diff
    DiffAdd = { bg = d.green },
    DiffChange = { bg = d.magenta },
    DiffDelete = { fg = a.com, bg = d.red },
    DiffText = 'DiffAdd',
    DiffAdded = 'DiffAdd',
    DiffRemoved = 'DiffDelete',

    -- :help spell
    SpellBad = { fg = c.red, undercurl = undercurl },
    SpellCap = { fg = c.blue, undercurl = undercurl },
    SpellLocal = { fg = c.yellow, undercurl = undercurl },
    SpellRare = { fg = b.yellow, undercurl = undercurl },

    -- :help group-name
    Comment = { fg = a.com, italic = italic },
    Identifier = { fg = a.fg },
    Function = { fg = b.yellow },
    Constant = { fg = c.magenta },
    String = { fg = b.blue, italic = italic },
    Character = { fg = c.blue },
    Number = { fg = b.magenta },
    Boolean = 'Number',
    Statement = { fg = c.yellow },
    Operator = { fg = b.red },
    PreProc = { fg = b.green },
    Type = { fg = c.cyan },
    Special = { fg = b.yellow },
    Delimiter = { fg = d.yellow },
    Underlined = { underline = underline },
    Bold = { bold = bold },
    Italic = { italic = italic },
    Ignore = { fg = a.ui },
    Error = { bg = d.red },
    Todo = { fg = a.com, bold = bold },

    -- :help treesitter-highlight-groups
    ['@variable'] = 'Identifier',
    ['@variable.builtin'] = '@string.special.symbol',
    ['@constant'] = 'Identifier',
    ['@constant.builtin'] = 'Constant',
    ['@constant.macro'] = 'Constant',
    ['@module'] = 'Identifier',
    ['@module.builtin'] = '@module',
    ['@label'] = { fg = b.cyan },
    ['@string.documentation'] = { fg = b.blue, nocombine = true },
    ['@string.escape'] = { fg = c.blue },
    ['@string.regexp'] = { fg = b.blue },
    ['@string.special'] = { fg = b.cyan },
    ['@string.special.symbol'] = { fg = a.fg, italic = italic },
    ['@string.special.path'] = 'Directory',
    ['@string.special.url'] = { fg = c.blue },
    ['@type.builtin'] = '@type',
    ['@function.builtin'] = '@function',
    ['@function.macro'] = '@function',
    ['@constructor'] = '@function',
    ['@keyword.function'] = 'PreProc',
    ['@keyword.import'] = 'PreProc',
    ['@keyword.directive'] = 'PreProc',
    ['@punctuation.delimiter'] = { fg = c.red },
    ['@comment.documentation'] = { fg = a.com, nocombine = true },
    ['@comment.error'] = 'Todo',
    ['@comment.note'] = 'Todo',
    ['@comment.todo'] = 'Todo',
    ['@comment.warning'] = 'Todo',
    ['@markup.italic'] = { italic = italic },
    ['@markup.strong'] = { bold = bold },
    ['@markup.strikethrough'] = { strikethrough = strikethrough },
    ['@markup.underline'] = { underline = underline },
    ['@markup.heading'] = 'Title',
    ['@markup.heading.2'] = { fg = b.yellow, bold = bold },
    ['@markup.heading.3'] = { fg = b.green, bold = bold },
    ['@markup.heading.5'] = '@markup.heading.2',
    ['@markup.heading.6'] = '@markup.heading.3',
    ['@markup.quote'] = 'Comment',
    ['@markup.math'] = '@markup.raw',
    ['@markup.link'] = { underline = underline },
    ['@markup.link.url'] = '@string.special.url',
    ['@markup.raw'] = '@string.special',
    ['@markup.raw.block'] = { fg = a.com },
    ['@markup.list'] = 'Delimiter',
    ['@diff.plus'] = 'DiffAdd',
    ['@diff.minus'] = 'DiffDelete',
    ['@diff.delta'] = 'DiffChange',
    ['@tag.attribute'] = '@label',
    ['@tag.delimiter'] = 'Delimiter',

    -- :help diagnostic-highlight
    DiagnosticError = { fg = c.red },
    DiagnosticWarn = { fg = b.yellow },
    DiagnosticInfo = { fg = c.blue },
    DiagnosticHint = { fg = c.cyan },
    DiagnosticOk = { fg = c.green },
    DiagnosticUnderlineError = { undercurl = undercurl, sp = c.red },
    DiagnosticUnderlineWarn = { undercurl = undercurl, sp = b.yellow },
    DiagnosticUnderlineInfo = { undercurl = undercurl, sp = c.blue },
    DiagnosticUnderlineHint = { undercurl = undercurl, sp = c.cyan },
    DiagnosticUnderlineOk = { undercurl = undercurl, sp = c.green },
    DiagnosticDeprecated = 'DiagnosticUnderlineError',
    DiagnosticUnnecessary = { undercurl = undercurl, sp = a.com },

    -- :help lsp-highlight
    LspReferenceText = { bg = a.float, underline = underline },

    -- :help lsp-semantic-highlight
    ['@lsp.type.enumMember'] = 'Constant',
    ['@lsp.type.macro'] = {},
    ['@lsp.type.namespace'] = 'Directory',
    ['@lsp.type.parameter'] = { fg = a.fg, bold = bold },
    ['@lsp.typemod.comment.documentation'] = '@comment.documentation',
    ['@lsp.typemod.variable.globalScope'] = { italic = italic },
} do
    if type(attrs) == 'table' then
        vim.api.nvim_set_hl(0, name, attrs)
    else
        vim.api.nvim_set_hl(0, name, { link = attrs })
    end
end
