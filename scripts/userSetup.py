"""DA3 Maya module startup hook.

Intentionally does not create Maya UI during application startup. Some Maya
setups are sensitive to module-level userSetup.py creating menus, shelves, or
workspace controls before the main UI is fully settled.
"""
