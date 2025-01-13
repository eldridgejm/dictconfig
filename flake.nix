{
  description = "A recursive, resolvable dictionary.";

  inputs.nixpkgs.url = github:NixOS/nixpkgs/nixos-24.11;

  outputs = {
    self,
    nixpkgs,
  }: let
    supportedSystems = ["x86_64-linux" "x86_64-darwin" "aarch64-darwin"];
    forAllSystems = f: nixpkgs.lib.genAttrs supportedSystems (system: f system);
  in rec {
    dictconfig = forAllSystems (
      system:
        with import nixpkgs {system = "${system}";};
          python3Packages.buildPythonPackage {
            name = "dictconfig";
            src = ./.;
            propagatedBuildInputs = with python3Packages; [jinja2];
            nativeBuildInputs = with python3Packages; [pytest black ipython sphinx sphinx_rtd_theme];
          }
    );

    devShell = forAllSystems (
      system:
        with import nixpkgs {
          system = "${system}";
          allowBroken = true;
        };
          mkShell {
            buildInputs = with python3Packages; [
              pytest
              sphinx
              sphinx_rtd_theme
              black
              ruff
              mypy

              # install gradelib package to 1) make sure it's installable, and
              # 2) to get its dependencies. But below we'll add it to PYTHONPATH
              # so we can develop it in place.
              dictconfig.${system}
            ];

            shellHook = ''
              export PYTHONPATH="$(pwd)/src/:$PYTHONPATH"
            '';
          }
    );

    defaultPackage = forAllSystems (
      system:
        self.dictconfig.${system}
    );
  };
}
