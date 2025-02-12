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
__version__ = "1.0.6"
__date__ = "2025-02-12"
__version_highlight__ = "Image viewer: Replace opencv imshow with a tkinter popup window"
__maintainer__ = "Juan Remirez de Esparza"
__email__ = "jremirez@hotmail.com"
__status__ = "Development"

# ######### Imports section ##########

import tkinter as tk
from tkinter import filedialog, scrolledtext, Spinbox, ttk, Label, Toplevel
import PIL.Image, PIL.ImageTk
import os
import cv2
import numpy as np
import time
import sys
try:
    import rawpy
    check_dng_frames_for_misalignment = True
except ImportError:
    check_dng_frames_for_misalignment = False

# Flag to control the processing loop
processing = False
stop_processing_requested = False

# log path
frame_alignment_checker_log_fullpath = ''


# Use a dictionary to store window size
window_size = {'width': 640, 'height': 480}

def is_frame_centered(img, film_type ='S8', threshold=10, slice_width=10):
    # Get dimensions of the binary image
    height, width = img.shape

    # Slice only the left part of the image
    if slice_width > width:
        raise ValueError("Slice width exceeds image width")
    sliced_image = img[:, :slice_width]

    # Convert to pure black and white (binary image)
    _, binary_img = cv2.threshold(sliced_image, 200, 255, cv2.THRESH_BINARY)
    # _, binary_img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)

    # Calculate the middle horizontal line
    middle = height // 2

    # Calculate margin
    margin = height*threshold//100

    # Sum along the width to get a 1D array representing white pixels at each height
    height_profile = np.sum(binary_img, axis=1)
    
    # Find where the sum is non-zero (white areas)
    if film_type == 'S8':
        white_heights = np.where(height_profile > 0)[0]
    else:
        white_heights = np.where(height_profile == 0)[0]
    
    areas = []
    start = None
    min_gap_size = int(height*0.08)  # minimum hole height is around 8% of the frame height
    previous = None
    for i in white_heights:
        if start is None:
            start = i
        if previous is not None and i-previous > 1: # end of first ares, check size
            if previous-start > min_gap_size:  # min_gap_size is minimum number of consecutive pixels to skip small gaps
                areas.append((start, previous - 1))
            start = i
        previous = i
    if start is not None and white_heights[-1]-start > min_gap_size:  # Add the last area if it exists
        areas.append((start, white_heights[-1]))
    
    result = 0
    bigger = 0
    area_count = 0
    for start, end in areas:
        area_count += 1
        if area_count > 2:
            break
        if end-start > bigger:
            bigger = end-start
            center = (start + end) // 2
            result = center
    if result != 0:
        if result >= middle - margin and result <= middle + margin:
            return True, 0
        elif result < middle - margin:
            return False, -(middle - result)
        elif result > middle + margin:
            return False, result - middle
    return False, -1



def show_image_popup(image):
    global window_size
    
    popup = Toplevel()
    popup.title("Image Viewer")

    # Convert the OpenCV image from BGR to RGB
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # Convert the image to a format Tkinter can display
    pil_image = PIL.Image.fromarray(image_rgb)
    photo = PIL.ImageTk.PhotoImage(image=pil_image)

    # Use a Label to display the image
    label = Label(popup, image=photo)
    label.image = photo  # Keep a reference
    label.pack(fill="both", expand=True)

    # Set initial size from saved size
    popup.geometry(f"{window_size['width']}x{window_size['height']}")

    # Make window resizable
    popup.resizable(width=True, height=True)

    # Function to save size and close the popup window
    def on_closing():
        window_size['width'] = popup.winfo_width()
        window_size['height'] = popup.winfo_height()
        popup.destroy()

    popup.protocol("WM_DELETE_WINDOW", on_closing)
    popup.bind('<Escape>', lambda e: on_closing())

    # Update label when window size changes, maintaining aspect ratio
    def on_resize(event):
        # Calculate the new size while maintaining aspect ratio
        img_width, img_height = pil_image.size
        aspect_ratio = img_width / img_height
        if event.width / event.height > aspect_ratio:
            # If window is wider than the image aspect ratio
            new_height = event.height
            new_width = int(new_height * aspect_ratio)
        else:
            # If window is taller than the image aspect ratio
            new_width = event.width
            new_height = int(new_width / aspect_ratio)

        # Resize the image
        resized_image = pil_image.resize((new_width, new_height), PIL.Image.LANCZOS)
        new_photo = PIL.ImageTk.PhotoImage(resized_image)
        
        # Update the label with the new image
        label.configure(image=new_photo)
        label.image = new_photo  # Update reference

    popup.bind('<Configure>', on_resize)


def display_image(image_path, bw=False):
    if check_dng_frames_for_misalignment and image_path.lower().endswith('.dng'):
        with rawpy.imread(image_path) as raw:
            rgb = raw.postprocess()
            # Convert the numpy array to something OpenCV can work with
            img = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    else:
        img = cv2.imread(image_path)

    if img is None:
        raise ValueError("Could not read the image")
    if bw:
        # Convert the image to grayscale
        gray_image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Convert to pure black and white (binary image)
        _, img = cv2.threshold(gray_image, 200, 255, cv2.THRESH_BINARY)

    # Display image
    show_image_popup(img)


def is_frame_in_file_centered(image_path, film_type ='S8', threshold=10, slice_width=10):
    # Read the image
    if check_dng_frames_for_misalignment and image_path.lower().endswith('.dng'):
        with rawpy.imread(image_path) as raw:
            rgb = raw.postprocess()
            # Convert the numpy array to something OpenCV can work with
            img = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    else:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        
    if img is None:
        raise ValueError("Could not read the image")
    
    # Call is_frame_centered with the image
    return is_frame_centered(img, film_type, threshold, slice_width)


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
    global processing, stop_processing_requested
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        result_text.delete(1.0, tk.END)  # Clear previous results
        threshold = int(spinbox.get())  # Get the value from Spinbox
        film_type = film_type_var.get()  # Get the selected mode
        processing = True
        root.config(cursor="watch")  # Change cursor to indicate processing
        stop_processing_requested = False
        stop_button.config(state=tk.NORMAL)  # Enable stop button
        root.after(0, process_images_in_folder, folder_selected, film_type, threshold)
    else:
        result_text.insert(tk.END, "No folder selected\n")


def process_images_in_folder(folder_path, film_type, threshold):
    global processing, stop_processing_requested
    sorted_filenames = sorted(os.listdir(folder_path))

    file_set = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.dng') if check_dng_frames_for_misalignment else ('.png', '.jpg', '.jpeg', '.gif', '.bmp')
    
    total_files = len([f for f in sorted_filenames if f.lower().endswith(file_set)])
    processed_files = 0
    misaligned_counter = 0
    empty_counter = 0
    # Record start time
    start_time = time.time()
    result_text.insert(tk.END, f"Processing {total_files} files in {folder_path}\n")

    for filename in sorted_filenames:
        if stop_processing_requested:  # Check if processing was stopped            
            break
        if filename.lower().endswith(file_set):
            image_path = os.path.join(folder_path, filename)
            centered, gap = is_frame_in_file_centered(image_path, film_type, threshold)
            if not centered:
                if gap == -1:
                    status = "possibly empty" 
                elif gap < 0:
                    status = f"{-gap} pixels too high" 
                else:
                    status = f"{gap} pixels too low"
                message = f"{image_path}, {status}\n"
                result_text.insert(tk.END, message)
                result_text.see(tk.END)
                if gap == -1:
                    empty_counter += 1
                else:
                    misaligned_counter += 1
                with open(frame_alignment_checker_log_fullpath, 'a') as f:
                    f.write(message)

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

    if stop_processing_requested:
        message = f"Processing stopped by user. Duration: {format_duration(duration)}\n"
        result_text.insert(tk.END, message)
        with open(frame_alignment_checker_log_fullpath, 'a') as f:
            f.write(message)
    else:
        message = f"Processing completed (using threshold = {threshold}). Duration: {format_duration(duration)}\n"
        result_text.insert(tk.END, message)
        with open(frame_alignment_checker_log_fullpath, 'a') as f:
            f.write(message)
    if processed_files > 0:
        if misaligned_counter+empty_counter > 0:
            message = f"{processed_files} frames verified, {misaligned_counter} misaligned ({misaligned_counter*100/processed_files:.2f}%), {empty_counter} possibly empty ({empty_counter*100/processed_files:.2f}%).\n"
            result_text.insert(tk.END, message)
            with open(frame_alignment_checker_log_fullpath, 'a') as f:
                f.write(message)
        else:
            message = f"{processed_files} frames verified, all are correctly aligned!!!\n"
            result_text.insert(tk.END, message)
            with open(frame_alignment_checker_log_fullpath, 'a') as f:
                f.write(message)
    # Scroll to the bottom
    result_text.see(tk.END)
    stop_button.config(state=tk.DISABLED)  # Disable stop button after processing ends or is stopped
    processing = False
    root.config(cursor="")  # Change cursor to indicate processing ended


def prevent_input(event):
    # Returning "break" prevents the event from propagating further
    return "break"

def stop_processing():
    global processing, stop_processing_requested
    stop_processing_requested = True


def terminate_main():
    global processing
    if processing:
        root.after(50, terminate_main)
    else:
        root.destroy()


def on_closing():
    global processing, stop_processing_requested
    if processing:
        if tk.messagebox.askokcancel("Quit", "Processing is ongoing. Do you want to stop it and quit?"):
            stop_processing_requested = True
            if processing:
                root.after(50, terminate_main)
            else:
                root.destroy()
    else:
        if tk.messagebox.askokcancel("Quit", "Do you want to quit?"):
            root.destroy()


# Function to update the widget size on window resize
def on_resize(event):
    # We'll resize the frame and the text widget will follow
    root.update_idletasks()


def on_mouse_click(event):
    global processing

    if processing:
        print(f"Processing files, ignoring click")
        return

    # Get the index of the click position
    click_position = event.widget.index(f"@{event.x},{event.y}")
    
    # Extract line number from click position
    line = int(click_position.split('.')[0])
    
    # Define the start and end of the line
    line_start = f"{line}.0"
    line_end = f"{line}.end"
    
    # Remove any previous highlights
    event.widget.tag_remove("highlight", "1.0", tk.END)
    
    # Add highlight to the clicked line
    event.widget.tag_add("highlight", line_start, line_end)
    
    # Get the text of the line (optional, for demonstration)
    line_text = event.widget.get(line_start, line_end)
    if event.num == 1:
        # Left mouse button
        root.after(100, lambda: display_image(line_text.split(',')[0]))  
    elif event.num == 2:
        # Middle mouse button
        print(f"{line_text.split(',')[0]}")
    elif event.num == 3:
        # Right mouse button
        root.after(100, lambda: display_image(line_text.split(',')[0], bw=True))


def keep_cursor(event):
    # If the cursor somehow changes, this will set it back to what we want
    if processing:
        event.widget.config(cursor="watch")  # Or whatever cursor you prefer
    else:
        event.widget.config(cursor="")  # Or whatever cursor you prefer


def init_logging():
    global frame_alignment_checker_log_fullpath

    # Initialize logging
    log_path = os.path.dirname(__file__)
    if log_path == "":
        log_path = os.getcwd()
    log_path = log_path + "/Logs"
    if not os.path.isdir(log_path):
        os.mkdir(log_path)

    # Initialize scan error logging
    frame_alignment_checker_log_fullpath = log_path + "/frame_alignment_checker." + time.strftime("%Y%m%d") + ".log"

def main (argv):
    global result_text, progress_bar, stop_button, root, spinbox, film_type_var

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
    # Bind to any event that might change the cursor; here we use <Enter> and <Leave>
    result_text.bind("<Enter>", keep_cursor)
    result_text.bind("<Leave>", keep_cursor)    
    # Bind the '<Key>' event to the prevent_input function
    result_text.bind("<Key>", prevent_input)
    # Bind the left mouse button click event to our function
    result_text.bind("<Button-1>", on_mouse_click)
    result_text.bind("<Button-2>", on_mouse_click)
    result_text.bind("<Button-3>", on_mouse_click)
    # Configure the highlight tag for appearance
    result_text.tag_configure("highlight", background="yellow", foreground="black")

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

    # Initialize logging
    init_logging()

    # Set up window close protocol
    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Bind the resize event to the update function
    root.bind("<Configure>", on_resize)

    # Set the minimum width to 300 pixels and the minimum height to 200 pixels
    root.minsize(width=600, height=300)

    # Start the GUI
    root.mainloop()


if __name__ == '__main__':
    main(sys.argv[1:])
