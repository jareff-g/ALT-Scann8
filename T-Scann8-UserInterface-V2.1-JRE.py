import tkinter as tk
from tkinter import filedialog

import tkinter.messagebox
from tkinter import *

# <remove> import pygame
# <remove> from pygame.locals import *
# <remove> import picamera
import os
import time
# <remove> import smbus
from datetime import datetime

# Global variables
FocusState = True
lastFocus = True
FocusZoomActive = False
BaseDir = '/home/juan/Vídeos/'  # dirplats in original Torulf code
CurrentDir = BaseDir
CurrentFrame = 1
CurrentExposure = 0
CurrentExposureStr = "Auto"
NegativeCaptureStatus = False
AdvanceMovieActive = False
RewindMovieActive = False
FastForwardActive = False
OpenFolderActive = False

win = Tk()  # creating the main window and storing the window object in 'win'
win.title('T-Scann 8')  # setting title of the window
win.geometry('1000x800')  # setting the size of the window


def dummy_func():  # Dummy function to get started
    tkinter.messagebox.showinfo("Greetings", "Hello! Welcome to T-Scann 8.")


def exit_app():  # Exit Application
    # Uncomment next two lines when running on RPi
    # <remove> camera.close()
    # <remove> pygame.display.quit()
    win.destroy()

    # poweroff()  # shut down Raspberry PI (remove "#" before poweroff)


def set_free_mode():
    # Uncomment next two lines when running on RPi
    # i2c.write_byte_data(16, 20, 0)
    tkinter.messagebox.showinfo("Free Mode (pending)", "i2c.write_byte_data(16, 20, 0)")

# Enable/Disable camera zoom to facilitate focus
def set_focus_zoom():
    global FocusZoomActive
    # Uncomment relevant next lines when running on RPi (commented with # <remove>)
    if FocusZoomActive == False:
        # <remove> camera.crop = (0.35, 0.35, 0.2, 0.2)  # Activate camera zoon
        time.sleep(.2)
        FocusZoomActive = True
    else:
        # <remove> camera.crop = (0.0, 0.0, 835, 720)  # Remove camera zoom
        FocusZoomActive = False

    tkinter.messagebox.showinfo("Focus Zoom (pending)", "camera.crop")

def set_new_folder():

    CurrentDir = tkinter.filedialog.askdirectory(initialdir=BaseDir, title="Select new folder for capture")
    folder_frame_folder_label.config(text=CurrentDir)

    tkinter.messagebox.showinfo("set_new_folder (pending)", CurrentDir)

def set_existing_folder():

    CurrentDir = tkinter.filedialog.askdirectory(initialdir=BaseDir, title="Select existing folder for capture")
    folder_frame_folder_label.config(text=CurrentDir)

    tkinter.messagebox.showinfo("set_existing_folder (pending)", CurrentDir)


def decrease_exp():
    global CurrentExposure
    global CurrentExposureStr
    # <remove> if CurrentExposure == 0:  # If we are in auto exposure mode, retrieve current value to start from there
        # <remove> CurrentExposure = camera.exposure_speed
    if CurrentExposure >= 2000:
        CurrentExposure -= 2000
    else:
        CurrentExposure = 0  # If we try to go below zero, back to auto exposure
    if CurrentExposure == 0:
        CurrentExposureStr = "Auto"
    else:
        CurrentExposureStr = str(CurrentExposure)

    exposure_frame_value_label.config(text=CurrentExposureStr)


def increase_exp():
    global CurrentExposure
    global CurrentExposureStr
    # <remove> if CurrentExposure == 0:  # If we are in auto exposure mode, retrieve current value to start from there
        # <remove> CurrentExposure = camera.exposure_speed
    CurrentExposure += 2000
    CurrentExposureStr = str(CurrentExposure)

    exposure_frame_value_label.config(text=CurrentExposureStr)


def advance_movie():
    global AdvanceMovieActive

    # Update button text
    if not AdvanceMovieActive:  # Advance movie is about to start...
        AdvanceMovie_btn.config(text='Stop advance movie')  # ...so now we propose to stop it in the button test
    else:
        AdvanceMovie_btn.config(text='Advance Movie')  # Otherwise change to default text to start the action
    AdvanceMovieActive = not AdvanceMovieActive
    # Send instruction to Arduino
    # <remove> i2c.write_byte_data(16, 30, 0)


def rewind_movie():
    global RewindMovieActive

    # Before proceeding, get confirmation from user that fild is correctly routed
    if not RewindMovieActive:  # Ask only when rewind is not ongoing
        answer = tkinter.messagebox.askyesno(title='Security check ',  message='Have you routed the film via the upper path?')
        if not answer:
            return()

    # Update button text
    if not RewindMovieActive:  # Rewind movie is about to start...
        Rewind_btn.config(text='Stop rewind')  # ...so now we propose to stop it in the button test
    else:
        Rewind_btn.config(text='Rewind')  # Otherwise change to default text to start the action
    RewindMovieActive = not RewindMovieActive
    # Send instruction to Arduino
    # <remove> i2c.write_byte_data(16, 30, 0)


def fast_forward_movie():
    global FastForwardActive

    if not FastForwardActive:  # Ask only when rewind is not ongoing
        answer = tkinter.messagebox.askyesno(title='Security check ',  message='Have you routed the film via the upper path?')
        if not answer:
            return()

    # Update button text
    if not FastForwardActive:  # Fast forward movie is about to start...
        FastForward_btn.config(text='Stop Fast Forward')  # ...so now we propose to stop it in the button test
    else:
        FastForward_btn.config(text='Fast Forward')  # Otherwise change to default text to start the action
    FastForwardActive = not FastForwardActive
    # Send instruction to Arduino
    # <remove> i2c.write_byte_data(16, 30, 0)  # TBD!!!!!! Does not exist in Arduino yet, get inspired by rewind


def single_step_movie():
    # <remove> i2c.write_byte_data(16, 40, 0)
    tkinter.messagebox.showinfo("Single Step (pending)", "i2c.write_byte_data(16, 40, 0)")


def negative_capture():
    global NegativeCaptureStatus

    if NegativeCaptureStatus == False:
        NegativeCaptureStatus = not NegativeCaptureStatus
        # <remove> camera.image_effect = 'negative'
        # <remove> camera.awb_gains = (1.7, 1.9)
    # <remove> else:
        # <remove> camera.awb_gains = (3.5, 1.0)
        # <remove> camera.image_effect = 'none'
    NegativeCaptureStatus = not NegativeCaptureStatus

def open_folder():
    global OpenFolderActive

    if not OpenFolderActive :
        OpenFolder_btn.config(text="Close Folder")
        # <remove> camera.start_preview(fullscreen=False, window=(85, 105, 0, 0))
        # <remove> os.system("pcmanfm \"%s\"" % dirplats)
    else:
        OpenFolder_btn.config(text="Open Folder")
        # <remove> os.system("killall pcmanfm")
        time.sleep(.5)
        # <remove> camera.start_preview(fullscreen=False, window=(85, 105, 840, 720))
        time.sleep(.5)

    OpenFolderActive = not OpenFolderActive

# Create horizontal button row at bottom
AdvanceMovie_btn = Button(win, text="Advance Movie", width=8, height=3, command=advance_movie, activebackground='green', activeforeground='white', wraplength=80)
AdvanceMovie_btn.place(x=30, y=650)
SingleStep_btn = Button(win, text="One frame forward", width=8, height=3, command=single_step_movie, activebackground='green', activeforeground='white', wraplength=80)
SingleStep_btn.place(x=130, y=650)
PosNeg_btn = Button(win, text="Pos/Neg", width=8, height=3, command=negative_capture, activebackground='green', activeforeground='white', wraplength=80)
PosNeg_btn.place(x=230, y=650)
Rewind_btn = Button(win, text="Rewind", width=8, height=3, command=rewind_movie, activebackground='green', activeforeground='white', wraplength=80)
Rewind_btn.place(x=330, y=650)
FastForward_btn = Button(win, text="Fast Forward", width=8, height=3, command=fast_forward_movie, activebackground='green', activeforeground='white', wraplength=80)
FastForward_btn.place(x=430, y=650)
Exit_btn = Button(win, text="Exit", width=8, height=3, command=exit_app, bg='red', fg='white', activebackground='green', activeforeground='white', wraplength=80)
Exit_btn.place(x=830, y=650)
# Create vertical button column at right
Start_btn = Button(win, text="START Scan", width=8, height=3, command=dummy_func, activebackground='green', activeforeground='white', wraplength=80)
Start_btn.place(x=830, y=40)
Free_btn = Button(win, text="Free Mode", width=8, height=3, command=set_free_mode, activebackground='green', activeforeground='white', wraplength=80)
Free_btn.place(x=830, y=110)
Focus_btn = Button(win, text="Adjust Focus", width=8, height=3, command=set_focus_zoom, activebackground='green', activeforeground='white', wraplength=80)
Focus_btn.place(x=830, y=180)
OpenFolder_btn = Button(win, text="Open Folder", width=8, height=3, command=open_folder, activebackground='green', activeforeground='white', wraplength=80)
OpenFolder_btn.place(x=830, y=500)

# Create frame to select exposure value
exposure_border_frame = Frame(win, width=8, height=1, bg='white')  # Change to bg to 'black' to have a border
exposure_border_frame.pack()
exposure_border_frame.place(x=530, y=650)

exposure_frame = Frame(exposure_border_frame, width=8, height=1, bg='white')
exposure_frame.pack(side=TOP, padx=1, pady=1)

exposure_frame_title = Frame(exposure_frame, width=8, height=1, bg='white')
exposure_frame_title.pack()
exposure_frame_title_label = Label(exposure_frame_title, text='Camera Exposure', width=14, height=1, bg='white')
exposure_frame_title_label.pack(side=TOP)
exposure_frame_value_label = Label(exposure_frame_title, text=CurrentExposureStr, width=8, height=1, font=("Arial", 20), wraplength=110, bg='white')
exposure_frame_value_label.pack(side=TOP)

exposure_frame_buttons = Frame(exposure_frame, width=8, height=1, bg='white')
exposure_frame_buttons.pack()
decrease_exp_btn = Button(exposure_frame_buttons, text='-', width=1, height=1, font=("Arial", 16, 'bold'), command=decrease_exp, activebackground='green', activeforeground='white', wraplength=80)
decrease_exp_btn.pack(side=LEFT)
increase_exp_btn = Button(exposure_frame_buttons, text='+', width=1, height=1, font=("Arial", 16, 'bold'), command=increase_exp, activebackground='green', activeforeground='white', wraplength=80)
increase_exp_btn.pack(side=LEFT)

# exposure_frame_aux = Frame(exposure_frame, width=8, height=1, bg='white') # Additional frame just to have some whitespace below buttons
# exposure_frame_aux.pack(side=TOP)
# exposure_frame_aux_label = Label(exposure_frame_aux, text='', width=14, height=1, bg='white')
# exposure_frame_aux_label.pack(side=TOP)

# Create frame to select target folder
folder_border_frame = Frame(win, width=16, height=8, bg='black')
folder_border_frame.pack()
folder_border_frame.place(x=810, y=250)

folder_frame = Frame(folder_border_frame, width=16, height=8)
folder_frame.pack(side=TOP, padx=1, pady=1)

folder_frame_title = Frame(folder_frame, width=16, height=4)
folder_frame_title.pack()
folder_frame_title_label = Label(folder_frame_title, text='Target Folder', width=16, height=1)
folder_frame_title_label.pack(side=TOP)
folder_frame_folder_label = Label(folder_frame_title, text=CurrentDir, width=16, height=3, font=("Arial", 8), wraplength=110)
folder_frame_folder_label.pack(side=TOP)

folder_frame_buttons = Frame(folder_frame, width=16, height=4, bd=2)
folder_frame_buttons.pack()
new_folder_btn = Button(folder_frame_buttons, text='New', width=5, height=1, command=set_new_folder, activebackground='green', activeforeground='white', wraplength=80)
new_folder_btn.pack(side=TOP)
existing_folder_btn = Button(folder_frame_buttons, text='Existing', width=5, height=1, command=set_existing_folder, activebackground='green', activeforeground='white', wraplength=80)
existing_folder_btn.pack(side=TOP)

# Create frame to display scanned images
Scanned_Images_border_frame = Frame(win, width=16, height=16, bg='black')
Scanned_Images_border_frame.pack()
Scanned_Images_border_frame.place(x=810, y=400)
Scanned_Images_frame = Frame(Scanned_Images_border_frame, width=16, height=16)
Scanned_Images_frame.pack(side=TOP, padx=1, pady=1)
Scanned_Images_label = Label(Scanned_Images_frame, text='Number of scanned Images', width=16, height=2, wraplength=120, bg='white')
Scanned_Images_label.pack(side=TOP)
Scanned_Image_number_label = Label(Scanned_Images_frame, text=CurrentFrame, font=("Arial", 24), width=5, height=1, wraplength=120, bg='white')
Scanned_Image_number_label.pack(side=TOP, fill='x')

win.mainloop()  # running the loop that works as a trigger
