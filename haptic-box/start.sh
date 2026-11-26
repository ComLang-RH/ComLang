#!/usr/bin/env bash
# Launch the Haptic Palm Writer app with the live 3D simulation of the CAD model.
#   ./start.sh            (from anywhere)
set -e
cd "$(dirname "$(readlink -f "$0")")"

if [ ! -x .venv/bin/python ]; then
  echo "Creating Python environment (.venv)..."
  python3 -m venv .venv
fi
if ! .venv/bin/python -c "import numpy, vosk, sounddevice" 2>/dev/null; then
  echo "Installing Python packages..."
  .venv/bin/pip install --quiet numpy vosk sounddevice pyserial
fi

# (Re)build the CAD meshes when missing or when the CAD macro changed.
if [ ! -f build/v2_mesh.json ] || [ haptic_box_v2.FCMacro -nt build/v2_mesh.json ] || [ hand_model.py -nt build/v2_mesh.json ]; then
  if command -v freecadcmd >/dev/null; then
    echo "Building the CAD model with FreeCAD (a few minutes: clearance + hand-fit checks)..."
    HAPTIC_DUMP=build/v2_mesh.json freecadcmd haptic_box_v2.FCMacro | grep -E "CLEARANCES|INTERFERENCE|HAND FIT" || true
  else
    echo "FreeCAD (freecadcmd) not found: the 3D view will be unavailable, the rest works."
  fi
fi

exec .venv/bin/python haptic_app.py "$@"
