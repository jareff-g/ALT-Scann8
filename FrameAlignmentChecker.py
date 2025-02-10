#!/usr/bin/env python
"""
ALT-Scann8 Utility - Frame Alignment Checker

This tool is standalone utility to check frames already scanned to see if the ar eproperly aligned or not

Licensed under a MIT LICENSE.
"""

__author__ = 'Juan Remirez de Esparza'
__copyright__ = "Copyright 2025, Juan Remirez de Esparza"
__credits__ = ["Juan Remirez de Esparza"]
__license__ = "MIT"
__module__ = "ALT-Scann8 - Frame Alignment Checker"
__version__ = "1.0.1"
__date__ = "2025-02-10"
__version_highlight__ = "Fix initial bugs after first version"
__maintainer__ = "Juan Remirez de Esparza"
__email__ = "jremirez@hotmail.com"
__status__ = "Development"

# ######### Imports section ##########

import tkinter as tk
from tkinter import filedialog, scrolledtext, Spinbox, ttk
import os
import cv2
import numpy as np
import time


def is_frame_centered(image_path, film_type ='S8', threshold=10, slice_width=10):
    # Read the image
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Could not read the image")

    # Convert to pure black and white (binary image)
    _, binary_img = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY)
    # _, binary_img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)

    # Get dimensions of the binary image
    height, width = binary_img.shape

    # Slice only the left part of the image
    if slice_width > width:
        raise ValueError("Slice width exceeds image width")
    sliced_image = binary_img[:, :slice_width]

    # Calculate the middle horizontal line
    middle = height // 2

    # Calculate margin
    margin = height*threshold//100

    # Sum along the width to get a 1D array representing white pixels at each height
    height_profile = np.sum(sliced_image, axis=1)
    
    # Find where the sum is non-zero (white areas)
    if film_type == 'S8':
        white_heights = np.where(height_profile > 0)[0]
    else:
        white_heights = np.where(height_profile == 0)[0]
    
    areas = []
    start = None
    previous = None
    for i in white_heights:
        if start is None:
            start = i
        if previous is not None and i-previous != 1:
            if start is not None:
                areas.append((start, previous - 1))
            start = i
        previous = i
    if start is not None:  # Add the last area if it exists
        areas.append((start, white_heights[-1]))
    
    results = []
    for start, end in areas:
        center = (start + end) // 2
        results.append(center)
    if len(results) != 1:
        return False, -1
    elif results[0] >= middle - margin and results[0] <= middle + margin:
        return True, 0
    elif results[0] < middle - margin:
        return False, (middle - margin) - results[0]
    elif results[0] > middle + margin:
        return False, results[0] - (middle + margin)
    else:
        return False, -1


# Flag to control the processing loop
processing = False

def format_duration(seconds):
    # Convert seconds to days, hours, minutes, and seconds
    days = int(seconds // (24 * 3600))
    seconds %= (24 * 3600)
    hours = int(seconds // 3600)
    seconds %= 3600
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    
    duration_parts = []
    
    # Only add non-zero parts to the list
    if days > 0:
        duration_parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        duration_parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        duration_parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0 or not duration_parts:  # If all other units are zero, still show seconds
        duration_parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    
    # Join the parts with commas and 'and' for the last item
    if len(duration_parts) > 1:
        return ', '.join(duration_parts[:-1]) + ' and ' + duration_parts[-1]
    else:
        return duration_parts[0] if duration_parts else "0 seconds"


def select_folder():
    global processing
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        result_text.delete(1.0, tk.END)  # Clear previous results
        threshold = int(spinbox.get())  # Get the value from Spinbox
        film_type = film_type_var.get()  # Get the selected mode
        processing = True
        stop_button.config(state=tk.NORMAL)  # Enable stop button
        root.after(0, process_images_in_folder, folder_selected, film_type, threshold)
    else:
        result_text.insert(tk.END, "No folder selected\n")

def process_images_in_folder(folder_path, film_type, threshold):
    global processing
    sorted_filenames = sorted(os.listdir(folder_path))
    
    total_files = len([f for f in sorted_filenames if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))])
    processed_files = 0
    misaligned_counter = 0
    # Record start time
    start_time = time.time()

    for filename in sorted_filenames:
        if not processing:  # Check if processing was stopped
            break
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            image_path = os.path.join(folder_path, filename)
            centered, gap = is_frame_centered(image_path, film_type, threshold)
            if not centered:
                result_text.insert(tk.END, f"Misaligned Frame detected: {image_path}, {gap}\n")
                result_text.see(tk.END)
                misaligned_counter += 1
            # Update progress
            processed_files += 1
            progress = (processed_files / total_files) * 100 if total_files > 0 else 0
            progress_bar['value'] = progress
            root.update_idletasks()
            root.update()
    
    # Record end time
    end_time = time.time()

    # Calculate duration
    duration = end_time - start_time

    if processing:
        result_text.insert(tk.END, f"Processing completed (using threshold = {threshold}). Duration: {format_duration(duration)}\n")
    else:
        result_text.insert(tk.END, f"Processing stopped by user. Duration: {format_duration(duration)}\n")
    if processed_files > 0:
        if misaligned_counter > 0:
            result_text.insert(tk.END, f"{processed_files} frames verified, {misaligned_counter} are not correctly aligned ({misaligned_counter*100//processed_files}%).\n")
        else:
            result_text.insert(tk.END, f"{processed_files} frames verified, all are correctly aligned!!!")
    # Scroll to the bottom
    result_text.see(tk.END)
    stop_button.config(state=tk.DISABLED)  # Disable stop button after processing ends or is stopped
    processing = False

def prevent_input(event):
    # Returning "break" prevents the event from propagating further
    return "break"

def stop_processing():
    global processing
    processing = False

def on_closing():
    global processing
    if processing:
        if tk.messagebox.askokcancel("Quit", "Processing is ongoing. Do you want to stop it and quit?"):
            processing = False
            root.destroy()
    else:
        if tk.messagebox.askokcancel("Quit", "Do you want to quit?"):
            root.destroy()

# Main window setup
root = tk.Tk()
root.title(f"ALT-Scann8 utility - Standalone Frame Alignment Checker (v{__version__})")

# Button to select folder
select_button = tk.Button(root, text="Select Folder", command=select_folder)
select_button.pack(pady=5)

# Frame for aligning threshold label
threshold_frame = tk.Frame(root)
threshold_frame.pack(pady=5)
# Label and Spinbox for selecting a threshold
tk.Label(threshold_frame, text="Threshold:").pack(side=tk.LEFT, padx=(20, 5), pady=5)
spinbox = Spinbox(threshold_frame, from_=0, to=100, width=5, textvariable=tk.StringVar(value='10'))
spinbox.pack(side=tk.LEFT, pady=5)

# Frame for aligning radio buttons horizontally
radio_frame = tk.Frame(root)
radio_frame.pack(pady=5)
film_type_var = tk.StringVar(value='S8')  # Default value
tk.Radiobutton(radio_frame, text='S8', variable=film_type_var, value='S8').pack(side=tk.LEFT)
tk.Radiobutton(radio_frame, text='R8', variable=film_type_var, value='R8').pack(side=tk.LEFT)

# Scrolled text widget for displaying results
result_text = scrolledtext.ScrolledText(root, width=40, height=10)
result_text.pack(fill=tk.BOTH, expand=True)
# Bind the '<Key>' event to the prevent_input function
result_text.bind("<Key>", prevent_input)

# Progress bar
progress_bar = ttk.Progressbar(root, length=200, mode='determinate')
progress_bar.pack(pady=5)

# Frame for aligning stop and close buttons horizontally
button_frame = tk.Frame(root)
button_frame.pack(pady=5)
stop_button = tk.Button(button_frame, text="Stop", command=stop_processing, state=tk.DISABLED)
stop_button.pack(side=tk.LEFT, padx=5)
close_button = tk.Button(button_frame, text="Close", command=on_closing)
close_button.pack(side=tk.LEFT, padx=5)

# Set up window close protocol
root.protocol("WM_DELETE_WINDOW", on_closing)

# Function to update the widget size on window resize
def on_resize(event):
    # We'll resize the frame and the text widget will follow
    root.update_idletasks()

# Bind the resize event to the update function
root.bind("<Configure>", on_resize)

# Start the GUI
root.mainloop()


