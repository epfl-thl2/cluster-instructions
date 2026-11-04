#!/usr/bin/env bash
# Copy into /thl2/<username>/my-project/run.sh and adapt these paths.
set -euo pipefail
: "${NB_USER:?NB_USER must be set; the submission helper supplies it}"

project_dir="/thl2/${NB_USER}/my-project"
python="/${NB_USER}/venvs/my-project/bin/python"

cd "$project_dir"
# Absolute interpreter path makes environment activation unnecessary.
# Add checkpoint/resume arguments appropriate for your training program.
exec "$python" -u train.py "$@"
