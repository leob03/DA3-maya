"""DA3 Maya module startup hook.

Kept intentionally empty. Some Maya/macOS setups are sensitive to creating
menus or shelves from module-level userSetup.py during application startup.
Use `import da3_maya; da3_maya.show()` or create a shelf button manually.
"""
