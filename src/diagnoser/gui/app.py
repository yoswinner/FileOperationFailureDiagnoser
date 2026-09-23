"""
Application entry point for the File Operation Failure Diagnoser GUI.

Launch from the project root:

    python -m diagnoser.gui.app

Or on Windows with the project venv:

    .\\venv\\Scripts\\Python.exe -m diagnoser.gui.app
"""

from diagnoser.gui.main_window import MainWindow


def main():
    """Create and run the main application window."""
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
