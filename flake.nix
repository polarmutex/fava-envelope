{
  description = "fava-envelope";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    flake-utils.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, ... }@inputs: inputs.flake-utils.lib.eachSystem [
    "x86_64-linux"
  ]
    (system:
      let pkgs = import nixpkgs {
        inherit system;
      };
      in
      {
        devShell = pkgs.mkShell rec {
          name = "beancount-prj";
          packages = with pkgs; [
            # python
            python3
            poetry
            python3Packages.beancount
          ];
          nativeBuildInputs = [ pkgs.pkg-config ];
          DBUS_PATH = "${pkgs.dbus}";
          shellHook = ''
            source $(poetry env info --path)/bin/activate
          '';
        };
      });
}
