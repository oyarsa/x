{
  description = "Declarative cloud VM provisioning with Nix + Home Manager";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
      };

      # User configuration - customize these
      userConfig = {
        username = "dev";
        fullName = "Italo Silva";
        email = "italo@maleldil.com";
        homeDirectory = "/home/dev";
      };
    in
    {
      # Home Manager configuration for standalone use on Ubuntu
      homeConfigurations.${userConfig.username} = home-manager.lib.homeManagerConfiguration {
        inherit pkgs;
        extraSpecialArgs = {
          inherit userConfig;
          # Pass config file paths for neovim module
          nvimConfigFiles = {
            gitLua = ./config/nvim/git.lua;
            symbolsLua = ./config/nvim/symbols.lua;
            rustAnalyzerLua = ./config/nvim/rust_analyzer.lua;
          };
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
