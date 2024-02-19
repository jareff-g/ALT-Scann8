"""
****************************************************************************************************************
Class Tooltips
Provides tooltips for TKInter widgets
Tooltip - Tooltips shared code for Aftercan and ALT-Scann8

This module provides tooltips for both projects. Might be converted to a submodule later on.

Licensed under a MIT LICENSE.

More info in README.md file
****************************************************************************************************************
"""
__author__ = 'Juan Remirez de Esparza'
__copyright__ = "Copyright 2022/24, Juan Remirez de Esparza"
__credits__ = ["Juan Remirez de Esparza"]
__license__ = "MIT"
__module__ = "Tooltips"
__version__ = "1.0.1"
__date__ = "2024-02-19"
__version_highlight__ = "Tooltips - Converted to class"
__maintainer__ = "Juan Remirez de Esparza"
__email__ = "jremirez@hotmail.com"
__status__ = "Development"

import tkinter as tk

class Tooltips():
    """
    Singleton class - ensures only one instance is ever created.
    """
    _instance = None
    DisableTooltips = False
    FontSize = 12
    screen_width = 0
    active_tooltips = []

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, font_size):
        if not hasattr(self, 'initialized'):
            Tooltips.FontSize = font_size
            Tooltips.DisableTooltips = False
            # Create a temporary root window just for obtaining screen information
            temp_root = tk.Tk()
            # Get the screen height
            Tooltips.screen_width = temp_root.winfo_screenwidth()
            # Destroy the temporary root window
            temp_root.destroy()
            self.initialized = True

    def format_text(self, text, max_line_width):
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            if len(current_line) + len(word) <= max_line_width:
                current_line += word + " "
            else:
                lines.append(current_line.strip())
                current_line = word + " "

        # Add the last line
        if current_line:
            lines.append(current_line.strip())

        return "\n".join(lines)

    def show(self, widget, text):
        if widget["state"] == 'disabled' or Tooltips.DisableTooltips:
            return

        if widget in Tooltips.active_tooltips:
            return  # Do not show again
        else:
            Tooltips.active_tooltips.append(widget)
        x, y = widget.winfo_pointerxy()
        x += 10
        y += 10

        tooltip_window = tk.Toplevel(widget)
        tooltip_window.wm_overrideredirect(True)
        #tooltip_window.wm_geometry(f"+{x}+{y}")

        formatted_text = self.format_text(text, 60)
        label = tk.Label(tooltip_window, text=formatted_text, background="light yellow", relief="solid", borderwidth=1, font=("Arial", Tooltips.FontSize))

        if x + label.winfo_reqwidth() > Tooltips.screen_width:
            x = Tooltips.screen_width - label.winfo_reqwidth()
        tooltip_window.wm_geometry(f"+{x}+{y}")

        label.pack()

        widget.tooltip_window = tooltip_window

    def remove(self, widget, event=None):
        if hasattr(widget, 'tooltip_window') and widget.tooltip_window:
            widget.tooltip_window.destroy()
            widget.tooltip_window = None
            if widget in Tooltips.active_tooltips:
                Tooltips.active_tooltips.remove(widget)


    def schedule_remove(self, widget, event=None):
        widget.after(20, lambda: self.remove(widget))

    def add(self, widget, tooltip_text):
        widget.bind("<Enter>", lambda event: self.show(widget, tooltip_text))
        widget.bind("<Leave>", lambda event: self.schedule_remove(widget))


    def disable(self):
        Tooltips.DisableTooltips = True

