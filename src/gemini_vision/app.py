import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
from tkinter import ttk
import subprocess
import os
import threading
import google.generativeai as genai
from PIL import Image, ImageTk
import re
import time
from markdown2 import Markdown
from tkhtmlview import HTMLText

# --- Main Application GUI Class ---
class GeminiVisionApp:
    def __init__(self, root):
        """
        Initializes the main application window and its widgets.
        """
        self.root = root
        self.root.title("Gemini Vision Assistant")
        self.root.geometry("1200x800") 
        
        # --- Light Theme Color Palette ---
        self.colors = {
            "root_bg": "#ececec",
            "frame_bg": "#ececec",
            "label_fg": "#333333",
            "button_bg": "#007aff",
            "button_fg": "gray20", # Preserving user's change
            "button_disabled_bg": "#c7c7c7",
            "entry_bg": "white",
            "entry_fg": "#333333",
            "text_bg": "white",
            "text_fg": "#333333",
            "status_bg": "#e0e0e0"
        }
        
        self.root.configure(bg=self.colors["root_bg"])

        # --- Member Variables ---
        self.api_key_var = tk.StringVar()
        self.model_var = tk.StringVar()
        self.last_loaded_api_key = None
        self.temp_screenshot_path = "temp_screenshot.png"
        self.thumbnail_image = None # To prevent garbage collection
        self.raw_markdown_result = "" # To store the original markdown for copy/save

        # --- API Key Storage Path ---
        self.cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "gemini_vision_app")
        self.api_key_file = os.path.join(self.cache_dir, "api_key.txt")
        self.permission_flag_file = os.path.join(self.cache_dir, ".permission.granted")

        # --- UI Setup ---
        self.create_widgets()
        
        # --- Load API Key on Startup ---
        self.load_api_key()
        
        # --- Show one-time permission dialog if needed ---
        self.root.after(100, self.check_and_show_permission_dialog_once)

    def create_widgets(self):
        style_args = {'bg': self.colors["frame_bg"], 'fg': self.colors["label_fg"], 'font': ('Helvetica Neue', 14)}
        button_style = {'bg': self.colors["button_bg"], 'fg': self.colors["button_fg"], 'font': ('Helvetica Neue', 13, 'bold'), 'relief': 'flat', 'padx': 10, 'pady': 8, 'borderwidth': 0}
        entry_style = {'bg': self.colors["entry_bg"], 'fg': self.colors["entry_fg"], 'insertbackground': self.colors["entry_fg"], 'relief': 'solid', 'borderwidth': 1, 'highlightthickness': 1, 'highlightcolor': self.colors["button_bg"], 'highlightbackground': '#cccccc', 'font': ('Helvetica Neue', 14)}

        top_controls_frame = tk.Frame(self.root, bg=style_args['bg'])
        top_controls_frame.pack(pady=10, padx=20, fill='x')

        # Add a shrink button
        shrink_button = tk.Button(top_controls_frame, text="Shrink to 💎", **button_style, command=self.shrink_to_floater)
        shrink_button.pack(side='right', padx=(10,0))

        api_frame = tk.Frame(top_controls_frame, bg=style_args['bg'])
        api_frame.pack(fill='x', expand=True, pady=(0, 5))
        tk.Label(api_frame, text="Gemini API Key:", **style_args).pack(side='left', anchor='w')
        self.api_key_entry = tk.Entry(api_frame, textvariable=self.api_key_var, show="*", width=40, **entry_style)
        self.api_key_entry.pack(side='left', padx=(10, 0), fill='x', expand=True)
        self.api_key_entry.bind("<FocusOut>", self.on_api_key_change)

        model_frame = tk.Frame(top_controls_frame, bg=style_args['bg'])
        model_frame.pack(fill='x', expand=True, pady=(0, 10))
        tk.Label(model_frame, text="Model:", **style_args).pack(side='left', anchor='w')
        self.model_var.set("Enter API Key to load models")
        self.model_menu = ttk.OptionMenu(model_frame, self.model_var, self.model_var.get())
        self.model_menu.pack(side='left', padx=(60, 0), fill='x', expand=True)
        self.model_menu.config(state=tk.DISABLED)

        paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned_window.pack(fill='both', expand=True, padx=20, pady=10)

        self.left_pane = ttk.Frame(paned_window, padding=10)
        paned_window.add(self.left_pane, weight=1)

        tk.Label(self.left_pane, text="1. Capture & Prompt", **style_args).pack(anchor='w', pady=(0, 5))
        self.capture_button = tk.Button(self.left_pane, text="Capture Window", **button_style, command=self.run_capture_workflow)
        self.capture_button.pack(fill='x', pady=(0, 10))
        self.capture_button.config(state=tk.DISABLED, bg=self.colors["button_disabled_bg"])

        self.thumbnail_label = tk.Label(self.left_pane, bg=self.colors['entry_bg'], relief='solid', borderwidth=1)
        self.thumbnail_label.pack(fill='both', expand=True, pady=(0, 10))

        tk.Label(self.left_pane, text="What to learn? (Optional)", **style_args).pack(anchor='w', pady=(5, 5))
        self.prompt_entry = tk.Entry(self.left_pane, width=70, **entry_style)
        self.prompt_entry.pack(fill='x', pady=(0, 10))
        self.prompt_entry.insert(0, "Transcribe this into a Markdown document.")

        self.process_button = tk.Button(self.left_pane, text="Process with Gemini", **button_style, command=self.run_processing_workflow)
        self.process_button.pack(fill='x')
        self.process_button.config(state=tk.DISABLED, bg=self.colors["button_disabled_bg"])

        right_pane = ttk.Frame(paned_window, padding=10)
        paned_window.add(right_pane, weight=1)

        tk.Label(right_pane, text="2. Review Result", **style_args).pack(anchor='w', pady=(0, 5))
        self.result_text = HTMLText(right_pane, background=self.colors['text_bg'])
        self.result_text.pack(fill='both', expand=True, pady=(0, 10))
        self.result_text.set_html("<p>Results will appear here...</p>")
        
        action_frame = tk.Frame(right_pane)
        action_frame.pack(fill='x')
        self.copy_button = tk.Button(action_frame, text="Copy Markdown", **button_style, command=self.copy_to_clipboard)
        self.copy_button.pack(side='left', expand=True, padx=(0, 5))
        self.save_button = tk.Button(action_frame, text="Save as .md", **button_style, command=self.save_as_markdown)
        self.save_button.pack(side='right', expand=True, padx=(5, 0))

        self.status_var = tk.StringVar()
        self.status_var.set("Ready. Enter API Key to begin.")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W, bg=self.colors["status_bg"], fg=self.colors["label_fg"], font=('Helvetica Neue', 11))
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def set_floater(self, floater):
        self.floater = floater

    def shrink_to_floater(self):
        self.root.withdraw()
        self.floater.deiconify()

    def on_api_key_change(self, event=None): self.fetch_and_update_models()
    def load_api_key(self):
        try:
            if os.path.exists(self.api_key_file):
                with open(self.api_key_file, 'r') as f:
                    api_key = f.read().strip()
                    if api_key:
                        self.api_key_var.set(api_key)
                        self.status_var.set("API Key loaded. Fetching models...")
                        self.fetch_and_update_models()
        except Exception as e: self.status_var.set(f"Could not load API key: {e}")
    def save_api_key(self, api_key):
        if not api_key: return
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(self.api_key_file, 'w') as f: f.write(api_key)
        except Exception as e: self.status_var.set(f"Could not save API key: {e}")
    def fetch_and_update_models(self):
        api_key = self.api_key_var.get().strip()
        if not api_key or api_key == self.last_loaded_api_key: return
        self.status_var.set("Fetching available models...")
        self.capture_button.config(state=tk.DISABLED, bg=self.colors["button_disabled_bg"])
        self.model_menu.config(state=tk.DISABLED)
        threading.Thread(target=self._fetch_models_thread, args=(api_key,)).start()
    def _fetch_models_thread(self, api_key):
        try:
            genai.configure(api_key=api_key)
            vision_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods and ('vision' in m.name or 'flash' in m.name)]
            if not vision_models: raise Exception("No compatible vision models found.")
            def get_sort_key(name):
                latest = 1 if 'latest' in name else 0
                version = float(match.group(1)) if (match := re.search(r'(\d+\.\d+)', name)) else 0.0
                return (-latest, -version, name)
            sorted_models = sorted(vision_models, key=get_sort_key)
            self.root.after(0, self._update_model_menu, sorted_models, api_key)
        except Exception as e: self.root.after(0, messagebox.showerror, "API Error", f"Failed to fetch models: {e}")
    def _update_model_menu(self, models, api_key):
        self.last_loaded_api_key = api_key
        menu = self.model_menu["menu"]
        menu.delete(0, "end")
        for name in models:
            menu.add_command(label=name, command=lambda v=name: self.model_var.set(v))
        default = 'models/gemini-2.5-flash'
        self.model_var.set(default if default in models else models[0])
        self.model_menu.config(state=tk.NORMAL)
        self.capture_button.config(state=tk.NORMAL, bg=self.colors["button_bg"])
        self.status_var.set("Models loaded. Ready to capture.")
        self.save_api_key(api_key)
    def check_and_show_permission_dialog_once(self):
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            if not os.path.exists(self.permission_flag_file):
                self.show_permission_dialog()
                with open(self.permission_flag_file, 'w') as f: f.write('granted')
        except Exception as e: print(f"Could not create permission flag file: {e}")
    def show_permission_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Permission Required")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("550x250")
        dialog.configure(bg=self.colors["root_bg"])
        main_frame = tk.Frame(dialog, bg=self.colors["root_bg"], padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)
        tk.Label(main_frame, text="Screen Recording Permission Needed", font=('Helvetica Neue', 16, 'bold'), bg=self.colors["root_bg"], fg=self.colors["label_fg"]).pack(pady=(0, 10))
        instructions = "To capture your screen, this application needs Screen Recording permission.\n\nPlease grant access in System Settings to the application you are using to run this script (e.g., Terminal or Visual Studio Code)."
        tk.Label(main_frame, text=instructions, font=('Helvetica Neue', 13), wraplength=500, justify="left", bg=self.colors["root_bg"], fg=self.colors["label_fg"]).pack(pady=(0, 20))
        button_frame = tk.Frame(main_frame, bg=self.colors["root_bg"])
        button_frame.pack(fill="x")
        def open_settings(): subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?ScreenRecording"])
        tk.Button(button_frame, text="Open System Settings", font=('Helvetica Neue', 13, 'bold'), bg=self.colors["button_bg"], fg=self.colors["button_fg"], relief="flat", command=open_settings).pack(side="left", expand=True, padx=5)
        tk.Button(button_frame, text="OK", font=('Helvetica Neue', 13), command=dialog.destroy).pack(side="right", expand=True, padx=5)
        self.root.wait_window(dialog)
    def run_capture_workflow(self):
        self.capture_button.config(state=tk.DISABLED)
        self.process_button.config(state=tk.DISABLED, bg=self.colors["button_disabled_bg"])
        threading.Thread(target=self._capture_thread).start()
    def _capture_thread(self):
        self.root.after(0, lambda: self.status_var.set("Taking screenshot... Please select a window."))
        self.root.after(0, self.root.withdraw)
        try:
            time.sleep(0.1) # Ensure the window is hidden
            subprocess.run(["screencapture", "-i", self.temp_screenshot_path], check=True)
            self.root.after(0, self.root.deiconify)
            if not os.path.exists(self.temp_screenshot_path):
                self.root.after(0, lambda: self.status_var.set("Screenshot cancelled. Ready."))
                self.root.after(0, lambda: self.capture_button.config(state=tk.NORMAL))
                return
            self.root.after(0, self._display_thumbnail)
        except subprocess.CalledProcessError:
            self.root.after(0, lambda: self.status_var.set("Screenshot failed or was cancelled."))
            self.root.after(0, self.root.deiconify)
            self.root.after(0, lambda: self.capture_button.config(state=tk.NORMAL))
    def _display_thumbnail(self):
        try:
            img = Image.open(self.temp_screenshot_path)
            max_width = self.left_pane.winfo_width()
            if max_width <= 1: max_width = 550
            max_height = 450
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            self.thumbnail_image = ImageTk.PhotoImage(img)
            self.thumbnail_label.config(image=self.thumbnail_image)
            self.status_var.set("Screenshot captured. Ready to process.")
            self.capture_button.config(state=tk.NORMAL)
            self.process_button.config(state=tk.NORMAL, bg=self.colors["button_bg"])
        except Exception as e: messagebox.showerror("Thumbnail Error", f"Could not display screenshot preview: {e}")
    def run_processing_workflow(self):
        if not os.path.exists(self.temp_screenshot_path):
            messagebox.showwarning("Warning", "No screenshot has been captured yet.")
            return
        self.capture_button.config(state=tk.DISABLED)
        self.process_button.config(state=tk.DISABLED, text="Processing...")
        threading.Thread(target=self._processing_thread).start()
    def _processing_thread(self):
        try:
            api_key = self.api_key_var.get()
            user_prompt = self.prompt_entry.get().strip() or "Transcribe this screenshot into a Markdown document."
            selected_model = self.model_var.get()
            self.root.after(0, lambda: self.status_var.set(f"Calling {os.path.basename(selected_model)}..."))
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(selected_model)
            img = Image.open(self.temp_screenshot_path)
            response = model.generate_content([user_prompt, img])
            self.raw_markdown_result = response.text
            markdown_converter = Markdown()
            html_content = markdown_converter.convert(self.raw_markdown_result)
            def update_ui_with_result():
                self.result_text.set_html(html_content)
                self.status_var.set("Success! Displaying result.")
            self.root.after(0, update_ui_with_result)
        except Exception as e:
            def show_error():
                self.status_var.set("An error occurred.")
                messagebox.showerror("Error", str(e))
            self.root.after(0, show_error)
        finally:
            self.root.after(0, self.reset_buttons_after_processing)
    def reset_buttons_after_processing(self):
        self.capture_button.config(state=tk.NORMAL)
        self.process_button.config(state=tk.NORMAL, text="Process with Gemini")
    def copy_to_clipboard(self):
        if self.raw_markdown_result:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.raw_markdown_result)
            self.status_var.set("Markdown result copied to clipboard.")
        else: self.status_var.set("Nothing to copy.")
    def save_as_markdown(self):
        if not self.raw_markdown_result:
            self.status_var.set("Nothing to save."); return
        file_path = filedialog.asksaveasfilename(defaultextension=".md", filetypes=[("Markdown Files", "*.md"), ("All Files", "*.*")], title="Save As")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f: f.write(self.raw_markdown_result)
                self.status_var.set(f"File saved to {os.path.basename(file_path)}")
            except Exception as e: messagebox.showerror("Save Error", f"Could not save file:\n{e}")

# --- Floating Button Window ---
class FloatingButton:
    def __init__(self, root, expand_callback, quit_callback):
        self.root = root
        self.expand_callback = expand_callback
        self.quit_callback = quit_callback
        
        # Create a Toplevel window for the floater
        self.floater = tk.Toplevel(root)
        self.floater.geometry("50x50+100+100")
        
        # Make it borderless and always on top
        self.floater.overrideredirect(True)
        self.floater.overrideredirect(False) # A temporary fix for macOS focus issues
        self.floater.wm_attributes("-topmost", True)
        
        # Create a button with the gem icon
        self.button = tk.Button(self.floater, 
                                text="💎", 
                                font=("Helvetica Neue", 24), 
                                command=self.expand_callback, 
                                relief="flat", 
                                bg="#ececec",
                                highlightthickness=0, # Explicitly remove border highlight
                                borderwidth=0)
        self.button.pack(expand=True, fill="both")
        
        # Create the right-click menu
        self.menu = tk.Menu(self.floater, tearoff=0)
        self.menu.add_command(label="Quit", command=self.quit_callback)

        # Bind events
        self.button.bind("<ButtonPress-1>", self.start_move)
        self.button.bind("<ButtonRelease-1>", self.stop_move)
        self.button.bind("<B1-Motion>", self.do_move)
        # Bind right-click for macOS and other systems
        self.button.bind("<Button-2>", self.show_menu)
        self.button.bind("<Button-3>", self.show_menu)

        self._offset_x = 0
        self._offset_y = 0

    def show_menu(self, event):
        """Displays the right-click context menu."""
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def start_move(self, event):
        self._offset_x = event.x
        self._offset_y = event.y

    def stop_move(self, event):
        self._offset_x = 0
        self._offset_y = 0

    def do_move(self, event):
        x = self.floater.winfo_pointerx() - self._offset_x
        y = self.floater.winfo_pointery() - self._offset_y
        self.floater.geometry(f"+{x}+{y}")
        
    def deiconify(self):
        self.floater.deiconify()

    def withdraw(self):
        self.floater.withdraw()
    
# --- Main Application Controller ---
class AppController:
    def __init__(self, root):
        self.root = root
        self.root.withdraw() # Hide the main tk root window

        # Create the main app window (initially hidden)
        self.main_window = tk.Toplevel(self.root)
        self.gui = GeminiVisionApp(self.main_window)
        self.main_window.protocol("WM_DELETE_WINDOW", self.shrink_from_window)
        self.main_window.withdraw()

        # Create the floating button and pass the quit callback
        self.floater = FloatingButton(self.root, self.expand_from_floater, self.quit_app)
        self.gui.set_floater(self.floater)
        
        # Handle Command-Q to quit the entire application
        self.root.createcommand('tk::mac::Quit', self.quit_app)

    def expand_from_floater(self):
        self.floater.withdraw()
        self.main_window.deiconify()
        self.main_window.lift()
        self.main_window.focus_force()
        
    def shrink_from_window(self):
        """Hides the main window and shows the floater."""
        self.main_window.withdraw()
        self.floater.deiconify()

    def quit_app(self):
        """Gracefully shuts down the entire application."""
        # Schedule the destroy command to avoid race conditions with the menu
        self.root.after(10, self.root.destroy)