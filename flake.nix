{
  description = "nix derivation for fava-envelope";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

    flake-parts.url = "github:hercules-ci/flake-parts";
    flake-parts.inputs.nixpkgs-lib.follows = "nixpkgs";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    git-hooks-nix = {
      url = "github:cachix/git-hooks.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      flake-parts,
      nixpkgs,
      uv2nix,
      pyproject-nix,
      pyproject-build-systems,
      git-hooks-nix,
      ...
    }@inputs:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];

      imports = [
        git-hooks-nix.flakeModule
      ];

      flake = {
        overlays.default = final: prev: {
          pythonPackagesExtensions = prev.pythonPackagesExtensions ++ [
            (_: python-prev: {
              fava-envelope = python-prev.buildPythonPackage {
                pname = "fava-envelope";
                version = "0.6.0";
                pyproject = true;
                src = inputs.self;
                build-system = [ python-prev.hatchling ];
                dependencies = with python-prev; [
                  fava
                  beanquery
                  beancount
                  polars
                  click
                ];
              };
            })
          ];
        };
      };

      perSystem =
        {
          config,
          system,
          ...
        }:
        let
          inherit (nixpkgs) lib;
          pkgs = import nixpkgs {
            inherit system;
            overlays = [ ];
          };

          workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

          overlay = workspace.mkPyprojectOverlay {
            sourcePreference = "wheel";
          };

          editableOverlay = workspace.mkEditablePyprojectOverlay {
            root = "$REPO_ROOT";
          };

          # Python sets grouped per system
          pythonSets =
            let
              # Base Python package set from pyproject.nix
              baseSet = pkgs.callPackage pyproject-nix.build.packages {
                python = pkgs.python313;
              };

              # An overlay of build fixups & test additions
              pyprojectOverrides = _final: prev: {
                fava-envelope = prev.fava-envelope.overrideAttrs (old: {
                  nativeBuildInputs = old.nativeBuildInputs ++ [
                    _final.editables
                  ];
                });
              };

              buildSystemOverrides =
                final: prev:
                let
                  inherit (final) resolveBuildSystem;
                  inherit (builtins) mapAttrs;
                  # Build system dependencies specified in the shape expected by resolveBuildSystem
                  # The empty lists below are lists of optional dependencies.
                  #
                  # A package `foo` with specification written as:
                  # `setuptools-scm[toml]` in pyproject.toml would be written as
                  # `foo.setuptools-scm = [ "toml" ]` in Nix
                  buildSysOverrides = {
                    # curlify.setuptools = [];
                    # fava-dashboards = {
                    #   hatchling = [];
                    #   hatch-vcs = [];
                    # };
                    # fava-envelope.pdm = [];
                    # ofxparse.setuptools = [];
                    # ofxtools.setuptools = [];
                  };
                in
                mapAttrs (
                  name: spec:
                  prev.${name}.overrideAttrs (old: {
                    nativeBuildInputs = old.nativeBuildInputs ++ resolveBuildSystem spec;
                  })
                ) buildSysOverrides;
            in
            baseSet.overrideScope (
              lib.composeManyExtensions [
                pyproject-build-systems.overlays.default
                overlay
                pyprojectOverrides
                buildSystemOverrides
              ]
            );
        in
        {
          _module.args = { inherit pkgs; };
          pre-commit.settings.hooks = {
            black.enable = true;
            ruff.enable = true;
          };

          devShells.default =
            let
              editablePythonSet = pythonSets.overrideScope editableOverlay;
              venv = editablePythonSet.mkVirtualEnv "fava-envelope-dev-env" {
                fava-envelope = [ "dev" ];
              };
            in
            pkgs.mkShell {
              env = {
                UV_NO_SYNC = "1";
                UV_PYTHON = "${venv}/bin/python";
                UV_PYTHON_DOWNLOADS = "never";
              };
              packages = with pkgs; [
                venv
                uv
                ruff
              ];
              shellHook = ''
                export REPO_ROOT=$(git rev-parse --show-toplevel)
                ${config.pre-commit.installationScript}
                # set a venv folder for basedpyright
                venv="$(cd $(dirname $(which python)); cd ..; pwd)"
                ln -Tsf "$venv" .venv
              '';
            };
          packages = {
            fava-envelope-env = pythonSets.mkVirtualEnv "fava-envelope-env" {
              fava-envelope = [ ];
            };
          };
        };
    };
}
