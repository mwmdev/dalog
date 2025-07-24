#!/bin/bash

set -e

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "Error: .env file not found"
    echo "Please create a .env file with your PyPI credentials:"
    echo "PYPI_TOKEN=your_pypi_token"
    echo "TESTPYPI_TOKEN=your_testpypi_token"
    exit 1
fi

# Check required environment variables
if [ -z "$PYPI_TOKEN" ] || [ -z "$TESTPYPI_TOKEN" ]; then
    echo "Error: Missing required environment variables"
    echo "Please set PYPI_TOKEN and TESTPYPI_TOKEN in your .env file"
    exit 1
fi

# Function to build package
build_package() {
    echo "Building package..."
    nix-shell --run "python -m build"
    echo "Package built successfully"
}

# Function to publish to TestPyPI
publish_test() {
    echo "Publishing to TestPyPI..."
    nix-shell --run "TWINE_USERNAME=__token__ TWINE_PASSWORD=$TESTPYPI_TOKEN twine upload --repository testpypi --verbose dist/*"
    echo "Published to TestPyPI successfully"
}

# Function to publish to PyPI
publish_prod() {
    echo "Publishing to PyPI..."
    nix-shell --run "TWINE_USERNAME=__token__ TWINE_PASSWORD=$PYPI_TOKEN twine upload --verbose dist/*"
    echo "Published to PyPI successfully"
}

# Function to clean dist directory
clean_dist() {
    if [ -d "dist" ]; then
        echo "Cleaning dist directory..."
        rm -rf dist/
    fi
}

# Main script logic
case "$1" in
    "test")
        clean_dist
        build_package
        publish_test
        ;;
    "prod")
        clean_dist
        build_package
        publish_prod
        ;;
    "both")
        clean_dist
        build_package
        publish_test
        echo "Waiting 5 seconds before publishing to PyPI..."
        sleep 5
        publish_prod
        ;;
    *)
        echo "Usage: $0 {test|prod|both}"
        echo ""
        echo "Commands:"
        echo "  test  - Publish to TestPyPI only"
        echo "  prod  - Publish to PyPI only"
        echo "  both  - Publish to TestPyPI first, then PyPI"
        echo ""
        echo "Make sure to create a .env file with:"
        echo "PYPI_TOKEN=your_pypi_token"
        echo "TESTPYPI_TOKEN=your_testpypi_token"
        exit 1
        ;;
esac