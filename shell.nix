{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    # Python with specific packages
    (python3.withPackages (ps: with ps; [
      pip
    ]))
  ];

  shellHook = ''
    echo "🚀 dalog Development Environment"
    echo "====================================="
    echo "Python: $(python --version)"
    
    # Create virtual environment
    python -m venv .venv
    source .venv/bin/activate

    # Install dependencies
    pip install -r requirements.txt
    
  '';

  # Environment variables
  PYTHONPATH = ".";
} 