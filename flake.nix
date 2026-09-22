{
  description = "A recursive, resolvable dictionary.";

  inputs.nixpkgs.url = github:NixOS/nixpkgs/nixos-24.11;

  outputs = {
    self,
    nixpkgs,
  }: let
    supportedSystems = ["x86_64-linux" "x86_64-darwin" "aarch64-darwin"];
    forAllSystems = f: nixpkgs.lib.genAttrs supportedSystems (system: f system);
  in {
    dictconfig = forAllSystems (
      system:
        with import nixpkgs {system = "${system}";};
          python3Packages.buildPythonPackage {
            name = "dictconfig";
            src = ./.;
            pyproject = true;
            build-system = [ python3Packages.setuptools ];
            propagatedBuildInputs = with python3Packages; [jinja2];
            nativeBuildInputs = (with python3Packages; [pytest black ipython sphinx]) ++ [(python3Packages.sphinx-rtd-theme or python3Packages.sphinx_rtd_theme)];
          }
    );

    defaultPackage = forAllSystems (
      system:
        self.dictconfig.${system}
    );
  };
}
