#!/usr/bin/env python
"""
ALT-Scann8 UI - Alternative software for T-Scann 8

This tool is a fork of the original user interface application of T-Scann 8

Some additional features of this version include:
- PiCamera 2 integration
- Use of Tkinter instead of Pygame
- Automatic exposure support
- Fast forward support

Licensed under a MIT LICENSE.

More info in README.md file
"""

__author__ = 'Juan Remirez de Esparza'
__copyright__ = "Copyright 2022, Juan Remirez de Esparza"
__credits__ = ["Juan Remirez de Esparza"]
__license__ = "MIT"
__version__ = "1.0"
__maintainer__ = "Juan Remirez de Esparza"
__email__ = "jremirez@hotmail.com"
__status__ = "Development"

# ######### Imports section ##########
import tkinter as tk
from tkinter import filedialog

import tkinter.messagebox
import tkinter.simpledialog
from tkinter import *

from PIL import ImageTk, Image

import os
import subprocess
import time
import json

from enum import Enum

from datetime import datetime
import logging
import sys
import getopt
import numpy

try:
    import smbus
    try:
        from picamera2 import Picamera2, Preview
        from libcamera import Transform
        # Global variable to isolate camera specific code (Picamera vs PiCamera2)
        IsPiCamera2 = True
    except ImportError:
        # If PiCamera2 cannot be imported, it will default to PiCamera legacy, so no need to change this
        IsPiCamera2 = False
        import picamera
        from io import BytesIO

    # Global variable to allow basic UI testing on PC (where PiCamera imports should fail)
    SimulatedRun = False
except ImportError:
    SimulatedRun = True
    IsPiCamera2 = False

import threading
import queue


#  ######### Global variable definition ##########
FocusState = True
lastFocus = True
FocusZoomActive = False
FocusZoomPosX = 0.35
FocusZoomPosY = 0.35
FocusZoomFactorX = 0.2
FocusZoomFactorY = 0.2
FreeWheelActive = False
BaseDir = '/home/juan/Vídeos/'  # dirplats in original code from Torulf
CurrentDir = BaseDir
CurrentFrame = 0  # bild in original code from Torulf
CurrentStill = 1  # used to take several stills of same frame, for settings analysis
CurrentScanStartTime = datetime.now()
CurrentScanStartFrame = 0
NegativeCaptureActive = False
HdrCaptureActive = False
HqCaptureActive = False
AdvanceMovieActive = False
RewindMovieActive = False  # SpolaState in original code from Torulf
RewindErrorOutstanding = False
RewindEndOutstanding = False
rwnd_speed_delay = 200   # informational only, should be in sync with Arduino, but for now we do not secure it
FastForwardActive = False
FastForwardErrorOutstanding = False
FastForwardEndOutstanding = False
OpenFolderActive = False
ScanOngoing = False  # PlayState in original code from Torulf (opposite meaning)
ScanStopRequested = False  # To handle stopping scan process asynchronously, with same button as start scan
NewFrameAvailable = False  # To be set to true upon reception of Arduino event
ScanProcessError = False  # To be set to true upon reception of Arduino event
ScanProcessError_LastTime = 0
ScriptDir = os.path.dirname(
    sys.argv[0])  # Directory where python scrips run, to store the json file with persistent data
PersistedDataFilename = os.path.join(ScriptDir, "ALT-Scann8.json")
PersistedDataLoaded = False
ArduinoTrigger = 0
MinFrameStepsS8 = 290
MinFrameStepsR8 = 240
MinFrameSteps = MinFrameStepsS8     # Minimum number of steps per frame, to be passed to Arduino
PTLevelS8 = 80
PTLevelR8 = 120
PTLevel = PTLevelS8     # Phototransistor reported level when hole is detected
# Token to be sent on program closure, to allow threads to shut down cleanly
END_TOKEN = object()
FrameArrivalTime = 0
# Variables to track windows movement and set preview accordingly
TopWinX = 0
TopWinY = 0
PreviewWinX = 90
PreviewWinY = 75
DeltaX = 0
DeltaY = 0
WinInitDone = False
FolderProcess = 0
LoggingMode = "WARNING"
LogLevel = 0
draw_capture_label = 0
button_lock_counter = 0

PiCam2PreviewEnabled=False
CaptureStabilizationDelay = 0.25
PostviewCounter = 0
FramesPerMinute = 0
RPiTemp = 0
last_temp = 1  # Needs to be different from RPiTemp the first time
TempInFahrenheit = False
LastTempInFahrenheit = False
save_bg = 'gray'
save_fg = 'black'
ZoomSize = 0
simulated_captured_frame_list = [None] * 1000
raw_simulated_capture_image = ''
simulated_capture_image = ''
simulated_images_in_list = 0
FilmHoleY = 300
SharpnessValue = 1

# Expert mode variables - By default Exposure and white balance are set as automatic, with adapt delay
ExpertMode = False
ExperimentalMode = False
MatchWaitMargin = 50    # Margin allowed to consider exposure/WB matches previous frame
                        # % of absolute value (1 for AWB color gain, and 8000 for exposure)
                        # That ,means we wait until the difference between a frame and the previous one is less
                        # than a percentage of the tolerance value
Tolerance_AE = 8000
Tolerance_AWB = 1
CurrentExposure = 0     # Zero means automatic exposure
ExposureAdaptPause = True   # by default (non-expert) we wait for camera to stabilize when AE changes
PreviousCurrentExposure = 0  # Used to spot changes in exposure, and cause a delay to allow camera to adapt
CurrentExposureStr = "Auto"
CurrentAwbAuto = False   # AWB disabled by default
AwbPause = False   # by default (non-expert) we wait for camera to stabilize when AWB changes
GainRed = 2.2  # 2.4
GainBlue = 2.2  # 2.8
PreviousGainRed = 1
PreviousGainBlue = 1

# Statistical information about where time is spent (expert mode only)
total_wait_time_preview_display = 0
total_wait_time_awb = 0
total_wait_time_autoexp = 0
session_start_time = 0
session_frames=0
max_wait_time = 5000
last_click_time = 0

ALT_Scann8_controller_detected = False

PreviewWarnAgain = True

FPM_LastMinuteFrameTimes = list()
FPM_StartTime = time.ctime()
FPM_CalculatedValue = -1
VideoCaptureActive = False

# *** HDR variables
image_list = []
dry_run_iterations = 3
min_exp = 10  # Originally 0.9
max_exp = 150 # Origially 56
num_steps = 4
step_value = 1
exp_list = []

# Persisted data
# Persisted data
SessionData = {
    "CurrentDate": str(datetime.now()),
    "CurrentDir": CurrentDir,
    "CurrentFrame": str(CurrentFrame),
    "CurrentExposure": str(CurrentExposure),
    "FilmHoleY": str(FilmHoleY),
    "NegativeCaptureActive": str(NegativeCaptureActive),
    "HdrCaptureActive": str(HdrCaptureActive),
    "HqCaptureActive": str(HqCaptureActive),
    "FilmType": 'S8',
    "MinFrameStepsS8": 290,
    "MinFrameStepsR8":  260,
    "MinFrameSteps":  290,
    "PTLevelS8":  80,
    "PTLevelR8":  200,
    "PTLevel":  80
}


def send_arduino_command(cmd, param=12345):
    global SimulatedRun, ALT_Scann8_controller_detected

    if not SimulatedRun:
        if ALT_Scann8_controller_detected or cmd == 1:
            #i2c.write_byte_data(16, cmd, 0)  # Send command to Arduino
            i2c.write_i2c_block_data(16, cmd, [int(param%256), int(param/256)])  # Send command to Arduino
            logging.debug("Sending command %i to Arduino", cmd)
        else:
            logging.error("Trying to send command %i to Arduino, "
                          "but ALT version not detected", cmd)


def exit_app():  # Exit Application
    global win
    global SimulatedRun
    global camera
    global PreviewMode

    # Uncomment next two lines when running on RPi
    if not SimulatedRun:
        send_arduino_command(11)   # Tell Arduino we stop (to turn off uv led
        # Close preview if required
        if not IsPiCamera2 or PiCam2PreviewEnabled:
            camera.stop_preview()
        camera.close()
    # Write session data upon exit
    with open(PersistedDataFilename, 'w') as f:
        json.dump(SessionData, f)

    win.destroy()

    # poweroff()  # shut down Raspberry PI (remove "#" before poweroff)


def set_free_mode():
    global FreeWheelActive
    global save_bg, save_fg
    global SimulatedRun
    global Free_btn

    if not FreeWheelActive:
        Free_btn.config(text='Lock Reels', bg='red', fg='white', relief=SUNKEN)
    else:
        Free_btn.config(text='Unlock Reels', bg=save_bg, fg=save_fg, relief=RAISED)

    if not SimulatedRun:
        send_arduino_command(20)

    FreeWheelActive = not FreeWheelActive

    # Enable/Disable related buttons
    button_status_change_except(Free_btn, FreeWheelActive)


# Enable/Disable camera zoom to facilitate focus
def set_focus_zoom():
    global FocusZoomActive
    global save_bg, save_fg
    global SimulatedRun
    global ZoomSize, Focus_btn
    global focus_lf_btn, focus_up_btn, focus_dn_btn, focus_rt_btn, focus_plus_btn, focus_minus_btn

    if not FocusZoomActive:
        Focus_btn.config(text='Focus Zoom OFF', bg='red', fg='white', relief=SUNKEN)
        if not SimulatedRun:
            if IsPiCamera2:
                camera.set_controls({"ScalerCrop": (int(0.35 * ZoomSize[0]), int(0.35 * ZoomSize[1])) +
                                                   (int(0.2 * ZoomSize[0]), int(0.2 * ZoomSize[1]))})
            else:
                camera.crop = (0.35, 0.35, 0.2, 0.2)  # Activate camera zoom
    else:
        Focus_btn.config(text='Focus Zoom ON', bg=save_bg, fg=save_fg, relief=RAISED)
        if not SimulatedRun:
            if IsPiCamera2:
                camera.set_controls({"ScalerCrop": (0, 0) + (ZoomSize[0], ZoomSize[1])})
            else:
                camera.crop = (0.0, 0.0, 835, 720)  # Remove camera zoom

    time.sleep(.2)
    FocusZoomActive = not FocusZoomActive

    # Enable/Disable related buttons
    button_status_change_except(Focus_btn, FocusZoomActive)
    # Enable disable buttons for focus move
    if ExpertMode:
        focus_lf_btn.config(state=NORMAL if FocusZoomActive else DISABLED)
        focus_up_btn.config(state=NORMAL if FocusZoomActive else DISABLED)
        focus_dn_btn.config(state=NORMAL if FocusZoomActive else DISABLED)
        focus_rt_btn.config(state=NORMAL if FocusZoomActive else DISABLED)
        focus_plus_btn.config(state=NORMAL if FocusZoomActive else DISABLED)
        focus_minus_btn.config(state=NORMAL if FocusZoomActive else DISABLED)

def adjust_focus_zoom():
    if not SimulatedRun:
        if IsPiCamera2:
            camera.set_controls({"ScalerCrop": (int(FocusZoomPosX * ZoomSize[0]), int(FocusZoomPosY * ZoomSize[1])) +
                                               (int(FocusZoomFactorX * ZoomSize[0]), int(FocusZoomFactorY * ZoomSize[1]))})
        else:
            camera.crop = (FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX, FocusZoomFactorY)  # Activate camera zoom


def set_focus_up():
    global FocusZoomPosX, FocusZoomPosY
    if FocusZoomPosY > 0.05:
        FocusZoomPosY = round(FocusZoomPosY - 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom up (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX, FocusZoomFactorY)

def set_focus_left():
    global FocusZoomPosX, FocusZoomPosY
    if FocusZoomPosX > 0.05:
        FocusZoomPosX = round(FocusZoomPosX - 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom left (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX, FocusZoomFactorY)


def set_focus_right():
    global FocusZoomPosX, FocusZoomPosY
    if FocusZoomPosX < (1-(FocusZoomFactorX - 0.05)):
        FocusZoomPosX = round(FocusZoomPosX + 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom right (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX, FocusZoomFactorY)


def set_focus_down():
    global FocusZoomPosX, FocusZoomPosY
    if FocusZoomPosY < (1-(FocusZoomFactorY - 0.05)):
        FocusZoomPosY = round(FocusZoomPosY + 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom down (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX, FocusZoomFactorY)

def set_focus_plus():
    global FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX, FocusZoomFactorY
    if FocusZoomFactorX >= 0.2:
        FocusZoomFactorX = round(FocusZoomFactorX - 0.1, 1)
        # Zoom factor is the same for X and Y, so we can safely add everything in the if statement for X
        if FocusZoomFactorY >= 0.2:
            FocusZoomFactorY = round(FocusZoomFactorY - 0.1, 1)
        # Adjust origin so that zoom is centered
        FocusZoomPosX = round(FocusZoomPosX + 0.05, 2)
        FocusZoomPosY = round(FocusZoomPosY + 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom plus (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX, FocusZoomFactorY)

def set_focus_minus():
    global FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX, FocusZoomFactorY
    if FocusZoomFactorX < 0.9:
        FocusZoomFactorX = round(FocusZoomFactorX + 0.1, 1)
        # Zoom factor is the same for X and Y, so we can safely add everything in the if statement for X
        if FocusZoomFactorY < 0.9:
            FocusZoomFactorY = round(FocusZoomFactorY + 0.1, 1)
        # Adjust origin so that zoom is centered
        FocusZoomPosX = round(FocusZoomPosX - 0.05, 2)
        FocusZoomPosY = round(FocusZoomPosY - 0.05, 2)
        # Adjust boundaries if needed
        if FocusZoomPosX < 0:
            FocusZoomPosX = 0
        if FocusZoomPosY < 0:
            FocusZoomPosY = 0
        if FocusZoomPosX + FocusZoomFactorX > 1:
            FocusZoomPosX = round(1 - FocusZoomFactorX, 2)
        if FocusZoomPosY + FocusZoomFactorY > 1:
            FocusZoomPosY = round(1 - FocusZoomFactorY, 2)
        adjust_focus_zoom()
        logging.debug("Zoom plus (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX, FocusZoomFactorY)


# A couple of helper funtcions to hide/display preview when needed (displaying popups with picamera legacy)
def hide_preview():
    if not SimulatedRun and not IsPiCamera2:
        camera.stop_preview()


def display_preview():
    if not SimulatedRun and not IsPiCamera2:
        camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))


def set_new_folder():
    global CurrentDir, CurrentFrame
    global SimulatedRun
    global folder_frame_target_dir
    global Scanned_Images_number_label

    requested_dir = ""

    # CurrentDir = tkinter.filedialog.askdirectory(initialdir=BaseDir, title="Select parent folder first")
    CurrentDir = BaseDir
    # folder_frame_target_dir.config(text=CurrentDir)
    # Disable preview to make tkinter dialogs visible
    hide_preview()
    while requested_dir == "" or requested_dir is None:
        requested_dir = tk.simpledialog.askstring(title="Enter new folder name", prompt="New folder name?")
        if requested_dir is None:
            return
        if requested_dir == "":
            tk.messagebox.showerror("Error!", "Please specify a name for the folder to be created.")

    newly_created_dir = os.path.join(CurrentDir, requested_dir)

    if not os.path.isdir(newly_created_dir):
        os.mkdir(newly_created_dir)
        CurrentFrame = 0
        CurrentDir = newly_created_dir
    else:
        tk.messagebox.showerror("Error!", "Folder " + requested_dir + " already exists!")

    display_preview()

    folder_frame_target_dir.config(text=CurrentDir)
    Scanned_Images_number_label.config(text=str(CurrentFrame))
    SessionData["CurrentDir"] = str(CurrentDir)
    SessionData["CurrentFrame"] = str(CurrentFrame)


def set_existing_folder():
    global CurrentDir, CurrentFrame
    global SimulatedRun

    # Disable preview to make tkinter dialogs visible
    hide_preview()
    if not SimulatedRun:
        CurrentDir = tk.filedialog.askdirectory(initialdir=BaseDir, title="Select existing folder for capture")
    else:
        CurrentDir = tk.filedialog.askdirectory(initialdir=BaseDir,
                                                title="Select existing folder with snapshots for simulated run")
    if not CurrentDir:
        return
    else:
        folder_frame_target_dir.config(text=CurrentDir)
        SessionData["CurrentDir"] = str(CurrentDir)

    current_frame_str = tk.simpledialog.askstring(title="Enter number of last captured frame",
                                                  prompt="Last frame captured?")
    if current_frame_str is None:
        CurrentFrame = 0
        return
    else:
        if current_frame_str == '':
            current_frame_str = '0'
        CurrentFrame = int(current_frame_str)
        Scanned_Images_number_label.config(text=current_frame_str)
        SessionData["CurrentFrame"] = str(CurrentFrame)

    display_preview()


# In order to display a non-too-cryptic value for the exposure (what we keep in 'CurrentExposure')
# we will convert it to a higher level by using a similar algorythm as the one used by torulf in his original code:
# We take '20000' as the base reference of zero, with chunks of 2000's up and down moving the counter by one unit
# 'CurrentExposure' = zero wil always be displayed as 'Auto'

def decrease_exp():
    global CurrentExposure, CurrentExposureStr
    global SimulatedRun

    if not ExpertMode:
        return

    if not SimulatedRun:
        if CurrentExposure == 0:  # If we are in auto exposure mode, retrieve current value to start from there
            if IsPiCamera2:
                metadata = camera.capture_metadata()
                CurrentExposure = metadata["ExposureTime"]
                # CurrentExposure = camera.controls.ExposureTime # Does not work, need to get all metadata
            else:
                CurrentExposure = camera.exposure_speed

    if CurrentExposure >= 2000:
        CurrentExposure -= 2000
    else:
        CurrentExposure = 1  # Do not allow zero or below

    if CurrentExposure == 0:
        CurrentExposureStr = "Auto"
    else:
        CurrentExposureStr = str(round((CurrentExposure - 20000) / 2000))

    if CurrentExposure != "Auto":
        SessionData["CurrentExposure"] = str(CurrentExposure)

    exposure_frame_value_label.config(text=CurrentExposureStr)
    exposure_frame.config(text="Auto Exposure " + ('ON' if CurrentExposure == 0 else 'OFF'))

    if not SimulatedRun:
        if IsPiCamera2:
            camera.controls.ExposureTime = CurrentExposure  # maybe will not work, check pag 26 of picamera2 specs
        else:
            camera.shutter_speed = CurrentExposure
    auto_exp_wait_checkbox.config(state=DISABLED)


def auto_exp():
    global CurrentExposure, CurrentExposureStr

    if not ExpertMode:
        return

    if (CurrentExposure != 0):
        CurrentExposure = 0
        CurrentExposureStr = "Auto"
        SessionData["CurrentExposure"] = CurrentExposureStr
        exposure_frame_value_label.config(text=CurrentExposureStr)
        if not SimulatedRun:
            if IsPiCamera2:
                camera.controls.ExposureTime = CurrentExposure  # maybe will not work, check pag 26 of picamera2 specs
            else:
                camera.shutter_speed = CurrentExposure
    else:
        if not SimulatedRun:
            # Since we are in auto exposure mode, retrieve current value to start from there
            if IsPiCamera2:
                metadata = camera.capture_metadata()
                CurrentExposure = metadata["ExposureTime"]
                # CurrentExposure = camera.controls.ExposureTime # Does not work, need to get all metadata
            else:
                CurrentExposure = camera.exposure_speed
        else:
            CurrentExposure = 3500  # Arbitrary Value for Simulated run
        CurrentExposureStr = str(round((CurrentExposure - 20000) / 2000))

    exposure_frame_value_label.config(text=CurrentExposureStr)
    exposure_frame.config(text="Auto Exposure " + ('ON' if CurrentExposure == 0 else 'OFF'))
    auto_exp_wait_checkbox.config(state=NORMAL if CurrentExposure == 0 else DISABLED)
    decrease_exp_btn.config(state=NORMAL if CurrentExposure != 0 else DISABLED)
    increase_exp_btn.config(state=NORMAL if CurrentExposure != 0 else DISABLED)


def increase_exp():
    global CurrentExposure, CurrentExposureStr
    global SimulatedRun

    if not ExpertMode:
        return

    if not SimulatedRun:
        if CurrentExposure == 0:  # If we are in auto exposure mode, retrieve current value to start from there
            if IsPiCamera2:
                metadata = camera.capture_metadata()
                CurrentExposure = metadata["ExposureTime"]
                # CurrentExposure = camera.controls.ExposureTime
            else:
                CurrentExposure = camera.exposure_speed
    CurrentExposure += 2000
    CurrentExposureStr = str(round((CurrentExposure - 20000) / 2000))

    SessionData["CurrentExposure"] = str(CurrentExposure)

    exposure_frame_value_label.config(text=CurrentExposureStr)
    exposure_frame.config(text="Auto Exposure " + ('ON' if CurrentExposure == 0 else 'OFF'))

    if not SimulatedRun:
        if IsPiCamera2:
            camera.controls.ExposureTime = CurrentExposure
        else:
            camera.shutter_speed = CurrentExposure
    auto_exp_wait_checkbox.config(state=DISABLED)


def auto_exposure_change_pause_selection():
    global auto_exposure_change_pause
    global ExposureAdaptPause
    ExposureAdaptPause = auto_exposure_change_pause.get()
    SessionData["ExposureAdaptPause"] = str(ExposureAdaptPause)


def auto_white_balance_change_pause_selection():
    global auto_white_balance_change_pause
    global AwbPause
    AwbPause = auto_white_balance_change_pause.get()
    SessionData["AwbPause"] = str(AwbPause)


def colour_gain_red_plus():
    global colour_gains_red_value_label
    global GainBlue, GainRed

    if not ExpertMode:
        return()

    GainRed += 0.1
    SessionData["GainRed"] = str(GainRed)
    colour_gains_red_value_label.config(text=str(round(GainRed, 1)))
    if not SimulatedRun and not CurrentAwbAuto:
        if IsPiCamera2:
            # camera.set_controls({"AwbEnable": 0})
            camera.set_controls({"ColourGains": (GainRed, GainBlue)})
        else:
            # camera.awb_mode = 'off'
            camera.awb_gains = (GainRed, GainBlue)


def colour_gain_red_minus():
    global colour_gains_red_value_label
    global GainBlue, GainRed

    if not ExpertMode:
        return ()

    GainRed -= 0.1
    SessionData["GainRed"] = str(GainRed)
    colour_gains_red_value_label.config(text=str(round(GainRed, 1)))
    if not SimulatedRun and not CurrentAwbAuto:
        if IsPiCamera2:
            # camera.set_controls({"AwbEnable": 0})
            camera.set_controls({"ColourGains": (GainRed, GainBlue)})
        else:
            # camera.awb_mode = 'off'
            camera.awb_gains = (GainRed, GainBlue)


def colour_gain_blue_plus():
    global colour_gains_blue_value_label
    global GainBlue, GainRed

    if not ExpertMode:
        return ()

    GainBlue += 0.1
    SessionData["GainBlue"] = str(GainBlue)
    colour_gains_blue_value_label.config(text=str(round(GainBlue, 1)))
    if not SimulatedRun and not CurrentAwbAuto:
        if IsPiCamera2:
            # camera.set_controls({"AwbEnable": 0})
            camera.set_controls({"ColourGains": (GainRed, GainBlue)})
        else:
            # camera.awb_mode = 'off'
            camera.awb_gains = (GainRed, GainBlue)


def colour_gain_blue_minus():
    global colour_gains_blue_value_label
    global GainBlue, GainRed

    if not ExpertMode:
        return ()

    GainBlue -= 0.1
    SessionData["GainBlue"] = str(GainBlue)
    colour_gains_blue_value_label.config(text=str(round(GainBlue, 1)))
    if not SimulatedRun and not CurrentAwbAuto:
        if IsPiCamera2:
            # camera.set_controls({"AwbEnable": 0})
            camera.set_controls({"ColourGains": (GainRed, GainBlue)})
        else:
            # camera.awb_mode = 'off'
            camera.awb_gains = (GainRed, GainBlue)


def colour_gain_auto():
    global CurrentAwbAuto
    global GainBlue, GainRed
    global colour_gains_auto_btn, awb_frame
    global colour_gains_red_btn_plus, colour_gains_red_btn_minus
    global colour_gains_blue_btn_plus, colour_gains_blue_btn_minus
    global colour_gains_red_value_label, colour_gains_blue_value_label

    if not ExpertMode:
        return ()

    CurrentAwbAuto = not CurrentAwbAuto
    SessionData["CurrentAwbAuto"] = str(CurrentAwbAuto)
    SessionData["GainRed"] = str(GainRed)
    SessionData["GainBlue"] = str(GainBlue)

    if CurrentAwbAuto:
        awb_frame.config(text='Automatic White Balance ON')
        awb_wait_checkbox.config(state=NORMAL)
        colour_gains_red_btn_plus.config(state=DISABLED)
        colour_gains_red_btn_minus.config(state=DISABLED)
        colour_gains_blue_btn_plus.config(state=DISABLED)
        colour_gains_blue_btn_minus.config(state=DISABLED)
        colour_gains_red_value_label.config(text="Auto")
        colour_gains_blue_value_label.config(text="Auto")
        if not SimulatedRun:
            if IsPiCamera2:
                camera.set_controls({"AwbEnable": 1})
            else:
                camera.awb_mode = 'auto'
    else:
        awb_frame.config(text='Automatic White Balance OFF')
        awb_wait_checkbox.config(state=DISABLED)
        colour_gains_red_btn_plus.config(state=NORMAL)
        colour_gains_red_btn_minus.config(state=NORMAL)
        colour_gains_blue_btn_plus.config(state=NORMAL)
        colour_gains_blue_btn_minus.config(state=NORMAL)
        if not SimulatedRun:
            if IsPiCamera2:
                # Retrieve current gain values from Camera
                metadata = camera.capture_metadata()
                camera_colour_gains = metadata["ColourGains"]
                GainRed = camera_colour_gains[0]
                GainBlue = camera_colour_gains[1]
                colour_gains_red_value_label.config(text=str(round(GainRed, 1)))
                colour_gains_blue_value_label.config(text=str(round(GainBlue, 1)))
                camera.set_controls({"AwbEnable": 0})
            else:
                GainRed = camera.awb_gains[0]
                GainBlue = camera.awb_gains[1]
                colour_gains_red_value_label.config(text=str(round(GainRed, 1)))
                colour_gains_blue_value_label.config(text=str(round(GainBlue, 1)))
                camera.awb_mode = 'off'
                camera.awb_gains = (GainRed, GainBlue)
        else:  # Add fake values for simulated run
            colour_gains_red_value_label.config(text=str(round(GainRed, 1)))
            colour_gains_blue_value_label.config(text=str(round(GainBlue, 1)))


def min_frame_steps_selection(updown):
    global min_frame_steps_spinbox, min_frame_steps_str
    global MinFrameSteps
    MinFrameSteps = int(min_frame_steps_spinbox.get())
    SessionData["MinFrameSteps"] = MinFrameSteps
    SessionData["MinFrameSteps" + SessionData["FilmType"]] = MinFrameSteps
    send_arduino_command(52, MinFrameSteps)


def min_frame_steps_spinbox_focus_out(event):
    global min_frame_steps_spinbox, min_frame_steps_str
    global MinFrameSteps
    MinFrameSteps = int(min_frame_steps_spinbox.get())
    SessionData["MinFrameSteps"] = MinFrameSteps
    SessionData["MinFrameSteps" + SessionData["FilmType"]] = MinFrameSteps
    send_arduino_command(52, MinFrameSteps)


def pt_level_selection(updown):
    global pt_level_spinbox, pt_level_str
    global PTLevel
    PTLevel = int(pt_level_spinbox.get())
    SessionData["PTLevel"] = PTLevel
    SessionData["PTLevel" + SessionData["FilmType"]] = PTLevel
    send_arduino_command(50, PTLevel)


def pt_level_spinbox_focus_out(event):
    global pt_level_spinbox, pt_level_str
    global PTLevel
    PTLevel = int(pt_level_spinbox.get())
    SessionData["PTLevel"] = PTLevel
    SessionData["PTLevel" + SessionData["FilmType"]] = PTLevel
    send_arduino_command(50, PTLevel)


def stabilization_delay_down():
    global stabilization_delay, CaptureStabilizationDelay

    if (CaptureStabilizationDelay > 0):
        CaptureStabilizationDelay -= 0.01
        CaptureStabilizationDelay = round(CaptureStabilizationDelay, 2)
    stabilization_delay.config(text=str(round(CaptureStabilizationDelay * 1000))+' ms')
    SessionData["CaptureStabilizationDelay"] = str(CaptureStabilizationDelay)

def stabilization_delay_up():
    global stabilization_delay, CaptureStabilizationDelay

    if (CaptureStabilizationDelay < 0.5):
        CaptureStabilizationDelay += 0.01
        CaptureStabilizationDelay = round(CaptureStabilizationDelay, 2)
    stabilization_delay.config(text=str(round(CaptureStabilizationDelay * 1000))+' ms')
    SessionData["CaptureStabilizationDelay"] = str(CaptureStabilizationDelay)

def rwnd_speed_down():
    global rwnd_speed_delay
    global rwnd_speed_control_delay

    if not SimulatedRun:
        send_arduino_command(62)
    if rwnd_speed_delay + rwnd_speed_delay*0.1 < 4000:
        rwnd_speed_delay += rwnd_speed_delay*0.1
    else:
        rwnd_speed_delay = 4000
    #rwnd_speed_control_delay.config(text=str(round((2000-rwnd_speed_delay)*100/1800))+'%')
    rwnd_speed_control_delay.config(text=str(round(60/(rwnd_speed_delay * 375 / 1000000))) + 'rpm')

def rwnd_speed_up():
    global rwnd_speed_delay
    global rwnd_speed_control_delay

    if not SimulatedRun:
        send_arduino_command(63)
    if rwnd_speed_delay -rwnd_speed_delay*0.1 > 200:
        rwnd_speed_delay -= rwnd_speed_delay*0.1
    else:
        rwnd_speed_delay = 200
    #rwnd_speed_control_delay.config(text=str(round((2000-rwnd_speed_delay)*100/1800))+'%')
    rwnd_speed_control_delay.config(text=str(round(60/(rwnd_speed_delay * 375 / 1000000))) + 'rpm')


def button_status_change_except(except_button, active):
    global Free_btn, SingleStep_btn, Snapshot_btn, AdvanceMovie_btn
    global Rewind_btn, FastForward_btn, Start_btn
    global PosNeg_btn, Focus_btn, Start_btn, Exit_btn
    global film_type_S8_btn, film_type_R8_btn
    global PiCam2_preview_btn, hdr_btn, hq_btn, turbo_btn
    global button_lock_counter

    if active:
        button_lock_counter += 1
    else:
        button_lock_counter -= 1
    if button_lock_counter > 1 or (not active and button_lock_counter > 0):
        return
    if except_button != Free_btn:
        Free_btn.config(state=DISABLED if active else NORMAL)
    if except_button != SingleStep_btn:
        SingleStep_btn.config(state=DISABLED if active else NORMAL)
    if except_button != Snapshot_btn:
        Snapshot_btn.config(state=DISABLED if active else NORMAL)
    if except_button != AdvanceMovie_btn:
        AdvanceMovie_btn.config(state=DISABLED if active else NORMAL)
    if except_button != Rewind_btn:
        Rewind_btn.config(state=DISABLED if active else NORMAL)
    if except_button != FastForward_btn:
        FastForward_btn.config(state=DISABLED if active else NORMAL)
    if except_button != PosNeg_btn:
        PosNeg_btn.config(state=DISABLED if active else NORMAL)
    if except_button != Focus_btn and not IsPiCamera2:
        Focus_btn.config(state=DISABLED if active else NORMAL)
    if except_button != Start_btn and (not IsPiCamera2 or not PiCam2PreviewEnabled):
        Start_btn.config(state=DISABLED if active else NORMAL)
    if except_button != Exit_btn:
        Exit_btn.config(state=DISABLED if active else NORMAL)
    if except_button != film_type_S8_btn:
        film_type_S8_btn.config(state=DISABLED if active else NORMAL)
    if except_button != film_type_R8_btn:
        film_type_R8_btn.config(state=DISABLED if active else NORMAL)
    if ExperimentalMode and IsPiCamera2:
        if except_button != hdr_btn:
            hdr_btn.config(state=DISABLED if active else NORMAL)
        if except_button != hq_btn:
            hq_btn.config(state=DISABLED if active else NORMAL)
        if except_button != turbo_btn:
            turbo_btn.config(state=DISABLED if active else NORMAL)

    if IsPiCamera2:
        if except_button != PiCam2_preview_btn and except_button != Free_btn:
            PiCam2_preview_btn.config(state=DISABLED if active else NORMAL)



def advance_movie():
    global AdvanceMovieActive
    global save_bg, save_fg
    global SimulatedRun

    # Update button text
    if not AdvanceMovieActive:  # Advance movie is about to start...
        AdvanceMovie_btn.config(text='Stop movie', bg='red',
                                fg='white', relief=SUNKEN)  # ...so now we propose to stop it in the button test
    else:
        AdvanceMovie_btn.config(text='Movie forward', bg=save_bg,
                                fg=save_fg, relief=RAISED)  # Otherwise change to default text to start the action
    AdvanceMovieActive = not AdvanceMovieActive
    # Send instruction to Arduino
    if not SimulatedRun:
        send_arduino_command(30)

    # Enable/Disable related buttons
    button_status_change_except(AdvanceMovie_btn, AdvanceMovieActive)


def rewind_movie():
    global RewindMovieActive
    global SimulatedRun
    global RewindErrorOutstanding, RewindEndOutstanding
    global save_bg, save_fg

    if SimulatedRun and RewindMovieActive:  # no callback from Arduino in simulated mode
        RewindEndOutstanding = True

    # Before proceeding, get confirmation from user that fild is correctly routed
    if not RewindMovieActive:  # Ask only when rewind is not ongoing
        """ # Since algorithm to detect film in filmgate is nto secured, this warning is no longer needed
        # Disable preview to make tkinter dialogs visible
        hide_preview()
        answer = tk.messagebox.askyesno(title='Security check ',
                                        message='Have you routed the film via the upper path?')
        display_preview()
        if not answer:
            return()
        """
        RewindMovieActive = True
        # Update button text
        Rewind_btn.config(text='Stop\n<<', bg='red', fg='white', relief=SUNKEN)  # ...so now we propose to stop it in the button test
        # Enable/Disable related buttons
        button_status_change_except(Rewind_btn, RewindMovieActive)
        # Invoke rewind_loop to continue processing until error or end event
        win.after(5, rewind_loop)
    elif RewindErrorOutstanding:
        hide_preview()
        confirm = tk.messagebox.askyesno(title='Error during rewind',
                                         message='It seems there is film loaded via filmgate. \
                                         \r\nAre you sure you want to proceed?')
        display_preview()
        if confirm:
            time.sleep(0.2)
            if not SimulatedRun:
                send_arduino_command(64)    # Forced rewind, no filmgate check
                # Invoke fast_forward_loop a first time when fast-forward starts
                win.after(5, rewind_loop)
        else:
            RewindMovieActive = False
    elif RewindEndOutstanding:
        RewindMovieActive = False

    if not RewindMovieActive:
        Rewind_btn.config(text='<<', bg=save_bg, fg=save_fg, relief=RAISED)  # Otherwise change to default text to start the action
        # Enable/Disable related buttons
        button_status_change_except(Rewind_btn, RewindMovieActive)

    if not RewindErrorOutstanding and not RewindEndOutstanding:  # invoked from button
        time.sleep(0.2)
        if not SimulatedRun:
            send_arduino_command(60)

    if RewindErrorOutstanding:
        RewindErrorOutstanding = False
    if RewindEndOutstanding:
        RewindEndOutstanding = False




def rewind_loop():
    global RewindMovieActive
    global SimulatedRun
    global RewindErrorOutstanding

    if RewindMovieActive:
        # Invoke rewind_loop one more time, as long as rewind is ongoing
        if not RewindErrorOutstanding and not RewindEndOutstanding:
            win.after(5, rewind_loop)
        else:
            rewind_movie()


def fast_forward_movie():
    global FastForwardActive
    global SimulatedRun
    global FastForwardErrorOutstanding, FastForwardEndOutstanding
    global save_bg, save_fg

    if SimulatedRun and FastForwardActive:  # no callback from Arduino in simulated mode
        FastForwardEndOutstanding = True

    # Before proceeding, get confirmation from user that fild is correctly routed
    if not FastForwardActive:  # Ask only when rewind is not ongoing
        """ # Since algorithm to detect film in filmgate is nto secured, this warning is no longer needed
        # Disable preview to make tkinter dialogs visible
        hide_preview()
        answer = tk.messagebox.askyesno(title='Security check ',
                                        message='Have you routed the film via the upper path?')
        display_preview()
        if not answer:
            return ()
        """
        FastForwardActive = True
        # Update button text
        FastForward_btn.config(text='Stop\n>>', bg='red', fg='white', relief=SUNKEN)
        # Enable/Disable related buttons
        button_status_change_except(FastForward_btn, FastForwardActive)
        # Invoke fast_forward_loop a first time when fast-forward starts
        win.after(5, fast_forward_loop)
    elif FastForwardErrorOutstanding:
        hide_preview()
        confirm = tk.messagebox.askyesno(title='Error during fast forward',
                                         message='It seems there is film loaded via filmgate. \
                                         \r\nAre you sure you want to proceed?')
        display_preview()
        if confirm:
            time.sleep(0.2)
            if not SimulatedRun:
                send_arduino_command(65)    # Forced FF, no filmgate check
                # Invoke fast_forward_loop a first time when fast-forward starts
                win.after(5, fast_forward_loop)
        else:
            FastForwardActive = False
    elif FastForwardEndOutstanding:
        FastForwardActive = False

    if not FastForwardActive:
        FastForward_btn.config(text='>>', bg=save_bg, fg=save_fg, relief=RAISED)
        # Enable/Disable related buttons
        button_status_change_except(FastForward_btn, FastForwardActive)

    if not FastForwardErrorOutstanding and not FastForwardEndOutstanding:  # invoked from button
        time.sleep(0.2)
        if not SimulatedRun:
            send_arduino_command(61)

    if FastForwardErrorOutstanding:
        FastForwardErrorOutstanding = False
    if FastForwardEndOutstanding:
        FastForwardEndOutstanding = False


def fast_forward_loop():
    global FastForwardActive
    global SimulatedRun
    global FastForwardErrorOutstanding

    if FastForwardActive:
        # Invoke fast_forward_loop one more time, as long as rewind is ongoing
        if not FastForwardErrorOutstanding and not FastForwardEndOutstanding:
            win.after(5, fast_forward_loop)
        else:
            fast_forward_movie()


def capture_display_thread(queue, event, id):
    global message

    # logging.info("I'll be updating the preview image outside of the main scanning loop, to optimize speed")
    logging.debug("Started capture_display_thread")
    while not event.is_set() or not queue.empty():
        message = queue.get()
        curtime = time.time()
        logging.debug("Retrieved message from capture display queue (len=%i)", queue.qsize())
        if message == END_TOKEN:
            break
        # If too many items in queue the skip display
        if (queue.qsize() <= 5):
            # Invert image if button selected
            if NegativeCaptureActive:
                image_array = numpy.asarray(message[0])
                image_array = numpy.negative(image_array)
                message[0] = Image.fromarray(image_array)
            draw_preview_image(message[0])
            logging.debug("Display thread complete: %s ms", str(round((time.time() - curtime) * 1000, 1)))
        else:
            logging.debug("Display queue almost full: Dropping frame")
    logging.debug("Exiting capture_display_thread")


def capture_save_thread(queue, event, id):
    global CurrentDir
    global message

    # logging.info("I'll be updating the preview image outside of the main scanning loop, to optimize speed")
    os.chdir(CurrentDir)
    logging.debug("Started capture_save_thread n.%i", id)
    while not event.is_set() or not queue.empty():
        message = queue.get()
        curtime = time.time()
        logging.info("Thread %i: Retrieved message from capture save queue", id)
        if message == END_TOKEN:
            break
        # Invert image if button selected
        if NegativeCaptureActive:
            image_array = numpy.asarray(message[0])
            image_array = numpy.negative(image_array)
            message[0] = Image.fromarray(image_array)
        if message[2] != 0:
            message[0].save('hdrpic-%05d.%i.jpg' % (message[1],message[2]))
        else:
            message[0].save('picture-%05d.jpg' % message[1], quality=95)
        logging.debug("Thread %i saved image: %s ms", id, str(round((time.time() - curtime) * 1000, 1)))
    logging.debug("Exiting capture_save_thread n.%i", id)

def draw_preview_image(preview_image):
    global draw_capture_label
    global preview_border_frame
    # global PreviewAreaImage
    global win
    global total_wait_time_preview_display

    curtime = time.time()

    preview_image = preview_image.resize((844, 634))
    PreviewAreaImage = ImageTk.PhotoImage(preview_image)
    # The Label widget is a standard Tkinter widget used to display a text or image on the screen.
    ####draw_capture_label = tk.Label(preview_border_frame, image=PreviewAreaImage)
    # next two lines to avoid flickering. However, they might cause memory problems
    draw_capture_label.config(image=PreviewAreaImage)
    draw_capture_label.image = PreviewAreaImage
    draw_capture_label.pack()

    # The Pack geometry manager packs widgets in rows or columns.
    # draw_capture_label.place(x=0, y=0) # This line is probably causing flickering, to be checked

    total_wait_time_preview_display += (time.time() - curtime)
    logging.debug("Display preview image: %s ms", str(round((time.time() - curtime) * 1000, 1)))


def capture_single_step():
    if not SimulatedRun:
        capture(True)


def single_step_movie():
    global SimulatedRun
    global camera

    if not SimulatedRun:
        send_arduino_command(40)

        if IsPiCamera2:
            # If no camera preview, capture frame in memory and display it
            # Single step is not a critical operation, waiting 100ms for it to happen should be enough
            # No need to implement confirmation from Arduino, as we have for regular capture during scan
            time.sleep(0.5)
            single_step_image = camera.capture_image("main")
            draw_preview_image(single_step_image)


def emergency_stop():
    global SimulatedRun
    if not SimulatedRun:
        send_arduino_command(90)


def update_rpi_temp():
    global SimulatedRun
    global RPiTemp
    if not SimulatedRun:
        file = open('/sys/class/thermal/thermal_zone0/temp', 'r')
        temp_str = file.readline()
        file.close()
        RPiTemp = int(int(temp_str) / 100) / 10
    else:
        RPiTemp = 64.5


# Not operational in RPi (only 4 frames per minute)
def switch_hdr_capture():
    global HdrCaptureActive
    global hdr_btn

    HdrCaptureActive = not HdrCaptureActive
    SessionData["HdrCaptureActive"] = str(HdrCaptureActive)
    hdr_btn.config(text='HDR Off' if HdrCaptureActive else 'HDR On',
                   relief=SUNKEN if HdrCaptureActive else RAISED,
                   bg='red' if HdrCaptureActive else save_bg,
                   fg='white' if HdrCaptureActive else save_fg)


# Capture with sensor at 4056x3040
# Frames delivered still at 2028x1520, but better quality
def switch_hq_capture():
    global HqCaptureActive
    global hq_btn

    HqCaptureActive = not HqCaptureActive
    if IsPiCamera2:
        PiCam2_configure()
    SessionData["HqCaptureActive"] = str(HqCaptureActive)
    hq_btn.config(text='HQ Off' if HqCaptureActive else 'HQ On',
                   relief=SUNKEN if HqCaptureActive else RAISED,
                   bg='red' if HqCaptureActive else save_bg,
                   fg='white' if HqCaptureActive else save_fg)


# Capture using Video configuration
# Faster than still
def switch_turbo_capture():
    global VideoCaptureActive
    global turbo_btn

    VideoCaptureActive = not VideoCaptureActive
    if IsPiCamera2:
        PiCam2_configure()
    SessionData["VideoCaptureActive"] = str(VideoCaptureActive)
    turbo_btn.config(text='Turbo Off' if VideoCaptureActive else 'Turbo On',
                   relief=SUNKEN if VideoCaptureActive else RAISED,
                   bg='red' if VideoCaptureActive else save_bg,
                   fg='white' if VideoCaptureActive else save_fg)


def switch_negative_capture():
    global NegativeCaptureActive
    global SimulatedRun
    global PosNeg_btn

    NegativeCaptureActive = not NegativeCaptureActive
    SessionData["NegativeCaptureActive"] = str(NegativeCaptureActive)
    PosNeg_btn.config(text='Positive image' if NegativeCaptureActive else 'Negative image',
                      relief=SUNKEN if NegativeCaptureActive else RAISED,
                      bg='red' if NegativeCaptureActive else save_bg,
                      fg='white' if NegativeCaptureActive else save_fg)

    if not SimulatedRun:
        if IsPiCamera2:
            # Do nothing for PiCamera2, image turns negative at save time
            logging.debug("Negative mode " + "On" if NegativeCaptureActive else "Off")
        else:
            if NegativeCaptureActive:
                camera.image_effect = 'negative'
                camera.awb_gains = (1.7, 1.9)
            else:
                camera.image_effect = 'none'
                camera.awb_gains = (3.5, 1.0)


def open_folder():
    global OpenFolderActive
    global FolderProcess
    global save_bg, save_fg
    global SimulatedRun
    global OpenFolder_btn

    if not OpenFolderActive:
        OpenFolder_btn.config(text="Close Folder", bg='red', fg='white')
        hide_preview()
        FolderProcess = subprocess.Popen(["pcmanfm", BaseDir])
    else:
        OpenFolder_btn.config(text="Open Folder", bg=save_bg, fg=save_fg)
        FolderProcess.terminate()  # Does not work, needs to be debugged

        time.sleep(.5)
        display_preview()
        time.sleep(.5)

    OpenFolderActive = not OpenFolderActive


# Function to enable 'real' preview with PiCamera2
# Even if it is useless for capture (slow and imprecise) it is still needed for other tasks like:
#  - Focus
#  - Color adjustment
#  - Exposure adjustment
def PiCamera2_preview():
#def change_preview_status(mode):
    global win
    global capture_config, preview_config
    global PiCam2PreviewEnabled
    global PiCam2_preview_btn, Start_btn

    PiCam2PreviewEnabled = not PiCam2PreviewEnabled
    if not SimulatedRun and IsPiCamera2:
        if (PiCam2PreviewEnabled):
            camera.stop_preview()
            camera.start_preview(Preview.QTGL, x=PreviewWinX, y=PreviewWinY, width=840, height=720)
            time.sleep(0.1)
            camera.switch_mode(preview_config)
        else:
            camera.stop_preview()
            camera.start_preview(False)
            time.sleep(0.1)
            camera.switch_mode(capture_config)

    PiCam2_preview_btn.config(text='Real Time display ' + ('OFF' if PiCam2PreviewEnabled else 'ON'),
                      relief=SUNKEN if PiCam2PreviewEnabled else RAISED,
                      bg='red' if PiCam2PreviewEnabled else save_bg,
                      fg='white' if PiCam2PreviewEnabled else save_fg)

    # Do not allow scan to start while PiCam2 preview is active
    Start_btn.config(state=DISABLED if PiCam2PreviewEnabled else NORMAL)
    Focus_btn.config(state=NORMAL if PiCam2PreviewEnabled else DISABLED)


def set_s8():
    global SimulatedRun
    global film_type_R8_btn, film_type_S8_btn
    global PTLevel, PTLevelS8
    global MinFrameSteps, MinFrameStepsS8
    global pt_level_str, min_frame_steps_str

    film_type_S8_btn.config(relief=SUNKEN)
    film_type_R8_btn.config(relief=RAISED)
    SessionData["FilmType"] = "S8"
    time.sleep(0.2)

    PTLevel = PTLevelS8
    SessionData["PTLevel"] = PTLevel
    pt_level_str.set(str(PTLevel))
    MinFrameSteps = MinFrameStepsS8
    SessionData["MinFrameSteps"] = MinFrameSteps
    min_frame_steps_str.set(str(MinFrameSteps))
    if not SimulatedRun:
        send_arduino_command(19)
        send_arduino_command(50, PTLevel)
        send_arduino_command(52, MinFrameSteps)



def set_r8():
    global SimulatedRun
    global film_type_R8_btn, film_type_S8_btn
    global PTLevel, PTLevelR8
    global MinFrameSteps, MinFrameStepsR8
    global pt_level_str, min_frame_steps_str

    film_type_R8_btn.config(relief=SUNKEN)
    film_type_S8_btn.config(relief=RAISED)
    SessionData["FilmType"] = "R8"
    time.sleep(0.2)

    PTLevel = PTLevelR8
    SessionData["PTLevel"] = PTLevel
    pt_level_str.set(str(PTLevel))
    MinFrameSteps = MinFrameStepsR8
    SessionData["MinFrameSteps"] = MinFrameSteps
    min_frame_steps_str.set(str(MinFrameSteps))
    if not SimulatedRun:
        send_arduino_command(18)
        send_arduino_command(50, PTLevel)
        send_arduino_command(52, MinFrameSteps)


def film_hole_up():
    global film_hole_frame, FilmHoleY
    if FilmHoleY > 38:
        FilmHoleY -= 4
    film_hole_frame.place(x=4, y=FilmHoleY)
    SessionData["FilmHoleY"] = str(FilmHoleY)


def film_hole_down():
    global film_hole_frame, FilmHoleY
    if FilmHoleY < 758:
        FilmHoleY += 3  # Intentionally different from button up, to allow eventual fine tunning
    film_hole_frame.place(x=4, y=FilmHoleY)
    SessionData["FilmHoleY"] = str(FilmHoleY)


def match_wait_up():
    global match_wait_margin_value, MatchWaitMargin
    if MatchWaitMargin < 100:
        if MatchWaitMargin >= 10 and MatchWaitMargin < 90:
            MatchWaitMargin += 5
        else:
            MatchWaitMargin += 1
    match_wait_margin_value.config(text=str(MatchWaitMargin)+'%')
    SessionData["MatchWaitMargin"] = str(MatchWaitMargin)


def match_wait_down():
    global match_wait_margin_value, MatchWaitMargin
    if MatchWaitMargin > 0:
        if MatchWaitMargin > 10 and MatchWaitMargin <= 90:
            MatchWaitMargin -= 5
        else:
            MatchWaitMargin -= 1
    match_wait_margin_value.config(text=str(MatchWaitMargin)+'%')
    SessionData["MatchWaitMargin"] = str(MatchWaitMargin)


def sharpness_up():
    global sharpness_control_value, SharpnessValue
    if SharpnessValue < 16:
        SharpnessValue += 1
    sharpness_control_value.config(text=str(SharpnessValue))
    SessionData["SharpnessValue"] = str(SharpnessValue)


def sharpness_down():
    global sharpness_control_value, SharpnessValue
    if SharpnessValue > 0:
        SharpnessValue -= 1
    sharpness_control_value.config(text=str(SharpnessValue))
    SessionData["SharpnessValue"] = str(SharpnessValue)


def register_frame():
    global FPM_LastMinuteFrameTimes
    global FPM_StartTime
    global FPM_CalculatedValue

    # Get current time
    frame_time = time.time()
    # Determine if we should start new count (last capture older than 5 seconds)
    if len(FPM_LastMinuteFrameTimes) == 0 or FPM_LastMinuteFrameTimes[-1] < frame_time - 5:
        FPM_StartTime = frame_time
        FPM_LastMinuteFrameTimes.clear()
        FPM_CalculatedValue = -1
    # Add current time to list
    FPM_LastMinuteFrameTimes.append(frame_time)
    # Remove entries older than one minute
    FPM_LastMinuteFrameTimes.sort()
    while FPM_LastMinuteFrameTimes[0] <= frame_time-60:
        FPM_LastMinuteFrameTimes.remove(FPM_LastMinuteFrameTimes[0])
    # Calculate current value, only if current count has been going for more than 10 seconds
    if frame_time - FPM_StartTime > 60:  # no calculations needed, frames in list are all in th elast 60 seconds
        FPM_CalculatedValue = len(FPM_LastMinuteFrameTimes)
    elif frame_time - FPM_StartTime > 10:  # some  calculations needed if less than 60 sec
        FPM_CalculatedValue = int((len(FPM_LastMinuteFrameTimes) * 60) / (frame_time - FPM_StartTime))


def capture_hdr():
    global CurrentFrame
    global capture_display_queue, capture_save_queue
    global camera, exp_list, VideoCaptureActive

    if not IsPiCamera2:
        # Create the in-memory stream
        stream = BytesIO()
    image_list.clear()
    idx=1
    for exp in exp_list:
        logging.debug("capture_hdr: exp %.2f", exp)
        if IsPiCamera2:
            camera.set_controls({"ExposureTime": int(exp*1000)})
            # Depending on results, maybe set as well fps: {"FrameDurationLimits": (40000, 40000)}
            if VideoCaptureActive:
                for i in range(1, dry_run_iterations):
                    camera.capture_request()
                request = camera.capture_request()
                img = request.make_image("main")
                img = img.convert('RGB')
                captured_snapshot = img.copy()
                request.release()
            else:
                for i in range(1,dry_run_iterations):
                    camera.capture_image("main")
                captured_snapshot = camera.capture_image("main")
            # For PiCamera2, preview and save to file are handled in asynchronous threads
            queue_item = tuple((captured_snapshot, CurrentFrame, idx))
            if (idx == 3):   # Take only third image for preview
                capture_display_queue.put(queue_item)
            capture_save_queue.put(queue_item)
        else:
            camera.shutter_speed = exp*1000
            for i in range(1,dry_run_iterations):
                camera.capture(None, format='jpeg')     # Not sure None will work here
            camera.capture('hdrpic-%05d.%i.jpg' % (CurrentFrame, idx), quality=100)
        idx += 1


def capture(still):
    global CurrentDir, CurrentFrame, CurrentExposure
    global exposure_frame_value_label
    global SessionData
    global PreviousCurrentExposure
    global SimulatedRun
    global raw_simulated_capture_image
    global simulated_capture_image
    global ExposureAdaptPause
    global CurrentAwbAuto
    global AwbPause
    global PreviousGainRed, PreviousGainBlue
    global total_wait_time_autoexp, total_wait_time_awb
    global CurrentStill
    global capture_display_queue, capture_save_queue
    global HdrCaptureActive, HqCaptureActive
    global VideoCaptureActive

    if SimulatedRun:
        return()

    os.chdir(CurrentDir)

    # Wait for auto exposure to adapt only if allowed
    if CurrentExposure == 0 and ExposureAdaptPause:
        curtime = time.time()
        wait_loop_count = 0
        while True:  # In case of exposure change, give time for the camera to adapt
            if IsPiCamera2:
                metadata = camera.capture_metadata()
                aux_current_exposure = metadata["ExposureTime"]
            else:
                aux_current_exposure = camera.exposure_speed
            # With PiCamera2, exposure was changing too often, so level changed from 1000 to 2000, then to 4000
            # Finally changed to allow a percentage of the value used previously
            # As we initialize this percentage to 50%, we start with double the original value
            #if abs(aux_current_exposure - PreviousCurrentExposure) > 4000:
            if abs(aux_current_exposure - PreviousCurrentExposure) > (MatchWaitMargin * Tolerance_AE)/100:
                if (wait_loop_count % 10 == 0):
                    aux_exposure_str = "Auto (" + str(round((aux_current_exposure - 20000) / 2000)) + ")"
                    #print(f"AE match: ({aux_current_exposure},{aux_exposure_str})")
                    logging.info("AE match: (%i,%s)",aux_current_exposure, aux_exposure_str)
                wait_loop_count += 1
                if ExpertMode:
                    exposure_frame_value_label.config(text=aux_exposure_str)
                PreviousCurrentExposure = aux_current_exposure
                win.update()
                time.sleep(0.2)
                if (time.time() - curtime) * 1000 > max_wait_time:  # Never wait more than 5 seconds
                    break;
            else:
                break
        if wait_loop_count > 0:
            total_wait_time_autoexp+=(time.time() - curtime)
            #print(f"AE match delay: {str(round((time.time() - curtime) * 1000,1))} ms")
            logging.info("AE match delay: %s ms", str(round((time.time() - curtime) * 1000,1)))

    # Wait for auto white balance to adapt only if allowed
    if CurrentAwbAuto and AwbPause:
        curtime = time.time()
        wait_loop_count = 0
        while True:  # In case of exposure change, give time for the camera to adapt
            if IsPiCamera2:
                metadata = camera.capture_metadata()
                camera_colour_gains = metadata["ColourGains"]
                aux_gain_red = camera_colour_gains[0]
                aux_gain_blue = camera_colour_gains[1]
            else:
                aux_gain_red = camera.awb_gains[0]
                aux_gain_blue = camera.awb_gains[1]
            # Same as for exposure, difference allowed is a percentage of the maximum value
            #if abs(aux_gain_red-PreviousGainRed) >= 0.5 or abs(aux_gain_blue-PreviousGainBlue) >= 0.5:
            if abs(aux_gain_red-PreviousGainRed) >= (MatchWaitMargin * Tolerance_AWB/100) or \
               abs(aux_gain_blue-PreviousGainBlue) >= (MatchWaitMargin * Tolerance_AWB/100):
                if (wait_loop_count % 10 == 0):
                    aux_gains_str = "(" + str(round(aux_gain_red, 2)) + ", " + str(round(aux_gain_blue, 2)) + ")"
                    #print(f"AWB Match: {aux_gains_str})")
                    logging.info("AWB Match: %s", aux_gains_str)
                wait_loop_count += 1
                if ExpertMode:
                    colour_gains_red_value_label.config(text=str(round(aux_gain_red, 1)))
                    colour_gains_blue_value_label.config(text=str(round(aux_gain_blue, 1)))
                PreviousGainRed = aux_gain_red
                PreviousGainBlue = aux_gain_blue
                win.update()
                time.sleep(0.2)
                if (time.time() - curtime) * 1000 > max_wait_time:  # Never wait more than 5 seconds
                    break;
            else:
                break
        if wait_loop_count > 0:
            total_wait_time_awb+=(time.time() - curtime)
            #print(f"AWB Match delay: {str(round((time.time() - curtime) * 1000,1))} ms")
            logging.info("AWB Match delay: %s ms", str(round((time.time() - curtime) * 1000,1)))

    if not SimulatedRun:
        if IsPiCamera2:
            if PiCam2PreviewEnabled:
                if still:
                    camera.switch_mode_and_capture_file(capture_config, 'still-picture-%05d-%02d.jpg' % (CurrentFrame,CurrentStill))
                    CurrentStill += 1
                else:
                    # This one should not happen, will not allow PiCam2 scan in preview mode
                    camera.switch_mode_and_capture_file(capture_config, 'picture-%05d.jpg' % CurrentFrame)
            else:
                # Allow time to stabilize image, it can get too fast with PiCamera2
                # Maybe we could refine this (shorter time, Arduino specific slowdown?)
                # In principle, 100 ms seems OK. Tried with 50 and some frames were blurry
                # Time passed since frame arrival notification is deducted from the delay (it can be relevant,
                # if adaptation delay for AE and AWB is enabled)
                time.sleep(CaptureStabilizationDelay)
                """
                stabilization_time = CaptureStabilizationDelay-(time.time()-FrameArrivalTime)
                if stabilization_time > 0:
                    time.sleep(stabilization_time)
                else:
                    print(CaptureStabilizationDelay, time.time(), FrameArrivalTime)
                """
                if still:
                    captured_snapshot = camera.capture_image("main")
                    captured_snapshot.save('still-picture-%05d-%02d.jpg' % (CurrentFrame,CurrentStill))
                    CurrentStill += 1
                else:
                    if HdrCaptureActive:
                        capture_hdr()
                    else:
                        if VideoCaptureActive:
                            request = camera.capture_request()
                            img = request.make_image("main")
                            img = img.convert('RGB')
                            captured_snapshot = img.copy()
                            request.release()
                        else:
                            captured_snapshot = camera.capture_image("main")
                        # For PiCamera2, preview and save to file are handled in asynchronous threads
                        queue_item = tuple((captured_snapshot, CurrentFrame, 0))
                        capture_display_queue.put(queue_item)
                        capture_save_queue.put(queue_item)
        else:
            if still:
                camera.capture('still-picture-%05d-%02d.jpg' % (CurrentFrame,CurrentStill), quality=100)
                CurrentStill += 1
            else:
                if HdrCaptureActive:
                    capture_hdr()
                else:
                    camera.capture('picture-%05d.jpg' % CurrentFrame, quality=100)

    SessionData["CurrentDate"] = str(datetime.now())
    SessionData["CurrentFrame"] = str(CurrentFrame)


def start_scan_simulated():
    global CurrentDir
    global CurrentFrame
    global ScanOngoing
    global CurrentScanStartFrame, CurrentScanStartTime
    global simulated_captured_frame_list, simulated_images_in_list
    global ScanStopRequested
    global total_wait_time_autoexp, total_wait_time_awb, total_wait_time_preview_display, session_start_time
    global session_frames

    if ScanOngoing:
        ScanStopRequested = True  # Ending the scan process will be handled in the next (or ongoing) capture loop
    else:
        if BaseDir == CurrentDir:
            tk.messagebox.showerror("Error!",
                                    "Please specify a folder where to retrieve captured images for scan simulation.")
            return

        Start_btn.config(text="STOP Scan", bg='red', fg='white', relief=SUNKEN)
        SessionData["CurrentDate"] = str(datetime.now())
        SessionData["CurrentDir"] = CurrentDir
        SessionData["CurrentFrame"] = str(CurrentFrame)
        CurrentScanStartTime = datetime.now()
        CurrentScanStartFrame = CurrentFrame

        ScanOngoing = True

        # Enable/Disable related buttons
        button_status_change_except(Start_btn, ScanOngoing)

        # Reset time counters
        total_wait_time_preview_display = 0
        total_wait_time_awb = 0
        total_wait_time_autoexp = 0
        session_start_time = time.time()
        session_frames = 0

        # Get list of previously captured frames for scan simulation
        if not os.path.isdir(CurrentDir):
            tk.messagebox.showerror("Error!", "Folder " + CurrentDir + " does not  exist!")
        else:
            simulated_captured_frame_list = os.listdir(CurrentDir)
            simulated_captured_frame_list.sort()
            simulated_images_in_list = len(simulated_captured_frame_list)
            # Invoke capture_loop  a first time shen scan starts
            win.after(500, capture_loop_simulated)


def stop_scan_simulated():
    global ScanOngoing
    global save_bg
    global save_fg

    Start_btn.config(text="START Scan", bg=save_bg, fg=save_fg, relief=RAISED)

    ScanOngoing = False

    # Enable/Disable related buttons
    button_status_change_except(Start_btn, ScanOngoing)


def capture_loop_simulated():
    global CurrentDir, CurrentFrame, CurrentExposure
    global FramesPerMinute
    global NewFrameAvailable
    global ScanOngoing
    global preview_border_frame
    global raw_simulated_capture_image
    global simulated_capture_image
    global simulated_captured_frame_list, simulated_images_in_list
    global ScanStopRequested
    global total_wait_time_autoexp, total_wait_time_awb, total_wait_time_preview_display, session_start_time
    global session_frames

    if ScanStopRequested:
        stop_scan_simulated()
        ScanStopRequested = False
        curtime = time.time()
        if ExpertMode:
            logging.info("Total session time: %s seg for %i frames (%i ms per frame)",
                         str(round((curtime-session_start_time),1)),
                         session_frames,
                         round(((curtime-session_start_time)*1000/session_frames),1))
            logging.info("Total time to display preview image: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_preview_display),1)),
                         round((total_wait_time_preview_display*1000/session_frames),1))
            logging.info("Total time waiting for AWB adjustment: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_awb),1)),
                         round((total_wait_time_awb*1000/session_frames),1))
            logging.info("Total time waiting for AE adjustment: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_autoexp),1)),
                         round((total_wait_time_autoexp*1000/session_frames),1))
    if ScanOngoing:
        os.chdir(CurrentDir)
        frame_to_display = CurrentFrame % simulated_images_in_list
        filename, ext = os.path.splitext(simulated_captured_frame_list[frame_to_display])
        if ext == '.jpg':
            raw_simulated_capture_image = Image.open(simulated_captured_frame_list[frame_to_display])
            if NegativeCaptureActive:
                image_array = numpy.asarray(raw_simulated_capture_image)
                image_array = numpy.negative(image_array)
                raw_simulated_capture_image = Image.fromarray(image_array)
            draw_preview_image(raw_simulated_capture_image)

        CurrentFrame += 1
        session_frames += 1
        register_frame()
        SessionData["CurrentFrame"] = str(CurrentFrame)

        # Update number of captured frames
        Scanned_Images_number_label.config(text=str(CurrentFrame))
        # Update Frames per Minute
        scan_period_frames = CurrentFrame - CurrentScanStartFrame
        if FPM_CalculatedValue == -1:  # FPM not calculated yet, display some indication
            Scanned_Images_fpm.config(text=''.join([char*int(scan_period_frames) for char in '.']), anchor='w')
        else:
            FramesPerMinute = FPM_CalculatedValue
            Scanned_Images_fpm.config(text=str(int(FramesPerMinute)))
        win.update()

        # Invoke capture_loop one more time, as long as scan is ongoing
        win.after(500, capture_loop_simulated)


def start_scan():
    global CurrentDir, CurrentFrame
    global SessionData
    global ScanOngoing
    global CurrentScanStartFrame, CurrentScanStartTime
    global save_bg, save_fg
    global SimulatedRun
    global ScanStopRequested
    global NewFrameAvailable
    global total_wait_time_autoexp, total_wait_time_awb, total_wait_time_preview_display, session_start_time
    global session_frames

    if ScanOngoing:
        ScanStopRequested = True  # Ending the scan process will be handled in the next (or ongoing) capture loop
    else:
        if BaseDir == CurrentDir or not os.path.isdir(CurrentDir):
            hide_preview()
            tk.messagebox.showerror("Error!", "Please specify a folder where to store the captured images.")
            display_preview()
            return

        Start_btn.config(text="STOP Scan", bg='red', fg='white', relief=SUNKEN)
        SessionData["CurrentDate"] = str(datetime.now())
        SessionData["CurrentDir"] = CurrentDir
        SessionData["CurrentFrame"] = str(CurrentFrame)
        CurrentScanStartTime = datetime.now()
        CurrentScanStartFrame = CurrentFrame

        ScanOngoing = True

        # Set new frame indicator to false, in case this is the cause of the strange
        # behaviour after stopping/restarting the scan process
        NewFrameAvailable = False

        # Enable/Disable related buttons
        button_status_change_except(Start_btn, ScanOngoing)

        # Reset time counters
        total_wait_time_preview_display = 0
        total_wait_time_awb = 0
        total_wait_time_autoexp = 0
        session_start_time = time.time()
        session_frames = 0

        # Send command to Arduino to stop/start scan (as applicable, Arduino keeps its own status)
        if not SimulatedRun:
            send_arduino_command(10)

        # Invoke capture_loop a first time shen scan starts
        win.after(5, capture_loop)


def stop_scan():
    global ScanOngoing
    global save_bg
    global save_fg

    if ScanOngoing:  # Scanner session to be stopped
        Start_btn.config(text="START Scan", bg=save_bg, fg=save_fg, relief=RAISED)

    ScanOngoing = False

    # Enable/Disable related buttons
    button_status_change_except(Start_btn, ScanOngoing)


def capture_loop():
    global CurrentDir
    global CurrentFrame
    global CurrentExposure
    global SessionData
    global FramesPerMinute
    global NewFrameAvailable
    global ScanProcessError, ScanProcessError_LastTime
    global ScanOngoing
    global SimulatedRun
    global ScanStopRequested
    global total_wait_time_autoexp, total_wait_time_awb, total_wait_time_preview_display, session_start_time
    global session_frames, CurrentStill

    if ScanStopRequested:
        stop_scan()
        ScanStopRequested = False
        curtime = time.time()
        if ExpertMode and session_frames > 0:
            logging.info("Total session time: %s seg for %i frames (%i ms per frame)",
                         str(round((curtime-session_start_time),1)),
                         session_frames,
                         round(((curtime-session_start_time)*1000/session_frames),1))
            logging.info("Total time to display preview image: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_preview_display),1)),
                         round((total_wait_time_preview_display*1000/session_frames),1))
            logging.info("Total time waiting for AWB adjustment: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_awb),1)),
                         round((total_wait_time_awb*1000/session_frames),1))
            logging.info("Total time waiting for AE adjustment: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_autoexp),1)),
                         round((total_wait_time_autoexp*1000/session_frames),1))
    elif ScanOngoing:
        if NewFrameAvailable:
            FrameArrivalTime = time.time()  # Time in microseconds (used to honor stability delay)
            curtime = time.ctime()
            CurrentFrame += 1
            session_frames += 1
            register_frame()
            CurrentStill = 1
            capture(False)
            if not SimulatedRun:
                try:
                    # Set NewFrameAvailable to False here, to avoid overwriting new frame from arduino
                    NewFrameAvailable = False
                    logging.debug("Frame %i captured.", CurrentFrame)
                    send_arduino_command(12)  # Tell Arduino to move to next frame
                except IOError:
                    CurrentFrame -= 1
                    NewFrameAvailable = True  # Set NewFrameAvailable to True to repeat next time
                    # Log error to console
                    logging.warning("Error while telling Arduino to move to next Frame.")
                    logging.warning("Frame %i capture to be tried again.", CurrentFrame)
                    win.after(5, capture_loop)
                    return

            SessionData["CurrentDate"] = str(datetime.now())
            SessionData["CurrentDir"] = CurrentDir
            SessionData["CurrentFrame"] = str(CurrentFrame)
            if CurrentExposureStr == "Auto":
                SessionData["CurrentExposure"] = CurrentExposureStr
            else:
                SessionData["CurrentExposure"] = str(CurrentExposure)
            # with open(PersistedDataFilename, 'w') as f:
            #     json.dump(SessionData, f)

            # Update number of captured frames
            Scanned_Images_number_label.config(text=str(CurrentFrame))
            # Update Frames per Minute
            scan_period_frames = CurrentFrame - CurrentScanStartFrame
            if FPM_CalculatedValue == -1:   # FPM not calculated yet, display some indication
                Scanned_Images_fpm.config(text=''.join([char * int(scan_period_frames) for char in '.']), anchor='w')
            else:
                FramesPerMinute = FPM_CalculatedValue
                Scanned_Images_fpm.config(text=str(int(FPM_CalculatedValue)))
            win.update()
        elif ScanProcessError:
            if ScanProcessError_LastTime != 0:
                if time.time() - ScanProcessError_LastTime <= 5:     # Second error in less than 5 seconds: Stop
                    curtime = time.ctime()
                    logging.warning("Error during scan process.")
                    ScanProcessError = False
                    if ScanOngoing:
                        ScanStopRequested = True  # Stop in next capture loop
            ScanProcessError_LastTime = time.time()
            ScanProcessError = False
            if not ScanStopRequested:
                NewFrameAvailable = True    # Simulate new frame to continue scan
        # Invoke capture_loop one more time, as long as scan is ongoing
        win.after(5, capture_loop)


def temp_in_fahrenheit_selection():
    global temp_in_fahrenheit
    global TempInFahrenheit
    TempInFahrenheit = temp_in_fahrenheit.get()
    SessionData["TempInFahrenheit"] = str(TempInFahrenheit)


def temperature_loop():  # Update RPi temperature every 10 seconds
    global last_temp
    global RPi_temp_value_label
    global RPiTemp
    global temp_in_fahrenheit
    global LastTempInFahrenheit
    global TempInFahrenheit

    update_rpi_temp()
    if last_temp != RPiTemp or LastTempInFahrenheit != TempInFahrenheit:
        if TempInFahrenheit:
            rounded_temp = round(RPiTemp*1.8+32, 1)
            temp_str = str(rounded_temp) + 'ºF'
        else:
            rounded_temp = round(RPiTemp, 1)
            temp_str = str(rounded_temp) + 'º'
        RPi_temp_value_label.config(text=str(temp_str))
        win.update()
        last_temp = RPiTemp
        LastTempInFahrenheit = TempInFahrenheit

    win.after(1000, temperature_loop)


def arduino_listen_loop():  # Waits for Arduino communicated events adn dispatches accordingly
    global NewFrameAvailable
    global RewindErrorOutstanding, RewindEndOutstanding
    global FastForwardErrorOutstanding, FastForwardEndOutstanding
    global ArduinoTrigger
    global SimulatedRun
    global ScanProcessError
    global ScanOngoing
    global ALT_Scann8_controller_detected
    global last_cmd_time

    if not SimulatedRun:
        try:
            ArduinoTrigger = i2c.read_byte_data(16, 0)
        except IOError:
            ArduinoTrigger = 0
            # Log error to console
            logging.warning("Error while checking incoming event (%i) from Arduino. Will check again.", ArduinoTrigger)

    if ArduinoTrigger != 0:
        last_cmd_time = time.time()
    elif (ScanOngoing and (time.time() - last_cmd_time) > 3):
        # If scan is ongoing, and more than 3 seconds have passed since last command, maybe one
        # command from/to Arduino (frame received/go to next frame) has been lost.
        # In such case, we force a 'fake' new frame command to allow process to continue
        # This means a duplicate frame might be generated.
        last_cmd_time = time.time()
        NewFrameAvailable = True
        logging.warning("More than 3 sec. since last command: Forcing new "
                        "frame event (frame %i).",CurrentFrame)

    if ArduinoTrigger == 0:  # Do nothing
        pass
    elif ArduinoTrigger == 1:  # ALT Controller 0.9.1 or higher identified
        ALT_Scann8_controller_detected = True
        logging.info("Received ALT ID answer from Arduino - OK")
    elif ArduinoTrigger == 2:  # ALT Controller identified
        logging.info("Received pre-0.9.1 ALT ID answer from Arduino - KO")
    elif ArduinoTrigger == 3:  # ALT Controller was reloaded, need to identify again
        send_arduino_command(1, 1)
        logging.info("Received ALT ID request from Arduino, resending ID")
    elif ArduinoTrigger == 11:  # New Frame available
        NewFrameAvailable = True
    elif ArduinoTrigger == 12:  # Error during scan
        logging.warning("Received scan error from Arduino")
        ScanProcessError = True
    elif ArduinoTrigger == 60:  # Rewind ended, we can re-enable buttons
        RewindEndOutstanding = True
        logging.info("Received rewind end event from Arduino")
    elif ArduinoTrigger == 61:  # FastForward ended, we can re-enable buttons
        FastForwardEndOutstanding = True
        logging.info("Received fast forward end event from Arduino")
    elif ArduinoTrigger == 64:  # Error during Rewind
        RewindErrorOutstanding = True
        logging.warning("Received rewind error from Arduino")
    elif ArduinoTrigger == 65:  # Error during FastForward
        FastForwardErrorOutstanding = True
        logging.warning("Received fast forward error from Arduino")
    else:
        logging.warning("Unrecognized incoming event (%i) from Arduino.", ArduinoTrigger)

    ArduinoTrigger = 0

    win.after(5, arduino_listen_loop)


def on_form_event(dummy):
    global TopWinX
    global TopWinY
    global DeltaX
    global DeltaY
    global PreviewWinX
    global PreviewWinY
    global SimulatedRun
    global WinInitDone

    if not WinInitDone:
        return

    if not SimulatedRun and not IsPiCamera2:  # Only required for PiCamera legacy
        new_win_x = win.winfo_x()
        new_win_y = win.winfo_y()
        DeltaX = new_win_x - TopWinX
        DeltaY = new_win_y - TopWinY
        TopWinX = new_win_x
        TopWinY = new_win_y
        PreviewWinX = PreviewWinX + DeltaX
        PreviewWinY = PreviewWinY + DeltaY
        display_preview()

    """
    # Uncomment to have the details of each event
    for key in dir(event):
        if not key.startswith('_'):
            logging.debug("%s=%s", key, getattr(event, key))
    """


def preview_do_not_warn_again_selection():
    global preview_warn_again
    global PreviewWarnAgain
    global warn_again_from_toplevel

    PreviewWarnAgain = preview_warn_again.get()
    SessionData["PreviewWarnAgain"] = str(PreviewWarnAgain)


def close_preview_warning():
    global preview_warning

    preview_warning.destroy()
    preview_warning.quit()


def display_preview_warning():
    global win
    global preview_warning
    global preview_warn_again
    global PreviewWarnAgain
    global warn_again_from_toplevel

    if not PreviewWarnAgain:
        return

    hide_preview()
    warn_again_from_toplevel = tk.BooleanVar()
    preview_warning = Toplevel(win)
    preview_warning.title('*** PiCamera2 Preview warning ***')
    preview_warning.geometry('500x400')
    preview_warning.geometry('+250+250')  # setting the position of the window
    preview_label = Label(preview_warning, text='\rThe preview mode provided by PiCamera2 for use in '
                                                'X-Window environment is not really usable for '
                                                'ALT-Scann 8 during the film scanning process.\r\n'
                                                'Compared to the preview provided by PiCamera legacy it is:\r'
                                                '- Much slower (due to context switch between preview/capture)\r'
                                                '- Very imprecise (preview does not match captured image)\r\n'
                                                'PiCamera2 preview mode can and should still be used in some '
                                                'cases (typically for the focus procedure), however for the '
                                                'scanning process the image just captured is displayed instead\r\n',
                                                wraplength=450, justify=LEFT)
    preview_warn_again = tk.BooleanVar(value=PreviewWarnAgain)
    preview_btn = Button(preview_warning, text="OK", width=2, height=1, command=close_preview_warning)
    preview_checkbox = tk.Checkbutton(preview_warning, text='Do not show this warning again', height=1,
                                      variable=preview_warn_again, onvalue=False, offvalue=True,
                                      command=preview_do_not_warn_again_selection)

    preview_label.pack(side=TOP)
    preview_btn.pack(side=TOP, pady=10)
    preview_checkbox.pack(side=LEFT)

    preview_warning.mainloop()

    display_preview()


def load_persisted_data_from_disk():
    global PersistedDataFilename
    global SessionData
    global PersistedDataLoaded

    # Check if persisted data file exist: If it does, load it
    if os.path.isfile(PersistedDataFilename):
        persisted_data_file = open(PersistedDataFilename)
        SessionData = json.load(persisted_data_file)
        persisted_data_file.close()
        PersistedDataLoaded = True


def load_config_data():
    global film_hole_frame, FilmHoleY
    global SessionData
    global PostviewModule
    global PreviewWarnAgain
    global TempInFahrenheit
    global temp_in_fahrenheit_checkbox
    global PersistedDataLoaded
    global MatchWaitMargin, match_wait_margin_value
    global SharpnessValue
    global CaptureStabilizationDelay

    for item in SessionData:
        logging.info("%s=%s", item, str(SessionData[item]))
    if PersistedDataLoaded:
        logging.info("SessionData loaded from disk:")
        if 'PreviewWarnAgain' in SessionData:
            PreviewWarnAgain = eval(SessionData["PreviewWarnAgain"])
        if 'TempInFahrenheit' in SessionData:
            TempInFahrenheit = eval(SessionData["TempInFahrenheit"])
            if TempInFahrenheit:
                temp_in_fahrenheit_checkbox.select()
        if ExpertMode:
            if 'FilmHoleY' in SessionData:
                FilmHoleY = int(SessionData["FilmHoleY"])
                film_hole_frame.place(x=4, y=FilmHoleY)
            if 'MatchWaitMargin' in SessionData:
                MatchWaitMargin = int(SessionData["MatchWaitMargin"])
                match_wait_margin_value.config(text=str(MatchWaitMargin)+'%')
            if 'CaptureStabilizationDelay' in SessionData:
                CaptureStabilizationDelay = float(SessionData["CaptureStabilizationDelay"])
                stabilization_delay.config(text=str(round(CaptureStabilizationDelay*1000)) + ' ms')

        if ExperimentalMode:
            if 'SharpnessValue' in SessionData:
                SharpnessValue = int(SessionData["SharpnessValue"])
                sharpness_control_value.config(text=str(SharpnessValue))

def load_session_data():
    global SessionData
    global CurrentExposure, CurrentExposureStr, ExposureAdaptPause
    global CurrentDir
    global CurrentFrame
    global folder_frame_target_dir
    global NegativeCaptureActive, PosNeg_btn
    global HdrCaptureActive, HqCaptureActive
    global hq_btn, hdr_btn, turbo_btn
    global CurrentAwbAuto, AwbPause, GainRed, GainBlue
    global awb_wait_checkbox
    global colour_gains_red_value_label, colour_gains_blue_value_label
    global film_type_R8_btn, film_type_S8_btn
    global PersistedDataLoaded
    global exposure_frame_value_label
    global min_frame_steps_str, pt_level_str
    global MinFrameSteps, MinFrameStepsS8, MinFrameStepsR8
    global PTLevel, PTLevelS8, PTLevelR8

    if PersistedDataLoaded:
        win.after(2000, hide_preview)   # hide preview in 2 seconds to give time for initialization to complete
        confirm = tk.messagebox.askyesno(title='Persisted session data exist',
                                         message='ALT-Scann 8 was interrupted during the last session.\
                                         \r\nDo you want to continue from where it was stopped?')
        if confirm:
            logging.info("SessionData loaded from disk:")
            if 'CurrentDir' in SessionData:
                CurrentDir = SessionData["CurrentDir"]
                # If directory in configuration does not exist we set the current working dir
                if not os.path.isdir(CurrentDir):
                    CurrentDir = os.getcwd()
                folder_frame_target_dir.config(text=CurrentDir)
            if 'CurrentFrame' in SessionData:
                CurrentFrame = int(SessionData["CurrentFrame"])
                Scanned_Images_number_label.config(text=SessionData["CurrentFrame"])
            if 'FilmType' in SessionData:
                if SessionData["FilmType"] == "R8":
                    if not SimulatedRun:
                        send_arduino_command(18)
                    film_type_R8_btn.config(relief=SUNKEN)
                    film_type_S8_btn.config(relief=RAISED)
                elif SessionData["FilmType"] == "S8":
                    if not SimulatedRun:
                        send_arduino_command(19)
                    film_type_R8_btn.config(relief=RAISED)
                    film_type_S8_btn.config(relief=SUNKEN)
            if 'NegativeCaptureActive' in SessionData:
                NegativeCaptureActive = eval(SessionData["NegativeCaptureActive"])
                PosNeg_btn.config(text='Positive image' if NegativeCaptureActive else 'Negative image')
            if ExperimentalMode and IsPiCamera2:
                if 'HdrCaptureActive' in SessionData:
                    HdrCaptureActive = eval(SessionData["HdrCaptureActive"])
                    hdr_btn.config(text='HDR Off' if HdrCaptureActive else 'HDR On',
                                   relief=SUNKEN if HdrCaptureActive else RAISED,
                                   bg='red' if HdrCaptureActive else save_bg,
                                   fg='white' if HdrCaptureActive else save_fg)
                if 'HqCaptureActive' in SessionData:
                    HqCaptureActive = eval(SessionData["HqCaptureActive"])
                    hq_btn.config(text='HQ Off' if HqCaptureActive else 'HQ On',
                                  relief=SUNKEN if HqCaptureActive else RAISED,
                                  bg='red' if HqCaptureActive else save_bg,
                                  fg='white' if HqCaptureActive else save_fg)
                if 'VideoCaptureActive' in SessionData:
                    VideoCaptureActive = eval(SessionData["VideoCaptureActive"])
                    turbo_btn.config(text='Turbo Off' if VideoCaptureActive else 'Turbo On',
                                     relief=SUNKEN if VideoCaptureActive else RAISED,
                                     bg='red' if VideoCaptureActive else save_bg,
                                     fg='white' if VideoCaptureActive else save_fg)
            if ExpertMode:
                if 'CurrentExposure' in SessionData:
                    CurrentExposureStr = SessionData["CurrentExposure"]
                    if CurrentExposureStr == "Auto":
                        CurrentExposure = 0
                    else:
                        CurrentExposure = int(CurrentExposureStr)
                        CurrentExposureStr = str(round((CurrentExposure - 20000) / 2000))
                    exposure_frame_value_label.config(text=CurrentExposureStr)
                    exposure_frame.config(text="Auto Exposure " + ('ON' if CurrentExposure == 0 else 'OFF'))
                    decrease_exp_btn.config(state=DISABLED if CurrentExposure == 0 else NORMAL)
                    increase_exp_btn.config(state=DISABLED if CurrentExposure == 0 else NORMAL)
                if 'ExposureAdaptPause' in SessionData:
                    ExposureAdaptPause = eval(SessionData["ExposureAdaptPause"])
                    if ExposureAdaptPause:
                        auto_exp_wait_checkbox.select()
                if 'CurrentAwbAuto' in SessionData:
                    CurrentAwbAuto = eval(SessionData["CurrentAwbAuto"])
                    #if not CurrentAwbAuto:  # AWB on by default, if not call button to disable and perform needed actions
                    CurrentAwbAuto = not CurrentAwbAuto  # Invert value, as button action will invert the value again
                    colour_gain_auto()
                    #awb_frame.config(text='Automatic White Balance ON' if CurrentAwbAuto else 'Automatic White Balance OFF')
                if 'AwbPause' in SessionData:
                    AwbPause = eval(SessionData["AwbPause"])
                    if AwbPause:
                        awb_wait_checkbox.select()
                if 'GainRed' in SessionData:
                    GainRed = float(SessionData["GainRed"])
                    colour_gains_red_value_label.config(text="Auto" if CurrentAwbAuto else str(round(GainRed, 1)))
                if 'GainBlue' in SessionData:
                    GainBlue = float(SessionData["GainBlue"])
                    colour_gains_blue_value_label.config(text="Auto" if CurrentAwbAuto else str(round(GainBlue, 1)))
                # Recover frame alignment values
                if 'MinFrameSteps' in SessionData:
                    MinFrameSteps = SessionData["MinFrameSteps"]
                    min_frame_steps_str.set(str(MinFrameSteps))
                    if not SimulatedRun:
                        send_arduino_command(52, MinFrameSteps)
                if 'MinFrameStepsS8' in SessionData:
                    MinFrameStepsS8 = SessionData["MinFrameStepsS8"]
                if 'MinFrameStepsR8' in SessionData:
                    MinFrameStepsR8 = SessionData["MinFrameStepsR8"]
                if 'PTLevel' in SessionData:
                    PTLevel = SessionData["PTLevel"]
                    pt_level_str.set(str(PTLevel))
                    if not SimulatedRun:
                        send_arduino_command(50, PTLevel)
                if 'PTLevelS8' in SessionData:
                    PTLevelS8 = SessionData["PTLevelS8"]
                if 'PTLevelR8' in SessionData:
                    PTLevelR8 = SessionData["PTLevelR8"]

        display_preview()


def PiCam2_configure():
    global camera, capture_config, preview_config
    global CurrentExposure, CurrentAwbAuto, SharpnessValue
    global HqCaptureActive
    global VideoCaptureActive

    camera.stop()
    if HqCaptureActive:
        if VideoCaptureActive:
            capture_config = camera.create_video_configuration(main={"size": (2028, 1520)},
                                           raw={"size": (4056, 3040)},
                                           transform=Transform(hflip=True),
                                           controls={"FrameRate": 120.0})
        else:
            capture_config = camera.create_still_configuration(main={"size": (2028, 1520)},
                                           raw={"size": (4056, 3040)},
                                           transform=Transform(hflip=True))

    else:
        if VideoCaptureActive:
            capture_config = camera.create_video_configuration(main={"size": (2028, 1520)},
                                           raw={"size": (2028, 1520)},
                                           transform=Transform(hflip=True),
                                           controls={"FrameRate": 120.0})
        else:
            capture_config = camera.create_still_configuration(main={"size": (2028, 1520)},
                                           raw={"size": (2028, 1520)},
                                           transform=Transform(hflip=True))

    preview_config = camera.create_preview_configuration({"size": (840, 720)}, transform=Transform(hflip=True))
    # Camera preview window is not saved in configuration, so always off on start up (we start in capture mode)
    camera.configure(capture_config)
    camera.set_controls({"ExposureTime": CurrentExposure})
    camera.set_controls({"AnalogueGain": 1.0})
    camera.set_controls({"AwbEnable": 1 if CurrentAwbAuto else 0})
    camera.set_controls({"ColourGains": (2.2, 2.2)})  # Red 2.2, Blue 2.2 seem to be OK
    # In PiCamera2, '1' is the standard sharpness
    # It can be a floating point number from 0.0 to 16.0
    camera.set_controls({"Sharpness": SharpnessValue})
    # draft.NoiseReductionModeEnum.HighQuality not defined, yet
    # However, looking at the PiCamera2 Source Code, it seems the default value for still configuration
    # is already HighQuality, so not much to worry about
    # camera.set_controls({"NoiseReductionMode": draft.NoiseReductionModeEnum.HighQuality})
    # No preview by default
    camera.options['quality'] = 100  # jpeg quality: values from 0 to 100. Repyl from David Plowman in PiCam2 list
    camera.start(show_preview=False)


def tscann8_init():
    global win
    global camera
    global CurrentExposure
    global TopWinX
    global TopWinY
    # global preview_border_frame
    # global draw_capture_label
    global i2c
    global WinInitDone
    global CurrentDir
    global CurrentFrame
    global ZoomSize
    global capture_config
    global preview_config
    # global draw_capture_label
    global PreviewWinX, PreviewWinY
    global LogLevel
    global capture_display_queue, capture_display_event
    global capture_save_queue, capture_save_event
    global step_value, exp_list, min_exp, max_exp, num_steps

    # Initialize logging
    log_path = os.path.dirname(__file__)
    if log_path == "":
        log_path = os.getcwd()
    log_file_fullpath = log_path + "/ALT-Scann8." + time.strftime("%Y%m%d") + ".log"
    logging.basicConfig(
        level=LogLevel,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file_fullpath),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logging.info("Log file: %s", log_file_fullpath)

    if SimulatedRun:
        logging.info("Not running on Raspberry Pi, simulated run for UI debugging purposes only")
    else:
        logging.info("Running on Raspberry Pi")

    # Init HDR variables
    step_value = (max_exp - min_exp) / num_steps
    exp_list = numpy.arange(min_exp, max_exp, step_value).tolist()

    # Try to determine Video folder of user logged in
    homefolder = os.environ['HOME']
    if os.path.isdir(os.path.join(homefolder, 'Videos')):
        BaseDir = os.path.join(homefolder, 'Videos')
    elif os.path.isdir(os.path.join(homefolder, 'Vídeos')):
        BaseDir = os.path.join(homefolder, 'Vídeos')
    elif os.path.isdir(os.path.join(homefolder, 'Video')):
        BaseDir = os.path.join(homefolder, 'Video')
    else:
        BaseDir = homefolder
    CurrentDir = BaseDir

    if not SimulatedRun:
        i2c = smbus.SMBus(1)

    win = Tk()  # creating the main window and storing the window object in 'win'
    win.title('ALT-Scann 8')  # setting title of the window
    win.geometry('1100x810')  # setting the size of the window
    win.geometry('+50+50')  # setting the position of the window
    # Prevent window resize
    win.minsize(1100, 810)
    win.maxsize(1100, 810)
    if ExperimentalMode or ExpertMode:
        win.geometry('1100x930')  # setting the size of the window
        win.minsize(1100, 930)
        win.maxsize(1100, 930)

    if SimulatedRun:
        win.wm_title(string='*** ALT-Scann 8 SIMULATED RUN * NOT OPERATIONAL ***')

    win.update_idletasks()

    # Get Top window coordinates
    TopWinX = win.winfo_x()
    TopWinY = win.winfo_y()

    WinInitDone = True

    """
    # Create a frame to add a border to the preview
    preview_border_frame = Frame(win, width=844, height=634, bg='dark grey')
    preview_border_frame.pack()
    preview_border_frame.place(x=38, y=38)
    # Also a label to draw images when preview is not used
    draw_capture_label = tk.Label(preview_border_frame)
    """

    if not SimulatedRun:
        if IsPiCamera2:
            # Change preview coordinated for PiCamere2 to avoid confusion with overlay mode in PiCamera legacy
            PreviewWinX = 250
            PreviewWinY = 150
            camera = Picamera2()
            PiCam2_configure()
            ZoomSize = camera.capture_metadata()['ScalerCrop'][2:]
            # JRE 20/09/2022: Attempt to speed up overall process in PiCamera2 by having captured images
            # displayed in the preview area by a dedicated thread, so that time consumed in this task
            # does not impact the scan process speed
            capture_display_queue = queue.Queue(maxsize=10)
            capture_display_event = threading.Event()
            capture_save_queue = queue.Queue(maxsize=10)
            capture_save_event = threading.Event()
            display_thread = threading.Thread(target=capture_display_thread, args=(capture_display_queue, capture_display_event,0))
            save_thread_1 = threading.Thread(target=capture_save_thread, args=(capture_save_queue, capture_save_event,1))
            save_thread_2 = threading.Thread(target=capture_save_thread, args=(capture_save_queue, capture_save_event,2))
            save_thread_3 = threading.Thread(target=capture_save_thread, args=(capture_save_queue, capture_save_event,3))
            display_thread.start()
            save_thread_1.start()
            save_thread_2.start()
            save_thread_3.start()
            logging.debug("Threads initialized")
        else:
            camera = picamera.PiCamera()
            # From version 3.0 of UI (and implicitly for PiCamera legacy) Torulf recommends not to use mode 3 anymore,
            # even for HQ Camera
            camera.sensor_mode = 2
            # settings resolution higher for HQ camera 2028, 1520
            camera.resolution = (2028, 1520)  # not supported in picamera2
            camera.iso = 100  # not supported in picamera2
            # New from Torulf in UI 3.0: "Have chosen to lower the sharpness, as it mostly emphasizes scratches on the film."
            #camera.sharpness = 100
            camera.sharpness = SharpnessValue
            camera.hflip = True
            camera.awb_mode = 'auto'
            # camera.awb_gains = (3.5, 1.0)
            camera.start_preview(fullscreen=False, window=(90, 75, 840, 720))
            camera.shutter_speed = CurrentExposure

    # Enable events on windows movements, to allow preview to follow
    # lblText = tk.Label(win, text='')
    # lblText.pack()
    if not SimulatedRun and not IsPiCamera2:
        win.bind('<Configure>', on_form_event)

    logging.debug("ALT-Scann 8 initialized")


def build_ui():
    global win
    global ExperimentalMode
    global AdvanceMovie_btn
    global SingleStep_btn
    global Snapshot_btn
    global PosNeg_btn
    global Rewind_btn
    global FastForward_btn
    global Free_btn
    global Focus_btn
    global RPi_temp_value_label
    global Exit_btn
    global Start_btn
    global folder_frame_target_dir
    global Scanned_Images_number_label
    global Scanned_Images_fpm
    global exposure_frame_value_label, exposure_frame
    global film_type_S8_btn
    global film_type_R8_btn
    global save_bg, save_fg
    global PreviewStatus
    global auto_exposure_change_pause
    global auto_exp_wait_checkbox
    global decrease_exp_btn, increase_exp_btn
    global ExposureAdaptPause
    global temp_in_fahrenheit
    global TempInFahrenheit
    global colour_gains_red_value_label
    global colour_gains_blue_value_label
    global colour_gains_auto_btn, awb_frame
    global colour_gains_red_btn_plus, colour_gains_red_btn_minus
    global colour_gains_blue_btn_plus, colour_gains_blue_btn_minus
    global auto_white_balance_change_pause
    global awb_wait_checkbox
    global OpenFolder_btn
    global film_hole_frame, FilmHoleY
    global temp_in_fahrenheit_checkbox
    global rwnd_speed_control_delay
    global match_wait_margin_value
    global sharpness_control_value
    global PiCam2_preview_btn
    global stabilization_delay
    global focus_lf_btn, focus_up_btn, focus_dn_btn, focus_rt_btn, focus_plus_btn, focus_minus_btn
    global preview_border_frame
    global draw_capture_label
    global hdr_btn, hq_btn, turbo_btn
    global min_frame_steps_spinbox, min_frame_steps_str
    global MinFrameSteps
    global pt_level_spinbox, pt_level_str
    global PTLevel
    global min_frame_steps_spinbox, pt_level_spinbox

    # Create a frame to contain the top area (preview + Right buttons) ***************
    top_area_frame = Frame(win, width=850, height=650)
    top_area_frame.pack(side=TOP, anchor=NW)
    # Create a frame to add a border to the preview
    preview_border_frame = Frame(top_area_frame, width=844, height=634, bg='dark grey')
    preview_border_frame.pack(side=LEFT, anchor=N, padx=(38, 0), pady=(38, 0))
    # Also a label to draw images when preview is not used
    draw_capture_label = tk.Label(preview_border_frame)
    # Create a frame to contain the top area (preview + Right buttons) ***************
    top_right_area_frame = Frame(top_area_frame, width=850, height=650)
    top_right_area_frame.pack(side=LEFT, anchor=NW, padx=(20, 0), pady=(30, 0), fill=Y)

    # Frame for standard widgets at the bottom ***************************************
    bottom_area_frame = Frame(win, width=950, height=50)
    bottom_area_frame.pack(side=TOP, padx=5, pady=5, anchor=NW, fill=X)

    # Advance movie button (slow forward through filmgate)
    AdvanceMovie_btn = Button(bottom_area_frame, text="Movie Forward", width=8, height=3, command=advance_movie,
                              activebackground='green', activeforeground='white', wraplength=80, relief=RAISED)
    AdvanceMovie_btn.pack(side=LEFT, padx=(30, 0), pady=5)
    # Once first button created, get default colors, to revert when we change them
    save_bg = AdvanceMovie_btn['bg']
    save_fg = AdvanceMovie_btn['fg']

    # Frame for single step/snapshot
    sstep_area_frame = Frame(bottom_area_frame, width=50, height=50)
    sstep_area_frame.pack(side=LEFT, padx=(5, 0), pady=5)
    # Advance one single frame
    SingleStep_btn = Button(sstep_area_frame, text="Single Step", width=8, height=1, command=single_step_movie,
                            activebackground='green', activeforeground='white', wraplength=80)
    SingleStep_btn.pack(side=TOP)
    Snapshot_btn = Button(sstep_area_frame, text="Snapshot", width=8, height=1, command=capture_single_step,
                            activebackground='green', activeforeground='white', wraplength=80)
    Snapshot_btn.pack(side=TOP)

    # Rewind movie (via upper path, outside of film gate)
    Rewind_btn = Button(bottom_area_frame, text="<<", font=("Arial", 16), width=2, height=2, command=rewind_movie,
                        activebackground='green', activeforeground='white', wraplength=80, relief=RAISED)
    Rewind_btn.pack(side=LEFT, padx=(5, 0), pady=5)
    # Fast Forward movie (via upper path, outside of film gate)
    FastForward_btn = Button(bottom_area_frame, text=">>", font=("Arial", 16), width=2, height=2, command=fast_forward_movie,
                             activebackground='green', activeforeground='white', wraplength=80, relief=RAISED)
    FastForward_btn.pack(side=LEFT, padx=(5, 0), pady=5)

    # Unlock reels button (to load film, rewind, etc)
    Free_btn = Button(bottom_area_frame, text="Unlock Reels", width=8, height=3, command=set_free_mode, activebackground='green',
                      activeforeground='white', wraplength=80, relief=RAISED)
    Free_btn.pack(side=LEFT, padx=(5, 0), pady=5)

    # Switch Positive/negative modes
    PosNeg_btn = Button(bottom_area_frame, text="Negative image", width=8, height=3, command=switch_negative_capture,
                        activebackground='green', activeforeground='white', wraplength=80, relief=RAISED)
    PosNeg_btn.pack(side=LEFT, padx=(5, 0), pady=5)

    if ExperimentalMode and IsPiCamera2:
        # Switch HDR mode on/off
        hdr_btn = Button(bottom_area_frame, text="HDR On", width=8, height=3, command=switch_hdr_capture,
                            activebackground='green', activeforeground='white', wraplength=80, relief=RAISED)
        hdr_btn.pack(side=LEFT, padx=(5, 0), pady=5)

        # Switch HD mode on/off (Capture with sensor in 4056x3040, still delivering 2025x1520, but better quality)
        hq_btn = Button(bottom_area_frame, text="HQ On", width=8, height=3, command=switch_hq_capture,
                            activebackground='green', activeforeground='white', wraplength=80, relief=RAISED)
        hq_btn.pack(side=LEFT, padx=(5, 0), pady=5)

        # Switch VideoCaptureActive mode on/off (Capture video Configuration)
        turbo_btn = Button(bottom_area_frame, text="Turbo On", width=8, height=3, command=switch_turbo_capture,
                            activebackground='green', activeforeground='white', wraplength=80, relief=RAISED)
        turbo_btn.pack(side=LEFT, padx=(5, 0), pady=5)

    # Pi Camera preview selection: Preview (by PiCamera), disabled, postview (display last captured frame))
    if IsPiCamera2 or SimulatedRun:
        PiCam2_preview_btn = Button(bottom_area_frame, text="Real Time display ON", width=8, height=3, command=PiCamera2_preview,
                           activebackground='green', activeforeground='white', wraplength=80, relief=RAISED)
        PiCam2_preview_btn.pack(side=LEFT, padx=(5, 0), pady=5)

    # Activate focus zoom, to facilitate focusing the camera
    Focus_btn = Button(bottom_area_frame, text="Focus Zoom ON", width=8, height=3, command=set_focus_zoom,
                       activebackground='green', activeforeground='white', wraplength=80, relief=RAISED)
    Focus_btn.config(state=DISABLED if IsPiCamera2 else NORMAL)
    Focus_btn.pack(side=LEFT, padx=(5, 0), pady=5)

    # Create vertical button column at right *************************************
    # Start scan button
    if SimulatedRun:
        Start_btn = Button(top_right_area_frame, text="START Scan", width=14, height=5, command=start_scan_simulated,
                           activebackground='green', activeforeground='white', wraplength=80)
    else:
        Start_btn = Button(top_right_area_frame, text="START Scan", width=14, height=5, command=start_scan, activebackground='green',
                           activeforeground='white', wraplength=80)
    Start_btn.pack(side=TOP, padx=(5, 0), pady=(5, 0))

    # Create frame to select target folder
    folder_frame = LabelFrame(top_right_area_frame, text='Target Folder', width=16, height=8)
    folder_frame.pack(side=TOP, padx=(5, 0), pady=(5, 0))

    folder_frame_target_dir = Label(folder_frame, text=CurrentDir, width=22, height=3, font=("Arial", 8),
                                    wraplength=120)
    folder_frame_target_dir.pack(side=TOP)

    folder_frame_buttons = Frame(folder_frame, width=16, height=4, bd=2)
    folder_frame_buttons.pack()
    new_folder_btn = Button(folder_frame_buttons, text='New', width=5, height=1, command=set_new_folder,
                            activebackground='green', activeforeground='white', wraplength=80, font=("Arial", 10))
    new_folder_btn.pack(side=LEFT)
    existing_folder_btn = Button(folder_frame_buttons, text='Existing', width=5, height=1, command=set_existing_folder,
                                 activebackground='green', activeforeground='white', wraplength=80, font=("Arial", 10))
    existing_folder_btn.pack(side=LEFT)

    # Create frame to display number of scanned images, and frames per minute
    scanned_images_frame = LabelFrame(top_right_area_frame, text='Scanned frames', width=16, height=4)
    scanned_images_frame.pack(side=TOP, padx=(5, 0), pady=(5, 0))

    Scanned_Images_number_label = Label(scanned_images_frame, text=str(CurrentFrame), font=("Arial", 24), width=5,
                                        height=1)
    Scanned_Images_number_label.pack(side=TOP, padx=21)

    scanned_images_fpm_frame = Frame(scanned_images_frame, width=16, height=2)
    scanned_images_fpm_frame.pack(side=TOP)
    scanned_images_fpm_label = Label(scanned_images_fpm_frame, text='Frames/Min:', font=("Arial", 8), width=12,
                                     height=1)
    scanned_images_fpm_label.pack(side=LEFT)
    Scanned_Images_fpm = Label(scanned_images_fpm_frame, text=str(FramesPerMinute), font=("Arial", 8), width=8,
                               height=1)
    Scanned_Images_fpm.pack(side=LEFT)

    # Create frame to select S8/R8 film
    film_type_frame = LabelFrame(top_right_area_frame, text='Film type', width=16, height=1)
    film_type_frame.pack(side=TOP, padx=(5, 0), pady=(5, 0))

    film_type_buttons = Frame(film_type_frame, width=16, height=1)
    film_type_buttons.pack(side=TOP, padx=4, pady=5)
    film_type_S8_btn = Button(film_type_buttons, text='S8', width=3, height=1, font=("Arial", 16, 'bold'),
                              command=set_s8, activebackground='green', activeforeground='white',
                              relief=SUNKEN)
    film_type_S8_btn.pack(side=LEFT)
    film_type_R8_btn = Button(film_type_buttons, text='R8', width=3, height=1, font=("Arial", 16, 'bold'),
                              command=set_r8, activebackground='green', activeforeground='white')
    film_type_R8_btn.pack(side=LEFT)

    # Create frame to display RPi temperature
    rpi_temp_frame = LabelFrame(top_right_area_frame, text='RPi Temp.', width=8, height=1)
    rpi_temp_frame.pack(side=TOP, padx=(5, 0), pady=(5, 0))
    temp_str = str(RPiTemp)+'º'
    RPi_temp_value_label = Label(rpi_temp_frame, text=temp_str, font=("Arial", 18), width=8, height=1)
    RPi_temp_value_label.pack(side=TOP, padx=12)

    temp_in_fahrenheit = tk.BooleanVar(value=TempInFahrenheit)
    temp_in_fahrenheit_checkbox = tk.Checkbutton(rpi_temp_frame, text='Fahrenheit', height=1,
                                                 variable=temp_in_fahrenheit, onvalue=True, offvalue=False,
                                                 command=temp_in_fahrenheit_selection)
    temp_in_fahrenheit_checkbox.pack(side=TOP)

    # Application Exit button
    Exit_btn = Button(top_right_area_frame, text="Exit", width=12, height=5, command=exit_app, activebackground='red',
                      activeforeground='white', wraplength=80)
    Exit_btn.pack(side=BOTTOM, padx=(5, 0), pady=(5, 0))


    # Create extended frame for expert adn experimental areas
    if ExpertMode or ExperimentalMode:
        extended_frame = Frame(win)
        #extended_frame.place(x=30, y=790)
        extended_frame.pack(side=TOP, anchor=W, padx=(30, 0))
    if ExpertMode:
        expert_frame = LabelFrame(extended_frame, text='Expert Area', width=8, height=5, font=("Arial", 7))
        expert_frame.pack(side=LEFT, ipadx=5)

        # Exposure
        exposure_frame = LabelFrame(expert_frame, text='Auto Exposure ' + ('ON' if CurrentExposure == 0 else 'OFF'),
                                    width=16, height=2, font=("Arial", 7))
        exposure_frame.pack(side=LEFT, padx=5, pady=5)

        exposure_frame_value_label = Label(exposure_frame, text=CurrentExposureStr, width=8, height=1,
                                           font=("Arial", 7))
        exposure_frame_value_label.pack(side=TOP, padx=18)

        exposure_frame_buttons = Frame(exposure_frame, width=8, height=1)
        exposure_frame_buttons.pack(side=TOP)
        decrease_exp_btn = Button(exposure_frame_buttons, text='-', width=1, height=1, font=("Arial", 7),
                                  command=decrease_exp, activebackground='green', activeforeground='white',
                                  state=DISABLED if CurrentExposure == 0 else NORMAL)
        decrease_exp_btn.pack(side=LEFT)
        auto_exp_btn = Button(exposure_frame_buttons, text='AE', width=2, height=1, font=("Arial", 7),
                              command=auto_exp, activebackground='green', activeforeground='white')
        auto_exp_btn.pack(side=LEFT)
        increase_exp_btn = Button(exposure_frame_buttons, text='+', width=1, height=1, font=("Arial", 7),
                                  command=increase_exp, activebackground='green', activeforeground='white',
                                  state=DISABLED if CurrentExposure == 0 else NORMAL)
        increase_exp_btn.pack(side=LEFT)

        auto_exposure_change_pause = tk.BooleanVar(value=ExposureAdaptPause)
        auto_exp_wait_checkbox = tk.Checkbutton(exposure_frame, text='Match wait', height=1,
                                                variable=auto_exposure_change_pause, onvalue=True, offvalue=False,
                                                command=auto_exposure_change_pause_selection, font=("Arial", 7))
        auto_exp_wait_checkbox.pack(side=TOP)

        # Automatic White Balance
        awb_frame = LabelFrame(expert_frame, text='Automatic White Balance ' + ('ON' if CurrentAwbAuto else 'OFF'), width=8, height=1,
                               font=("Arial", 7))
        awb_frame.pack(side=LEFT, padx=5, pady=5)

        awb_buttons_frame = Frame(awb_frame, width=10, height=1)
        awb_buttons_frame.pack(side=TOP, pady=2)

        colour_gains_red_btn_plus = Button(awb_buttons_frame, text="Red-", command=colour_gain_red_minus,
                                           activebackground='green', activeforeground='white', font=("Arial", 7),
                                           state=DISABLED if CurrentAwbAuto else NORMAL)
        colour_gains_red_btn_plus.grid(row=0, column=0, pady=2)
        colour_gains_auto_btn1 = Button(awb_buttons_frame, text='AWB', width=2, height=1, command=colour_gain_auto,
                                       activebackground='green', activeforeground='white', font=("Arial", 7))
        colour_gains_auto_btn1.grid(row=0, column=1, pady=2)
        colour_gains_red_btn_minus = Button(awb_buttons_frame, text="Red+", command=colour_gain_red_plus,
                                            activebackground='green', activeforeground='white', font=("Arial", 7),
                                            state=DISABLED if CurrentAwbAuto else NORMAL)
        colour_gains_red_btn_minus.grid(row=0, column=2, pady=2)
        colour_gains_red_value_label = Label(awb_buttons_frame, text='Auto' if CurrentAwbAuto else str(GainRed), width=5, height=1, font=("Arial", 7))
        colour_gains_red_value_label.grid(row=0, column=3, pady=2)
        colour_gains_blue_btn_plus = Button(awb_buttons_frame, text="Blue-", command=colour_gain_blue_minus,
                                            activebackground='green', activeforeground='white', font=("Arial", 7),
                                            state=DISABLED if CurrentAwbAuto else NORMAL)
        colour_gains_blue_btn_plus.grid(row=1, column=0, pady=2)
        colour_gains_auto_btn2 = Button(awb_buttons_frame, text='AWB', width=2, height=1, command=colour_gain_auto,
                                       activebackground='green', activeforeground='white', font=("Arial", 7))
        colour_gains_auto_btn2.grid(row=1, column=1, pady=2)
        colour_gains_blue_btn_minus = Button(awb_buttons_frame, text="Blue+", command=colour_gain_blue_plus,
                                             activebackground='green', activeforeground='white', font=("Arial", 7),
                                             state=DISABLED if CurrentAwbAuto else NORMAL)
        colour_gains_blue_btn_minus.grid(row=1, column=2, pady=2)
        colour_gains_blue_value_label = Label(awb_buttons_frame, text='Auto' if CurrentAwbAuto else str(GainBlue), width=5, height=1, font=("Arial", 7))
        colour_gains_blue_value_label.grid(row=1, column=3, pady=2)


        auto_white_balance_change_pause = tk.BooleanVar(value=AwbPause)
        awb_wait_checkbox = tk.Checkbutton(awb_frame, text='Match wait', height=1,
                                           variable=auto_white_balance_change_pause, onvalue=True, offvalue=False,
                                           command=auto_white_balance_change_pause_selection, font=("Arial", 7),
                                           state=NORMAL if CurrentAwbAuto else DISABLED)
        awb_wait_checkbox.pack(side=TOP, pady=2)

        # Match wait (exposure & AWB) margin allowance (0%, wait for same value, 100%, any value will do)
        match_wait_margin_frame = LabelFrame(expert_frame, text="Match margin", width=8, height=2,
                                             font=("Arial", 7))
        match_wait_margin_frame.pack(side=LEFT, padx=2)

        match_wait_margin_value = Label(match_wait_margin_frame, text=str(MatchWaitMargin)+'%',
                                         width=4, height=1, font=("Arial", 7))
        match_wait_margin_value.pack(side=TOP)
        match_wait_margin_down = Button(match_wait_margin_frame, text="-", width=1, height=1, command=match_wait_down,
                                        activebackground='green', activeforeground='white', font=("Arial", 8))
        match_wait_margin_down.pack(side=LEFT)
        match_wait_margin_up = Button(match_wait_margin_frame, text="+", width=1, height=1, command=match_wait_up,
                                      activebackground='green', activeforeground='white', font=("Arial", 8))
        match_wait_margin_up.pack(side=RIGHT)
        match_wait_margin_bottom_frame = Frame(match_wait_margin_frame, height=10)   # frame just to add space at the bottom
        match_wait_margin_bottom_frame.pack(side=TOP, pady=14)

        # Focus zoom control (in out, up, down, left, right)
        Focus_frame = LabelFrame(expert_frame, text='Focus control', width=12, height=3, font=("Arial", 7))
        Focus_frame.pack(side=LEFT, padx=2)

        Focus_btn_grid_frame = Frame(Focus_frame, width=10, height=10)
        Focus_btn_grid_frame.pack(side=LEFT)

        # focus zoom displacement buttons, to further facilitate focusing the camera
        focus_plus_btn = Button(Focus_btn_grid_frame, text="+", width=1, height=1, command=set_focus_plus,
                                activebackground='green', activeforeground='white', state=DISABLED, font=("Arial", 7))
        focus_plus_btn.grid(row=0, column=2)
        focus_minus_btn = Button(Focus_btn_grid_frame, text="-", width=1, height=1, command=set_focus_minus,
                                 activebackground='green', activeforeground='white', state=DISABLED, font=("Arial", 7))
        focus_minus_btn.grid(row=0, column=0)
        focus_lf_btn = Button(Focus_btn_grid_frame, text="←", width=1, height=1, command=set_focus_left,
                              activebackground='green', activeforeground='white', state=DISABLED, font=("Arial", 7))
        focus_lf_btn.grid(row=1, column=0)
        focus_up_btn = Button(Focus_btn_grid_frame, text="↑", width=1, height=1, command=set_focus_up,
                              activebackground='green', activeforeground='white', state=DISABLED, font=("Arial", 7))
        focus_up_btn.grid(row=0, column=1)
        focus_dn_btn = Button(Focus_btn_grid_frame, text="↓", width=1, height=1, command=set_focus_down,
                              activebackground='green', activeforeground='white', state=DISABLED, font=("Arial", 7))
        focus_dn_btn.grid(row=1, column=1)
        focus_rt_btn = Button(Focus_btn_grid_frame, text="→", width=1, height=1, command=set_focus_right,
                              activebackground='green', activeforeground='white', state=DISABLED, font=("Arial", 7))
        focus_rt_btn.grid(row=1, column=2)

        # Display entry to adjust capture stabilization delay (100 ms by default)
        stabilization_delay_frame = LabelFrame(expert_frame, text="Stabilization", width=8, height=1,
                                              font=("Arial", 7))
        stabilization_delay_frame.pack(side=LEFT, padx=2)

        stabilization_delay = Label(stabilization_delay_frame,
                                         text=str(round(CaptureStabilizationDelay*1000)) + ' ms',
                                         width=8, height=1, font=("Arial", 7))
        stabilization_delay.pack(side=TOP)
        stabilization_delay_down_btn = Button(stabilization_delay_frame, text="-", width=1, height=1, command=stabilization_delay_down,
                                         activebackground='green', activeforeground='white', font=("Arial", 8))
        stabilization_delay_down_btn.pack(side=LEFT)
        stabilization_delay_up_btn = Button(stabilization_delay_frame, text="+", width=1, height=1, command=stabilization_delay_up,
                                       activebackground='green', activeforeground='white', font=("Arial", 8))
        stabilization_delay_up_btn.pack(side=RIGHT)
        stabilization_delay_bottom_frame = Frame(stabilization_delay_frame)  # frame just to add space at the bottom
        stabilization_delay_bottom_frame.pack(side=BOTTOM, pady=18)

        # Display marker for film hole
        film_hole_frame = Frame(win, width=1, height=11, bg='black')
        film_hole_frame.pack(side=TOP, padx=1, pady=1)
        film_hole_frame.place(x=4, y=FilmHoleY)
        film_hole_label = Label(film_hole_frame, justify=LEFT, font=("Arial", 8), width=5, height=11,
                                bg='white', fg='white')
        film_hole_label.pack(side=TOP)

        # Up/Down buttons to move marker for film hole
        film_hole_control_frame = LabelFrame(expert_frame, text="Hole mark pos.", width=8, height=2,
                                             font=("Arial", 7))
        film_hole_control_frame.pack(side=LEFT, padx=5)
        film_hole_control_up = Button(film_hole_control_frame, text="↑", width=5, height=1, command=film_hole_up,
                                      activebackground='green', activeforeground='white', font=("Arial", 7))
        film_hole_control_up.pack(side=TOP)
        film_hole_control_down = Button(film_hole_control_frame, text="↓", width=5, height=1, command=film_hole_down,
                                        activebackground='green', activeforeground='white', font=("Arial", 7))
        film_hole_control_down.pack(side=TOP)
        film_hole_bottom_frame = Frame(film_hole_control_frame)  # frame just to add space at the bottom
        film_hole_bottom_frame.pack(side=BOTTOM, pady=1)

        # Frame to add frame align controls
        frame_alignment_frame = LabelFrame(expert_frame, text="Frame align", width=16, height=2,
                                           font=("Arial", 7))
        frame_alignment_frame.pack(side=LEFT, padx=5)
        # Spinbox to select MinFrameSteps on Arduino
        min_frame_steps_label = tk.Label(frame_alignment_frame,
                                         text='Steps/frame:',
                                         width=10, font=("Arial", 7))
        min_frame_steps_label.grid(row=0, column=0, padx=2, pady=1, sticky=E)
        min_frame_steps_str = tk.StringVar(value=str(MinFrameSteps))
        min_frame_steps_selection_aux = frame_alignment_frame.register(
            min_frame_steps_selection)
        min_frame_steps_spinbox = tk.Spinbox(
            frame_alignment_frame,
            command=(min_frame_steps_selection_aux, '%d'), width=8,
            textvariable=min_frame_steps_str, from_=100, to=300, font=("Arial", 7))
        min_frame_steps_spinbox.grid(row=0, column=1, padx=2, pady=1, sticky=W)
        min_frame_steps_spinbox.bind("<FocusOut>", min_frame_steps_spinbox_focus_out)
        min_frame_steps_selection('down')
        # Spinbox to select PTLevel on Arduino
        pt_level_label = tk.Label(frame_alignment_frame,
                                  text='PT Level:',
                                  width=10, font=("Arial", 7))
        pt_level_label.grid(row=1, column=0, padx=2, pady=1, sticky=E)
        pt_level_str = tk.StringVar(value=str(PTLevel))
        pt_level_selection_aux = frame_alignment_frame.register(
            pt_level_selection)
        pt_level_spinbox = tk.Spinbox(
            frame_alignment_frame,
            command=(pt_level_selection_aux, '%d'), width=8,
            textvariable=pt_level_str, from_=0, to=900, font=("Arial", 7))
        pt_level_spinbox.grid(row=1, column=1, padx=2, pady=1, sticky=W)
        pt_level_spinbox.bind("<FocusOut>", pt_level_spinbox_focus_out)
        pt_level_selection('down')

        if ExperimentalMode:
            experimental_frame = LabelFrame(extended_frame, text='Experimental Area', width=8, height=5, font=("Arial", 7))
            experimental_frame.pack(side=LEFT, ipadx=5, fill=Y)
            #experimental_frame.place(x=900, y=790)

            # Sharpness, control to allow playign with the values and see the results
            sharpness_control_frame = LabelFrame(experimental_frame, text="Sharpness", width=8, height=2,
                                                 font=("Arial", 7))
            sharpness_control_frame.pack(side=LEFT, padx=2)

            sharpness_control_value = Label(sharpness_control_frame, text=str(SharpnessValue),
                                             width=4, height=1, font=("Arial", 7))
            sharpness_control_value.pack(side=TOP)
            sharpness_control_value_down = Button(sharpness_control_frame, text="-", width=1, height=1, command=sharpness_down,
                                            activebackground='green', activeforeground='white', font=("Arial", 8))
            sharpness_control_value_down.pack(side=LEFT)
            sharpness_control_value_up = Button(sharpness_control_frame, text="+", width=1, height=1, command=sharpness_up,
                                          activebackground='green', activeforeground='white', font=("Arial", 8))
            sharpness_control_value_up.pack(side=RIGHT)
            sharpness_control_bottom_frame = Frame(sharpness_control_frame, height=10)   # frame just to add space at the bottom
            sharpness_control_bottom_frame.pack(side=TOP, pady=13)

            # Display entry to throttle Rwnd/FF speed
            rwnd_speed_control_frame = LabelFrame(experimental_frame, text="RW/FF speed", width=8, height=2,
                                                  font=("Arial", 7))
            rwnd_speed_control_frame.pack(side=LEFT, padx=2)

            rwnd_speed_control_delay = Label(rwnd_speed_control_frame,
                                             text=str(round(60 / (rwnd_speed_delay * 375 / 1000000))) + ' rpm',
                                             width=8, height=1, font=("Arial", 7))
            rwnd_speed_control_delay.pack(side=TOP)
            rwnd_speed_control_down = Button(rwnd_speed_control_frame, text="-", width=1, height=1, command=rwnd_speed_down,
                                             activebackground='green', activeforeground='white', font=("Arial", 8))
            rwnd_speed_control_down.pack(side=LEFT)
            rwnd_speed_control_up = Button(rwnd_speed_control_frame, text="+", width=1, height=1, command=rwnd_speed_up,
                                           activebackground='green', activeforeground='white', font=("Arial", 8))
            rwnd_speed_control_up.pack(side=RIGHT)
            rwnd_speed_bottom_frame = Frame(rwnd_speed_control_frame)  # frame just to add space at the bottom
            rwnd_speed_bottom_frame.pack(side=BOTTOM, pady=18)

            # Open target folder (to me this is useless. Also, gives problem with closure, not as easy at I imagined)
            # Leave it in the expert area, disabled, just in case it is reused
            openfolder_frame = LabelFrame(experimental_frame, text='Open Folder', width=8, height=2, font=("Arial", 7))
            openfolder_frame.pack(side=LEFT, padx=5)
            OpenFolder_btn = Button(openfolder_frame, text="Open Folder", width=8, height=3, command=open_folder,
                                    activebackground='green', activeforeground='white', wraplength=80, state=DISABLED,
                                    font=("Arial", 7))
            OpenFolder_btn.pack(side=TOP, padx=5, pady=5)


def main(argv):
    global SimulatedRun
    global ExpertMode, ExperimentalMode
    global LogLevel, LoggingMode
    global capture_display_event, capture_save_event
    global capture_display_queue, capture_save_queue

    opts, args = getopt.getopt(argv, "sexl:h")

    for opt, arg in opts:
        if opt == '-s':
            SimulatedRun = True
        elif opt == '-e':
            ExpertMode = True
        elif opt == '-x':
            ExperimentalMode = True
        elif opt == '-l':
            LoggingMode = arg
        elif opt == '-h':
            print("ALT-Scann 8 Command line parameters")
            print("  -s             Start Simulated session (for developers only)")
            print("  -e             Activate expert mode")
            print("  -x             Activate experimental mode (for developers only)")
            print("  -l <log mode>  Set log level (standard Python values (DEBUG, INFO, WARNING, ERROR)")
            exit()

    LogLevel = getattr(logging, LoggingMode.upper(), None)
    if not isinstance(LogLevel, int):
        raise ValueError('Invalid log level: %s' % LogLevel)

    tscann8_init()

    if not SimulatedRun:
        arduino_listen_loop()
        send_arduino_command(1, 1)

    build_ui()

    load_persisted_data_from_disk()

    load_config_data()

    if IsPiCamera2:     # Warning only for PiCamera2
        if PreviewWarnAgain:  # schedule hiding preview in 2 seconds to make warning visible
            win.after(2000, hide_preview)
            display_preview_warning()

    load_session_data()

    temperature_loop()

    # Main Loop
    win.mainloop()  # running the loop that works as a trigger

    if IsPiCamera2:
        capture_display_event.set()
        capture_save_event.set()
        capture_display_queue.put(END_TOKEN)
        capture_save_queue.put(END_TOKEN)
        capture_save_queue.put(END_TOKEN)
        capture_save_queue.put(END_TOKEN)

    if not SimulatedRun:
        camera.close()


if __name__ == '__main__':
    main(sys.argv[1:])

