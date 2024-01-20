#!/usr/bin/env python
"""
Tooltip - Tooltips chared coe for Aftercan and ALT-Scann8

This module provides tooltips for both projects. Might be converted to a submodule later on.

Licensed under a MIT LICENSE.

More info in README.md file
"""

__author__ = 'Juan Remirez de Esparza'
__copyright__ = "Copyright 2022¡4, Juan Remirez de Esparza"
__credits__ = ["Juan Remirez de Esparza"]
__license__ = "MIT"
__version__ = "1.0"
__date__ = "2024-01-19"
__version_highlight__ = "Tooltips comon coe for ALT-Scann8 and AfterScan"
__maintainer__ = "Juan Remirez de Esparza"
__email__ = "jremirez@hotmail.com"
__status__ = "Development"

import tkinter as tk

DisableTooltips = False
FontSize = 12


def format_tooltip_text(text, max_line_width):
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




def show_tooltip(widget, text):
    global DisableTooltips
    if widget["state"] == 'disabled' or DisableTooltips:
        return
    x, y, _, _ = widget.bbox("insert")
    x += widget.winfo_rootx() + 25
    y += widget.winfo_rooty() + 25

    tooltip_window = tk.Toplevel(widget)
    tooltip_window.wm_overrideredirect(True)
    tooltip_window.wm_geometry(f"+{x}+{y}")

    formatted_text = format_tooltip_text(text, 60)
    label = tk.Label(tooltip_window, text=formatted_text, background="light yellow", relief="solid", borderwidth=1, font=("Arial", FontSize))
    label.pack()

    widget.tooltip_window = tooltip_window

def hide_tooltip(widget):
    if hasattr(widget, 'tooltip_window') and widget.tooltip_window:
        widget.tooltip_window.destroy()
        widget.tooltip_window = None


def setup_tooltip(widget, tooltip_text):
    widget.bind("<Enter>", lambda event: show_tooltip(widget, tooltip_text))
    widget.bind("<Leave>", lambda event: hide_tooltip(widget))


def init_tooltips(font_size):
    global DisableTooltips, FontSize
    FontSize = font_size
    DisableTooltips = False


def disable_tooltips():
    global DisableTooltips
    DisableTooltips = True

