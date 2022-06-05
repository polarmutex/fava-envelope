{
  description = "Application packaged using poetry2nix";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs";
  inputs.poetry2nix.url = "github:nix-community/poetry2nix";

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    {
      # Nixpkgs overlay providing the application
      overlay = nixpkgs.lib.composeManyExtensions [
        poetry2nix.overlay
      ];
    } // (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [
            self.overlay
          ];
        };
      in
      {
        devShell =
          let
            fava_envelope_env = pkgs.poetry2nix.mkPoetryEnv {
              projectDir = ./.;
              editablePackageSources = {
                fava_envelope = ./fava_envelope;
              };
              overrides = pkgs.poetry2nix.overrides.withDefaults (
                self: super: {
                  python-magic = pkgs.python39.pkgs.python_magic;
                  numpy = pkgs.python39.pkgs.numpy;
                }
              );
            };
          in
          pkgs.mkShell {
            buildInputs = [
              fava_envelope_env
              pkgs.poetry
            ];
          };
      }));
}
