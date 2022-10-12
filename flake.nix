{
  description = "nix derivation for fava-envelope";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs";
    flake-utils.url = "github:numtide/flake-utils";
    #polar-nur.url = "github:polarmutex/nur";
  };

  outputs = { self, nixpkgs, flake-utils, ... }@inputs:
    { } // (flake-utils.lib.eachSystem [
      "aarch64-linux"
      "aarch64-darwin"
      "x86_64-darwin"
      "x86_64-linux"
    ]
      (system:
        let
          pkgs = import nixpkgs {
            inherit system;
            config.allowUnsupportedSystem = true;
            overlays = [
              #self.overlay
              #polar-nur.overlays.default
            ];
          };
        in
        {

          devShell = pkgs.mkShell rec {
            name = "favaEnvelopePythonEnv";
            venvDir = "./.venv";
            buildInputs = [
              pkgs.pre-commit
              pkgs.python310Packages.python
              pkgs.python310Packages.venvShellHook
              #pkgs.zlib
            ];
            # Run this command, only after creating the virtual environment
            postVenvCreation = ''
              unset SOURCE_DATE_EPOCH
              pip install -r requirements-dev.txt
            '';
            # Now we can execute any commands within the virtual environment.
            # This is optional and can be left out to run pip manually.
            postShellHook = ''
              # export LD_LIBRARY_PATH=${pkgs.stdenv.cc.cc.lib}/lib:${pkgs.zlib}/lib:$LD_LIBRARY_PATH
              export LD_LIBRARY_PATH=${pkgs.stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH
              # allow pip to install wheels
              unset SOURCE_DATE_EPOCH
            '';

          };

        }));
}
