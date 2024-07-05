{
  description = "nix derivation for fava-envelope";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs";
    flake-utils.url = "github:numtide/flake-utils";
    pyproject-nix.url = "github:nix-community/pyproject.nix";
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
          # config.allowUnsupportedSystem = true;
          overlays = [
            (
              _: prev: {
                pythonPackagesExtensions =
                  prev.pythonPackagesExtensions
                  ++ [
                    (py-final: _: {
                      fava = py-final.buildPythonPackage rec {
                        pname = "fava";
                        version = "1.27.3";
                        format = "pyproject";
                        src = python.pkgs.fetchPypi {
                          inherit pname version;
                          sha256 = "sha256-GsnXZaazEiOhyjbIinHRD1fdoqlAp3d5csrmtydxmGM=";
                        };
                        nativeBuildInputs = with python.pkgs; [setuptools-scm];
                        propagatedBuildInputs = with python.pkgs; [
                          babel
                          beancount
                          cheroot
                          click
                          flask
                          flask-babel
                          jaraco-functools
                          jinja2
                          markdown2
                          ply
                          simplejson
                          werkzeug
                        ];
                        postPatch = ''
                          substituteInPlace pyproject.toml \
                            --replace 'setuptools_scm>=8.0' 'setuptools_scm'
                        '';
                      };
                    })
                  ];
              }
            )
          ];
        };

        project = inputs.pyproject-nix.lib.project.loadPyproject {
          projectRoot = ./.;
        };

        python = pkgs.python3;
      in {
        devShell = let
          path = "~/repos/personal/fava-envelope/devel";
          entrypoints = {};
          editablePackage = python.pkgs.toPythonModule (
            pkgs.runCommand "fava-envelope-editable"
            {} ''
              mkdir -p "$out/${python.sitePackages}"
              cd "$out/${python.sitePackages}"

              # See https://docs.python.org/3.8/library/site.html for info on such .pth files
              # These add another site package path for each line
              echo '${toString path}' > fava-envelope-editable.pth

              # Create a very simple egg so pkg_resources can find this package
              # See https://setuptools.readthedocs.io/en/latest/formats.html for more info on the egg format
              mkdir "fava-envelope.egg-info"
              cd "fava-envelope.egg-info"

              # Just enough standard PKG-INFO fields for an editable installation
              cat > PKG-INFO <<EOF
              Metadata-Version = "2.1";
              Name = fava-envelope;
              Version = 0.5.8;
              Summary = "";
              EOF

              ${pkgs.lib.optionalString (entrypoints != {}) ''
                cat > entry_points.txt <<EOF
                ${pkgs.lib.generators.toINI {} entrypoints}
                EOF
              ''}
            ''
          );
          arg = project.renderers.withPackages {inherit python;};
          pythonEnv = python.withPackages arg;
        in
          pkgs.mkShell {
            # venvDir = "./.venv";
            packages = with pkgs; [
              pythonEnv
              python.pkgs.black
              # python3Packages.virtualenv
              # python3Packages.venvShellHook
            ];
            shellHook = ''
              venv="$(cd $(dirname $(which python)); cd ..; pwd)"
              ln -Tsf "$venv" .venv
              export PYTHONPATH=./src:$PYTHONPATH
            '';
          };
      }));
}
