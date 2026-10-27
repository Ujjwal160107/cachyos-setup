# 20 cores, 15 GB RAM: tools that start one worker per core exhaust memory, and
# systemd-oomd then kills the whole VS Code scope. Cap the two that do.
set -gx PYTEST_XDIST_AUTO_NUM_WORKERS 6
set -gx PYRIGHT_THREADS 4
