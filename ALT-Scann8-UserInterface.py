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
__copyright__ = "Copyright 2022-23, Juan Remirez de Esparza"
__credits__ = ["Juan Remirez de Esparza"]
__license__ = "MIT"
__version__ = "1.8.15"
__date__ = "2024-01-01"
__version_highlight__ = "Picamera legacy code removal"
__maintainer__ = "Juan Remirez de Esparza"
__email__ = "jremirez@hotmail.com"
__status__ = "Development"

# ######### Imports section ##########
import tkinter as tk
from tkinter import filedialog

import tkinter.messagebox
import tkinter.simpledialog
from tkinter import DISABLED, NORMAL, LEFT, RIGHT, Y, TOP, BOTTOM, N, W, E, NW, X, RAISED, SUNKEN
from tkinter import Toplevel, Label, Button, Frame, LabelFrame, Canvas

from PIL import ImageTk, Image

import os
import time
import json

from datetime import datetime
import logging
import sys
import getopt

import numpy as np

try:
    import smbus
    from picamera2 import Picamera2, Preview
    from libcamera import Transform
    # Global variable to isolate camera specific code (Picamera vs PiCamera2)
    IsPiCamera2 = True
    # Global variable to allow basic UI testing on PC (where PiCamera imports should fail)
    SimulatedRun = False
except ImportError:
    SimulatedRun = True

import threading
import queue


#  ######### Global variable definition (I know, too many...) ##########
Controller_Id = 0   # 1 - Arduino, 2 - RPi Pico
FocusState = True
lastFocus = True
FocusZoomActive = False
FocusZoomPosX = 0.35
FocusZoomPosY = 0.35
FocusZoomFactorX = 0.2
FocusZoomFactorY = 0.2
FreeWheelActive = False
BaseDir = '/home/juan/Vídeos'  # dirplats in original code from Torulf
CurrentDir = BaseDir
FrameFilenamePattern = "picture-%05d.jpg"
FrameHdrFilenamePattern = "picture-%05d.%1d.jpg"   # HDR frames using standard filename (2/12/2023)
StillFrameFilenamePattern = "still-picture-%05d-%02d.jpg"
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
last_frame_time = 0
MinFrameStepsS8 = 290
MinFrameStepsR8 = 240
MinFrameSteps = MinFrameStepsS8     # Minimum number of steps per frame, to be passed to Arduino
FrameSteps_auto = True
FrameExtraSteps = 0     # Extra steps manually added after frame detected
FrameFineTune = 70      # Frame fine tune: PT threshold value as % between min adn max PT values
PTLevelS8 = 80
PTLevelR8 = 120
PTLevel = PTLevelS8     # Phototransistor reported level when hole is detected
PTLevel_auto = True
# Token to be sent on program closure, to allow threads to shut down cleanly
END_TOKEN = object()
FrameArrivalTime = 0
ScanSpeed = 5   # Speed of scan process (1-10 controls a variable delay inside the Arduino scan function)
# Variables to track windows movement and set preview accordingly
TopWinX = 0
TopWinY = 0
PreviewWinX = 90
PreviewWinY = 75
PreviewWidth = 844
PreviewHeight = 634
DeltaX = 0
DeltaY = 0
WinInitDone = False
FolderProcess = 0
LoggingMode = "INFO"
LogLevel = 0
draw_capture_label = 0
button_lock_counter = 0

PiCam2PreviewEnabled=False
CaptureStabilizationDelay = 0.1  # 100 ms
PostviewCounter = 0
FramesPerMinute = 0
FramesToGo = 0
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
FilmHoleY1 = 300
FilmHoleY2 = 300
SharpnessValue = 1

# Commands (RPI to Arduino)
CMD_VERSION_ID = 1
CMD_GET_CNT_STATUS = 2
CMD_RESET_CONTROLLER = 3
CMD_START_SCAN = 10
CMD_TERMINATE = 11
CMD_GET_NEXT_FRAME = 12
CMD_SET_REGULAR_8 = 18
CMD_SET_SUPER_8 = 19
CMD_SWITCH_REEL_LOCK_STATUS = 20
CMD_FILM_FORWARD = 30
CMD_SINGLE_STEP = 40
CMD_ADVANCE_FRAME = 41
CMD_ADVANCE_FRAME_FRACTION = 42
CMD_SET_PT_LEVEL = 50
CMD_SET_MIN_FRAME_STEPS = 52
CMD_SET_FRAME_FINE_TUNE = 54
CMD_SET_EXTRA_STEPS = 56
CMD_REWIND = 60
CMD_FAST_FORWARD = 61
CMD_INCREASE_WIND_SPEED = 62
CMD_DECREASE_WIND_SPEED = 63
CMD_UNCONDITIONAL_REWIND = 64
CMD_UNCONDITIONAL_FAST_FORWARD = 65
CMD_SET_SCAN_SPEED = 70
CMD_REPORT_PLOTTER_INFO = 87
# Responses (Arduino to RPi)
RSP_VERSION_ID = 1
RSP_FORCE_INIT = 2
RSP_FRAME_AVAILABLE = 80
RSP_SCAN_ERROR = 81
RSP_REWIND_ERROR = 82
RSP_FAST_FORWARD_ERROR = 83
RSP_REWIND_ENDED = 84
RSP_FAST_FORWARD_ENDED = 85
RSP_REPORT_AUTO_LEVELS = 86
RSP_REPORT_PLOTTER_INFO = 87
RSP_SCAN_ENDED = 88

# Expert mode variables - By default Exposure and white balance are set as automatic, with adapt delay
ExpertMode = False
ExperimentalMode = False
PlotterMode = False
plotter_canvas = None
plotter_width=200
plotter_height=160
PrevPTValue = 0
MaxPT = 100
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
ManualScanEnabled = False
CameraDisabled = False  # To allow testing scanner without a camera installed

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
# 4 iterations seem to be enough for exposure to catch up (started with 9, 4 gives same results, 3 is not enough)
dry_run_iterations = 4
# HDR, min/max exposure range. Used to be from 10 to 150, but original values found elsewhere (1-56) are better
# Finally set to 4-104
hdr_lower_exp = 8
hdr_min_exp = hdr_lower_exp
hdr_max_exp = 104
hdr_best_exp = 0
hdr_bracket_width = 50
hdr_num_exposures = 3   # Changed from 4 exposures to 3, probably an odd number is better (and 3 faster that 4)
hdr_step_value = 1
hdr_exp_list = []
hdr_rev_exp_list = []
HdrViewX4Active = False
recalculate_hdr_exp_list = False
force_adjust_hdr_bracket = False
HdrBracketAuto = False
hdr_auto_bracket_frames = 8    # Every n frames, bracket is recalculated

# Persisted data
# Persisted data
SessionData = {
    "CurrentDate": str(datetime.now()),
    "CurrentDir": CurrentDir,
    "CurrentFrame": str(CurrentFrame),
    "CurrentExposure": str(CurrentExposure),
    "NegativeCaptureActive": str(NegativeCaptureActive),
    "HdrCaptureActive": str(HdrCaptureActive),
    "HqCaptureActive": str(HqCaptureActive),
    "FilmType": 'S8',
    "MinFrameStepsS8": 290,
    "MinFrameStepsR8":  260,
    "MinFrameSteps":  290,
    "FrameFineTune":  70,
    "FrameExtraSteps": 0,
    "PTLevelS8":  80,
    "PTLevelR8":  200,
    "PTLevel":  80,
    "PTLevelAuto": True,
    "FrameStepsAuto": True,
    "HdrMinExp": hdr_min_exp,
    "HdrMaxExp": hdr_max_exp,
    "HdrBracketWidth": hdr_bracket_width,
    "HdrBracketAuto": True,
    "FramesToGo": FramesToGo
}

def exit_app():  # Exit Application
    global win
    global SimulatedRun
    global camera
    global PreviewMode

    # Uncomment next two lines when running on RPi
    if not SimulatedRun:
        send_arduino_command(CMD_TERMINATE)   # Tell Arduino we stop (to turn off uv led
        # Close preview if required
        if not CameraDisabled:
            if PiCam2PreviewEnabled:
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
        send_arduino_command(CMD_SWITCH_REEL_LOCK_STATUS)

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
        if not SimulatedRun and not CameraDisabled:
            camera.set_controls(
                {"ScalerCrop": (int(FocusZoomPosX * ZoomSize[0]), int(FocusZoomPosY * ZoomSize[1])) +
                               (int(FocusZoomFactorX * ZoomSize[0]), int(FocusZoomFactorY * ZoomSize[1]))})
    else:
        Focus_btn.config(text='Focus Zoom ON', bg=save_bg, fg=save_fg, relief=RAISED)
        if not SimulatedRun and not CameraDisabled:
            camera.set_controls({"ScalerCrop": (0, 0) + (ZoomSize[0], ZoomSize[1])})

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
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"ScalerCrop": (int(FocusZoomPosX * ZoomSize[0]), int(FocusZoomPosY * ZoomSize[1])) +
                                           (int(FocusZoomFactorX * ZoomSize[0]), int(FocusZoomFactorY * ZoomSize[1]))})


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


def set_new_folder():
    global CurrentDir, CurrentFrame
    global SimulatedRun
    global folder_frame_target_dir
    global Scanned_Images_number_label

    requested_dir = ""

    CurrentDir = BaseDir
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

    folder_frame_target_dir.config(text=CurrentDir)
    Scanned_Images_number_label.config(text=str(CurrentFrame))
    SessionData["CurrentDir"] = str(CurrentDir)
    SessionData["CurrentFrame"] = str(CurrentFrame)


def set_existing_folder():
    global CurrentDir, CurrentFrame
    global SimulatedRun

    if not SimulatedRun:
        CurrentDir = filedialog.askdirectory(initialdir=CurrentDir, title="Select existing folder for capture")
    else:
        CurrentDir = filedialog.askdirectory(initialdir=CurrentDir,
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


# In order to display a non-too-cryptic value for the exposure (what we keep in 'CurrentExposure')
# we will convert it to a higher level by using a similar algorythm as the one used by Torulf in his original code:
# We take '20000' as the base reference of zero, with chunks of 2000's up and down moving the counter by one unit
# 'CurrentExposure' = zero wil always be displayed as 'Auto'


def exposure_selection(updown):
    global exposure_spinbox, exposure_str
    global CurrentExposure, CurrentExposureStr
    global SimulatedRun
    global auto_exp_wait_checkbox

    if not ExpertMode:
        return

    if CurrentExposure == 0:  # Do not allow spinbox changes when in auto mode (should not happen as spinbox is readonly)
        return

    CurrentExposure = CurrentExposure + 2000 if updown=='up' else CurrentExposure - 2000

    if CurrentExposure <= 0:
        CurrentExposure = 1  # Do not allow zero or below
    else:
        CurrentExposure = CurrentExposure / 2000 * 2000 # in case we are starting from 1

    if CurrentExposure == 0:
        CurrentExposureStr = "Auto"
    else:
        CurrentExposureStr = str(round((CurrentExposure - 20000) / 2000))

    SessionData["CurrentExposure"] = str(CurrentExposure)

    exposure_spinbox.config(state='readonly' if CurrentExposure == 0 else NORMAL)

    if not SimulatedRun and not CameraDisabled:
        camera.controls.ExposureTime = int(CurrentExposure)  # maybe will not work, check pag 26 of picamera2 specs

    auto_exp_wait_checkbox.config(state=NORMAL if CurrentExposure == 0 else DISABLED)
    exposure_spinbox.config(value=CurrentExposureStr)


def exposure_spinbox_auto():
    global exposure_spinbox, exposure_str
    global CurrentExposure, CurrentExposureStr
    global SimulatedRun
    global auto_exp_wait_checkbox
    global exposure_btn, exposure_spinbox

    if CurrentExposure != 0:  # Not in automatic mode, activate auto
        CurrentExposure = 0
        CurrentExposureStr = "Auto"
        SessionData["CurrentExposure"] = str(CurrentExposure)
        if not SimulatedRun and not CameraDisabled:
            camera.controls.ExposureTime = int(CurrentExposure)  # maybe will not work, check pag 26 of picamera2 specs
    else:
        if not SimulatedRun and not CameraDisabled:
            # Since we are in auto exposure mode, retrieve current value to start from there
            metadata = camera.capture_metadata()
            CurrentExposure = metadata["ExposureTime"]
        else:
            CurrentExposure = 3500  # Arbitrary Value for Simulated run
        CurrentExposureStr = str(round((CurrentExposure - 20000) / 2000))
        SessionData["CurrentExposure"] = str(CurrentExposure)

    auto_exp_wait_checkbox.config(state=NORMAL if CurrentExposure == 0 else DISABLED)
    exposure_spinbox.config(value=CurrentExposureStr)
    arrange_widget_state(CurrentExposure == 0, [exposure_btn, exposure_spinbox])


def auto_exposure_change_pause_selection():
    global auto_exposure_change_pause
    global ExposureAdaptPause
    ExposureAdaptPause = auto_exposure_change_pause.get()
    SessionData["ExposureAdaptPause"] = str(ExposureAdaptPause)



def wb_red_selection(updown):
    global colour_gains_red_value_label
    global GainBlue, GainRed
    global wb_red_spinbox, wb_red_str
    global SimulatedRun

    if not ExpertMode:
        return

    if CurrentAwbAuto:  # Do not allow spinbox changes when in auto mode (should not happen as spinbox is readonly)
        return

    GainRed = float(wb_red_spinbox.get())
    SessionData["GainRed"] = GainRed

    if not SimulatedRun and not CurrentAwbAuto and not CameraDisabled:
        # camera.set_controls({"AwbEnable": 0})
        camera.set_controls({"ColourGains": (GainRed, GainBlue)})



def wb_blue_selection(updown):
    global colour_gains_blue_value_label
    global GainBlue, GainRed
    global wb_blue_spinbox, wb_blue_str
    global SimulatedRun

    if not ExpertMode:
        return

    if CurrentAwbAuto:  # Do not allow spinbox changes when in auto mode (should not happen as spinbox is readonly)
        return

    GainBlue = float(wb_blue_spinbox.get())
    SessionData["GainBlue"] = GainBlue

    if not SimulatedRun and not CurrentAwbAuto and not CameraDisabled:
        # camera.set_controls({"AwbEnable": 0})
        camera.set_controls({"ColourGains": (GainRed, GainBlue)})


def wb_spinbox_auto():
    global colour_gains_red_value_label
    global wb_red_spinbox, wb_red_str
    global wb_blue_spinbox, wb_blue_str
    global awb_red_wait_checkbox, awb_blue_wait_checkbox
    global CurrentAwbAuto
    global GainBlue, GainRed
    global colour_gains_auto_btn, awb_frame
    global colour_gains_red_btn_plus, colour_gains_red_btn_minus
    global colour_gains_blue_btn_plus, colour_gains_blue_btn_minus
    global colour_gains_red_value_label, colour_gains_blue_value_label

    if not ExpertMode:
        return

    CurrentAwbAuto = not CurrentAwbAuto
    SessionData["CurrentAwbAuto"] = str(CurrentAwbAuto)
    SessionData["GainRed"] = str(GainRed)
    SessionData["GainBlue"] = str(GainBlue)

    if CurrentAwbAuto:
        awb_red_wait_checkbox.config(state=NORMAL)
        awb_blue_wait_checkbox.config(state=NORMAL)
        if not SimulatedRun and not CameraDisabled:
            camera.set_controls({"AwbEnable": 1})
    else:
        awb_red_wait_checkbox.config(state=DISABLED)
        awb_blue_wait_checkbox.config(state=DISABLED)
        if not SimulatedRun and not CameraDisabled:
            # Retrieve current gain values from Camera
            metadata = camera.capture_metadata()
            camera_colour_gains = metadata["ColourGains"]
            GainRed = camera_colour_gains[0]
            GainBlue = camera_colour_gains[1]
            colour_gains_red_value_label.config(text=str(round(GainRed, 1)))
            colour_gains_blue_value_label.config(text=str(round(GainBlue, 1)))
            camera.set_controls({"AwbEnable": 0})

    arrange_widget_state(CurrentAwbAuto, [wb_blue_btn, wb_blue_spinbox])
    arrange_widget_state(CurrentAwbAuto, [wb_red_btn, wb_red_spinbox])



def auto_white_balance_change_pause_selection():
    global auto_white_balance_change_pause
    global AwbPause
    AwbPause = auto_white_balance_change_pause.get()
    SessionData["AwbPause"] = str(AwbPause)


def Manual_scan_activated_selection():
    global ManualScanEnabled, Manual_scan_activated
    global manual_scan_advance_fraction_5_btn, manual_scan_advance_fraction_20_btn, manual_scan_take_snap_btn
    ManualScanEnabled = Manual_scan_activated.get()
    manual_scan_advance_fraction_5_btn.config(state=NORMAL if ManualScanEnabled else DISABLED)
    manual_scan_advance_fraction_20_btn.config(state=NORMAL if ManualScanEnabled else DISABLED)
    manual_scan_take_snap_btn.config(state=NORMAL if ManualScanEnabled else DISABLED)


def manual_scan_advance_frame_fraction(steps):
    if not ExpertMode:
        return
    if not SimulatedRun:
        send_arduino_command(CMD_ADVANCE_FRAME_FRACTION, steps)
        time.sleep(0.2)
        capture('preview')
        time.sleep(0.2)

def manual_scan_advance_frame_fraction_5():
    manual_scan_advance_frame_fraction(5)


def manual_scan_advance_frame_fraction_20():
    manual_scan_advance_frame_fraction(20)


def manual_scan_take_snap():
    if not ExpertMode:
        return
    if not SimulatedRun:
        capture('manual')
        time.sleep(0.2)
        send_arduino_command(CMD_ADVANCE_FRAME)
        time.sleep(0.2)
        capture('preview')
        time.sleep(0.2)


def match_wait_margin_selection(updown):
    global colour_gains_red_value_label
    global MatchWaitMargin, match_wait_margin_spinbox
    global wb_red_spinbox, wb_red_str
    global SimulatedRun

    if not ExpertMode:
        return

    MatchWaitMargin = int(match_wait_margin_spinbox.get())
    SessionData["MatchWaitMargin"] = MatchWaitMargin

def stabilization_delay_selection(updown):
    global stabilization_delay_label
    global CaptureStabilizationDelay
    global stabilization_delay_spinbox, stabilization_delay_str
    global SimulatedRun

    if not ExpertMode:
        return

    CaptureStabilizationDelay = int(stabilization_delay_spinbox.get())/1000
    SessionData["CaptureStabilizationDelay"] = str(CaptureStabilizationDelay)


def stabilization_delay_spinbox_focus_out(event):
    global stabilization_delay_label
    global CaptureStabilizationDelay
    global stabilization_delay_spinbox, stabilization_delay_str
    global SimulatedRun

    CaptureStabilizationDelay = int(stabilization_delay_spinbox.get())/1000
    SessionData["CaptureStabilizationDelay"] = str(CaptureStabilizationDelay)


def sharpness_control_selection(updown):
    global sharpness_control_label
    global SharpnessValue
    global sharpness_control_spinbox, sharpness_control_str
    global SimulatedRun

    if not ExpertMode:
        return

    SharpnessValue = int(sharpness_control_spinbox.get())
    SessionData["SharpnessValue"] = str(SharpnessValue)


def sharpness_control_spinbox_focus_out(event):
    global sharpness_control_label
    global SharpnessValue
    global sharpness_control_spinbox, sharpness_control_str
    global SimulatedRun

    SharpnessValue = int(sharpness_control_spinbox.get())
    SessionData["SharpnessValue"] = str(SharpnessValue)


def rwnd_speed_control_selection(updown):
    global rwnd_speed_control_label
    global rwnd_speed_delay
    global rwnd_speed_control_spinbox, rwnd_speed_control_str
    global SimulatedRun

    if not ExpertMode:
        return

    if updown == 'up':
        rwnd_speed_up()
    else:
        rwnd_speed_down()

def rwnd_speed_down():
    global rwnd_speed_delay
    global rwnd_speed_control_delay

    if not SimulatedRun:
        send_arduino_command(CMD_INCREASE_WIND_SPEED)
    if rwnd_speed_delay + rwnd_speed_delay*0.1 < 4000:
        rwnd_speed_delay += rwnd_speed_delay*0.1
    else:
        rwnd_speed_delay = 4000
    rwnd_speed_control_spinbox.config(text=str(round(60/(rwnd_speed_delay * 375 / 1000000))) + 'rpm')

def rwnd_speed_up():
    global rwnd_speed_delay
    global rwnd_speed_control_delay

    if not SimulatedRun:
        send_arduino_command(CMD_DECREASE_WIND_SPEED)
    if rwnd_speed_delay -rwnd_speed_delay*0.1 > 200:
        rwnd_speed_delay -= rwnd_speed_delay*0.1
    else:
        rwnd_speed_delay = 200
    rwnd_speed_control_spinbox.config(text=str(round(60/(rwnd_speed_delay * 375 / 1000000))) + 'rpm')


def min_frame_steps_selection(updown):
    global min_frame_steps_spinbox, min_frame_steps_str
    global MinFrameSteps
    MinFrameSteps = int(min_frame_steps_spinbox.get())
    SessionData["MinFrameSteps"] = MinFrameSteps
    SessionData["MinFrameSteps" + SessionData["FilmType"]] = MinFrameSteps
    send_arduino_command(CMD_SET_MIN_FRAME_STEPS, MinFrameSteps)


def min_frame_steps_spinbox_focus_out(event):
    global min_frame_steps_spinbox, min_frame_steps_str
    global MinFrameSteps
    MinFrameSteps = int(min_frame_steps_spinbox.get())
    SessionData["MinFrameSteps"] = MinFrameSteps
    SessionData["MinFrameSteps" + SessionData["FilmType"]] = MinFrameSteps
    if not FrameSteps_auto: # Not sure we can have a focus out event for a disabled control, but just in case
        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, MinFrameSteps)


def min_frame_steps_spinbox_auto():
    global min_frame_steps_spinbox, min_frame_steps_str, min_frame_steps_btn
    global MinFrameSteps, FrameSteps_auto

    FrameSteps_auto = not FrameSteps_auto

    arrange_widget_state(FrameSteps_auto, [min_frame_steps_btn, min_frame_steps_spinbox])

    SessionData["FrameStepsAuto"] = FrameSteps_auto
    send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0 if FrameSteps_auto else MinFrameSteps)


def frame_fine_tune_selection(updown):
    global frame_fine_tune_spinbox, frame_fine_tune_str
    global FrameFineTune
    FrameFineTune = int(frame_fine_tune_spinbox.get())
    SessionData["FrameFineTune"] = FrameFineTune
    SessionData["FrameFineTune" + SessionData["FilmType"]] = FrameFineTune
    send_arduino_command(CMD_SET_FRAME_FINE_TUNE, FrameFineTune)


def frame_fine_tune_spinbox_focus_out(event):
    global frame_fine_tune_spinbox, frame_fine_tune_str
    global FrameFineTune
    FrameFineTune = int(frame_fine_tune_spinbox.get())
    SessionData["FrameFineTune"] = FrameFineTune
    SessionData["FrameFineTune" + SessionData["FilmType"]] = FrameFineTune
    send_arduino_command(CMD_SET_FRAME_FINE_TUNE, FrameFineTune)


def frame_extra_steps_selection(updown):
    global frame_extra_steps_spinbox, frame_extra_steps_str
    global FrameExtraSteps
    FrameExtraSteps = int(frame_extra_steps_spinbox.get())
    SessionData["FrameExtraSteps"] = FrameExtraSteps
    send_arduino_command(CMD_SET_EXTRA_STEPS, FrameExtraSteps)


def frame_extra_steps_spinbox_focus_out(event):
    global frame_extra_steps_spinbox, frame_extra_steps_str
    global FrameExtraSteps
    FrameExtraSteps = int(frame_extra_steps_spinbox.get())
    SessionData["FrameExtraSteps"] = FrameExtraSteps
    send_arduino_command(CMD_SET_EXTRA_STEPS, FrameExtraSteps)


def pt_level_selection(updown):
    global pt_level_spinbox, pt_level_str
    global PTLevel
    PTLevel = int(pt_level_spinbox.get())
    SessionData["PTLevel"] = PTLevel
    SessionData["PTLevel" + SessionData["FilmType"]] = PTLevel
    send_arduino_command(CMD_SET_PT_LEVEL, PTLevel)


def pt_level_spinbox_focus_out(event):
    global pt_level_spinbox, pt_level_str
    global PTLevel
    PTLevel = int(pt_level_spinbox.get())
    SessionData["PTLevel"] = PTLevel
    SessionData["PTLevel" + SessionData["FilmType"]] = PTLevel
    if not PTLevel_auto: # Not sure we can have a focus out event for a disabled control, but just in case
        send_arduino_command(CMD_SET_PT_LEVEL, PTLevel)


def pt_level_spinbox_auto():
    global pt_level_spinbox, pt_level_str, pt_level_btn
    global PTLevel, PTLevel_auto

    PTLevel_auto = not PTLevel_auto

    arrange_widget_state(PTLevel_auto, [pt_level_btn, pt_level_spinbox])

    SessionData["PTLevelAuto"] = PTLevel_auto
    send_arduino_command(CMD_SET_PT_LEVEL, 0 if PTLevel_auto else PTLevel)


def scan_speed_selection(updown):
    global scan_speed_spinbox, scan_speed_label_str
    global ScanSpeed
    ScanSpeed = int(scan_speed_spinbox.get())
    SessionData["ScanSpeed"] = ScanSpeed
    send_arduino_command(CMD_SET_SCAN_SPEED, ScanSpeed)


def scan_speed_spinbox_focus_out(event):
    global scan_speed_spinbox, scan_speed_label_str
    global ScanSpeed
    ScanSpeed = int(scan_speed_spinbox.get())
    SessionData["ScanSpeed"] = ScanSpeed
    send_arduino_command(CMD_SET_SCAN_SPEED, ScanSpeed)


def hdr_check_min_exp(event):
    global hdr_min_exp_spinbox, hdr_min_exp_str, hdr_min_exp, recalculate_hdr_exp_list
    global hdr_max_exp, hdr_max_exp_str
    global hdr_bracket_width, hdr_bracket_width_str
    global force_adjust_hdr_bracket

    if not ExpertMode:
        return

    save_value = hdr_min_exp
    hdr_min_exp = int(hdr_min_exp_str.get())
    if hdr_min_exp < hdr_lower_exp:
        hdr_min_exp = hdr_lower_exp
    hdr_max_exp = hdr_min_exp + hdr_bracket_width
    if hdr_max_exp > 1000:
        hdr_bracket_width -= hdr_max_exp-1000  # Reduce bracked
        hdr_max_exp = 1000
        force_adjust_hdr_bracket = True
    hdr_min_exp_str.set(str(hdr_min_exp))
    hdr_max_exp_str.set(hdr_max_exp)
    hdr_bracket_width_str.set(hdr_bracket_width)
    if save_value != hdr_min_exp:
        recalculate_hdr_exp_list = True
    SessionData["HdrMinExp"] = hdr_min_exp
    SessionData["HdrMaxExp"] = hdr_max_exp
    SessionData["HdrBracketWidth"] = hdr_max_exp


def hdr_check_max_exp(event):
    global hdr_max_exp_spinbox, hdr_min_exp_str, hdr_min_exp, recalculate_hdr_exp_list
    global hdr_max_exp, hdr_max_exp_str
    global hdr_bracket_width, hdr_bracket_width_str
    global force_adjust_hdr_bracket

    if not ExpertMode:
        return

    save_value = hdr_max_exp
    hdr_max_exp = int(hdr_max_exp_str.get())
    if hdr_max_exp > 1000:
        hdr_max_exp = 1000
    if (hdr_max_exp > hdr_min_exp):
        hdr_bracket_width = hdr_max_exp - hdr_min_exp
        force_adjust_hdr_bracket = True
    else:
        hdr_min_exp = hdr_max_exp - hdr_bracket_width
    if hdr_min_exp < hdr_lower_exp:
        hdr_min_exp = hdr_lower_exp
        hdr_bracket_width = hdr_max_exp - hdr_min_exp  # Reduce bracket
        force_adjust_hdr_bracket = True
    hdr_min_exp_str.set(str(hdr_min_exp))
    hdr_max_exp_str.set(hdr_max_exp)
    hdr_bracket_width_str.set(hdr_bracket_width)
    if save_value != hdr_max_exp:
        recalculate_hdr_exp_list = True
    SessionData["HdrMinExp"] = hdr_min_exp
    SessionData["HdrMaxExp"] = hdr_max_exp
    SessionData["HdrBracketWidth"] = hdr_max_exp


def hdr_check_bracket_width(event):
    global hdr_bracket_width_spinbox, hdr_bracket_width_str, hdr_bracket_width
    global hdr_min_exp, hdr_min_exp_str
    global hdr_max_exp, hdr_max_exp_str
    global recalculate_hdr_exp_list
    global force_adjust_hdr_bracket

    if not ExpertMode:
        return

    save_value = hdr_bracket_width
    hdr_bracket_width = int(hdr_bracket_width_str.get())

    if (hdr_bracket_width < 4):
        hdr_bracket_width = 4
        hdr_bracket_width_str.set(hdr_bracket_width)
    if (hdr_bracket_width > 200):
        hdr_bracket_width = 200
        hdr_bracket_width_str.set(hdr_bracket_width)

    if save_value != hdr_bracket_width:
        force_adjust_hdr_bracket = True
        middle_exp = int((hdr_min_exp + (hdr_max_exp-hdr_min_exp))/2)
        hdr_min_exp = int(middle_exp - (hdr_bracket_width/2))
        if hdr_min_exp < hdr_lower_exp:
            hdr_min_exp = hdr_lower_exp
            hdr_max_exp = hdr_min_exp + hdr_bracket_width
        else:
            hdr_max_exp = int(middle_exp + (hdr_bracket_width/2))
        hdr_min_exp_str.set(str(hdr_min_exp))
        hdr_max_exp_str.set(hdr_max_exp)
        SessionData["HdrMinExp"] = hdr_min_exp
        SessionData["HdrMaxExp"] = hdr_max_exp
        SessionData["HdrBracketWidth"] = hdr_bracket_width


def button_status_change_except(except_button, active):
    global Free_btn, SingleStep_btn, Snapshot_btn, AdvanceMovie_btn
    global Rewind_btn, FastForward_btn, Start_btn
    global PosNeg_btn, Focus_btn, Start_btn, Exit_btn
    global film_type_S8_btn, film_type_R8_btn
    global PiCam2_preview_btn, hdr_btn, hq_btn, turbo_btn
    global button_lock_counter
    global hdr_capture_active_checkbox

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
    if except_button != Start_btn and not PiCam2PreviewEnabled:
        Start_btn.config(state=DISABLED if active else NORMAL)
    if except_button != Exit_btn:
        Exit_btn.config(state=DISABLED if active else NORMAL)
    if except_button != film_type_S8_btn:
        film_type_S8_btn.config(state=DISABLED if active else NORMAL)
    if except_button != film_type_R8_btn:
        film_type_R8_btn.config(state=DISABLED if active else NORMAL)
    hdr_capture_active_checkbox.config(state=DISABLED if active else NORMAL)
    if ExperimentalMode:
        if except_button != hq_btn:
            hq_btn.config(state=DISABLED if active else NORMAL)
        if except_button != turbo_btn:
            turbo_btn.config(state=DISABLED if active else NORMAL)

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
        send_arduino_command(CMD_FILM_FORWARD)

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
        RewindMovieActive = True
        # Update button text
        Rewind_btn.config(text='Stop\n<<', bg='red', fg='white', relief=SUNKEN)  # ...so now we propose to stop it in the button test
        # Enable/Disable related buttons
        button_status_change_except(Rewind_btn, RewindMovieActive)
        # Invoke rewind_loop to continue processing until error or end event
        win.after(5, rewind_loop)
    elif RewindErrorOutstanding:
        confirm = tk.messagebox.askyesno(title='Error during rewind',
                                         message='It seems there is film loaded via filmgate. \
                                         \r\nAre you sure you want to proceed?')
        if confirm:
            time.sleep(0.2)
            if not SimulatedRun:
                send_arduino_command(CMD_UNCONDITIONAL_REWIND)    # Forced rewind, no filmgate check
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
            send_arduino_command(CMD_REWIND)

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
        FastForwardActive = True
        # Update button text
        FastForward_btn.config(text='Stop\n>>', bg='red', fg='white', relief=SUNKEN)
        # Enable/Disable related buttons
        button_status_change_except(FastForward_btn, FastForwardActive)
        # Invoke fast_forward_loop a first time when fast-forward starts
        win.after(5, fast_forward_loop)
    elif FastForwardErrorOutstanding:
        confirm = tk.messagebox.askyesno(title='Error during fast forward',
                                         message='It seems there is film loaded via filmgate. \
                                         \r\nAre you sure you want to proceed?')
        if confirm:
            time.sleep(0.2)
            if not SimulatedRun:
                send_arduino_command(CMD_UNCONDITIONAL_FAST_FORWARD)    # Forced FF, no filmgate check
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
            send_arduino_command(CMD_FAST_FORWARD)

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
                image_array = np.asarray(message[0])
                image_array = np.negative(image_array)
                message[0] = Image.fromarray(image_array)
            draw_preview_image(message[0], message[2])
            logging.debug("Display thread complete: %s ms", str(round((time.time() - curtime) * 1000, 1)))
        else:
            logging.warning("Display queue almost full: Skipping frame display")
    logging.debug("Exiting capture_display_thread")


def capture_save_thread(queue, event, id):
    global CurrentDir
    global message
    global ScanStopRequested

    if os.path.isdir(CurrentDir):
        os.chdir(CurrentDir)
    else:
        logging.error("Target dir %s unmounted: Stop scan session", CurrentDir)
        ScanStopRequested = True    # If target dir does not exist, stop scan
        return
    logging.debug("Started capture_save_thread n.%i", id)
    while not event.is_set() or not queue.empty():
        message = queue.get()
        curtime = time.time()
        logging.debug("Thread %i: Retrieved message from capture save queue", id)
        if message == END_TOKEN:
            break
        # Invert image if button selected
        if NegativeCaptureActive:
            image_array = np.asarray(message[0])
            image_array = np.negative(image_array)
            message[0] = Image.fromarray(image_array)
        if message[2] > 1:  # Hdr frame 1 has standard filename
            logging.debug("Saving HDR frame n.%i", message[2])
            message[0].save(FrameHdrFilenamePattern % (message[1],message[2]), quality=95)
        else:
            message[0].save(FrameFilenamePattern % message[1], quality=95)
        logging.debug("Thread %i saved image: %s ms", id, str(round((time.time() - curtime) * 1000, 1)))
    logging.debug("Exiting capture_save_thread n.%i", id)

def draw_preview_image(preview_image, idx):
    global draw_capture_label
    global preview_border_frame
    global win
    global total_wait_time_preview_display
    global hdr_view_4_image

    curtime = time.time()


    if idx == 0 or (idx == 2 and not HdrViewX4Active):
        preview_image = preview_image.resize((PreviewWidth, PreviewHeight))
        PreviewAreaImage = ImageTk.PhotoImage(preview_image)
    elif HdrViewX4Active:
        # if using View4X mode and there are 5 exposures, we do not display the 5th
        # and if there are 3, 4th position will always be empty
        quarter_image = preview_image.resize((int(PreviewWidth/2), int(PreviewHeight/2)))
        if idx == 1:
            hdr_view_4_image.paste(quarter_image, (0, 0))
        elif idx == 2:
            hdr_view_4_image.paste(quarter_image, (int(PreviewWidth/2), 0))
        elif idx == 3:
            hdr_view_4_image.paste(quarter_image, (0, int(PreviewHeight/2)))
        elif idx == 4:
            hdr_view_4_image.paste(quarter_image, (int(PreviewWidth / 2), int(PreviewHeight/2)))
        PreviewAreaImage = ImageTk.PhotoImage(hdr_view_4_image)

    if idx == 0 or (idx == 2 and not HdrViewX4Active) or HdrViewX4Active:
        # The Label widget is a standard Tkinter widget used to display a text or image on the screen.
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
        capture('still')


def single_step_movie():
    global SimulatedRun
    global camera

    if not SimulatedRun:
        send_arduino_command(CMD_SINGLE_STEP)

        if not CameraDisabled:
            # If no camera preview, capture frame in memory and display it
            # Single step is not a critical operation, waiting 100ms for it to happen should be enough
            # No need to implement confirmation from Arduino, as we have for regular capture during scan
            time.sleep(0.5)
            single_step_image = camera.capture_image("main")
            draw_preview_image(single_step_image, 0)


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


def hdr_set_controls():
    global hdr_capture_active
    global hdr_bracket_width_label, hdr_bracket_width_spinbox
    global hdr_viewx4_active_checkbox, hdr_min_exp_label, hdr_min_exp_spinbox, hdr_max_exp_label, hdr_max_exp_spinbox

    hdr_viewx4_active_checkbox.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_min_exp_label.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_min_exp_spinbox.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_max_exp_label.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_max_exp_spinbox.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_bracket_width_label.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_bracket_width_spinbox.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_bracket_width_auto_checkbox.config(state=NORMAL if HdrCaptureActive else DISABLED)

def switch_hdr_capture():
    global CurrentExposure
    global SimulatedRun
    global hdr_capture_active, HdrCaptureActive, HdrBracketAuto
    global hdr_min_exp_spinbox, hdr_max_exp_spinbox, hdr_bracket_width_auto_checkbox

    HdrCaptureActive = hdr_capture_active.get()
    SessionData["HdrCaptureActive"] = str(HdrCaptureActive)

    hdr_set_controls()
    if HdrCaptureActive:    # If HDR enabled, handle automatic control settings for widgets
        arrange_widget_state(HdrBracketAuto, [hdr_min_exp_spinbox, hdr_max_exp_spinbox, hdr_bracket_width_auto_checkbox])
    else:    # If disabling HDR, need to set standard exposure as set in UI
        if CurrentExposure == 0:  # Automatic mode
            SessionData["CurrentExposure"] = str(CurrentExposure)
            if not SimulatedRun and not CameraDisabled:
                camera.controls.ExposureTime = int(
                    CurrentExposure)  # maybe will not work, check pag 26 of picamera2 specs
        else:
            if not SimulatedRun:
                # Since we are in auto exposure mode, retrieve current value to start from there
                if not CameraDisabled:
                    metadata = camera.capture_metadata()
                    CurrentExposure = metadata["ExposureTime"]
                else:
                    CurrentExposure = camera.exposure_speed
            else:
                CurrentExposure = 3500  # Arbitrary Value for Simulated run
            SessionData["CurrentExposure"] = str(CurrentExposure)

def switch_hdr_viewx4():
    global HdrViewX4Active, hdr_viewx4_active
    HdrViewX4Active = hdr_viewx4_active.get()
    SessionData["HdrViewX4Active"] = str(HdrViewX4Active)



# Capture with sensor at 4056x3040
# Frames delivered still at 2028x1520, but better quality
def switch_hq_capture():
    global HqCaptureActive
    global hq_btn

    HqCaptureActive = not HqCaptureActive
    if not CameraDisabled:
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
    if not CameraDisabled:
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

    if not SimulatedRun and not CameraDisabled:
        # Do nothing for PiCamera2, image turns negative at save time
        logging.debug("Negative mode " + "On" if NegativeCaptureActive else "Off")


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
    if not SimulatedRun and not CameraDisabled:
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
    global FilmHoleY1, FilmHoleY2
    global ALT_scann_init_done
    global film_hole_frame_1, film_hole_frame_2

    film_type_S8_btn.config(relief=SUNKEN)
    film_type_R8_btn.config(relief=RAISED)
    SessionData["FilmType"] = "S8"
    time.sleep(0.2)

    PTLevel = PTLevelS8
    if ALT_scann_init_done:
        SessionData["PTLevel"] = PTLevel
        SessionData["MinFrameSteps"] = MinFrameSteps
    pt_level_str.set(str(PTLevel))
    MinFrameSteps = MinFrameStepsS8
    min_frame_steps_str.set(str(MinFrameSteps))
    # Set reference film holes
    FilmHoleY1 = 300
    FilmHoleY2 = 300
    film_hole_frame_1.place(x=4, y=FilmHoleY2, height=140)
    film_hole_frame_2.place(x=4, y=FilmHoleY2, height=140)
    if not SimulatedRun:
        send_arduino_command(CMD_SET_SUPER_8)
        send_arduino_command(CMD_SET_PT_LEVEL, 0 if PTLevel_auto else PTLevel)
        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0 if FrameSteps_auto else MinFrameSteps)



def set_r8():
    global SimulatedRun
    global film_type_R8_btn, film_type_S8_btn
    global PTLevel, PTLevelR8
    global MinFrameSteps, MinFrameStepsR8
    global pt_level_str, min_frame_steps_str
    global film_hole_frame_1, film_hole_frame_2

    film_type_R8_btn.config(relief=SUNKEN)
    film_type_S8_btn.config(relief=RAISED)
    SessionData["FilmType"] = "R8"
    time.sleep(0.2)

    PTLevel = PTLevelR8
    if ALT_scann_init_done:
        SessionData["PTLevel"] = PTLevel
        SessionData["MinFrameSteps"] = MinFrameSteps
    pt_level_str.set(str(PTLevel))
    MinFrameSteps = MinFrameStepsR8
    min_frame_steps_str.set(str(MinFrameSteps))
    # Set reference film holes
    FilmHoleY1 = 40
    FilmHoleY2 = 540
    film_hole_frame_1.place(x=4, y=FilmHoleY1, height=100)
    film_hole_frame_2.place(x=4, y=FilmHoleY2, height=130)
    if not SimulatedRun:
        send_arduino_command(CMD_SET_REGULAR_8)
        send_arduino_command(CMD_SET_PT_LEVEL, 0 if PTLevel_auto else PTLevel)
        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0 if FrameSteps_auto else MinFrameSteps)



def register_frame():
    global FPM_LastMinuteFrameTimes
    global FPM_StartTime
    global FPM_CalculatedValue

    # Get current time
    frame_time = time.time()
    # Determine if we should start new count (last capture older than 5 seconds)
    if len(FPM_LastMinuteFrameTimes) == 0 or FPM_LastMinuteFrameTimes[-1] < frame_time - 12:
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
    global camera, hdr_exp_list, hdr_rev_exp_list, VideoCaptureActive
    global recalculate_hdr_exp_list, dry_run_iterations
    global HdrBracketAuto

    if HdrBracketAuto and session_frames % hdr_auto_bracket_frames == 0:
        adjust_hdr_bracket()

    if recalculate_hdr_exp_list:
        hdr_reinit()
        perform_dry_run = True
        recalculate_hdr_exp_list = False
    else:
        perform_dry_run = False

    image_list.clear()
    # session_frames should be equal to 1 for the first captured frame of the scan session.
    # For HDR this means we need to unconditionally wait for exposure adaptation
    # For following frames, we can skip dry run for the first capture since we alternate the sense of the exposures on each frame
    if session_frames == 1:
        perform_dry_run = True

    if session_frames % 2 == 1:
        work_list = hdr_exp_list
        idx = 1
        idx_inc = 1
    else:
        work_list = hdr_rev_exp_list
        idx = hdr_num_exposures
        idx_inc = -1
    for exp in work_list:
        logging.debug("capture_hdr: exp %.2f", exp)
        if perform_dry_run:
            camera.set_controls({"ExposureTime": int(exp*1000)})
        else:
            time.sleep(CaptureStabilizationDelay)  # Allow time to stabilize image only if no dry run
        # Depending on results, maybe set as well fps: {"FrameDurationLimits": (40000, 40000)}
        if VideoCaptureActive:
            if perform_dry_run:
                for i in range(1, dry_run_iterations):
                    camera.capture_request()
                    win.update()
            request = camera.capture_request()
            win.update()
            img = request.make_image("main")
            img = img.convert('RGB')
            captured_snapshot = img.copy()
            request.release()
        else:
            if perform_dry_run:
                for i in range(1,dry_run_iterations):   # Perform a few dummy captures to allow exposure stabilization
                    camera.capture_image("main")
                    win.update()
            captured_snapshot = camera.capture_image("main")
            win.update()
        # We skip dry run only for the first capture of each frame,
        # as it is the same exposure as the last capture of the previous one
        perform_dry_run = True
        # For PiCamera2, preview and save to file are handled in asynchronous threads
        queue_item = tuple((captured_snapshot, CurrentFrame, idx))
        capture_display_queue.put(queue_item)
        capture_save_queue.put(queue_item)
        idx += idx_inc


def adjust_hdr_bracket_auto():
    global HdrCaptureActive, HdrBracketAuto, hdr_bracket_auto
    global hdr_max_exp_spinbox, hdr_min_exp_spinbox

    if not HdrCaptureActive:
        return

    HdrBracketAuto = hdr_bracket_auto.get()
    SessionData["HdrBracketAuto"] = HdrBracketAuto

    arrange_widget_state(HdrBracketAuto, [hdr_max_exp_spinbox, hdr_min_exp_spinbox])


def adjust_hdr_bracket():
    global camera, VideoCaptureActive, HdrCaptureActive
    global recalculate_hdr_exp_list, dry_run_iterations
    global hdr_min_exp, hdr_max_exp, hdr_best_exp, hdr_bracket_width
    global hdr_min_exp_str, hdr_max_exp_str
    global PreviousCurrentExposure, HdrBracketAuto
    global hdr_max_exp_spinbox, hdr_min_exp_spinbox
    global save_bg, save_fg
    global force_adjust_hdr_bracket

    if not HdrCaptureActive:
        return

    if SimulatedRun or CameraDisabled:
        aux_current_exposure = 20
    else:
        camera.set_controls({"ExposureTime": 0})    # Set automatic exposure, 7 shots allowed to catch up
        if VideoCaptureActive:
            for i in range(1, dry_run_iterations * 2):
                camera.capture_request()
                win.update()
        else:
            for i in range(1, dry_run_iterations * 2):
                camera.capture_image("main")
                win.update()

        # Since we are in auto exposure mode, retrieve current value to start from there
        metadata = camera.capture_metadata()
        aux_current_exposure = int(metadata["ExposureTime"]/1000)

    if aux_current_exposure != PreviousCurrentExposure or force_adjust_hdr_bracket:  # Adjust only if auto exposure changes
        logging.debug(f"Adjusting bracket, prev/cur exp: {PreviousCurrentExposure} -> {aux_current_exposure}")
        force_adjust_hdr_bracket = False
        PreviousCurrentExposure = aux_current_exposure
        hdr_best_exp = aux_current_exposure
        hdr_min_exp = max(hdr_best_exp-int(hdr_bracket_width/2), hdr_lower_exp)
        hdr_min_exp_str.set(str(hdr_min_exp))
        hdr_max_exp = hdr_min_exp + hdr_bracket_width
        hdr_max_exp_str.set(hdr_max_exp)
        SessionData["HdrMinExp"] = hdr_min_exp
        SessionData["HdrMaxExp"] = hdr_max_exp
        recalculate_hdr_exp_list = True
        logging.debug(f"Adjusting bracket: {hdr_min_exp}, {hdr_max_exp}")



# 4 possible modes:
# 'normal': Standard capture during automated scan (display and save)
# 'manual': Manual capture during manual scan (display and save)
# 'still': Button to capture still (specific filename)
# 'preview': Manual scan, display only, do not save
def capture(mode):
    global CurrentDir, CurrentFrame, CurrentExposure
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

    if SimulatedRun or CameraDisabled:
        return

    os.chdir(CurrentDir)

    # Wait for auto exposure to adapt only if allowed (and if not using HDR)
    if CurrentExposure == 0 and ExposureAdaptPause and not HdrCaptureActive:
        curtime = time.time()
        wait_loop_count = 0
        while True:  # In case of exposure change, give time for the camera to adapt
            metadata = camera.capture_metadata()
            aux_current_exposure = metadata["ExposureTime"]
            # With PiCamera2, exposure was changing too often, so level changed from 1000 to 2000, then to 4000
            # Finally changed to allow a percentage of the value used previously
            # As we initialize this percentage to 50%, we start with double the original value
            #if abs(aux_current_exposure - PreviousCurrentExposure) > 4000:
            if abs(aux_current_exposure - PreviousCurrentExposure) > (MatchWaitMargin * Tolerance_AE)/100:
                if (wait_loop_count % 10 == 0):
                    aux_exposure_str = "Auto (" + str(round((aux_current_exposure - 20000) / 2000)) + ")"
                    logging.debug("AE match: (%i,%s)",aux_current_exposure, aux_exposure_str)
                wait_loop_count += 1
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
            logging.debug("AE match delay: %s ms", str(round((time.time() - curtime) * 1000,1)))

    # Wait for auto white balance to adapt only if allowed
    if CurrentAwbAuto and AwbPause:
        curtime = time.time()
        wait_loop_count = 0
        while True:  # In case of exposure change, give time for the camera to adapt
            metadata = camera.capture_metadata()
            camera_colour_gains = metadata["ColourGains"]
            aux_gain_red = camera_colour_gains[0]
            aux_gain_blue = camera_colour_gains[1]
            # Same as for exposure, difference allowed is a percentage of the maximum value
            #if abs(aux_gain_red-PreviousGainRed) >= 0.5 or abs(aux_gain_blue-PreviousGainBlue) >= 0.5:
            if abs(aux_gain_red-PreviousGainRed) >= (MatchWaitMargin * Tolerance_AWB/100) or \
               abs(aux_gain_blue-PreviousGainBlue) >= (MatchWaitMargin * Tolerance_AWB/100):
                if (wait_loop_count % 10 == 0):
                    aux_gains_str = "(" + str(round(aux_gain_red, 2)) + ", " + str(round(aux_gain_blue, 2)) + ")"
                    #print(f"AWB Match: {aux_gains_str})")
                    logging.debug("AWB Match: %s", aux_gains_str)
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
            logging.debug("AWB Match delay: %s ms", str(round((time.time() - curtime) * 1000,1)))

    if not SimulatedRun:
        if PiCam2PreviewEnabled:
            if mode == 'still':
                camera.switch_mode_and_capture_file(capture_config, StillFrameFilenamePattern % (CurrentFrame,CurrentStill))
                CurrentStill += 1
            else:
                # This one should not happen, will not allow PiCam2 scan in preview mode
                camera.switch_mode_and_capture_file(capture_config, FrameFilenamePattern % CurrentFrame)
        else:
            time.sleep(CaptureStabilizationDelay)   # Allow time to stabilize image, it can get too fast with PiCamera2
            if mode == 'still':
                captured_snapshot = camera.capture_image("main")
                captured_snapshot.save(StillFrameFilenamePattern % (CurrentFrame,CurrentStill))
                CurrentStill += 1
            else:
                if HdrCaptureActive:
                    # Stabilization delay for HDR managed inside capture_hdr
                    capture_hdr()
                else:
                    time.sleep(CaptureStabilizationDelay)  # Allow time to stabilize image, too fast with PiCamera2
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
                    logging.debug("Displaying frame %i", CurrentFrame)
                    if mode == 'normal' or mode == 'manual':    # Do not save in preview mode, only display
                        capture_save_queue.put(queue_item)
                        logging.debug("Saving frame %i", CurrentFrame)
                        if mode == 'manual':  # In manual mode, increase CurrentFrame
                            CurrentFrame += 1
                            # Update number of captured frames
                            Scanned_Images_number_label.config(text=str(CurrentFrame))

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
    global last_frame_time


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
        last_frame_time = time.time() + 3

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
    global FramesPerMinute, FramesToGo, frames_to_go_str, time_to_go_str, frames_to_go_entry, time_to_go_time
    global NewFrameAvailable
    global ScanOngoing
    global preview_border_frame
    global raw_simulated_capture_image
    global simulated_capture_image
    global simulated_captured_frame_list, simulated_images_in_list
    global ScanStopRequested
    global total_wait_time_autoexp, total_wait_time_awb, total_wait_time_preview_display, session_start_time
    global session_frames
    global Scanned_Images_fpm
    global SessionData

    if ScanStopRequested:
        stop_scan_simulated()
        ScanStopRequested = False
        curtime = time.time()
        if ExpertMode:
            logging.debug("Total session time: %s seg for %i frames (%i ms per frame)",
                         str(round((curtime-session_start_time),1)),
                         session_frames,
                         round(((curtime-session_start_time)*1000/session_frames),1))
            logging.debug("Total time to display preview image: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_preview_display),1)),
                         round((total_wait_time_preview_display*1000/session_frames),1))
            logging.debug("Total time waiting for AWB adjustment: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_awb),1)),
                         round((total_wait_time_awb*1000/session_frames),1))
            logging.debug("Total time waiting for AE adjustment: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_autoexp),1)),
                         round((total_wait_time_autoexp*1000/session_frames),1))
    if ScanOngoing:
        os.chdir(CurrentDir)
        frame_to_display = CurrentFrame % simulated_images_in_list
        filename, ext = os.path.splitext(simulated_captured_frame_list[frame_to_display])
        if ext == '.jpg':
            raw_simulated_capture_image = Image.open(simulated_captured_frame_list[frame_to_display])
            if NegativeCaptureActive:
                image_array = np.asarray(raw_simulated_capture_image)
                image_array = np.negative(image_array)
                raw_simulated_capture_image = Image.fromarray(image_array)
            draw_preview_image(raw_simulated_capture_image, 0)

        # Update remaining time
        aux = frames_to_go_str.get()
        if aux.isdigit():
            FramesToGo = int(aux)
            if FramesToGo > 0:
                FramesToGo -= 1
                frames_to_go_str.set(str(FramesToGo))
                SessionData["FramesToGo"] = FramesToGo
                if FramesPerMinute != 0:
                    minutes_pending = FramesToGo // FramesPerMinute
                    time_to_go_str.set(f"Time to go: {(minutes_pending // 60):02} h, {(minutes_pending % 60):02} m")

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
    global last_frame_time

    if ScanOngoing:
        ScanStopRequested = True  # Ending the scan process will be handled in the next (or ongoing) capture loop
    else:
        if BaseDir == CurrentDir or not os.path.isdir(CurrentDir):
            tk.messagebox.showerror("Error!", "Please specify a folder where to store the captured images.")
            return

        Start_btn.config(text="STOP Scan", bg='red', fg='white', relief=SUNKEN)
        SessionData["CurrentDate"] = str(datetime.now())
        SessionData["CurrentDir"] = CurrentDir
        SessionData["CurrentFrame"] = str(CurrentFrame)
        CurrentScanStartTime = datetime.now()
        CurrentScanStartFrame = CurrentFrame

        ScanOngoing = True
        last_frame_time = time.time() + 3

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
            send_arduino_command(CMD_START_SCAN)

        # Invoke capture_loop a first time when scan starts
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
    global FramesPerMinute, FramesToGo, frames_to_go_str, time_to_go_str
    global NewFrameAvailable
    global ScanProcessError, ScanProcessError_LastTime
    global ScanOngoing
    global SimulatedRun
    global ScanStopRequested
    global total_wait_time_autoexp, total_wait_time_awb, total_wait_time_preview_display, session_start_time
    global session_frames, CurrentStill
    global Scanned_Images_fpm

    if ScanStopRequested:
        stop_scan()
        ScanStopRequested = False
        curtime = time.time()
        if ExpertMode and session_frames > 0:
            logging.debug("Total session time: %s seg for %i frames (%i ms per frame)",
                         str(round((curtime-session_start_time),1)),
                         session_frames,
                         round(((curtime-session_start_time)*1000/session_frames),1))
            logging.debug("Total time to display preview image: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_preview_display),1)),
                         round((total_wait_time_preview_display*1000/session_frames),1))
            logging.debug("Total time waiting for AWB adjustment: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_awb),1)),
                         round((total_wait_time_awb*1000/session_frames),1))
            logging.debug("Total time waiting for AE adjustment: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_autoexp),1)),
                         round((total_wait_time_autoexp*1000/session_frames),1))
    elif ScanOngoing:
        if NewFrameAvailable:
            # Update remaining time
            aux = frames_to_go_str.get()
            if aux.isdigit():
                FramesToGo = int(aux)
                if FramesToGo > 0:
                    FramesToGo -= 1
                    frames_to_go_str.set(str(FramesToGo))
                    SessionData["FramesToGo"] = FramesToGo
                    if FramesPerMinute != 0:
                        minutes_pending = FramesToGo // FramesPerMinute
                        time_to_go_str.set(f"Time to go: {(minutes_pending // 60):02} h, {(minutes_pending % 60):02} m")
            CurrentFrame += 1
            session_frames += 1
            register_frame()
            CurrentStill = 1
            capture('normal')
            if not SimulatedRun:
                try:
                    # Set NewFrameAvailable to False here, to avoid overwriting new frame from arduino
                    NewFrameAvailable = False
                    logging.debug("Frame %i captured.", CurrentFrame)
                    send_arduino_command(CMD_GET_NEXT_FRAME)  # Tell Arduino to move to next frame
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


def UpdatePlotterWindow(PTValue):
    global plotter_canvas
    global MaxPT, PrevPTValue
    global plotter_width, plotter_height

    if plotter_canvas == None:
        return

    if PTValue > MaxPT * 10:
        return

    MaxPT = max(MaxPT,PTValue)
    plotter_canvas.create_text(10, 5, text=str(MaxPT), anchor='nw', font=f"Helvetica {8}")
    # Shift the graph to the left
    for item in plotter_canvas.find_all():
        plotter_canvas.move(item, -5, 0)

    # Delete lines moving out of the canvas
    for item in plotter_canvas.find_overlapping(-10,0,0, plotter_height):
        plotter_canvas.delete(item)

    # Draw the new line segment
    plotter_canvas.create_line(plotter_width-6, plotter_height-(PrevPTValue/(MaxPT/plotter_height)), plotter_width-1, plotter_height-(PTValue/(MaxPT/plotter_height)), width=1, fill="blue")

    PrevPTValue = PTValue
    if MaxPT > 100:  # Do not allow below 100
        MaxPT-=1 # Dynamic max


# send_arduino_command: No response expected
def send_arduino_command(cmd, param=0):
    global SimulatedRun, ALT_Scann8_controller_detected
    global i2c

    if not SimulatedRun:
        time.sleep(0.0001)  #wait 100 µs, to avoid I/O errors
        try:
            i2c.write_i2c_block_data(16, cmd, [int(param % 256), int(param >> 8)])  # Send command to Arduino
        except IOError:
            logging.warning("Error while sending command %i (param %i) to Arduino. Retrying...", cmd, param)
            time.sleep(0.2)  #wait 100 µs, to avoid I/O errors
            i2c.write_i2c_block_data(16, cmd, [int(param%256), int(param>>8)])  # Send command to Arduino

        time.sleep(0.0001)  #wait 100 µs, same


def arduino_listen_loop():  # Waits for Arduino communicated events and dispatches accordingly
    global NewFrameAvailable
    global RewindErrorOutstanding, RewindEndOutstanding
    global FastForwardErrorOutstanding, FastForwardEndOutstanding
    global ArduinoTrigger
    global SimulatedRun
    global ScanProcessError
    global ScanOngoing
    global ALT_Scann8_controller_detected
    global last_frame_time
    global pt_level_str, min_frame_steps_str
    global Controller_Id
    global ScanStopRequested
    global i2c

    max_inactivity_delay = 6 if HdrCaptureActive else 3

    if not SimulatedRun:
        try:
            ArduinoData = i2c.read_i2c_block_data(16, CMD_GET_CNT_STATUS, 5)
            ArduinoTrigger = ArduinoData[0]
            ArduinoParam1 = ArduinoData[1] * 256 + ArduinoData[2]
            ArduinoParam2 = ArduinoData[3] * 256 + ArduinoData[4]
        except IOError as e:
            ArduinoTrigger = 0
            # Log error to console
            # When error is 121, not really an error, means Arduino has nothing to data available for us
            if e.errno != 121:
                logging.warning(f"Non-critical IOError ({e}) while checking incoming event from Arduino. Will check again.")

    if ScanOngoing and time.time() > last_frame_time:
        # If scan is ongoing, and more than 3 seconds have passed since last command, maybe one
        # command from/to Arduino (frame received/go to next frame) has been lost.
        # In such case, we force a 'fake' new frame command to allow process to continue
        # This means a duplicate frame might be generated.
        last_frame_time = time.time() + max_inactivity_delay
        NewFrameAvailable = True
        logging.warning("More than %i sec. since last command: Forcing new "
                        "frame event (frame %i).", max_inactivity_delay, CurrentFrame)

    if ArduinoTrigger == 0:  # Do nothing
        pass
    elif ArduinoTrigger == RSP_VERSION_ID:  # New Frame available
        Controller_Id = ArduinoParam1
        if Controller_Id == 1:
            logging.info("Arduino controller detected")
        elif Controller_Id == 2:
            logging.info("Raspberry Pi Pico controller detected")
    elif ArduinoTrigger == RSP_FORCE_INIT:  # Controller reloaded, sent init sequence again
        logging.debug("Controller requested to reinit")
        reinit_controller()
    elif ArduinoTrigger == RSP_FRAME_AVAILABLE:  # New Frame available
        last_frame_time = time.time() + max_inactivity_delay
        NewFrameAvailable = True
    elif ArduinoTrigger == RSP_SCAN_ERROR:  # Error during scan
        logging.warning("Received scan error from Arduino (%i, %i)", ArduinoParam1, ArduinoParam2)
        ScanProcessError = True
    elif ArduinoTrigger == RSP_SCAN_ENDED:  # Scan arrived at the end of the reel
        logging.warning("End of reel reached: Scan terminated")
        ScanStopRequested = True
    elif ArduinoTrigger == RSP_REPORT_AUTO_LEVELS:  # Get auto levels from Arduino, to be displayed in UI, if auto on
        if (PTLevel_auto):
            pt_level_str.set(str(ArduinoParam1))
        if (FrameSteps_auto):
            min_frame_steps_str.set(str(ArduinoParam2))
    elif ArduinoTrigger == RSP_REWIND_ENDED:  # Rewind ended, we can re-enable buttons
        RewindEndOutstanding = True
        logging.debug("Received rewind end event from Arduino")
    elif ArduinoTrigger == RSP_FAST_FORWARD_ENDED:  # FastForward ended, we can re-enable buttons
        FastForwardEndOutstanding = True
        logging.debug("Received fast forward end event from Arduino")
    elif ArduinoTrigger == RSP_REWIND_ERROR:  # Error during Rewind
        RewindErrorOutstanding = True
        logging.warning("Received rewind error from Arduino")
    elif ArduinoTrigger == RSP_FAST_FORWARD_ERROR:  # Error during FastForward
        FastForwardErrorOutstanding = True
        logging.warning("Received fast forward error from Arduino")
    elif ArduinoTrigger == RSP_REPORT_PLOTTER_INFO:  # Integrated plotter info
        if PlotterMode:
            UpdatePlotterWindow(ArduinoParam1)
    else:
        logging.warning("Unrecognized incoming event (%i) from Arduino.", ArduinoTrigger)

    if ArduinoTrigger != 0:
        ArduinoTrigger = 0

    win.after(10, arduino_listen_loop)


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
    global SessionData
    global PostviewModule
    global PreviewWarnAgain
    global TempInFahrenheit
    global temp_in_fahrenheit_checkbox
    global PersistedDataLoaded
    global MatchWaitMargin, match_wait_margin_str
    global SharpnessValue
    global CaptureStabilizationDelay, stabilization_delay_str

    for item in SessionData:
        logging.debug("%s=%s", item, str(SessionData[item]))
    if PersistedDataLoaded:
        logging.debug("SessionData loaded from disk:")
        if 'PreviewWarnAgain' in SessionData:
            PreviewWarnAgain = eval(SessionData["PreviewWarnAgain"])
        if 'TempInFahrenheit' in SessionData:
            TempInFahrenheit = eval(SessionData["TempInFahrenheit"])
            if TempInFahrenheit:
                temp_in_fahrenheit_checkbox.select()
        if ExpertMode:
            if 'MatchWaitMargin' in SessionData:
                MatchWaitMargin = int(SessionData["MatchWaitMargin"])
                match_wait_margin_str.set(str(MatchWaitMargin))
            if 'CaptureStabilizationDelay' in SessionData:
                CaptureStabilizationDelay = float(SessionData["CaptureStabilizationDelay"])
                stabilization_delay_str.set(str(round(CaptureStabilizationDelay * 1000)))

        if ExperimentalMode:
            if 'SharpnessValue' in SessionData:
                SharpnessValue = int(SessionData["SharpnessValue"])
                sharpness_control_spinbox.config(text=str(SharpnessValue))

def arrange_widget_state(auto_state, widget_list):
    for widget in widget_list:
        if isinstance(widget, tk.Button):
            current_text = widget.cget("text")
            new_text = current_text
            if current_text.startswith("AUTO "):
                if not auto_state:
                    new_text = current_text[len("AUTO "):]  # Remove "AUTO " if it's at the beginning
            else:
                if auto_state:
                    new_text = "AUTO " + current_text  # Add "AUTO " if it's not present
            widget.config(text=new_text,
                             relief=SUNKEN if auto_state else RAISED,
                             bg='sea green' if auto_state else save_bg,
                             fg='white' if auto_state else save_fg)
        elif isinstance(widget, tk.Spinbox):
            widget.config(state='readonly' if auto_state else 'normal')
        elif isinstance(widget, tk.Checkbutton):
            if auto_state:
                widget.select()
            else:
                widget.deselect()


def load_session_data():
    global SessionData
    global CurrentExposure, CurrentExposureStr, ExposureAdaptPause
    global CurrentDir
    global CurrentFrame, FramesToGo
    global folder_frame_target_dir
    global NegativeCaptureActive, PosNeg_btn
    global hq_btn, hdr_btn, turbo_btn
    global CurrentAwbAuto, AwbPause, GainRed, GainBlue
    global awb_red_wait_checkbox, awb_blue_wait_checkbox
    global colour_gains_red_value_label, colour_gains_blue_value_label
    global auto_exp_wait_checkbox
    global film_type_R8_btn, film_type_S8_btn
    global PersistedDataLoaded
    global min_frame_steps_str, frame_fine_tune_str, pt_level_str
    global MinFrameSteps, MinFrameStepsS8, MinFrameStepsR8, FrameFineTune, FrameSteps_auto, FrameExtraSteps, frame_extra_steps_str
    global PTLevel, PTLevelS8, PTLevelR8, PTLevel_auto
    global ScanSpeed, scan_speed_str
    global exposure_str
    global wb_red_str, wb_blue_str
    global HqCaptureActive
    global hdr_capture_active_checkbox, HdrCaptureActive
    global hdr_viewx4_active_checkbox, HdrViewX4Active
    global hdr_min_exp, hdr_max_exp, hdr_bracket_width_auto_checkbox
    global hdr_min_exp_str, hdr_max_exp_str, hdr_bracket_width
    global HdrBracketAuto, hdr_bracket_auto, hdr_min_exp, hdr_max_exp, hdr_max_exp_spinbox, hdr_min_exp_spinbox
    global exposure_btn, wb_red_btn, wb_blue_btn, exposure_spinbox, wb_red_spinbox, wb_blue_spinbox
    global frames_to_go_str

    if PersistedDataLoaded:
        confirm = tk.messagebox.askyesno(title='Persisted session data exist',
                                         message='ALT-Scann 8 was interrupted during the last session.\
                                         \r\nDo you want to continue from where it was stopped?')
        if confirm:
            logging.debug("SessionData loaded from disk:")
            if 'CurrentDir' in SessionData:
                CurrentDir = SessionData["CurrentDir"]
                # If directory in configuration does not exist we set the current working dir
                if not os.path.isdir(CurrentDir):
                    CurrentDir = os.getcwd()
                folder_frame_target_dir.config(text=CurrentDir)
            if 'CurrentFrame' in SessionData:
                CurrentFrame = int(SessionData["CurrentFrame"])
                Scanned_Images_number_label.config(text=SessionData["CurrentFrame"])
            if 'FramesToGo' in SessionData:
                FramesToGo = int(SessionData["FramesToGo"])
                frames_to_go_str.set(str(FramesToGo))
            if 'FilmType' in SessionData:
                if SessionData["FilmType"] == "R8":
                    set_r8()
                    film_type_R8_btn.config(relief=SUNKEN)
                    film_type_S8_btn.config(relief=RAISED)
                elif SessionData["FilmType"] == "S8":
                    set_s8()
                    film_type_R8_btn.config(relief=RAISED)
                    film_type_S8_btn.config(relief=SUNKEN)
            if 'NegativeCaptureActive' in SessionData:
                NegativeCaptureActive = eval(SessionData["NegativeCaptureActive"])
                PosNeg_btn.config(text='Positive image' if NegativeCaptureActive else 'Negative image')
            if 'HdrCaptureActive' in SessionData:
                HdrCaptureActive = eval(SessionData["HdrCaptureActive"])
                hdr_set_controls()
                if HdrCaptureActive:
                    hdr_capture_active_checkbox.select()
            if 'HdrViewX4Active' in SessionData:
                HdrViewX4Active = eval(SessionData["HdrViewX4Active"])
                if HdrViewX4Active:
                    hdr_viewx4_active_checkbox.select()
            if 'HdrMinExp' in SessionData:
                hdr_min_exp = SessionData["HdrMinExp"]
                hdr_min_exp_str.set(hdr_min_exp)
            if 'HdrMaxExp' in SessionData:
                hdr_max_exp = SessionData["HdrMaxExp"]
                hdr_max_exp_str.set(hdr_max_exp)
            if ExperimentalMode:
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
                    if CurrentExposureStr == "Auto" or CurrentExposureStr == "0":
                        CurrentExposure = 0
                        CurrentExposureStr == "Auto"
                    else:
                        CurrentExposure = int(float(CurrentExposureStr))
                        CurrentExposureStr = str(round((CurrentExposure - 20000) / 2000))
                    exposure_str = CurrentExposureStr
                if 'ExposureAdaptPause' in SessionData:
                    ExposureAdaptPause = eval(SessionData["ExposureAdaptPause"])
                    auto_exp_wait_checkbox.config(state=NORMAL if CurrentExposure == 0 else DISABLED)
                    if ExposureAdaptPause:
                        auto_exp_wait_checkbox.select()
                if 'CurrentAwbAuto' in SessionData:
                    CurrentAwbAuto = eval(SessionData["CurrentAwbAuto"])
                    #if not CurrentAwbAuto:  # AWB on by default, if not call button to disable and perform needed actions
                    wb_blue_spinbox.config(state='readonly' if CurrentAwbAuto else NORMAL)
                    wb_red_spinbox.config(state='readonly' if CurrentAwbAuto else NORMAL)
                    awb_red_wait_checkbox.config(state=NORMAL if CurrentAwbAuto else DISABLED)
                    awb_blue_wait_checkbox.config(state=NORMAL if CurrentAwbAuto else DISABLED)
                if 'AwbPause' in SessionData:
                    AwbPause = eval(SessionData["AwbPause"])
                    if AwbPause:
                        awb_red_wait_checkbox.select()
                        awb_blue_wait_checkbox.select()
                if 'GainRed' in SessionData:
                    GainRed = float(SessionData["GainRed"])
                    wb_red_str.set(GainRed)
                if 'GainBlue' in SessionData:
                    GainBlue = float(SessionData["GainBlue"])
                    wb_blue_str.set(GainBlue)
                # Recover frame alignment values
                if 'MinFrameSteps' in SessionData:
                    MinFrameSteps = SessionData["MinFrameSteps"]
                    min_frame_steps_str.set(str(MinFrameSteps))
                    send_arduino_command(CMD_SET_MIN_FRAME_STEPS, MinFrameSteps)
                if 'FrameStepsAuto' in SessionData:
                    FrameSteps_auto = SessionData["FrameStepsAuto"]
                    min_frame_steps_str.set(str(MinFrameSteps))
                    if FrameSteps_auto:
                        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0)
                    else:
                        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, MinFrameSteps)
                if 'MinFrameStepsS8' in SessionData:
                    MinFrameStepsS8 = SessionData["MinFrameStepsS8"]
                if 'MinFrameStepsR8' in SessionData:
                    MinFrameStepsR8 = SessionData["MinFrameStepsR8"]
                if 'FrameFineTune' in SessionData:
                    FrameFineTune = SessionData["FrameFineTune"]
                    frame_fine_tune_str.set(str(FrameFineTune))
                    send_arduino_command(CMD_SET_FRAME_FINE_TUNE, FrameFineTune)
                if 'FrameExtraSteps' in SessionData:
                    FrameExtraSteps = SessionData["FrameExtraSteps"]
                    FrameExtraSteps = min(FrameExtraSteps, 20)
                    frame_extra_steps_str.set(str(FrameExtraSteps))
                    send_arduino_command(CMD_SET_EXTRA_STEPS, FrameExtraSteps)
                if 'PTLevelAuto' in SessionData:
                    PTLevel_auto = SessionData["PTLevelAuto"]
                    pt_level_str.set(str(PTLevel))
                    if PTLevel_auto:
                        send_arduino_command(CMD_SET_PT_LEVEL, 0)
                    else:
                        send_arduino_command(CMD_SET_PT_LEVEL, PTLevel)
                if 'PTLevel' in SessionData:
                    PTLevel = SessionData["PTLevel"]
                    if not PTLevel_auto:
                        pt_level_str.set(str(PTLevel))
                        send_arduino_command(CMD_SET_PT_LEVEL, PTLevel)
                if 'PTLevelS8' in SessionData:
                    PTLevelS8 = SessionData["PTLevelS8"]
                if 'PTLevelR8' in SessionData:
                    PTLevelR8 = SessionData["PTLevelR8"]
                if 'ScanSpeed' in SessionData:
                    ScanSpeed = SessionData["ScanSpeed"]
                    scan_speed_str.set(str(ScanSpeed))
                    send_arduino_command(CMD_SET_SCAN_SPEED, ScanSpeed)
                if 'HdrBracketAuto' in SessionData:
                    HdrBracketAuto = SessionData["HdrBracketAuto"]
                    hdr_bracket_auto.set(HdrBracketAuto)
                if 'HdrMinExp' in SessionData:
                    hdr_min_exp = SessionData["HdrMinExp"]
                if 'HdrMaxExp' in SessionData:
                    hdr_max_exp = SessionData["HdrMaxExp"]
                if 'HdrBracketWidth' in SessionData:
                    hdr_bracket_width = SessionData["HdrBracketWidth"]
                    hdr_bracket_width_str.set(str(hdr_bracket_width))

    # Update widget state whether or not config loaded (to honor app default values)
    arrange_widget_state(CurrentExposure == 0, [exposure_btn, exposure_spinbox])
    arrange_widget_state(PTLevel_auto, [pt_level_btn, pt_level_spinbox])
    arrange_widget_state(FrameSteps_auto, [min_frame_steps_btn, min_frame_steps_spinbox])
    hdr_set_controls()
    if HdrCaptureActive:  # If HDR enabled, handle automatic control settings for widgets
        arrange_widget_state(HdrBracketAuto, [hdr_max_exp_spinbox, hdr_min_exp_spinbox])


def reinit_controller():
    global PTLevel_auto, PTLevel
    global FrameSteps_auto, MinFrameSteps
    global FrameFineTune, ScanSpeed, FrameExtraSteps

    if PTLevel_auto:
        send_arduino_command(CMD_SET_PT_LEVEL, 0)
    else:
        send_arduino_command(CMD_SET_PT_LEVEL, PTLevel)

    if FrameSteps_auto:
        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0)
    else:
        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, MinFrameSteps)

    if 'FilmType' in SessionData:
        if SessionData["FilmType"] == "R8":
            send_arduino_command(CMD_SET_REGULAR_8)
        else:
            send_arduino_command(CMD_SET_SUPER_8)

    send_arduino_command(CMD_SET_FRAME_FINE_TUNE, FrameFineTune)
    send_arduino_command(CMD_SET_EXTRA_STEPS, FrameExtraSteps)
    send_arduino_command(CMD_SET_SCAN_SPEED, ScanSpeed)

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
    camera.options['quality'] = 100  # jpeg quality: values from 0 to 100. Reply from David Plowman in PiCam2 list. Test with 60?
    camera.start(show_preview=False)


def hdr_init():
    global hdr_step_value, hdr_exp_list, hdr_rev_exp_list, hdr_min_exp, hdr_max_exp, hdr_num_exposures, hdr_view_4_image

    hdr_view_4_image = Image.new("RGB", (PreviewWidth, PreviewHeight))
    hdr_reinit()

def hdr_reinit():
    global hdr_step_value, hdr_exp_list, hdr_rev_exp_list, hdr_min_exp, hdr_max_exp, hdr_best_exp, hdr_num_exposures, hdr_view_4_image

    if hdr_num_exposures == 3:
        hdr_exp_list.clear()
        hdr_exp_list += [hdr_min_exp, hdr_best_exp, hdr_max_exp]
    elif hdr_num_exposures == 5:
        hdr_exp_list.clear()
        hdr_exp_list += [hdr_min_exp, hdr_min_exp + int((hdr_best_exp-hdr_min_exp)/2), hdr_best_exp, hdr_best_exp + int((hdr_max_exp-hdr_best_exp)/2), hdr_max_exp]

    hdr_exp_list.sort()
    logging.debug("hdr_exp_list=%s",hdr_exp_list)
    hdr_rev_exp_list = list(reversed(hdr_exp_list))


def tscann8_init():
    global win
    global camera
    global CurrentExposure
    global TopWinX
    global TopWinY
    global i2c
    global WinInitDone
    global CurrentDir
    global CurrentFrame
    global ZoomSize
    global capture_config
    global preview_config
    global PreviewWinX, PreviewWinY
    global LogLevel
    global capture_display_queue, capture_display_event
    global capture_save_queue, capture_save_event

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

    logging.info("ALT-Scann8 %s (%s)", __version__, __date__)
    logging.info("Log file: %s", log_file_fullpath)

    if SimulatedRun:
        logging.info("Not running on Raspberry Pi, simulated run for UI debugging purposes only")
    else:
        logging.info("Running on Raspberry Pi")

    # Init HDR variables
    hdr_init()

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
    logging.debug("BaseDir=%s",BaseDir)

    if not SimulatedRun:
        i2c = smbus.SMBus(1)
        # Set the I2C clock frequency to 400 kHz
        i2c.write_byte_data(16, 0x0F, 0x46)  # I2C_SCLL register
        i2c.write_byte_data(16, 0x10, 0x47)  # I2C_SCLH register

    win = tkinter.Tk()  # creating the main window and storing the window object in 'win'
    win.title('ALT-Scann8 v' + __version__)  # setting title of the window
    win.geometry('1100x810')  # setting the size of the window
    win.geometry('+50+50')  # setting the position of the window
    # Prevent window resize
    win.minsize(1100, 810)
    win.maxsize(1100, 810)
    if ExperimentalMode or ExpertMode:
        win.geometry('1100x930')  # setting the size of the window
        win.minsize(1100, 950)
        win.maxsize(1100, 950)

    if SimulatedRun:
        win.wm_title(string='ALT-Scann8 v' + __version__ + ' ***  SIMULATED RUN, NOT OPERATIONAL ***')

    reset_controller()

    get_controller_version()

    send_arduino_command(CMD_REPORT_PLOTTER_INFO, PlotterMode)

    win.update_idletasks()

    # Get Top window coordinates
    TopWinX = win.winfo_x()
    TopWinY = win.winfo_y()

    WinInitDone = True

    if not SimulatedRun and not CameraDisabled:
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
    global exposure_frame
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
    global awb_red_wait_checkbox, awb_blue_wait_checkbox
    global film_hole_frame_1, film_hole_frame_2, FilmHoleY1, FilmHoleY2
    global temp_in_fahrenheit_checkbox
    global rwnd_speed_control_delay
    global match_wait_margin_value
    global sharpness_control_value
    global PiCam2_preview_btn
    global focus_lf_btn, focus_up_btn, focus_dn_btn, focus_rt_btn, focus_plus_btn, focus_minus_btn
    global preview_border_frame
    global draw_capture_label
    global hdr_btn, hq_btn, turbo_btn
    global min_frame_steps_str, frame_fine_tune_str
    global MinFrameSteps
    global pt_level_spinbox, pt_level_str
    global PTLevel
    global min_frame_steps_spinbox, frame_fine_tune_spinbox, pt_level_spinbox
    global frame_extra_steps_spinbox, frame_extra_steps_str
    global scan_speed_str, ScanSpeed, scan_speed_spinbox
    global exposure_spinbox, exposure_str
    global wb_red_spinbox, wb_red_str
    global wb_blue_spinbox, wb_blue_str
    global match_wait_margin_spinbox, match_wait_margin_str
    global stabilization_delay_spinbox, stabilization_delay_str
    global sharpness_control_spinbox, sharpness_control_str
    global rwnd_speed_control_spinbox, rwnd_speed_control_str
    global Manual_scan_activated, ManualScanEnabled, manual_scan_advance_fraction_5_btn, manual_scan_advance_fraction_20_btn, manual_scan_take_snap_btn
    global plotter_canvas
    global hdr_capture_active_checkbox, hdr_capture_active, hdr_viewx4_active
    global hdr_min_exp_str, hdr_max_exp_str
    global hdr_viewx4_active_checkbox, hdr_min_exp_label, hdr_min_exp_spinbox, hdr_max_exp_label, hdr_max_exp_spinbox
    global min_frame_steps_btn, pt_level_btn
    global exposure_btn, wb_red_btn, wb_blue_btn, exposure_spinbox, wb_red_spinbox, wb_blue_spinbox
    global hdr_bracket_width_spinbox, hdr_bracket_width_label, hdr_bracket_width_str, hdr_bracket_width
    global hdr_bracket_auto, hdr_bracket_width_auto_checkbox
    global frames_to_go_str, FramesToGo, time_to_go_str

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
                              activebackground='#f0f0f0', wraplength=80, relief=RAISED)
    AdvanceMovie_btn.pack(side=LEFT, padx=(30, 0), pady=5)
    # Once first button created, get default colors, to revert when we change them
    save_bg = AdvanceMovie_btn['bg']
    save_fg = AdvanceMovie_btn['fg']

    # Frame for single step/snapshot
    sstep_area_frame = Frame(bottom_area_frame, width=50, height=50)
    sstep_area_frame.pack(side=LEFT, padx=(5, 0), pady=5)
    # Advance one single frame
    SingleStep_btn = Button(sstep_area_frame, text="Single Step", width=8, height=1, command=single_step_movie,
                            activebackground='#f0f0f0', wraplength=80)
    SingleStep_btn.pack(side=TOP)
    Snapshot_btn = Button(sstep_area_frame, text="Snapshot", width=8, height=1, command=capture_single_step,
                            activebackground='#f0f0f0', wraplength=80)
    Snapshot_btn.pack(side=TOP)

    # Rewind movie (via upper path, outside of film gate)
    Rewind_btn = Button(bottom_area_frame, text="<<", font=("Arial", 16), width=2, height=2, command=rewind_movie,
                        activebackground='#f0f0f0', wraplength=80, relief=RAISED)
    Rewind_btn.pack(side=LEFT, padx=(5, 0), pady=5)
    # Fast Forward movie (via upper path, outside of film gate)
    FastForward_btn = Button(bottom_area_frame, text=">>", font=("Arial", 16), width=2, height=2, command=fast_forward_movie,
                             activebackground='#f0f0f0', wraplength=80, relief=RAISED)
    FastForward_btn.pack(side=LEFT, padx=(5, 0), pady=5)

    # Unlock reels button (to load film, rewind, etc)
    Free_btn = Button(bottom_area_frame, text="Unlock Reels", width=8, height=3, command=set_free_mode, activebackground='#f0f0f0',
                      wraplength=80, relief=RAISED)
    Free_btn.pack(side=LEFT, padx=(5, 0), pady=5)

    # Switch Positive/negative modes
    PosNeg_btn = Button(bottom_area_frame, text="Negative image", width=8, height=3, command=switch_negative_capture,
                        activebackground='#f0f0f0', wraplength=80, relief=RAISED)
    PosNeg_btn.pack(side=LEFT, padx=(5, 0), pady=5)

    if ExperimentalMode:
        # Switch HD mode on/off (Capture with sensor in 4056x3040, still delivering 2025x1520, but better quality)
        hq_btn = Button(bottom_area_frame, text="HQ On", width=8, height=3, command=switch_hq_capture,
                            activebackground='#f0f0f0', wraplength=80, relief=RAISED)
        hq_btn.pack(side=LEFT, padx=(5, 0), pady=5)

        # Switch VideoCaptureActive mode on/off (Capture video Configuration)
        turbo_btn = Button(bottom_area_frame, text="Turbo On", width=8, height=3, command=switch_turbo_capture,
                            activebackground='#f0f0f0', wraplength=80, relief=RAISED)
        turbo_btn.pack(side=LEFT, padx=(5, 0), pady=5)

    # Pi Camera preview selection: Preview (by PiCamera), disabled, postview (display last captured frame))
    PiCam2_preview_btn = Button(bottom_area_frame, text="Real Time display ON", width=8, height=3, command=PiCamera2_preview,
                       activebackground='#f0f0f0', wraplength=80, relief=RAISED)
    PiCam2_preview_btn.pack(side=LEFT, padx=(5, 0), pady=5)

    # Activate focus zoom, to facilitate focusing the camera
    Focus_btn = Button(bottom_area_frame, text="Focus Zoom ON", width=8, height=3, command=set_focus_zoom,
                       activebackground='#f0f0f0', wraplength=80, relief=RAISED)
    Focus_btn.config(state=DISABLED)
    Focus_btn.pack(side=LEFT, padx=(5, 0), pady=5)

    # Focus zoom control (in out, up, down, left, right)
    Focus_frame = LabelFrame(bottom_area_frame, text='Focus control', width=12, height=3, font=("Arial", 7))
    Focus_frame.pack(side=LEFT, padx=2)

    Focus_btn_grid_frame = Frame(Focus_frame, width=10, height=10)
    Focus_btn_grid_frame.pack(side=LEFT)

    # focus zoom displacement buttons, to further facilitate focusing the camera
    focus_plus_btn = Button(Focus_btn_grid_frame, text="+", width=1, height=1, command=set_focus_plus,
                            activebackground='#f0f0f0', state=DISABLED, font=("Arial", 7))
    focus_plus_btn.grid(row=0, column=2)
    focus_minus_btn = Button(Focus_btn_grid_frame, text="-", width=1, height=1, command=set_focus_minus,
                             activebackground='#f0f0f0', state=DISABLED, font=("Arial", 7))
    focus_minus_btn.grid(row=0, column=0)
    focus_lf_btn = Button(Focus_btn_grid_frame, text="←", width=1, height=1, command=set_focus_left,
                          activebackground='#f0f0f0', state=DISABLED, font=("Arial", 7))
    focus_lf_btn.grid(row=1, column=0)
    focus_up_btn = Button(Focus_btn_grid_frame, text="↑", width=1, height=1, command=set_focus_up,
                          activebackground='#f0f0f0', state=DISABLED, font=("Arial", 7))
    focus_up_btn.grid(row=0, column=1)
    focus_dn_btn = Button(Focus_btn_grid_frame, text="↓", width=1, height=1, command=set_focus_down,
                          activebackground='#f0f0f0', state=DISABLED, font=("Arial", 7))
    focus_dn_btn.grid(row=1, column=1)
    focus_rt_btn = Button(Focus_btn_grid_frame, text="→", width=1, height=1, command=set_focus_right,
                          activebackground='#f0f0f0', state=DISABLED, font=("Arial", 7))
    focus_rt_btn.grid(row=1, column=2)

    # Create vertical button column at right *************************************
    # Start scan button
    if SimulatedRun:
        Start_btn = Button(top_right_area_frame, text="START Scan", width=14, height=5, command=start_scan_simulated,
                           activebackground='#f0f0f0', wraplength=80)
    else:
        Start_btn = Button(top_right_area_frame, text="START Scan", width=14, height=5, command=start_scan,
                           activebackground='#f0f0f0', wraplength=80)
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
                            activebackground='#f0f0f0', wraplength=80, font=("Arial", 10))
    new_folder_btn.pack(side=LEFT)
    existing_folder_btn = Button(folder_frame_buttons, text='Existing', width=5, height=1, command=set_existing_folder,
                                 activebackground='#f0f0f0', wraplength=80, font=("Arial", 10))
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

    # Create frame to display number of frames to go, and estimated time to finish
    frames_to_go_frame = LabelFrame(top_right_area_frame, text='Frames to go', width=16, height=4)
    frames_to_go_frame.pack(side=TOP, padx=(5, 0), pady=(5, 0))
    frames_to_go_str = tk.StringVar(value=str(FramesToGo))
    frames_to_go_entry = tk.Entry(frames_to_go_frame,textvariable=frames_to_go_str, width=8, font=("Arial", 8))
    frames_to_go_entry.pack(side=TOP, padx=(5, 0), pady=(5, 5))
    time_to_go_str = tk.StringVar(value='')
    time_to_go_time = Label(frames_to_go_frame, textvariable=time_to_go_str, font=("Arial", 8), width=22, height=1)
    time_to_go_time.pack(side=TOP)

    # Create frame to select S8/R8 film
    film_type_frame = LabelFrame(top_right_area_frame, text='Film type', width=16, height=1)
    film_type_frame.pack(side=TOP, padx=(5, 0), pady=(5, 0))

    film_type_buttons = Frame(film_type_frame, width=16, height=1)
    film_type_buttons.pack(side=TOP, padx=4, pady=5)
    film_type_S8_btn = Button(film_type_buttons, text='S8', width=3, height=1, font=("Arial", 16, 'bold'),
                              command=set_s8, activebackground='#f0f0f0',
                              relief=SUNKEN)
    film_type_S8_btn.pack(side=LEFT)
    film_type_R8_btn = Button(film_type_buttons, text='R8', width=3, height=1, font=("Arial", 16, 'bold'),
                              command=set_r8, activebackground='#f0f0f0')
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


    # Create extended frame for expert and experimental areas
    if ExpertMode or ExperimentalMode:
        extended_frame = Frame(win)
        #extended_frame.place(x=30, y=790)
        extended_frame.pack(side=TOP, anchor=W, padx=(30, 0))
    if ExpertMode:
        expert_frame = LabelFrame(extended_frame, text='Expert Area', width=8, height=5, font=("Arial", 7))
        expert_frame.pack(side=LEFT, padx=2, pady=2)

        # Exposure / white balance
        exp_wb_frame = LabelFrame(expert_frame, text='Auto Exposure / White Balance ', pady=11,
                                    width=16, height=2, font=("Arial", 7))
        ### exp_wb_frame.pack(side=LEFT, padx=5, pady=5)
        exp_wb_frame.grid(row=0, rowspan=2, column=0, padx=4, pady=4, sticky=N)

        catch_up_delay_label = tk.Label(exp_wb_frame,
                                         text='Catch-up\ndelay',
                                         width=10, font=("Arial", 7))
        catch_up_delay_label.grid(row=0, column=2, padx=2, pady=1)
        exposure_btn = Button(exp_wb_frame, text="Exposure:", width=12, height=1,
                                                    command=exposure_spinbox_auto,
                                                    activebackground='#f0f0f0',
                                                    state=NORMAL, font=("Arial", 7))
        exposure_btn.grid(row=1, column=0, padx=2, pady=1, sticky=E)

        exposure_str = tk.StringVar(value=str(CurrentExposure))

        exposure_selection_aux = exp_wb_frame.register(exposure_selection)
        exposure_spinbox = tk.Spinbox(
            exp_wb_frame,
            command=(exposure_selection_aux, '%d'), width=8,
            textvariable=exposure_str, from_=-100, to=100, font=("Arial", 7))
        exposure_spinbox.grid(row=1, column=1, padx=2, pady=1, sticky=W)

        auto_exposure_change_pause = tk.BooleanVar(value=ExposureAdaptPause)
        auto_exp_wait_checkbox = tk.Checkbutton(exp_wb_frame, text='', height=1, state=DISABLED,
                                                variable=auto_exposure_change_pause, onvalue=True, offvalue=False,
                                                command=auto_exposure_change_pause_selection, font=("Arial", 7))
        auto_exp_wait_checkbox.grid(row=1, column=2, padx=2, pady=1)
        arrange_widget_state(CurrentExposure == 0, [exposure_btn, exposure_spinbox])

        # Automatic White Balance
        wb_red_btn = Button(exp_wb_frame, text="AWB Red:", width=12, height=1,
                                                    command=wb_spinbox_auto,
                                                    activebackground='#f0f0f0',
                                                    state=NORMAL, font=("Arial", 7))
        wb_red_btn.grid(row=2, column=0, padx=2, pady=1, sticky=E)
        wb_red_str = tk.StringVar(value=str(GainRed))

        wb_red_selection_aux = exp_wb_frame.register(wb_red_selection)
        wb_red_spinbox = tk.Spinbox(
            exp_wb_frame,
            command=(wb_red_selection_aux, '%d'), width=8,
            textvariable=wb_red_str, from_=-9.9, to=9.9, increment=0.1, font=("Arial", 7))
        wb_red_spinbox.grid(row=2, column=1, padx=2, pady=1, sticky=W)

        wb_blue_btn = Button(exp_wb_frame, text="AWB Blue:", width=12, height=1,
                                                    command=wb_spinbox_auto,
                                                    activebackground='#f0f0f0',
                                                    state=NORMAL, font=("Arial", 7))
        wb_blue_btn.grid(row=3, column=0, padx=2, pady=1, sticky=E)
        wb_blue_str = tk.StringVar(value=str(GainBlue))

        wb_blue_selection_aux = exp_wb_frame.register(wb_blue_selection)
        wb_blue_spinbox = tk.Spinbox(
            exp_wb_frame,
            command=(wb_blue_selection_aux, '%d'), width=8,
            textvariable=wb_blue_str, from_=-9.9, to=9.9, increment=0.1, font=("Arial", 7))
        wb_blue_spinbox.grid(row=3, column=1, padx=2, pady=1, sticky=W)

        auto_white_balance_change_pause = tk.BooleanVar(value=AwbPause)
        awb_red_wait_checkbox = tk.Checkbutton(exp_wb_frame, text='', height=1, state=DISABLED,
                                                variable=auto_white_balance_change_pause, onvalue=True, offvalue=False,
                                                command=auto_white_balance_change_pause_selection, font=("Arial", 7))
        awb_red_wait_checkbox.grid(row=2, column=2, padx=2, pady=1)
        awb_blue_wait_checkbox = tk.Checkbutton(exp_wb_frame, text='', height=1, state=DISABLED,
                                                variable=auto_white_balance_change_pause, onvalue=True, offvalue=False,
                                                command=auto_white_balance_change_pause_selection, font=("Arial", 7))
        awb_blue_wait_checkbox.grid(row=3, column=2, padx=2, pady=1)

        # Match wait (exposure & AWB) margin allowance (0%, wait for same value, 100%, any value will do)
        match_wait_margin_label = tk.Label(exp_wb_frame,
                                         text='Match margin (%):',
                                         width=14, font=("Arial", 7))
        match_wait_margin_label.grid(row=4, column=0, padx=2, pady=1, sticky=E)

        match_wait_margin_str = tk.StringVar(value=str(MatchWaitMargin))

        match_wait_margin_selection_aux = exp_wb_frame.register(match_wait_margin_selection)
        match_wait_margin_spinbox = tk.Spinbox(
            exp_wb_frame,
            command=(match_wait_margin_selection_aux, '%d'), width=8,
            textvariable=match_wait_margin_str, from_=0, to=100, increment=5, font=("Arial", 7))
        match_wait_margin_spinbox.grid(row=4, column=1, padx=2, pady=1, sticky=W)

        # Display markers for film hole reference
        film_hole_frame_1 = Frame(win, width=1, height=1, bg='black')
        film_hole_frame_1.pack(side=TOP, padx=1, pady=1)
        film_hole_frame_1.place(x=4, y=FilmHoleY1, height=140)
        film_hole_label_1 = Label(film_hole_frame_1, justify=LEFT, font=("Arial", 8), width=5, height=11,
                                bg='white', fg='white')
        film_hole_label_1.pack(side=TOP)

        film_hole_frame_2 = Frame(win, width=1, height=1, bg='black')
        film_hole_frame_2.pack(side=TOP, padx=1, pady=1)
        film_hole_frame_2.place(x=4, y=FilmHoleY2, height=140)
        film_hole_label_2 = Label(film_hole_frame_2, justify=LEFT, font=("Arial", 8), width=5, height=11,
                                bg='white', fg='white')
        film_hole_label_2.pack(side=TOP)

        # Frame to add frame align controls
        frame_alignment_frame = LabelFrame(expert_frame, text="Frame align", width=16, height=2,
                                           font=("Arial", 7))
        frame_alignment_frame.grid(row=0, rowspan=2, column=2, padx=4, pady=4, sticky=NW)
        # Spinbox to select MinFrameSteps on Arduino
        min_frame_steps_btn = Button(frame_alignment_frame, text="Steps/frame:", width=12, height=1,
                                                    command=min_frame_steps_spinbox_auto,
                                                    activebackground='#f0f0f0',
                                                    state=NORMAL, font=("Arial", 7))
        min_frame_steps_btn.grid(row=0, column=0, padx=2, pady=3, sticky=E)
        min_frame_steps_str = tk.StringVar(value=str(MinFrameSteps))
        min_frame_steps_selection_aux = frame_alignment_frame.register(
            min_frame_steps_selection)
        min_frame_steps_spinbox = tk.Spinbox(
            frame_alignment_frame,
            command=(min_frame_steps_selection_aux, '%d'), width=8,
            textvariable=min_frame_steps_str, from_=100, to=600, font=("Arial", 7))
        min_frame_steps_spinbox.grid(row=0, column=1, padx=2, pady=3, sticky=W)
        min_frame_steps_spinbox.bind("<FocusOut>", min_frame_steps_spinbox_focus_out)
        # Spinbox to select PTLevel on Arduino
        pt_level_btn = Button(frame_alignment_frame, text="PT Level:", width=12, height=1,
                                                    command=pt_level_spinbox_auto,
                                                    activebackground='#f0f0f0',
                                                    state=NORMAL, font=("Arial", 7))
        pt_level_btn.grid(row=1, column=0, padx=2, pady=3, sticky=E)
        pt_level_str = tk.StringVar(value=str(PTLevel))
        pt_level_selection_aux = frame_alignment_frame.register(
            pt_level_selection)
        pt_level_spinbox = tk.Spinbox(
            frame_alignment_frame,
            command=(pt_level_selection_aux, '%d'), width=8,
            textvariable=pt_level_str, from_=0, to=900, font=("Arial", 7))
        pt_level_spinbox.grid(row=1, column=1, padx=2, pady=3, sticky=W)
        pt_level_spinbox.bind("<FocusOut>", pt_level_spinbox_focus_out)
        # Spinbox to select FrameFineTune on Arduino
        frame_fine_tune_label = tk.Label(frame_alignment_frame,
                                         text='Fine tune:',
                                         width=10, font=("Arial", 7))
        frame_fine_tune_label.grid(row=2, column=0, padx=2, pady=3, sticky=E)
        frame_fine_tune_str = tk.StringVar(value=str(FrameFineTune))
        frame_fine_tune_selection_aux = frame_alignment_frame.register(
            frame_fine_tune_selection)
        frame_fine_tune_spinbox = tk.Spinbox(
            frame_alignment_frame,
            command=(frame_fine_tune_selection_aux, '%d'), width=8,
            textvariable=frame_fine_tune_str, from_=5, to=95, increment=5, font=("Arial", 7))
        frame_fine_tune_spinbox.grid(row=2, column=1, padx=2, pady=3, sticky=W)
        frame_fine_tune_spinbox.bind("<FocusOut>", frame_fine_tune_spinbox_focus_out)
        # Spinbox to select Extra Steps on Arduino
        frame_extra_steps_label = tk.Label(frame_alignment_frame,
                                         text='Extra Steps:',
                                         width=10, font=("Arial", 7))
        frame_extra_steps_label.grid(row=3, column=0, padx=2, pady=3, sticky=E)
        frame_extra_steps_str = tk.StringVar(value=str(FrameExtraSteps))
        frame_extra_steps_selection_aux = frame_alignment_frame.register(
            frame_extra_steps_selection)
        frame_extra_steps_spinbox = tk.Spinbox(
            frame_alignment_frame,
            command=(frame_extra_steps_selection_aux, '%d'), width=8,
            textvariable=frame_extra_steps_str, from_=0, to=20, font=("Arial", 7))
        frame_extra_steps_spinbox.grid(row=3, column=1, padx=2, pady=3, sticky=W)
        frame_extra_steps_spinbox.bind("<FocusOut>", frame_extra_steps_spinbox_focus_out)

        # Frame to add scan speed control
        speed_quality_frame = LabelFrame(expert_frame, text="Scan speed / Stabilization delay", width=18, height=2,
                                           font=("Arial", 7))
        ### speed_quality_frame.pack(side=LEFT, padx=5)
        speed_quality_frame.grid(row=1, column=1, columnspan=2, padx=4, pady=4, sticky=W)

        # Spinbox to select Speed on Arduino (1-10)
        scan_speed_label = tk.Label(speed_quality_frame,
                                         text='Speed:',
                                         width=7, font=("Arial", 7))
        scan_speed_label.pack(side=LEFT, padx=4)
        scan_speed_str = tk.StringVar(value=str(ScanSpeed))
        scan_speed_selection_aux = speed_quality_frame.register(
            scan_speed_selection)
        scan_speed_spinbox = tk.Spinbox(
            speed_quality_frame,
            command=(scan_speed_selection_aux, '%d'), width=3,
            textvariable=scan_speed_str, from_=1, to=10, font=("Arial", 7))
        scan_speed_spinbox.pack(side=LEFT, padx=4)
        scan_speed_spinbox.bind("<FocusOut>", scan_speed_spinbox_focus_out)
        scan_speed_selection('down')

        # Display entry to adjust capture stabilization delay (100 ms by default)
        stabilization_delay_label = tk.Label(speed_quality_frame,
                                         text='Delay (ms):',
                                         width=10, font=("Arial", 7))
        stabilization_delay_label.pack(side=LEFT, padx=4)
        stabilization_delay_str = tk.StringVar(value=str(round(CaptureStabilizationDelay*1000)))
        stabilization_delay_selection_aux = speed_quality_frame.register(
            stabilization_delay_selection)
        stabilization_delay_spinbox = tk.Spinbox(
            speed_quality_frame,
            command=(stabilization_delay_selection_aux, '%d'), width=4,
            textvariable=stabilization_delay_str, from_=0, to=1000, increment=10, font=("Arial", 7))
        stabilization_delay_spinbox.pack(side=LEFT, padx=4)
        stabilization_delay_spinbox.bind("<FocusOut>", stabilization_delay_spinbox_focus_out)

        # Frame to add HDR controls (on/off, exp. bracket, position, auto-adjust)
        hdr_frame = LabelFrame(expert_frame, text="Multi-exposure fusion", width=18, height=2, pady=7,
                                           font=("Arial", 7))
        hdr_frame.grid(row=0, column=1, padx=4, pady=4, sticky=N)
        hdr_capture_active = tk.BooleanVar(value=HdrCaptureActive)
        hdr_capture_active_checkbox = tk.Checkbutton(hdr_frame, text=' Active', height=1, width=6,
                                                     variable=hdr_capture_active, onvalue=True, offvalue=False,
                                                     command=switch_hdr_capture, font=("Arial", 7))
        hdr_capture_active_checkbox.grid(row=0, column=0, padx=2, pady=1)
        hdr_viewx4_active = tk.BooleanVar(value=HdrViewX4Active)
        hdr_viewx4_active_checkbox = tk.Checkbutton(hdr_frame, text=' View X4', height=1, width=7,
                                                     variable=hdr_viewx4_active, onvalue=True, offvalue=False,
                                                     command=switch_hdr_viewx4, font=("Arial", 7), state=DISABLED)
        hdr_viewx4_active_checkbox.grid(row=0, column=1, padx=2, pady=1)

        hdr_min_exp_label = tk.Label(hdr_frame, text='Lower exp. (ms):', width=16, font=("Arial", 7), state=DISABLED)
        hdr_min_exp_label.grid(row=1, column=0, padx=2, pady=1, sticky=E)
        hdr_min_exp_str = tk.StringVar(value=str(hdr_min_exp))
        hdr_min_exp_spinbox = tk.Spinbox(hdr_frame, command=(hdr_check_min_exp, '%d'), width=8,
            textvariable=hdr_min_exp_str, from_=hdr_lower_exp, to=999, increment=1, font=("Arial", 7), state=DISABLED)
        hdr_min_exp_spinbox.grid(row=1, column=1, padx=2, pady=1, sticky=W)
        hdr_min_exp_spinbox.bind("<FocusOut>", hdr_check_min_exp)

        hdr_max_exp_label = tk.Label(hdr_frame, text='Higher exp. (ms):', width=16, font=("Arial", 7), state=DISABLED)
        hdr_max_exp_label.grid(row=2, column=0, padx=2, pady=1, sticky=E)
        hdr_max_exp_str = tk.StringVar(value=str(hdr_max_exp))
        hdr_max_exp_spinbox = tk.Spinbox(hdr_frame, command=(hdr_check_max_exp, '%d'), width=8,
            textvariable=hdr_max_exp_str, from_=2, to=1000, increment=1, font=("Arial", 7), state=DISABLED)
        hdr_max_exp_spinbox.grid(row=2, column=1, padx=2, pady=1, sticky=W)
        hdr_max_exp_spinbox.bind("<FocusOut>", hdr_check_max_exp)

        hdr_bracket_width_label = tk.Label(hdr_frame, text='Bracket width (ms):', width=16, font=("Arial", 7), state=DISABLED)
        hdr_bracket_width_label.grid(row=3, column=0, padx=2, pady=1, sticky=E)
        hdr_bracket_width_str = tk.StringVar(value=str(hdr_bracket_width))
        hdr_bracket_width_spinbox = tk.Spinbox(hdr_frame, command=(hdr_check_bracket_width, '%d'), width=8,
            textvariable=hdr_bracket_width_str, from_=4, to=200, increment=1, font=("Arial", 7), state=DISABLED)
        hdr_bracket_width_spinbox.grid(row=3, column=1, padx=2, pady=1, sticky=W)
        hdr_bracket_width_spinbox.bind("<FocusOut>", hdr_check_bracket_width)

        hdr_bracket_auto = tk.BooleanVar(value=HdrBracketAuto)
        hdr_bracket_width_auto_checkbox = tk.Checkbutton(hdr_frame, text=' Auto bracket', width=10, height=1,
                                              variable=hdr_bracket_auto, onvalue=True, offvalue=False,
                                              command=adjust_hdr_bracket_auto, font=("Arial", 7))
        hdr_bracket_width_auto_checkbox.grid(row=4, column=0, padx=2, pady=1, sticky=W)

        # Integrated plotter
        if PlotterMode:
            integrated_plotter_frame = LabelFrame(extended_frame, text='Plotter Area', width=8, height=5, font=("Arial", 7))
            integrated_plotter_frame.pack(side=LEFT, ipadx=5, fill=Y, padx=2, pady=2)
            plotter_canvas = Canvas(integrated_plotter_frame, bg='white',
                                         width=plotter_width, height=plotter_height)
            plotter_canvas.pack(side=TOP, anchor=N)

        if ExperimentalMode:
            experimental_frame = LabelFrame(extended_frame, text='Experimental Area', width=8, height=5, font=("Arial", 7))
            experimental_frame.pack(side=LEFT, ipadx=5, fill=Y, padx=2, pady=2)

            # Sharpness, control to allow playing with the values and see the results
            sharpness_control_label = tk.Label(experimental_frame,
                                                 text='Sharpness:',
                                                 width=20, font=("Arial", 7))
            sharpness_control_label.grid(row=0, column=0, padx=2, pady=1, sticky=E)
            sharpness_control_str = tk.StringVar(value=str(SharpnessValue))
            sharpness_control_selection_aux = experimental_frame.register(
                sharpness_control_selection)
            sharpness_control_spinbox = tk.Spinbox(
                experimental_frame,
                command=(sharpness_control_selection_aux, '%d'), width=8,
                textvariable=sharpness_control_str, from_=0, to=16, increment=1, font=("Arial", 7))
            sharpness_control_spinbox.grid(row=0, column=1, padx=2, pady=1, sticky=W)
            sharpness_control_spinbox.bind("<FocusOut>", sharpness_control_spinbox_focus_out)

            # Display entry to throttle Rwnd/FF speed
            rwnd_speed_control_label = tk.Label(experimental_frame,
                                                 text='RW/FF speed rpm):',
                                                 width=20, font=("Arial", 7))
            rwnd_speed_control_label.grid(row=1, column=0, padx=2, pady=1, sticky=E)
            rwnd_speed_control_str = tk.StringVar(value=str(round(60 / (rwnd_speed_delay * 375 / 1000000))))

            rwnd_speed_control_selection_aux = experimental_frame.register(
                rwnd_speed_control_selection)
            rwnd_speed_control_spinbox = tk.Spinbox(
                experimental_frame, state='readonly',
                command=(rwnd_speed_control_selection_aux, '%d'), width=8,
                textvariable=rwnd_speed_control_str, from_=40, to=800, increment=50, font=("Arial", 7))
            rwnd_speed_control_spinbox.grid(row=1, column=1, padx=2, pady=1, sticky=W)

            # Damaged film helpers, to help handling damaged film (broken perforations)
            Damaged_film_frame = LabelFrame(experimental_frame, text='Damaged film', width=18, height=3, font=("Arial", 7))
            Damaged_film_frame.grid(row=2, column=0, columnspan=2, padx=4, pady=4, sticky='')
            # Checkbox to enable/disable manual scan
            Manual_scan_activated = tk.BooleanVar(value=ManualScanEnabled)
            Manual_scan_checkbox = tk.Checkbutton(Damaged_film_frame, text='Enable manual scan', width=20, height=1,
                                                   variable=Manual_scan_activated, onvalue=True,
                                                   offvalue=False,
                                                   command=Manual_scan_activated_selection, font=("Arial", 7))
            Manual_scan_checkbox.pack(side=TOP)
            # Common area for buttons
            Manual_scan_btn_frame = Frame(Damaged_film_frame, width=18, height=2)
            Manual_scan_btn_frame.pack(side=TOP)

            # Manual scan buttons
            manual_scan_advance_fraction_5_btn = Button(Manual_scan_btn_frame, text="+5", width=1, height=1, command=manual_scan_advance_frame_fraction_5,
                                    state=DISABLED, font=("Arial", 7))
            manual_scan_advance_fraction_5_btn.pack(side=LEFT, ipadx=5, fill=Y)
            manual_scan_advance_fraction_20_btn = Button(Manual_scan_btn_frame, text="+20", width=1, height=1, command=manual_scan_advance_frame_fraction_20,
                                    state=DISABLED, font=("Arial", 7))
            manual_scan_advance_fraction_20_btn.pack(side=LEFT, ipadx=5, fill=Y)
            manual_scan_take_snap_btn = Button(Manual_scan_btn_frame, text="Snap", width=1, height=1, command=manual_scan_take_snap,
                                     state=DISABLED, font=("Arial", 7))
            manual_scan_take_snap_btn.pack(side=RIGHT, ipadx=5, fill=Y)


def get_controller_version():
    global Controller_Id
    if Controller_Id == 0:
        logging.debug("Requesting controller version")
        send_arduino_command(CMD_VERSION_ID)

def reset_controller():
    logging.debug("Resetting controller")
    send_arduino_command(CMD_RESET_CONTROLLER)
    time.sleep(0.5)


def main(argv):
    global SimulatedRun
    global ExpertMode, ExperimentalMode, PlotterMode
    global LogLevel, LoggingMode
    global capture_display_event, capture_save_event
    global capture_display_queue, capture_save_queue
    global ALT_scann_init_done
    global CameraDisabled

    opts, args = getopt.getopt(argv, "sexl:ph")

    for opt, arg in opts:
        if opt == '-s':
            SimulatedRun = True
        elif opt == '-e':
            ExpertMode = True
        elif opt == '-x':
            ExperimentalMode = True
        elif opt == '-d':
            CameraDisabled = True
        elif opt == '-l':
            LoggingMode = arg
        elif opt == '-h':
            print("ALT-Scann 8 Command line parameters")
            print("  -s             Start Simulated session")
            print("  -e             Activate expert mode")
            print("  -x             Activate experimental mode")
            print("  -p             Activate integratted plotter")
            print("  -d             Disable camera (for development purposes)")
            print("  -l <log mode>  Set log level (standard Python values (DEBUG, INFO, WARNING, ERROR)")
            exit()
        elif opt == '-p':
            PlotterMode = True

    ExpertMode = True   # Expert mode becomes default
    LogLevel = getattr(logging, LoggingMode.upper(), None)
    if not isinstance(LogLevel, int):
        raise ValueError('Invalid log level: %s' % LogLevel)

    ALT_scann_init_done = False

    tscann8_init()

    if not SimulatedRun:
        arduino_listen_loop()

    build_ui()

    load_persisted_data_from_disk()     # Read json file in memory, to be processed by 'load_session_data'

    load_config_data()
    load_session_data()

    ALT_scann_init_done = True

    temperature_loop()

    # Main Loop
    win.mainloop()  # running3 the loop that works as a trigger

    if not SimulatedRun and not CameraDisabled:
        capture_display_event.set()
        capture_save_event.set()
        capture_display_queue.put(END_TOKEN)
        capture_save_queue.put(END_TOKEN)
        capture_save_queue.put(END_TOKEN)
        capture_save_queue.put(END_TOKEN)

    if not SimulatedRun and not CameraDisabled:
        camera.close()


if __name__ == '__main__':
    main(sys.argv[1:])

