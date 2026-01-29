{ config, pkgs, lib, configFiles, ... }:

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

  # Neovim configuration files - using source to preserve editor support
  xdg.configFile = {
    "nvim/init.vim".source = configFiles.nvim.initVim;
    "nvim/.luarc.json".source = configFiles.nvim.luarc;

    # Lua modules
    "nvim/lua/init.lua".source = configFiles.nvim.lua.init;
    "nvim/lua/config.lua".source = configFiles.nvim.lua.config;
    "nvim/lua/lsp.lua".source = configFiles.nvim.lua.lsp;
    "nvim/lua/git.lua".source = configFiles.nvim.lua.git;
    "nvim/lua/symbols.lua".source = configFiles.nvim.lua.symbols;

    # LSP server configurations
    "nvim/lsp/ruff.lua".source = configFiles.nvim.lsp.ruff;
    "nvim/lsp/eslint.lua".source = configFiles.nvim.lsp.eslint;
    "nvim/lsp/pyright.lua".source = configFiles.nvim.lsp.pyright;
    "nvim/lsp/lua_ls.lua".source = configFiles.nvim.lsp.lua_ls;
    "nvim/lsp/ts_ls.lua".source = configFiles.nvim.lsp.ts_ls;
    "nvim/lsp/rust_analyzer.lua".source = configFiles.nvim.lsp.rust_analyzer;
  };
}
