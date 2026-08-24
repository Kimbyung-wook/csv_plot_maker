import os

# Headless test environment: no display available for Qt to attach to.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
