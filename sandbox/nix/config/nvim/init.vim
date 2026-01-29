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
