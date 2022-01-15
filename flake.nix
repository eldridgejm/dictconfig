{
  description = "A recursive, resolvable dictionary.";

  inputs.nixpkgs.url = github:NixOS/nixpkgs/21.11;

  outputs = { self, nixpkgs }: 
    let
      supportedSystems = [ "x86_64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs supportedSystems (system: f system);
    in
      {
        dictconfig = forAllSystems (system:
          with import nixpkgs { system = "${system}"; };

            python3Packages.buildPythonPackage {
              name = "dictconfig";
              src = ./.;
              propagatedBuildInputs = with python3Packages; [ jinja2 ];
              nativeBuildInputs = with python3Packages; [ pytest black ipython sphinx sphinx_rtd_theme ];
            }

          );

        defaultPackage = forAllSystems (system:
            self.dictconfig.${system}
          );
      };

}
