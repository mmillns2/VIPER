{
  description = "VIPER development environment with Python, HDF5, and serial comms";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/25.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        pythonEnv = pkgs.python313.withPackages (ps: with ps; [
          h5py
          numpy
          pandas
          matplotlib
          pyserial
        ]);
      in {
        devShells.default = pkgs.mkShell {
          name = "viper-dev-shell";

          buildInputs = [
            pythonEnv
            pkgs.hdf5
            pkgs.clang-tools
          ];

          shellHook = ''
            export VIPER_DIR="$(pwd)"
            export PATH="$VIPER_DIR/bin:$PATH"

            echo "======================================"
            echo "VIPER Development Environment Activated"
            echo "--------------------------------------"
            echo "VIPER_DIR: $VIPER_DIR"
            echo "Python: $(python3 --version)"
            echo "--------------------------------------"

            if [ -f "$VIPER_DIR/assets/VIPER.txt" ]; then
              cat "$VIPER_DIR/assets/VIPER.txt"
            fi

            echo "Type 'viper <gauge.conf> <recording.conf>' to run."
            echo "======================================"
          '';
        };
      }
    );
}
