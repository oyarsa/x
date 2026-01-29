{
  description = "Declarative cloud VM provisioning with Nix + Home Manager";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Claude Code with hourly updates (nixpkgs can lag behind)
    claude-code = {
      url = "github:sadjow/claude-code-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, claude-code, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
      };

      # Claude Code package from the hourly-updated flake
      claude-code-pkg = claude-code.packages.${system}.default;

      # User configuration - customize these
      userConfig = {
        username = "dev";
        fullName = "Italo Silva";
        email = "italo@maleldil.com";
        homeDirectory = "/home/dev";
      };

      # Configuration file paths - edit these files directly for customization
      configFiles = {
        # Neovim configuration
        nvim = {
          initVim = ./config/nvim/init.vim;
          luarc = ./config/nvim/.luarc.json;
          lua = {
            init = ./config/nvim/lua/init.lua;
            config = ./config/nvim/lua/config.lua;
            lsp = ./config/nvim/lua/lsp.lua;
            git = ./config/nvim/lua/git.lua;
            symbols = ./config/nvim/lua/symbols.lua;
          };
          lsp = {
            ruff = ./config/nvim/lsp/ruff.lua;
            eslint = ./config/nvim/lsp/eslint.lua;
            pyright = ./config/nvim/lsp/pyright.lua;
            lua_ls = ./config/nvim/lsp/lua_ls.lua;
            ts_ls = ./config/nvim/lsp/ts_ls.lua;
            rust_analyzer = ./config/nvim/lsp/rust_analyzer.lua;
          };
        };

        # Fish shell configuration
        fish = {
          config = ./config/fish/config.fish;
          confD = {
            envVars = ./config/fish/conf.d/env_vars.fish;
            jj = ./config/fish/conf.d/jj.fish;
          };
          functions = {
            vim = ./config/fish/functions/vim.fish;
            tree = ./config/fish/functions/tree.fish;
            rg = ./config/fish/functions/rg.fish;
            yolo = ./config/fish/functions/yolo.fish;
            fx = ./config/fish/functions/,fx.fish;
            jq = ./config/fish/functions/,jq.fish;
          };
        };

        # Tmux configuration
        tmux = ./config/tmux/tmux.conf;

        # Jujutsu configuration
        jjconfig = ./config/jjconfig.toml;
      };
    in
    {
      # Home Manager configuration for standalone use on Ubuntu
      homeConfigurations.${userConfig.username} = home-manager.lib.homeManagerConfiguration {
        inherit pkgs;
        extraSpecialArgs = {
          inherit userConfig configFiles claude-code-pkg;
        };
        modules = [
          ./home.nix
          ./modules/packages.nix
          ./modules/fish.nix
          ./modules/neovim.nix
          ./modules/tmux.nix
          ./modules/git.nix
          ./modules/starship.nix
        ];
      };

      # Development shell for working on this config
      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [
          nil  # Nix LSP
          nixfmt-rfc-style  # Nix formatter
        ];
      };

      # Packages available in this flake
      packages.${system} = {
        # Bootstrap script as a package
        bootstrap = pkgs.writeShellScriptBin "nix-vm-bootstrap" (builtins.readFile ./bootstrap.sh);
      };

      # Easy activation command
      apps.${system} = {
        default = {
          type = "app";
          program = "${self.packages.${system}.bootstrap}/bin/nix-vm-bootstrap";
        };

        switch = {
          type = "app";
          program = toString (pkgs.writeShellScript "switch" ''
            home-manager switch --flake ${self}#${userConfig.username}
          '');
        };
      };
    };
}
