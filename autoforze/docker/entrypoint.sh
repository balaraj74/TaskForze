#!/bin/sh
set -e

# First-run: neither config nor workspace exists.
# If config.json is already mounted but workspace is missing we skip onboard to
# avoid the interactive "Overwrite? (y/n)" prompt hanging in a non-TTY container.
if [ ! -d "${HOME}/.autoforze/workspace" ] && [ ! -f "${HOME}/.autoforze/config.json" ]; then
    autoforze onboard
    echo ""
    echo "First-run setup complete."
    echo "Edit ${HOME}/.autoforze/config.json (add your API key, etc.) then restart the container."
    exit 0
fi

exec autoforze gateway "$@"
