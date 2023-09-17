{
  description = "nix derivation for fava-envelope";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs";
    flake-utils.url = "github:numtide/flake-utils";
    #polar-nur.url = "github:polarmutex/nur";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    ...
  } @ inputs:
    {}
    // (flake-utils.lib.eachSystem [
        "aarch64-linux"
        "aarch64-darwin"
        "x86_64-darwin"
        "x86_64-linux"
      ]
      (system: let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnsupportedSystem = true;
          overlays = [
            #self.overlay
            #polar-nur.overlays.default
          ];
        };
      in {
        devShell = pkgs.mkShell {
          venvDir = "./.venv";
          packages = with pkgs; [
            pdm
            python311
            python311Packages.virtualenv
            python311Packages.venvShellHook
          ];

          postVenvCreation = ''
            unset SOURCE_DATE_EPOCH
            pdm install
          '';

          LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
            pkgs.stdenv.cc.cc
            # Add any missing library needed
            # You can use the nix-index package to locate them, e.g. nix-locate -w --top-level --at-root /lib/libudev.so.1
          ];
        };
      }));
}
