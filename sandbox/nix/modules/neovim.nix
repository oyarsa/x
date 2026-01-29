{ config, pkgs, lib, nvimConfigFiles, ... }:

{
  programs.neovim = {
    enable = true;
    defaultEditor = true;
    viAlias = true;
    vimAlias = true;

    # Extra packages available to neovim (for LSP servers, formatters, etc.)
    extraPackages = with pkgs; [
      # Language servers
      lua-language-server
      nodePackages.typescript-language-server
      nodePackages.vscode-eslint-language-server
      pyright
      ruff
      rust-analyzer

      # Tools used by config
      fd
      ripgrep
      bat
      fzf
    ];
  };

  # Neovim configuration files
  xdg.configFile = {
    # Main init.vim
    "nvim/init.vim".text = ''
      let mapleader = " "
      let maplocalleader = ","

      lua require("init")

      " Enable syntax highlighting
      syntax on
      filetype plugin indent on

      " Line numbers
      set number
      set relativenumber

      " UI elements
      set ruler
      set showcmd
      set showmatch
      set hidden

      " Indentation
      set autoindent
      set smartindent
      set expandtab
      set shiftwidth=4
      set tabstop=4
      set softtabstop=4

      " Search improvements
      set incsearch
      set ignorecase
      set smartcase

      " UI and UX improvements
      set wildmenu
      set wildmode=longest:full,full
      set scrolloff=8
      set sidescrolloff=5
      set nowrap
      set signcolumn=yes
      set shortmess+=c

      " Disable swap and backup
      set noswapfile
      set nobackup
      set nowritebackup

      " Performance
      set timeout
      set timeoutlen=300

      " Quality of life
      set mouse=a
      set noerrorbells
      set visualbell t_vb=

      " Key mappings (these are all personal preference)
      inoremap jk <Esc>

      " Navigation mappings
      nnoremap J 6j
      xnoremap J 6j
      onoremap J 6j

      nnoremap K 6k
      xnoremap K 6k
      onoremap K 6k

      nnoremap H ^
      xnoremap H ^
      onoremap H ^

      nnoremap L $
      xnoremap L $
      onoremap L $

      nnoremap M J
      xnoremap M J
      onoremap M J

      " Clear search
      nnoremap <leader>c :nohlsearch<CR>

      " System clipboard
      nnoremap <leader>p "+p
      xnoremap <leader>p "+p
      nnoremap <leader>P "+P
      xnoremap <leader>P "+P
      nnoremap <leader>y "+y
      xnoremap <leader>y "+y

      " Comment (requires neovim 0.10+ or vim-commentary plugin)
      nmap <C-c> gcc
      xmap <C-c> gc
      omap <C-c> gc

      " Window movement (vim + tmux integration)
      function! TmuxMove(direction)
          let winnr_before = winnr()
          execute 'wincmd ' . a:direction
          " If we press a movement key but don't change windows, it means
          " we're at a border and could change to tmux
          if winnr() == winnr_before
              let tmux_dir = {'h': 'L', 'j': 'D', 'k': 'U', 'l': 'R'}[a:direction]
              silent call system('tmux select-pane -' . tmux_dir)
          endif
      endfunction

      nnoremap <silent> <C-h> :call TmuxMove('h')<CR>
      nnoremap <silent> <C-j> :call TmuxMove('j')<CR>
      nnoremap <silent> <C-k> :call TmuxMove('k')<CR>
      nnoremap <silent> <C-l> :call TmuxMove('l')<CR>

      " Replace buffer with clipboard
      nnoremap <leader>RR ggVG"+p

      " Window management
      nnoremap <leader>oq <C-w>c
      nnoremap <leader>oo <C-w>o
      nnoremap <leader>oh <C-w>s
      nnoremap <leader>ov <C-w>v
      nnoremap <leader>o= <C-w>=

      set termguicolors
      set background=dark
      colorscheme slate
      " Change highlight on open/close parens
      highlight MatchParen guibg=#444444 guifg=#f0c674 gui=underline,bold
      highlight ColorColumn guibg=#4a4a4a

      nnoremap gn :bnext<CR>
      nnoremap gp :bprev<CR>

      " Enable ripgrep smartcase for :grep
      set grepprg=rg\ --vimgrep\ --smart-case
    '';

    # Lua init
    "nvim/lua/init.lua".text = ''
      require("config")
      require("lsp")
      require("git")
      require("symbols")
    '';

    # Main Lua config
    "nvim/lua/config.lua".text = ''
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

      -- fzf setup: use FZF_VIM_PATH env var, or fall back to Ubuntu apt path
      local fzf_path = os.getenv('FZF_VIM_PATH') or '/usr/share/doc/fzf/examples'
      vim.opt.rtp:append(fzf_path)

      -- <leader>ff Open fzf window to search files with preview
      vim.keymap.set('n', '<leader>ff', ':Files<CR>', { desc = "Fuzzy find files" })
      vim.api.nvim_create_user_command('Files', function()
          local preview_pos = vim.o.columns > 120 and "right:60%" or "bottom:50%"
          vim.fn['fzf#run']({
              source = 'fd --type f',
              sink = 'e',
              options = '--reverse --preview "bat --color=always {}" --preview-window=' .. preview_pos,
              window = { width = 0.95, height = 0.9, border = 'rounded' },
          })
      end, {})


      -- <leader>fg Grep and show quickfix list
      vim.keymap.set('n', '<leader>fg', ':Grep<CR>', { desc = "Grep and show quickfix list" })
      vim.api.nvim_create_user_command('Grep', function()
          vim.fn.inputsave()
          local pattern = vim.fn.input('Rg: ')
          vim.fn.inputrestore()
          if pattern ~= "" then
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

                  if path == "" then
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
                  if name == "" then
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
    '';

    # LSP configuration
    "nvim/lua/lsp.lua".text = ''
      vim.api.nvim_create_user_command("Lsp", "checkhealth vim.lsp", {})

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

      vim.keymap.set("n", "<leader>ld", vim.diagnostic.open_float,
          { desc = "Open diagnostic float" })
      vim.keymap.set("n", "<leader>lD", vim.diagnostic.setqflist,
          { desc = "Open diagnostics in quickfix list" })

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
                  [vim.diagnostic.severity.ERROR] = " ",
                  [vim.diagnostic.severity.WARN] = " ",
                  [vim.diagnostic.severity.HINT] = " ",
                  [vim.diagnostic.severity.INFO] = " ",
              },
          },
      })

      vim.lsp.enable({
          "rust_analyzer",
          "pyright",
          "ruff",
          "ts_ls",
          "lua_ls",
          "eslint",
      })
    '';

    # Git integration
    "nvim/lua/git.lua".text = builtins.readFile nvimConfigFiles.gitLua;

    # Symbol picker
    "nvim/lua/symbols.lua".text = builtins.readFile nvimConfigFiles.symbolsLua;

    # LSP server configs
    "nvim/lsp/ruff.lua".text = ''
      return {
          cmd = { 'ruff', 'server' },
          filetypes = { 'python' },
          root_markers = { 'pyproject.toml', 'ruff.toml', '.ruff.toml', '.git' },
      }
    '';

    "nvim/lsp/eslint.lua".text = ''
      return {
          cmd = { "vscode-eslint-language-server", "--stdio" },
          filetypes = { "javascript", "javascriptreact", "typescript", "typescriptreact" },
          root_markers = { ".eslintrc", ".eslintrc.js", ".eslintrc.json", "eslint.config.js", "eslint.config.mjs" },
          settings = {
              workingDirectories = { mode = "auto" },
          },
      }
    '';

    "nvim/lsp/pyright.lua".text = ''
      return {
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
      }
    '';

    "nvim/lsp/lua_ls.lua".text = ''
      return {
          cmd = { 'lua-language-server' },
          filetypes = { 'lua' },
          root_markers = { '.luarc.json', '.luarc.jsonc', '.git' },
      }
    '';

    "nvim/lsp/ts_ls.lua".text = ''
      return {
          cmd = { "typescript-language-server", "--stdio" },
          filetypes = { "javascript", "javascriptreact", "typescript", "typescriptreact" },
          root_markers = { "tsconfig.json", "jsconfig.json", "package.json" },
      }
    '';

    "nvim/lsp/rust_analyzer.lua".text = builtins.readFile nvimConfigFiles.rustAnalyzerLua;

    # Lua language server config
    "nvim/.luarc.json".text = ''
      {
          "diagnostics.globals": [
              "vim"
          ]
      }
    '';
  };
}
