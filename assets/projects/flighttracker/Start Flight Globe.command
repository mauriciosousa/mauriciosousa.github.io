#!/bin/bash
# Double-click to start the Flight Globe helper and open the tracker in your browser.
# Close this window (or press Ctrl+C) to stop it.
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
  exec python3 serve.py
fi
echo "Python 3 is needed to run the helper. Install it with:  xcode-select --install"
read -r -p "Press Return to close."
