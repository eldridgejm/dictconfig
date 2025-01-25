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
            format = "pyproject";
            propagatedBuildInputs = with python3Packages; [jinja2];
            nativeBuildInputs = with python3Packages; [setuptools wheel pip];
          }
    );

    devShell = forAllSystems (
      system:
        with import nixpkgs {
          system = "${system}";
        };
          mkShell {
            buildInputs = with python3Packages; [
              pytest
              ruff
              sphinx
              sphinx_rtd_theme

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
