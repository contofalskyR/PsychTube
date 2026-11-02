#!/bin/bash
# Double-click to run PsychTube locally (macOS). Serves the site folder at http://localhost:8000
cd "$(dirname "$0")/site" || exit 1
echo "PsychTube at http://localhost:8000  (press Ctrl+C to stop)"
( sleep 1; open "http://localhost:8000" ) &
python3 -m http.server 8000
