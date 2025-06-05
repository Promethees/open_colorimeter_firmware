#!/bin/bash

# Exit if any command fails
set -e

echo "Checking if Homebrew is installed..."
if ! command -v brew &>/dev/null; then
  echo "Homebrew not found. Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
  echo "Homebrew is already installed."
fi

echo "Installing Python 3 via Homebrew..."
brew install python

echo "Verifying Python installation..."
python3 --version

echo "Installing hidapi package via pip3..."
pip3 install hidapi

echo "✅ Python and hidapi installed successfully on macOS."
