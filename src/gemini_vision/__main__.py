import tkinter as tk
from .app import AppController

def main():
    """The main entry point for the application."""
    if os.name != "posix":
         print("This application is designed for macOS and uses the 'screencapture' utility.")
         return
         
    root = tk.Tk()
    app = AppController(root)
    root.mainloop()

if __name__ == "__main__":
    main()