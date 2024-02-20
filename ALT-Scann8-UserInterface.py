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
__copyright__ = "Copyright 2022-24, Juan Remirez de Esparza"
__credits__ = ["Juan Remirez de Esparza"]
__license__ = "MIT"
__module__ = "ALT-Scann8"
__version__ = "1.9.34"
__date__ = "2024-02-20"
__version_highlight__ = "Save frames using PiCamera2 method whenever possible"
__maintainer__ = "Juan Remirez de Esparza"
__email__ = "jremirez@hotmail.com"
__status__ = "Development"

# ######### Imports section ##########
import tkinter as tk
from tkinter import filedialog

import tkinter.messagebox
import tkinter.simpledialog
from tkinter import DISABLED, NORMAL, LEFT, RIGHT, Y, TOP, BOTTOM, N, W, E, NW, RAISED, SUNKEN
from tkinter import Label, Button, Frame, LabelFrame, Canvas, OptionMenu

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
    import psutil
    check_disk_space = True
except ImportError:
    check_disk_space = False

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
import cv2

from camera_resolutions import CameraResolutions
from dynamic_spinbox import DynamicSpinbox
from tooltip import Tooltips
from rolling_average import RollingAverage

#  ######### Global variable definition (I know, too many...) ##########
win = None
as_tooltips = None
ExitingApp = False
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
FrameFilenamePattern = "picture-%05d.%s"
HdrFrameFilenamePattern = "picture-%05d.%1d.%s"   # HDR frames using standard filename (2/12/2023)
StillFrameFilenamePattern = "still-picture-%05d-%02d.jpg"
CurrentFrame = 0  # bild in original code from Torulf
frames_to_go_key_press_time = 0
CurrentStill = 1  # used to take several stills of same frame, for settings analysis
CurrentScanStartTime = datetime.now()
CurrentScanStartFrame = 0
HdrCaptureActive = False
AdvanceMovieActive = False
RetreatMovieActive = False
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
# Directory where python scrips run, to store the json file with persistent data
ScriptDir = os.path.dirname(__file__)
PersistedDataFilename = os.path.join(ScriptDir, "ALT-Scann8.json")
PersistedDataLoaded = False
# Variables to deal with remaining disk space
available_space_mb = 0
disk_space_error_to_notify = False

ArduinoTrigger = 0
last_frame_time = 0
reference_inactivity_delay = 6    # Max time (in sec) we wait for next frame. If expired, we force next frame again
max_inactivity_delay = reference_inactivity_delay
# Minimum number of steps per frame, to be passed to Arduino
MinFrameStepsS8 = 290
MinFrameStepsR8 = 240
# Phototransistor reported level when hole is detected
PTLevelS8 = 80
PTLevelR8 = 120
# Tokens identify type of elements in queues
# Token to be inserted in each queue on program closure, to allow threads to shut down cleanly
active_threads = 0
num_threads = 0
END_TOKEN = "TERMINATE_PROCESS"  # Sent on program closure, to allow threads to shut down cleanly
IMAGE_TOKEN = "IMAGE_TOKEN"  # Queue element is an image
REQUEST_TOKEN = "REQUEST_TOKEN"  # Queue element is a PiCamera2 request
MaxQueueSize = 16
DisableThreads = False
FrameArrivalTime = 0
# Ids to allow cancelling afters on exit
onesec_after = 0
arduino_after = 0
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
BigSize = True
ForceSmallSize = False
ForceBigSize = False
FolderProcess = 0
LoggingMode = "INFO"
LogLevel = 0
draw_capture_canvas = 0
button_lock_counter = 0

PiCam2PreviewEnabled=False
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
simulated_capture_image = ''
simulated_images_in_list = 0
FilmHoleY1 = 260 if BigSize else 210
FilmHoleY2 = 260 if BigSize else 210

# Commands (RPI to Arduino)
CMD_VERSION_ID = 1
CMD_GET_CNT_STATUS = 2
CMD_RESET_CONTROLLER = 3
CMD_START_SCAN = 10
CMD_TERMINATE = 11
CMD_GET_NEXT_FRAME = 12
CMD_STOP_SCAN = 13
CMD_SET_REGULAR_8 = 18
CMD_SET_SUPER_8 = 19
CMD_SWITCH_REEL_LOCK_STATUS = 20
CMD_FILM_FORWARD = 30
CMD_FILM_BACKWARD = 31
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
CMD_SET_STALL_TIME = 72
CMD_SET_AUTO_STOP = 74
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
RSP_FILM_FORWARD_ENDED = 89


# Expert mode variables - By default Exposure and white balance are set as automatic, with adapt delay
ExpertMode = True
ExperimentalMode = True
PlotterMode = True
plotter_canvas = None
plotter_width = 240
plotter_height = 180
PrevPTValue = 0
PrevThresholdLevel = 0
MaxPT = 100
MinPT = 800
Tolerance_AE = 8000
Tolerance_AWB = 1
PreviousCurrentExposure = 0  # Used to spot changes in exposure, and cause a delay to allow camera to adapt
AwbPause = False   # by default (non-expert) we wait for camera to stabilize when AWB changes
PreviousGainRed = 1
PreviousGainBlue = 1
ManualScanEnabled = False
CameraDisabled = False  # To allow testing scanner without a camera installed

# Statistical information about where time is spent (expert mode only)
total_wait_time_save_image = 0
total_wait_time_preview_display = 0
total_wait_time_awb = 0
total_wait_time_autoexp = 0
time_save_image = None
time_preview_display = None
time_awb = None
time_autoexp = None
session_start_time = 0
session_frames=0
max_wait_time = 5000
last_click_time = 0

ALT_Scann8_controller_detected = False

FPM_LastMinuteFrameTimes = list()
FPM_StartTime = time.ctime()
FPM_CalculatedValue = -1

# *** HDR variables
MergeMertens = None
images_to_merge = []
# 4 iterations seem to be enough for exposure to catch up (started with 9, 4 gives same results, 3 is not enough)
dry_run_iterations = 4
# HDR, min/max exposure range. Used to be from 10 to 150, but original values found elsewhere (1-56) are better
# Finally set to 4-104
hdr_lower_exp = 8
hdr_higher_exp = 104
hdr_best_exp = 0
hdr_min_bracket_width = 4
hdr_max_bracket_width = 400
hdr_num_exposures = 3   # Changed from 4 exposures to 3, probably an odd number is better (and 3 faster than 4)
hdr_step_value = 1
hdr_exp_list = []
hdr_rev_exp_list = []
HdrViewX4Active = False
recalculate_hdr_exp_list = False
force_adjust_hdr_bracket = False
HdrBracketAuto = False
HdrMergeInPlace = False
hdr_auto_bracket_frames = 8    # Every n frames, bracket is recalculated

# *** Simulated sensor modes to ellaborate resolution list
camera_resolutions = None
simulated_sensor_modes = [{'bit_depth': 10,
                           'crop_limits': (696, 528, 2664, 1980),
                           'exposure_limits': (31, 667234896, None),
                           'format': 'SRGGB10_CSI2P',
                           'fps': 120.05,
                           'size': (1332, 990),
                           'unpacked': 'SRGGB10'},
                          {'bit_depth': 12,
                           'crop_limits': (0, 440, 4056, 2160),
                           'exposure_limits': (60, 674181621, None),
                           'format': 'SRGGB12_CSI2P',
                           'fps': 50.03,
                           'size': (2028, 1080),
                           'unpacked': 'SRGGB12'},
                          {'bit_depth': 12,
                           'crop_limits': (0, 0, 4056, 3040),
                           'exposure_limits': (60, 674181621, None),
                           'format': 'SRGGB12_CSI2P',
                           'fps': 40.01,
                           'size': (2028, 1520),
                           'unpacked': 'SRGGB12'},
                          {'bit_depth': 12,
                           'crop_limits': (0, 0, 4056, 3040),
                           'exposure_limits': (114, 694422939, None),
                           'format': 'SRGGB12_CSI2P',
                           'fps': 10.0,
                           'size': (4056, 3040),
                           'unpacked': 'SRGGB12'}]

# Persisted data
SessionData = {
    "CurrentDate": str(datetime.now()),
    "CurrentDir": CurrentDir,
    "CurrentFrame": str(CurrentFrame),
    "CurrentExposure": 0,
    "NegativeCaptureActive": False,
    "HdrCaptureActive": str(HdrCaptureActive),
    "FilmType": 'S8',
    "MinFrameStepsS8": 290,
    "MinFrameStepsR8":  240,
    "MinFrameSteps":  290,
    "FrameFineTune":  50,
    "FrameExtraSteps": 0,
    "PTLevelS8":  80,
    "PTLevelR8":  200,
    "PTLevel":  80,
    "PTLevelAuto": True,
    "FrameStepsAuto": True,
    "HdrMinExp": hdr_lower_exp,
    "HdrMaxExp": hdr_higher_exp,
    "HdrBracketWidth": 50,
    "HdrBracketShift": 0,
    "HdrBracketAuto": True,
    "HdrMergeInPlace": False,
    "FramesToGo": FramesToGo
}

# ********************************************************
# ALT-Scann8 code
# ********************************************************

def exit_app():  # Exit Application
    global win
    global SimulatedRun
    global camera
    global PreviewMode
    global ExitingApp
    global onesec_after, arduino_after

    win.config(cursor="watch")
    win.update()
    # Flag app is exiting for all outstanding afters to expire
    ExitingApp = True
    if onesec_after != 0:
        win.after_cancel(onesec_after)
    if arduino_after != 0:
        win.after_cancel(arduino_after)
    # Terminate threads
    if not SimulatedRun and not CameraDisabled:
        capture_display_event.set()
        capture_save_event.set()
        capture_display_queue.put(END_TOKEN)
        capture_save_queue.put(END_TOKEN)
        capture_save_queue.put(END_TOKEN)
        capture_save_queue.put(END_TOKEN)

        while active_threads > 0:
            win.update()
            logging.debug(f"Waiting for threads to exit, {active_threads} pending")
            time.sleep(0.2)

    # Uncomment next two lines when running on RPi
    if not SimulatedRun:
        send_arduino_command(CMD_TERMINATE)   # Tell Arduino we stop (to turn off uv led
        # Close preview if required
        if not CameraDisabled:
            if PiCam2PreviewEnabled:
                camera.stop_preview()
            camera.close()
    # Set window position for next run
    SessionData["WindowPos"] = win.geometry()
    SessionData["AutoStopActive"] = auto_stop_enabled.get()
    SessionData["AutoStopType"] = autostop_type.get()
    if frames_to_go_str.get() == '':
        SessionData["FramesToGo"] = -1
    # Write session data upon exit
    with open(PersistedDataFilename, 'w') as f:
        json.dump(SessionData, f)

    win.config(cursor="")

    win.destroy()


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


def set_auto_stop_enabled():
    if not SimulatedRun:
        send_arduino_command(CMD_SET_AUTO_STOP, auto_stop_enabled.get() and autostop_type.get() == 'No_film')
        logging.debug(f"Sent Auto Stop to Arduino: {auto_stop_enabled.get() and autostop_type.get() == 'No_film'}")
    autostop_no_film_rb.config(state=NORMAL if auto_stop_enabled.get() else DISABLED)
    autostop_counter_zero_rb.config(state=NORMAL if auto_stop_enabled.get() else DISABLED)
    logging.debug(f"Set Auto Stop: {auto_stop_enabled.get()}, {autostop_type.get()}")


# Enable/Disable camera zoom to facilitate focus
def set_focus_zoom():
    global FocusZoomActive
    global save_bg, save_fg
    global SimulatedRun
    global ZoomSize
    global focus_lf_btn, focus_up_btn, focus_dn_btn, focus_rt_btn, focus_plus_btn, focus_minus_btn

    if real_time_zoom.get():
        real_time_zoom_checkbox.config(fg="white")  # Change background color and text color when checked
        real_time_display_checkbox.config(state=DISABLED)
    else:
        real_time_zoom_checkbox.config(fg="black")  # Change back to default colors when unchecked
        real_time_display_checkbox.config(state=NORMAL)

    if not SimulatedRun and not CameraDisabled:
        if real_time_zoom.get():
            camera.set_controls(
                {"ScalerCrop": (int(FocusZoomPosX * ZoomSize[0]), int(FocusZoomPosY * ZoomSize[1])) +
                               (int(FocusZoomFactorX * ZoomSize[0]), int(FocusZoomFactorY * ZoomSize[1]))})
        else:
            camera.set_controls({"ScalerCrop": (0, 0) + (ZoomSize[0], ZoomSize[1])})

    time.sleep(.2)
    FocusZoomActive = not FocusZoomActive

    # Enable disable buttons for focus move
    if ExpertMode:
        focus_lf_btn.config(state=NORMAL if FocusZoomActive else DISABLED)
        focus_up_btn.config(state=NORMAL if FocusZoomActive else DISABLED)
        focus_dn_btn.config(state=NORMAL if FocusZoomActive else DISABLED)
        focus_rt_btn.config(state=NORMAL if FocusZoomActive else DISABLED)
        focus_plus_btn.config(state=NORMAL if FocusZoomActive else DISABLED)
        focus_minus_btn.config(state=NORMAL if FocusZoomActive else DISABLED)

def adjust_focus_zoom():
    global ZoomSize
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"ScalerCrop": (int(FocusZoomPosX * ZoomSize[0]), int(FocusZoomPosY * ZoomSize[1])) +
                                           (int(FocusZoomFactorX * ZoomSize[0]), int(FocusZoomFactorY * ZoomSize[1]))})


def set_focus_up():
    global FocusZoomPosX, FocusZoomPosY
    if FocusZoomPosY >= 0.05:
        FocusZoomPosY = round(FocusZoomPosY - 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom up (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX, FocusZoomFactorY)

def set_focus_left():
    global FocusZoomPosX, FocusZoomPosY
    if FocusZoomPosX >= 0.05:
        FocusZoomPosX = round(FocusZoomPosX - 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom left (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX, FocusZoomFactorY)


def set_focus_right():
    global FocusZoomPosX, FocusZoomPosY
    if FocusZoomPosX <= (1-(FocusZoomFactorX - 0.05)):
        FocusZoomPosX = round(FocusZoomPosX + 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom right (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX, FocusZoomFactorY)


def set_focus_down():
    global FocusZoomPosX, FocusZoomPosY
    if FocusZoomPosY <= (1-(FocusZoomFactorY - 0.05)):
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
    global Scanned_Images_number_str

    requested_dir = ""
    success = False

    while requested_dir == "" or requested_dir is None:
        requested_dir = tk.simpledialog.askstring(title="Enter new folder name", prompt=f"Enter new folder name (to be created under {CurrentDir}):")
        if requested_dir is None:
            return
        if requested_dir == "":
            tk.messagebox.showerror("Error!", "Please specify a name for the folder to be created.")

    newly_created_dir = os.path.join(CurrentDir, requested_dir)

    if not os.path.isdir(newly_created_dir):
        try:
            os.mkdir(newly_created_dir)
            CurrentFrame = 0
            CurrentDir = newly_created_dir
            success = True
        except FileExistsError:
            tk.messagebox.showerror("Error", f"Folder {requested_dir} already exists.")
        except PermissionError:
            tk.messagebox.showerror("Error", f"Folder {requested_dir}, permission denied to create directory.")
        except OSError as e:
            tk.messagebox.showerror("Error", f"While creating folder {requested_dir}, OS error: {e}.")
        except Exception as e:
            tk.messagebox.showerror("Error", f"While creating folder {requested_dir}, unexpected error: {e}.")
    else:
        tk.messagebox.showerror("Error!", "Folder " + requested_dir + " already exists.")

    if success:
        folder_frame_target_dir.config(text=CurrentDir)
        Scanned_Images_number_str.set(str(CurrentFrame))
        SessionData["CurrentDir"] = str(CurrentDir)
        SessionData["CurrentFrame"] = str(CurrentFrame)


def set_existing_folder():
    global CurrentDir, CurrentFrame
    global SimulatedRun

    if not SimulatedRun:
        NewDir = filedialog.askdirectory(initialdir=CurrentDir, title="Select existing folder for capture")
    else:
        NewDir = filedialog.askdirectory(initialdir=CurrentDir,
                                                title="Select existing folder with snapshots for simulated run")
    if not NewDir:
        return

    filecount = 0
    for name in os.listdir(NewDir):
        if os.path.isfile(os.path.join(NewDir, name)):
            filecount += 1

    current_frame_str = tk.simpledialog.askstring(title="Enter number of last captured frame",
                                                  prompt="Last frame captured?")
    if current_frame_str is None:
        current_frame_str = '0'

    if current_frame_str == '':
        current_frame_str = '0'
    NewCurrentFrame = int(current_frame_str)

    if filecount > 0 and NewCurrentFrame <= filecount:
        confirm = tk.messagebox.askyesno(title='Files exist in target folder',
                                         message=f"Newly selected folder already contains {filecount} files."
                                         f"\r\nSetting {NewCurrentFrame} as initial frame will overwrite some of them."
                                         f"Are you sure you want to continue?")
    else:
        confirm = True

    if confirm:
        CurrentFrame = NewCurrentFrame
        CurrentDir = NewDir

        Scanned_Images_number_str.set(str(current_frame_str))
        SessionData["CurrentFrame"] = str(CurrentFrame)

        folder_frame_target_dir.config(text=CurrentDir)
        SessionData["CurrentDir"] = str(CurrentDir)


def wb_spinbox_auto():
    global wb_red_spinbox
    global wb_blue_spinbox
    global awb_red_wait_checkbox, awb_blue_wait_checkbox
    global colour_gains_auto_btn, awb_frame
    global colour_gains_red_btn_plus, colour_gains_red_btn_minus
    global colour_gains_blue_btn_plus, colour_gains_blue_btn_minus

    if not ExpertMode:
        return

    SessionData["CurrentAwbAuto"] = AWB_enabled.get()
    SessionData["GainRed"] = wb_red_value.get()
    SessionData["GainBlue"] = wb_blue_value.get()

    if AWB_enabled.get():
        awb_red_wait_checkbox.config(state=NORMAL)
        if not SimulatedRun and not CameraDisabled:
            camera.set_controls({"AwbEnable": 1})
    else:
        awb_red_wait_checkbox.config(state=DISABLED)
        if not SimulatedRun and not CameraDisabled:
            # Do not retrieve current gain values from Camera (capture_metadata) to prevent conflicts
            # Since we update values in the UI regularly, use those.
            camera_colour_gains = (wb_red_value.get(), wb_blue_value.get())
            camera.set_controls({"AwbEnable": 0})
            camera.set_controls({"ColourGains": camera_colour_gains})
    arrange_widget_state(AWB_enabled.get(), [wb_red_btn, wb_red_spinbox, wb_blue_spinbox])



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


def frame_extra_steps_selection():
    aux = value_normalize(frame_extra_steps_value, -30, 30)
    SessionData["FrameExtraSteps"] = aux
    send_arduino_command(CMD_SET_EXTRA_STEPS, aux)


def button_status_change_except(except_button, active):
    global Free_btn, SingleStep_btn, Snapshot_btn, AdvanceMovie_btn, RetreatMovie_btn
    global Rewind_btn, FastForward_btn, Start_btn
    global Start_btn, Exit_btn
    global film_type_S8_rb, film_type_R8_rb
    global hdr_btn
    global button_lock_counter
    global hdr_capture_active_checkbox
    global real_time_zoom_checkbox, negative_image_checkbox

    if active:
        button_lock_counter += 1
    else:
        button_lock_counter -= 1
    if button_lock_counter > 1 or (not active and button_lock_counter > 0):
        return
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
    if except_button != negative_image_checkbox:
        negative_image_checkbox.config(state=DISABLED if active else NORMAL)
    if except_button != Start_btn and not PiCam2PreviewEnabled:
        Start_btn.config(state=DISABLED if active else NORMAL)
    if except_button != Exit_btn:
        Exit_btn.config(state=DISABLED if active else NORMAL)
    if except_button != film_type_S8_rb:
        film_type_S8_rb.config(state=DISABLED if active else NORMAL)
    if except_button != film_type_R8_rb:
        film_type_R8_rb.config(state=DISABLED if active else NORMAL)
    '''
    if except_button != file_type_jpg_rb:
        file_type_jpg_rb.config(state=DISABLED if active else NORMAL)
    if except_button != file_type_png_rb:
        file_type_png_rb.config(state=DISABLED if active else NORMAL)
    '''
    if except_button != file_type_dropdown:
        file_type_dropdown.config(state=DISABLED if active else NORMAL)
    if ExperimentalMode:
        if except_button != RetreatMovie_btn:
            RetreatMovie_btn.config(state=DISABLED if active else NORMAL)
        if except_button != Free_btn:
            Free_btn.config(state=DISABLED if active else NORMAL)
        if except_button != new_folder_btn:
            new_folder_btn.config(state=DISABLED if active else NORMAL)
        hdr_capture_active_checkbox.config(state=DISABLED if active else NORMAL)
    if except_button != real_time_display_checkbox:
        real_time_display_checkbox.config(state=DISABLED if active else NORMAL)
    if except_button != real_time_zoom_checkbox:
        real_time_zoom_checkbox.config(state=NORMAL if real_time_display.get() else DISABLED)
    if except_button != resolution_label:
        resolution_label.config(state=DISABLED if active else NORMAL)
    if except_button != resolution_dropdown:
        resolution_dropdown.config(state=DISABLED if active else NORMAL)
    if except_button != file_type_label:
        file_type_label.config(state=DISABLED if active else NORMAL)
    if except_button != file_type_dropdown:
        file_type_dropdown.config(state=DISABLED if active else NORMAL)
    if except_button != existing_folder_btn:
        existing_folder_btn.config(state=DISABLED if active else NORMAL)


def advance_movie(from_arduino = False):
    global AdvanceMovieActive
    global save_bg, save_fg
    global SimulatedRun
    global AdvanceMovie_btn

    # Update button text
    if not AdvanceMovieActive:  # Advance movie is about to start...
        AdvanceMovie_btn.config(text='Stop movie', bg='red',
                                fg='white', relief=SUNKEN)  # ...so now we propose to stop it in the button test
    else:
        AdvanceMovie_btn.config(text='Movie forward', bg=save_bg,
                                fg=save_fg, relief=RAISED)  # Otherwise change to default text to start the action
    AdvanceMovieActive = not AdvanceMovieActive
    # Send instruction to Arduino
    if not SimulatedRun and not from_arduino:   # Do not send Arduino command if triggered by Arduino response
        send_arduino_command(CMD_FILM_FORWARD)

    # Enable/Disable related buttons
    button_status_change_except(AdvanceMovie_btn, AdvanceMovieActive)


def retreat_movie():
    global RetreatMovieActive
    global save_bg, save_fg
    global SimulatedRun
    global RetreatMovie_btn

    # Update button text
    if not RetreatMovieActive:  # Advance movie is about to start...
        RetreatMovie_btn.config(text='Stop movie', bg='red',
                                fg='white', relief=SUNKEN)  # ...so now we propose to stop it in the button test
    else:
        RetreatMovie_btn.config(text='Movie backward', bg=save_bg,
                                fg=save_fg, relief=RAISED)  # Otherwise change to default text to start the action
    RetreatMovieActive = not RetreatMovieActive
    # Send instruction to Arduino
    if not SimulatedRun:
        send_arduino_command(CMD_FILM_BACKWARD)

    # Enable/Disable related buttons
    button_status_change_except(RetreatMovie_btn, RetreatMovieActive)


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

# *******************************************************************
# ********************** Capture functions **************************
# *******************************************************************
def reverse_image(image):
    image_array = np.asarray(image)
    image_array = np.negative(image_array)
    return Image.fromarray(image_array)


def capture_display_thread(queue, event, id):
    global active_threads
    logging.debug("Started capture_display_thread")
    while not event.is_set() or not queue.empty():
        message = queue.get()
        curtime = time.time()
        if ExitingApp:
            break
        logging.debug("Retrieved message from capture display queue (len=%i)", queue.qsize())
        if message == END_TOKEN:
            break
        type = message[0]
        if type != IMAGE_TOKEN:
            continue
        image = message[1]
        hdr_idx = message[3]

        # If too many items in queue the skip display
        if (MaxQueueSize - queue.qsize() <= 5):
            logging.warning("Display queue almost full: Skipping frame display")
        else:
            # Invert image if button selected
            if negative_image.get():
                image = reverse_image(image)
            draw_preview_image(image, hdr_idx)
            logging.debug("Display thread complete: %s ms", str(round((time.time() - curtime) * 1000, 1)))
    active_threads -= 1
    logging.debug("Exiting capture_display_thread")


def capture_save_thread(queue, event, id):
    global CurrentDir
    global ScanStopRequested
    global active_threads
    global total_wait_time_save_image

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
        if ExitingApp:
            break
        if message == END_TOKEN:
            break
        # Invert image if button selected
        is_dng = file_type_dropdown_selected.get() == 'dng'
        is_jpg = file_type_dropdown_selected.get() == 'jpg'
        # Extract info from message
        type = message[0]
        if type == REQUEST_TOKEN:
            request = message[1]
        elif type == IMAGE_TOKEN:
            captured_image = message[1]
        else:
            logging.error(f"Invalid message type received: {type}")
        frame_idx = message[2]
        hdr_idx = message[3]
        if is_dng:
            if hdr_idx > 1:  # Hdr frame 1 has standard filename
                request.save_dng(HdrFrameFilenamePattern % (frame_idx, hdr_idx, file_type_dropdown_selected.get()))
            else:  # Non HDR
                request.save_dng(FrameFilenamePattern % (frame_idx, file_type_dropdown_selected.get()))
            request.release()
            logging.debug("Thread %i saved request DNG image: %s ms", id, str(round((time.time() - curtime) * 1000, 1)))
        else:
            #if is_jpg or negative_image.get() and not is_dng:  # Plain file save
            if negative_image.get():
                if type == REQUEST_TOKEN:
                    captured_image = request.make_image('main')
                    request.release()
                captured_image = reverse_image(captured_image)
                if hdr_idx > 1:  # Hdr frame 1 has standard filename
                    logging.debug("Saving HDR frame n.%i", hdr_idx)
                    captured_image.save(HdrFrameFilenamePattern % (frame_idx, hdr_idx, file_type_dropdown_selected.get()), quality=95)
                else:
                    captured_image.save(FrameFilenamePattern % (frame_idx, file_type_dropdown_selected.get()), quality=95)
                logging.debug("Thread %i saved image: %s ms", id, str(round((time.time() - curtime) * 1000, 1)))
            else:
                if hdr_idx > 1:  # Hdr frame 1 has standard filename
                    request.save('main', HdrFrameFilenamePattern % (frame_idx, hdr_idx, file_type_dropdown_selected.get()))
                else:  # Non HDR
                    request.save('main', FrameFilenamePattern % (frame_idx, file_type_dropdown_selected.get()))
                request.release()
                logging.debug("Thread %i saved request image: %s ms", id, str(round((time.time() - curtime) * 1000, 1)))

        aux = time.time() - curtime
        total_wait_time_save_image += aux
        time_save_image.add_value(aux)
    active_threads -= 1
    logging.debug("Exiting capture_save_thread n.%i", id)

def draw_preview_image(preview_image, idx):
    global draw_capture_canvas
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
        draw_capture_canvas.create_image(0, 0, anchor=NW, image=PreviewAreaImage)
        draw_capture_canvas.image = PreviewAreaImage

        # The Pack geometry manager packs widgets in rows or columns.
        # draw_capture_label.place(x=0, y=0) # This line is probably causing flickering, to be checked

        aux = time.time() - curtime
        total_wait_time_preview_display += aux
        time_preview_display.add_value(aux)
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

def disk_space_available():
    global CurrentDir, available_space_mb, disk_space_error_to_notify

    if not check_disk_space:
        return True
    disk_usage = psutil.disk_usage(CurrentDir)
    available_space_mb = disk_usage.free / (1024 ** 2)

    if available_space_mb < 500:
        logging.debug(f"Disk space running out, only {available_space_mb} MB available")
        disk_space_error_to_notify = True
        return False
    else:
        return True


def hdr_set_controls():

    if not ExpertMode:
        return
    hdr_viewx4_active_checkbox.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_min_exp_label.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_min_exp_spinbox.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_max_exp_label.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_max_exp_spinbox.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_bracket_width_label.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_bracket_shift_label.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_bracket_width_spinbox.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_bracket_shift_spinbox.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_bracket_width_auto_checkbox.config(state=NORMAL if HdrCaptureActive else DISABLED)
    hdr_merge_in_place_checkbox.config(state=NORMAL if HdrCaptureActive else DISABLED)


def switch_hdr_capture():
    global SimulatedRun
    global hdr_capture_active, HdrCaptureActive, HdrBracketAuto
    global hdr_min_exp_spinbox, hdr_max_exp_spinbox, hdr_bracket_width_auto_checkbox
    global max_inactivity_delay


    HdrCaptureActive = hdr_capture_active.get()
    SessionData["HdrCaptureActive"] = str(HdrCaptureActive)

    hdr_set_controls()
    if HdrCaptureActive:    # If HDR enabled, handle automatic control settings for widgets
        max_inactivity_delay = max_inactivity_delay * 2
        arrange_widget_state(HdrBracketAuto, [hdr_min_exp_spinbox, hdr_max_exp_spinbox, hdr_bracket_width_auto_checkbox])
    else:    # If disabling HDR, need to set standard exposure as set in UI
        max_inactivity_delay = int(max_inactivity_delay / 2)
        if AE_enabled.get():  # Automatic mode
            CurrentExposure = 0
            if not SimulatedRun and not CameraDisabled:
                camera.controls.ExposureTime = 0    # maybe will not work, check pag 26 of picamera2 specs
        else:
            if not SimulatedRun and not CameraDisabled:
                # Since we are in auto exposure mode, retrieve current value to start from there
                metadata = camera.capture_metadata()
                CurrentExposure = metadata["ExposureTime"]
            else:
                CurrentExposure = 3500  # Arbitrary Value for Simulated run
        SessionData["CurrentExposure"] = CurrentExposure
        exposure_value.set(CurrentExposure)
    send_arduino_command(CMD_SET_STALL_TIME, max_inactivity_delay)
    logging.debug(f"max_inactivity_delay: {max_inactivity_delay}")

def switch_hdr_viewx4():
    global HdrViewX4Active, hdr_viewx4_active
    HdrViewX4Active = hdr_viewx4_active.get()
    SessionData["HdrViewX4Active"] = str(HdrViewX4Active)


def set_negative_image():
    SessionData["NegativeCaptureActive"] = negative_image.get()
    if negative_image.get():
        negative_image_checkbox.config(fg="white")  # Change background color and text color when checked
    else:
        negative_image_checkbox.config(fg="black")  # Change back to default colors when unchecked


def toggle_ui_size():
    global app_width, app_height
    global expert_frame, experimental_frame

    if toggle_ui_small.get():
        app_height -= 220 if BigSize else 170
        expert_frame.pack_forget()
        experimental_frame.pack_forget()
    else:
        app_height += 220 if BigSize else 170
        expert_frame.pack(side=LEFT)
        experimental_frame.pack(side=LEFT)
    # Prevent window resize
    win.minsize(app_width, app_height)
    win.maxsize(app_width, app_height)
    win.geometry(f'{app_width}x{app_height-20}')  # setting the size of the window

# Function to enable 'real' preview with PiCamera2
# Even if it is useless for capture (slow and imprecise) it is still needed for other tasks like:
#  - Focus
#  - Color adjustment
#  - Exposure adjustment
def set_real_time_display():
    global win
    global capture_config, preview_config
    global real_time_display, Start_btn

    if real_time_display.get():
        logging.debug("Real time display enabled")
        real_time_display_checkbox.config(fg="white")  # Change background color and text color when checked
    else:
        logging.debug("Real time display disabled")
        real_time_display_checkbox.config(fg="black")  # Change background color and text color when checked
    if not SimulatedRun and not CameraDisabled:
        if real_time_display.get():
            if camera._preview:
                camera.stop_preview()
            time.sleep(0.1)
            camera.start_preview(Preview.QTGL, x=PreviewWinX, y=PreviewWinY, width=840, height=720)
            time.sleep(0.1)
            camera.switch_mode(preview_config)
        else:
            if camera._preview:
                camera.stop_preview()
            camera.stop()
            camera.start()
            time.sleep(0.1)
            camera.switch_mode(capture_config)

    # Do not allow scan to start while PiCam2 preview is active
    Start_btn.config(state=DISABLED if real_time_display.get() else NORMAL)
    real_time_zoom_checkbox.config(state=NORMAL if real_time_display.get() else DISABLED)
    real_time_zoom_checkbox.deselect()
    real_time_display_checkbox.config(state=NORMAL)


def set_s8():
    global SimulatedRun, ExpertMode
    global PTLevelS8
    global MinFrameStepsS8
    global FilmHoleY1, FilmHoleY2
    global ALT_scann_init_done
    global film_hole_frame_1, film_hole_frame_2

    SessionData["FilmType"] = "S8"
    time.sleep(0.2)

    PTLevel = PTLevelS8
    MinFrameSteps = MinFrameStepsS8
    if ALT_scann_init_done:
        SessionData["PTLevel"] = PTLevel
        SessionData["MinFrameSteps"] = MinFrameSteps
    if ExpertMode:
        pt_level_value.set(PTLevel)
        steps_per_frame_value.set(MinFrameSteps)
    # Set reference film holes
    FilmHoleY1 = 260 if BigSize else 210
    FilmHoleY2 = 260 if BigSize else 210
    if ExpertMode:
        film_hole_frame_1.place(x=150 if BigSize else 130, y=FilmHoleY2, height=150 if BigSize else 130)
        film_hole_frame_2.place(x=150 if BigSize else 130, y=FilmHoleY2, height=150 if BigSize else 130)
    if not SimulatedRun:
        send_arduino_command(CMD_SET_SUPER_8)
        if ExpertMode:
            send_arduino_command(CMD_SET_PT_LEVEL, 0 if auto_pt_level_enabled.get() else PTLevel)
            send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0 if auto_framesteps_enabled.get() else MinFrameSteps)


def set_r8():
    global SimulatedRun
    global PTLevelR8
    global MinFrameStepsR8
    global film_hole_frame_1, film_hole_frame_2

    SessionData["FilmType"] = "R8"
    time.sleep(0.2)

    PTLevel = PTLevelR8
    MinFrameSteps = MinFrameStepsR8
    if ALT_scann_init_done:
        SessionData["PTLevel"] = PTLevel
        SessionData["MinFrameSteps"] = MinFrameSteps
    if ExpertMode:
        pt_level_value.set(PTLevel)
        steps_per_frame_value.set(MinFrameSteps)
    # Set reference film holes
    FilmHoleY1 = 20 if BigSize else 20
    FilmHoleY2 = 540 if BigSize else 380
    if ExpertMode:
        film_hole_frame_1.place(x=150 if BigSize else 130, y=FilmHoleY1, height=130 if BigSize else 70)
        film_hole_frame_2.place(x=150 if BigSize else 130, y=FilmHoleY2, height=110 if BigSize else 130)
    if not SimulatedRun:
        send_arduino_command(CMD_SET_REGULAR_8)
        if ExpertMode:
            send_arduino_command(CMD_SET_PT_LEVEL, 0 if auto_pt_level_enabled.get() else PTLevel)
            send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0 if auto_framesteps_enabled.get() else MinFrameSteps)


def register_frame():
    global FPM_LastMinuteFrameTimes
    global FPM_StartTime
    global FPM_CalculatedValue

    # Get current time
    frame_time = time.time()
    # Determine if we should start new count (last capture older than 5 seconds)
    if len(FPM_LastMinuteFrameTimes) == 0 or FPM_LastMinuteFrameTimes[-1] < frame_time - 30:
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
    if frame_time - FPM_StartTime > 60:  # no calculations needed, frames in list are all in the last 60 seconds
        FPM_CalculatedValue = len(FPM_LastMinuteFrameTimes)
    elif frame_time - FPM_StartTime > 10:  # some  calculations needed if less than 60 sec
        FPM_CalculatedValue = int((len(FPM_LastMinuteFrameTimes) * 60) / (frame_time - FPM_StartTime))


def adjust_hdr_bracket_auto():
    global HdrCaptureActive, HdrBracketAuto, hdr_bracket_auto
    global hdr_max_exp_spinbox, hdr_min_exp_spinbox

    if not HdrCaptureActive:
        return

    HdrBracketAuto = hdr_bracket_auto.get()
    SessionData["HdrBracketAuto"] = HdrBracketAuto

    arrange_widget_state(HdrBracketAuto, [hdr_max_exp_spinbox, hdr_min_exp_spinbox])


def adjust_merge_in_place():
    global HdrCaptureActive, HdrMergeInPlace, hdr_merge_in_place

    if not HdrCaptureActive:
        return

    HdrMergeInPlace = hdr_merge_in_place.get()
    SessionData["HdrMergeInPlace"] = HdrMergeInPlace


def adjust_hdr_bracket():
    global camera, HdrCaptureActive
    global recalculate_hdr_exp_list, dry_run_iterations
    global hdr_best_exp
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
        for i in range(1, dry_run_iterations * 2):
            camera.capture_image("main")

        # Since we are in auto exposure mode, retrieve current value to start from there
        metadata = camera.capture_metadata()
        aux_current_exposure = int(metadata["ExposureTime"]/1000)

    if aux_current_exposure != PreviousCurrentExposure or force_adjust_hdr_bracket:  # Adjust only if auto exposure changes
        logging.debug(f"Adjusting bracket, prev/cur exp: {PreviousCurrentExposure} -> {aux_current_exposure}")
        force_adjust_hdr_bracket = False
        PreviousCurrentExposure = aux_current_exposure
        hdr_best_exp = aux_current_exposure
        hdr_min_exp_value.set(max(hdr_best_exp-int(hdr_bracket_width_value.get()/2), hdr_lower_exp))
        hdr_max_exp_value.set(hdr_min_exp_value.get() + hdr_bracket_width_value.get())
        SessionData["HdrMinExp"] = hdr_min_exp_value.get()
        SessionData["HdrMaxExp"] = hdr_max_exp_value.get()
        recalculate_hdr_exp_list = True
        logging.debug(f"Adjusting bracket: {hdr_min_exp_value.get()}, {hdr_max_exp_value.get()}")


def capture_hdr(mode):
    global CurrentFrame
    global capture_display_queue, capture_save_queue
    global camera, hdr_exp_list, hdr_rev_exp_list
    global recalculate_hdr_exp_list, dry_run_iterations
    global HdrBracketAuto
    global MergeMertens

    if HdrBracketAuto and session_frames % hdr_auto_bracket_frames == 0:
        adjust_hdr_bracket()

    if recalculate_hdr_exp_list:
        hdr_reinit()
        perform_dry_run = True
        recalculate_hdr_exp_list = False
    else:
        perform_dry_run = False

    images_to_merge.clear()
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
    is_dng = file_type_dropdown_selected.get() == 'dng'
    for exp in work_list:
        exp = max(1, exp + hdr_bracket_shift_value.get())   # Apply bracket shift
        logging.debug("capture_hdr: exp %.2f", exp)
        if perform_dry_run:
            camera.set_controls({"ExposureTime": int(exp*1000)})
        else:
            time.sleep(stabilization_delay_value.get()/1000)  # Allow time to stabilize image only if no dry run
        if perform_dry_run:
            for i in range(1,dry_run_iterations):   # Perform a few dummy captures to allow exposure stabilization
                camera.capture_image("main")
        # We skip dry run only for the first capture of each frame,
        # as it is the same exposure as the last capture of the previous one
        perform_dry_run = True
        # For PiCamera2, preview and save to file are handled in asynchronous threads
        if HdrMergeInPlace and not is_dng:  # For now we do not even try to merge DNG images in place
            captured_image = camera.capture_image("main")    # If merge in place, Capture snapshot (no DNG allowed)
            # Convert Pillow image to NumPy array
            img_np = np.array(captured_image)
            # Convert the NumPy array to a format suitable for MergeMertens (e.g., float32)
            img_np_float32 = img_np.astype(np.float32)
            images_to_merge.append(img_np_float32)  # Add frame
        else:
            request = camera.capture_request(capture_config)
            captured_image = request.make_image('main')
            if not is_dng:  # If not using DNG we can still use multithread (if not disabled)
                # Reuse captured_image from preview
                # captured_image = request.make_image('main')
                if DisableThreads:  # Save image in main loop
                    draw_preview_image(captured_image, idx)  # Display preview
                    curtime = time.time()
                    if negative_image.get():
                        captured_image = reverse_image(captured_image)
                        request.release()  # release request, already have image, don't need it for non-DNG
                        if idx > 1:  # Hdr frame 1 has standard filename
                            captured_image.save(HdrFrameFilenamePattern % (CurrentFrame, idx,
                                                                           file_type_dropdown_selected.get()), quality=95)
                        else:
                            captured_image.save(FrameFilenamePattern % (CurrentFrame, file_type_dropdown_selected.get()),
                                                quality=95)
                        logging.debug("Capture hdr, saved image: %s ms", str(round((time.time() - curtime) * 1000, 1)))
                    else:   # id non-negative, save request as it is more efficient, specially for PNG
                        if idx > 1:  # Hdr frame 1 has standard filename
                            request.save('main', HdrFrameFilenamePattern % (CurrentFrame, idx, file_type_dropdown_selected.get()))
                        else:
                            request.save('main', FrameFilenamePattern % (CurrentFrame, file_type_dropdown_selected.get()))
                        request.release()  # release request, already have image, don't need it for non-DNG
                        logging.debug("Capture hdr, saved request image: %s ms", str(round((time.time() - curtime) * 1000, 1)))
                else:   # send image to threads
                    request.release()  # release request, already have image, don't need it for non-DNG
                    # Having the preview handled by a thread is not only not efficient, but algo quite sluggish
                    draw_preview_image(captured_image, idx)
                    """
                    # Leave this code commented for now
                    queue_item = tuple((IMAGE_TOKEN, captured_image, CurrentFrame, idx))
                    capture_display_queue.put(queue_item)
                    """
                    if mode == 'normal' or mode == 'manual':  # Do not save in preview mode, only display
                        queue_item = tuple((IMAGE_TOKEN, captured_image, CurrentFrame, idx))
                        capture_save_queue.put(queue_item)
                        logging.debug("Saving frame %i", CurrentFrame)
            else:  # DNG + HDR, threads not possible due to request conflicting with retrieve metadata
                """
                queue_item = tuple((IMAGE_TOKEN, captured_image, CurrentFrame, idx))
                capture_display_queue.put(queue_item)
                """
                draw_preview_image(captured_image, idx)  # Display preview
                curtime = time.time()
                if idx > 1:  # Hdr frame 1 has standard filename
                    request.save_dng(HdrFrameFilenamePattern % (CurrentFrame, idx, file_type_dropdown_selected.get()))
                else:  # Non HDR
                    request.save_dng(FrameFilenamePattern % (CurrentFrame, file_type_dropdown_selected.get()))
                request.release()
                logging.debug("Capture hdr, saved request image: %s ms", str(round((time.time() - curtime) * 1000, 1)))
        idx += idx_inc
    if HdrMergeInPlace and not is_dng:
        # Perform merge of the HDR image list
        img = MergeMertens.process(images_to_merge)
        # Convert the result back to PIL
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
        img = Image.fromarray(img)
        draw_preview_image(img, 0)  # Display preview
        img.save(FrameFilenamePattern % (CurrentFrame, file_type_dropdown_selected.get()), quality=95)


def capture_single(mode):
    global CurrentFrame
    global capture_display_queue, capture_save_queue
    global total_wait_time_save_image

    is_dng = file_type_dropdown_selected.get() == 'dng'
    if not DisableThreads:
        if not negative_image.get(): # or is_dng: # Cannot capture negative if target is DNG file, so we ignore it
            request = camera.capture_request(capture_config)
            # For PiCamera2, preview and save to file are handled in asynchronous threads
            captured_image = request.make_image('main')
            draw_preview_image(captured_image, 0)
            """
            display_queue_item = tuple((IMAGE_TOKEN, captured_image, CurrentFrame, 0))
            capture_display_queue.put(display_queue_item)
            logging.debug("Queueing frame %i for display", CurrentFrame)
            """
            if mode == 'normal' or mode == 'manual':  # Do not save in preview mode, only display
                save_queue_item = tuple((REQUEST_TOKEN, request, CurrentFrame, 0))
                capture_save_queue.put(save_queue_item)
                logging.debug("Queueing frame %i to be saved", CurrentFrame)
        else:
            captured_image = camera.capture_image("main")
            # For PiCamera2, preview and save to file are handled in asynchronous threads
            queue_item = tuple((IMAGE_TOKEN, captured_image, CurrentFrame, 0))
            #capture_display_queue.put(queue_item)
            draw_preview_image(captured_image, 0)
            if mode == 'normal' or mode == 'manual':  # Do not save in preview mode, only display
                capture_save_queue.put(queue_item)
                logging.debug("Saving frame %i", CurrentFrame)
        if mode == 'manual':  # In manual mode, increase CurrentFrame
            CurrentFrame += 1
            # Update number of captured frames
            Scanned_Images_number_str.set(str(CurrentFrame))
    else:
        request = camera.capture_request(capture_config)
        captured_image = request.make_image('main')
        curtime = time.time()
        if negative_image.get() and not is_dng: # Cannot capture negative if target is DNG file, so we ignore it
            request.release()
            captured_image = reverse_image(captured_image)
            draw_preview_image(captured_image, 0)
            captured_image.save(FrameFilenamePattern % (CurrentFrame, file_type_dropdown_selected.get()), quality=95)
            logging.debug("Capture single, saved image: %s ms", str(round((time.time() - curtime) * 1000, 1)))
        else:
            draw_preview_image(captured_image, 0)
            if is_dng:
                request.save_dng(FrameFilenamePattern % (CurrentFrame, file_type_dropdown_selected.get()))
            else:
                request.save('main', FrameFilenamePattern % (CurrentFrame, file_type_dropdown_selected.get()))
            request.release()
            logging.debug("Capture single, saved request image: %s ms", str(round((time.time() - curtime) * 1000, 1)))
        aux = time.time() - curtime
        total_wait_time_save_image += aux
        time_save_image.add_value(aux)
        if mode == 'manual':  # In manual mode, increase CurrentFrame
            CurrentFrame += 1
            # Update number of captured frames
            Scanned_Images_number_str.set(str(CurrentFrame))


# 4 possible modes:
# 'normal': Standard capture during automated scan (display and save)
# 'manual': Manual capture during manual scan (display and save)
# 'still': Button to capture still (specific filename)
# 'preview': Manual scan, display only, do not save
def capture(mode):
    global CurrentDir, CurrentFrame
    global SessionData
    global PreviousCurrentExposure
    global SimulatedRun
    global AwbPause
    global PreviousGainRed, PreviousGainBlue
    global total_wait_time_autoexp, total_wait_time_awb
    global CurrentStill
    global HdrCaptureActive

    if SimulatedRun or CameraDisabled:
        return

    os.chdir(CurrentDir)

    # Wait for auto exposure to adapt only if allowed (and if not using HDR)
    if AE_enabled.get() and auto_exposure_change_pause.get() and not HdrCaptureActive:
        curtime = time.time()
        wait_loop_count = 0
        while True:  # In case of exposure change, give time for the camera to adapt
            metadata = camera.capture_metadata()
            aux_current_exposure = metadata["ExposureTime"]
            # With PiCamera2, exposure was changing too often, so level changed from 1000 to 2000, then to 4000
            # Finally changed to allow a percentage of the value used previously
            # As we initialize this percentage to 50%, we start with double the original value
            if abs(aux_current_exposure - PreviousCurrentExposure) > (match_wait_margin_value.get() * Tolerance_AE)/100:
                if (wait_loop_count % 10 == 0):
                    logging.debug(f"AE match: ({aux_current_exposure/1000},Auto {PreviousCurrentExposure/1000})")
                wait_loop_count += 1
                PreviousCurrentExposure = aux_current_exposure
                time.sleep(0.2)
                if (time.time() - curtime) * 1000 > max_wait_time:  # Never wait more than 5 seconds
                    break;
            else:
                break
        if wait_loop_count > 0:
            exposure_value.set(aux_current_exposure / 1000)
            aux = time.time() - curtime
            total_wait_time_autoexp += aux
            time_autoexp.add_value(aux)
            logging.debug("AE match delay: %s ms", str(round((time.time() - curtime) * 1000,1)))
        else:
            time_autoexp.add_value(0)


    # Wait for auto white balance to adapt only if allowed
    if AWB_enabled.get() and AwbPause:
        curtime = time.time()
        wait_loop_count = 0
        while True:  # In case of exposure change, give time for the camera to adapt
            metadata = camera.capture_metadata()
            camera_colour_gains = metadata["ColourGains"]
            aux_gain_red = camera_colour_gains[0]
            aux_gain_blue = camera_colour_gains[1]
            # Same as for exposure, difference allowed is a percentage of the maximum value
            if abs(aux_gain_red-PreviousGainRed) >= (match_wait_margin_value.get() * Tolerance_AWB/100) or \
               abs(aux_gain_blue-PreviousGainBlue) >= (match_wait_margin_value.get() * Tolerance_AWB/100):
                if (wait_loop_count % 10 == 0):
                    aux_gains_str = "(" + str(round(aux_gain_red, 2)) + ", " + str(round(aux_gain_blue, 2)) + ")"
                    logging.debug("AWB Match: %s", aux_gains_str)
                wait_loop_count += 1
                PreviousGainRed = aux_gain_red
                PreviousGainBlue = aux_gain_blue
                time.sleep(0.2)
                if (time.time() - curtime) * 1000 > max_wait_time:  # Never wait more than 5 seconds
                    break;
            else:
                break
        if wait_loop_count > 0:
            if ExpertMode:
                wb_red_value.set(round(aux_gain_red, 1))
                wb_blue_value.set(round(aux_gain_blue, 1))
            aux = time.time() - curtime
            total_wait_time_awb += aux
            time_awb.add_value(aux)
            logging.debug("AWB Match delay: %s ms", str(round((time.time() - curtime) * 1000,1)))
        else:
            time_awb.add_value(0)


    if PiCam2PreviewEnabled:
        if mode == 'still':
            camera.switch_mode_and_capture_file(capture_config, StillFrameFilenamePattern % (CurrentFrame,CurrentStill))
            CurrentStill += 1
        else:
            # This one should not happen, will not allow PiCam2 scan in preview mode
            camera.switch_mode_and_capture_file(capture_config, FrameFilenamePattern % CurrentFrame)
    else:
        time.sleep(stabilization_delay_value.get()/1000)   # Allow time to stabilize image, it can get too fast with PiCamera2
        if mode == 'still':
            captured_image = camera.capture_image("main")
            captured_image.save(StillFrameFilenamePattern % (CurrentFrame,CurrentStill))
            CurrentStill += 1
        else:
            if HdrCaptureActive:
                # Stabilization delay for HDR managed inside capture_hdr
                capture_hdr(mode)
            else:
                capture_single(mode)

    SessionData["CurrentDate"] = str(datetime.now())
    SessionData["CurrentFrame"] = str(CurrentFrame)


def start_scan_simulated():
    global CurrentDir
    global CurrentFrame
    global ScanOngoing
    global CurrentScanStartFrame, CurrentScanStartTime
    global simulated_captured_frame_list, simulated_images_in_list
    global ScanStopRequested
    global total_wait_time_autoexp, total_wait_time_awb, total_wait_time_preview_display, session_start_time, total_wait_time_save_image
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
        arrange_custom_spinboxes_status(win)
        last_frame_time = time.time() + 3

        # Enable/Disable related buttons
        button_status_change_except(Start_btn, ScanOngoing)

        # Reset time counters
        total_wait_time_save_image = 0
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
    arrange_custom_spinboxes_status(win)

    # Enable/Disable related buttons
    button_status_change_except(Start_btn, ScanOngoing)


def capture_loop_simulated():
    global CurrentDir, CurrentFrame
    global FramesPerMinute, FramesToGo, frames_to_go_str, time_to_go_str, frames_to_go_entry, time_to_go_time
    global NewFrameAvailable
    global ScanOngoing
    global simulated_capture_image
    global simulated_captured_frame_list, simulated_images_in_list
    global ScanStopRequested
    global total_wait_time_autoexp, total_wait_time_awb, total_wait_time_preview_display, session_start_time, total_wait_time_save_image
    global session_frames
    global SessionData
    global Scanned_Images_time_str, Scanned_Images_Fpm_str
    global disk_space_error_to_notify
    global frames_to_go_key_press_time

    if ScanStopRequested:
        stop_scan_simulated()
        ScanStopRequested = False
        curtime = time.time()
        if ExpertMode:
            logging.debug("Total session time: %s seg for %i frames (%i ms per frame)",
                         str(round((curtime-session_start_time),1)),
                         session_frames,
                         round(((curtime-session_start_time)*1000/session_frames),1))
            logging.debug("Total time to save images: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_save_image),1)),
                         round((total_wait_time_save_image*1000/session_frames),1))
            logging.debug("Total time to display preview image: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_preview_display),1)),
                         round((total_wait_time_preview_display*1000/session_frames),1))
            logging.debug("Total time waiting for AWB adjustment: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_awb),1)),
                         round((total_wait_time_awb*1000/session_frames),1))
            logging.debug("Total time waiting for AE adjustment: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_autoexp),1)),
                         round((total_wait_time_autoexp*1000/session_frames),1))
        if disk_space_error_to_notify:
            tk.messagebox.showwarning("Disk space low",
                                      f"Running out of disk space, only {int(available_space_mb)} MB remain. Please delete some files before continuing current scan.")
            disk_space_error_to_notify = False
    if ScanOngoing:
        os.chdir(CurrentDir)
        frame_to_display = CurrentFrame % simulated_images_in_list
        filename, ext = os.path.splitext(simulated_captured_frame_list[frame_to_display])
        if ext == '.jpg':
            simulated_capture_image = Image.open(simulated_captured_frame_list[frame_to_display])
            if negative_image.get():
                simulated_capture_image = reverse_image(simulated_capture_image)
            draw_preview_image(simulated_capture_image, 0)

        # Update remaining time
        aux = frames_to_go_str.get()
        if aux.isdigit() and time.time() > frames_to_go_key_press_time:
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
        Scanned_Images_number_str.set(str(CurrentFrame))
        # Update film time
        fps = 18 if SessionData["FilmType"] == "S8" else 16
        film_time = f"Film time: {(CurrentFrame//fps)//60:02}:{(CurrentFrame//fps)%60:02}"
        Scanned_Images_time_str.set(film_time)
        # Update Frames per Minute
        scan_period_frames = CurrentFrame - CurrentScanStartFrame
        if FPM_CalculatedValue == -1:  # FPM not calculated yet, display some indication
            aux_str = ''.join([char*int(scan_period_frames) for char in '.'])
            Scanned_Images_Fpm_str.set(f"Frames/Min: {aux_str}")
        else:
            FramesPerMinute = FPM_CalculatedValue
            Scanned_Images_Fpm_str.set(f"Frames/Min: {FramesPerMinute}")

        # Invoke capture_loop one more time, as long as scan is ongoing
        win.after(500, capture_loop_simulated)

        # display rolling averages
        time_save_image_value.set(int(time_save_image.get_average()*1000) if time_save_image.get_average() is not None else 0)
        time_preview_display_value.set(int(time_preview_display.get_average()*1000) if time_preview_display.get_average() is not None else 0)
        time_awb_value.set(int(time_awb.get_average()*1000) if time_awb.get_average() is not None else 0)
        time_autoexp_value.set(int(time_autoexp.get_average()*1000) if time_autoexp.get_average() is not None else 0)

        if session_frames % 50 == 0 and not disk_space_available():  # Only every 50 frames (500MB buffer exist)
            logging.error("No disk space available, stopping scan process.")
            if ScanOngoing:
                ScanStopRequested = True  # Stop in next capture loop


def start_scan():
    global CurrentDir, CurrentFrame
    global SessionData
    global ScanOngoing
    global CurrentScanStartFrame, CurrentScanStartTime
    global save_bg, save_fg
    global SimulatedRun
    global ScanStopRequested
    global NewFrameAvailable
    global total_wait_time_autoexp, total_wait_time_awb, total_wait_time_preview_display, session_start_time, total_wait_time_save_image
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
        arrange_custom_spinboxes_status(win)
        last_frame_time = time.time() + 3

        # Set new frame indicator to false, in case this is the cause of the strange
        # behaviour after stopping/restarting the scan process
        NewFrameAvailable = False

        # Enable/Disable related buttons
        button_status_change_except(Start_btn, ScanOngoing)

        # Reset time counters
        total_wait_time_save_image = 0
        total_wait_time_preview_display = 0
        total_wait_time_awb = 0
        total_wait_time_autoexp = 0
        session_start_time = time.time()
        session_frames = 0

        # Send command to Arduino to start scan (as applicable, Arduino keeps its own status)
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
    arrange_custom_spinboxes_status(win)

    # Send command to Arduino to stop scan (as applicable, Arduino keeps its own status)
    if not SimulatedRun:
        logging.debug("Sending CMD_STOP_SCAN")
        send_arduino_command(CMD_STOP_SCAN)

    # Enable/Disable related buttons
    button_status_change_except(Start_btn, ScanOngoing)


def capture_loop():
    global CurrentDir
    global CurrentFrame
    global SessionData
    global FramesPerMinute, FramesToGo, frames_to_go_str, time_to_go_str
    global NewFrameAvailable
    global ScanProcessError, ScanProcessError_LastTime
    global ScanOngoing
    global SimulatedRun
    global ScanStopRequested
    global total_wait_time_autoexp, total_wait_time_awb, total_wait_time_preview_display, session_start_time, total_wait_time_save_image
    global session_frames, CurrentStill
    global Scanned_Images_time_str, Scanned_Images_Fpm_str
    global disk_space_error_to_notify
    global frames_to_go_key_press_time

    if ScanStopRequested:
        stop_scan()
        ScanStopRequested = False
        curtime = time.time()
        if ExpertMode and session_frames > 0:
            logging.debug("Total session time: %s seg for %i frames (%i ms per frame)",
                         str(round((curtime-session_start_time),1)),
                         session_frames,
                         round(((curtime-session_start_time)*1000/session_frames),1))
            logging.debug("Total time to save images: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_save_image),1)),
                         round((total_wait_time_save_image*1000/session_frames),1))
            logging.debug("Total time to display preview image: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_preview_display),1)),
                         round((total_wait_time_preview_display*1000/session_frames),1))
            logging.debug("Total time waiting for AWB adjustment: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_awb),1)),
                         round((total_wait_time_awb*1000/session_frames),1))
            logging.debug("Total time waiting for AE adjustment: %s seg, (%i ms per frame)",
                         str(round((total_wait_time_autoexp),1)),
                         round((total_wait_time_autoexp*1000/session_frames),1))
        if disk_space_error_to_notify:
            tk.messagebox.showwarning("Disk space low", f"Running out of disk space, only {int(available_space_mb)} MB remain. Please delete some files before continuing current scan.")
            disk_space_error_to_notify = False
    elif ScanOngoing:
        if NewFrameAvailable:
            # Update remaining time
            aux = frames_to_go_str.get()
            if aux.isdigit() and time.time() > frames_to_go_key_press_time:
                FramesToGo = int(aux)
                if FramesToGo > 0:
                    FramesToGo -= 1
                    frames_to_go_str.set(str(FramesToGo))
                    SessionData["FramesToGo"] = FramesToGo
                    if FramesPerMinute != 0:
                        minutes_pending = FramesToGo // FramesPerMinute
                        time_to_go_str.set(f"Time to go: {(minutes_pending // 60):02} h, {(minutes_pending % 60):02} m")
                else:
                    ScanStopRequested = True  # Stop in next capture loop
                    SessionData["FramesToGo"] = -1
                    frames_to_go_str.set('')    # clear frames to go box to prevent it stops again in next scan
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
            # with open(PersistedDataFilename, 'w') as f:
            #     json.dump(SessionData, f)

            # Update number of captured frames
            Scanned_Images_number_str.set(str(CurrentFrame))
            # Update film time
            fps = 18 if SessionData["FilmType"] == "S8" else 16
            film_time = f"Film time: {(CurrentFrame // fps) // 60:02}:{(CurrentFrame // fps) % 60:02}"
            Scanned_Images_time_str.set(film_time)
            # Update Frames per Minute
            scan_period_frames = CurrentFrame - CurrentScanStartFrame
            if FPM_CalculatedValue == -1:   # FPM not calculated yet, display some indication
                aux_str = ''.join([char * int(scan_period_frames) for char in '.'])
                Scanned_Images_Fpm_str.set(f"Frames/Min: {aux_str}")
            else:
                FramesPerMinute = FPM_CalculatedValue
                Scanned_Images_Fpm_str.set(f"Frames/Min: {FPM_CalculatedValue}")
            if session_frames % 50 == 0 and not disk_space_available():  # Only every 50 frames (500MB buffer exist)
                logging.error("No disk space available, stopping scan process.")
                if ScanOngoing:
                    ScanStopRequested = True  # Stop in next capture loop
        elif ScanProcessError:
            if ScanProcessError_LastTime != 0:
                if time.time() - ScanProcessError_LastTime <= 5:     # Second error in less than 5 seconds: Stop
                    curtime = time.ctime()
                    logging.error("Too many errors during scan process, stopping.")
                    ScanProcessError = False
                    if ScanOngoing:
                        ScanStopRequested = True  # Stop in next capture loop
            ScanProcessError_LastTime = time.time()
            ScanProcessError = False
            if not ScanStopRequested:
                NewFrameAvailable = True    # Simulate new frame to continue scan
                logging.warning(f"Error during scan process, frame {CurrentFrame}, simulating new frame. Maybe misaligned.")

        # display rolling averages
        if ExperimentalMode:
            time_save_image_value.set(int(time_save_image.get_average()*1000) if time_save_image.get_average() is not None else 0)
            time_preview_display_value.set(int(time_preview_display.get_average()*1000) if time_preview_display.get_average() is not None else 0)
            time_awb_value.set(int(time_awb.get_average()*1000) if time_awb.get_average() is not None else 0)
            time_autoexp_value.set(int(time_autoexp.get_average()*1000) if time_autoexp.get_average() is not None else 0)

        # Invoke capture_loop one more time, as long as scan is ongoing
        win.after(5, capture_loop)


def temp_in_fahrenheit_selection():
    global temp_in_fahrenheit
    global TempInFahrenheit
    TempInFahrenheit = temp_in_fahrenheit.get()
    SessionData["TempInFahrenheit"] = str(TempInFahrenheit)


def temperature_check():
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
        last_temp = RPiTemp
        LastTempInFahrenheit = TempInFahrenheit


def frames_to_go_key_press(event):
    global frames_to_go_key_press_time
    # Block keyboard entry if the flag is set
    if event.keysym not in {'1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
                            'KP_1', 'KP_2', 'KP_3', 'KP_4', 'KP_5', 'KP_6', 'KP_7', 'KP_8', 'KP_9', 'KP_0',
                            'Delete', 'BackSpace', 'Left', 'Right'}:
        return "break"
    else:
        frames_to_go_key_press_time = time.time() + 5   # 5 sec guard time to allow typing entire number


def preview_check():
    global real_time_display

    if SimulatedRun or CameraDisabled:
        return

    if real_time_display.get() and not camera._preview:
        real_time_display.set(False)
        set_real_time_display()

def onesec_periodic_checks():  # Update RPi temperature every 10 seconds
    global onesec_after

    temperature_check()
    preview_check()

    if not ExitingApp:
        onesec_after = win.after(1000, onesec_periodic_checks)


def set_file_type(event):
    SessionData["FileType"] = file_type_dropdown_selected.get()


def set_resolution(event):
    global max_inactivity_delay, camera_resolutions
    SessionData["CaptureResolution"] = resolution_dropdown_selected.get()
    camera_resolutions.set_active(resolution_dropdown_selected.get())
    if resolution_dropdown_selected.get() == "4056x3040":
        max_inactivity_delay = reference_inactivity_delay * 2
    else:
        max_inactivity_delay = reference_inactivity_delay
    send_arduino_command(CMD_SET_STALL_TIME, max_inactivity_delay)
    logging.debug(f"Set max_inactivity_delay as {max_inactivity_delay}")

    PiCam2_change_resolution()


def UpdatePlotterWindow(PTValue, ThresholdLevel):
    global plotter_canvas
    global MaxPT, MinPT, PrevPTValue, PrevThresholdLevel
    global plotter_width, plotter_height

    if plotter_canvas == None:
        logging.error("Plotter canvas does not exist, exiting...")
        return

    if PTValue > MaxPT * 10:
        logging.warning("PT level too high, ignoring it")
        return

    MaxPT = max(MaxPT,PTValue)
    MinPT = min(MinPT,PTValue)
    plotter_canvas.create_text(10, 5, text=str(MaxPT), anchor='nw', font=f"Helvetica {8}")
    plotter_canvas.create_text(10, plotter_height - 15, text=str(MinPT), anchor='nw', font=f"Helvetica {8}")
    # Shift the graph to the left
    for item in plotter_canvas.find_all():
        plotter_canvas.move(item, -5, 0)

    usable_height = plotter_height - 15
    # Delete lines moving out of the canvas
    for item in plotter_canvas.find_overlapping(-10,0,0, usable_height):
        plotter_canvas.delete(item)

    # Draw the new line segment for PT Level
    plotter_canvas.create_line(plotter_width-6, 15+usable_height-(PrevPTValue/(MaxPT/usable_height)), plotter_width-1, 15+usable_height-(PTValue/(MaxPT/usable_height)), width=1, fill="blue")
    # Draw the new line segment for threshold
    if (ThresholdLevel > MaxPT):
        logging.debug(f"ThresholdLevel value is wrong ({ThresholdLevel}), replacing by previous ({PrevThresholdLevel})")
        ThresholdLevel = PrevThresholdLevel     # Swap by previous if bigger than MaxPT, sometimes I2C losses second parameter, no idea why
    plotter_canvas.create_line(plotter_width-6, 15+usable_height-(PrevThresholdLevel/(MaxPT/usable_height)), plotter_width-1, 15+usable_height-(ThresholdLevel/(MaxPT/usable_height)), width=1, fill="red")
    PrevPTValue = PTValue
    PrevThresholdLevel = ThresholdLevel
    if MaxPT > 100:  # Do not allow below 100
        MaxPT-=1 # Dynamic max
    if MinPT < 800:  # Do not allow above 800
        MinPT+=1 # Dynamic min


# send_arduino_command: No response expected
def send_arduino_command(cmd, param=0):
    global SimulatedRun, ALT_Scann8_controller_detected
    global i2c
    global CurrentFrame

    if not SimulatedRun:
        time.sleep(0.0001)  #wait 100 µs, to avoid I/O errors
        try:
            i2c.write_i2c_block_data(16, cmd, [int(param % 256), int(param >> 8)])  # Send command to Arduino
        except IOError:
            logging.warning(f"Error while sending command {cmd} (param {param}) to Arduino while handling frame {CurrentFrame}. Retrying...")
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
    global last_frame_time, max_inactivity_delay
    global Controller_Id
    global ScanStopRequested
    global i2c, arduino_after

    if not SimulatedRun:
        try:
            ArduinoData = i2c.read_i2c_block_data(16, CMD_GET_CNT_STATUS, 5)
            ArduinoTrigger = ArduinoData[0]
            ArduinoParam1 = ArduinoData[1] * 256 + ArduinoData[2]
            ArduinoParam2 = ArduinoData[3] * 256 + ArduinoData[4]   # Sometimes this part arrives as 255, 255, no idea why
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
        last_frame_time = time.time() + int(max_inactivity_delay*0.34)      # Delay shared with arduino, 1/3rd less to avoid conflict with end reel
        NewFrameAvailable = True
        logging.warning("More than %i sec. since last command: Forcing new "
                        "frame event (frame %i).", int(max_inactivity_delay*0.34), CurrentFrame)

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
        last_frame_time = time.time() + max_inactivity_delay - 2    # Delay shared with arduino, 2 seconds less to avoid conflict with end reel
        NewFrameAvailable = True
    elif ArduinoTrigger == RSP_SCAN_ERROR:  # Error during scan
        logging.warning("Received scan error from Arduino (%i, %i)", ArduinoParam1, ArduinoParam2)
        ScanProcessError = True
    elif ArduinoTrigger == RSP_SCAN_ENDED:  # Scan arrived at the end of the reel
        logging.warning("End of reel reached: Scan terminated")
        ScanStopRequested = True
    elif ArduinoTrigger == RSP_REPORT_AUTO_LEVELS:  # Get auto levels from Arduino, to be displayed in UI, if auto on
        if ExpertMode:
            if (auto_pt_level_enabled.get()):
                pt_level_value.set(ArduinoParam1)
            if (auto_framesteps_enabled.get()):
                steps_per_frame_value.set(ArduinoParam2)
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
            UpdatePlotterWindow(ArduinoParam1, ArduinoParam2)
    elif ArduinoTrigger == RSP_FILM_FORWARD_ENDED:
        logging.warning("Received film forward end from Arduino")
        advance_movie(True)
    else:
        logging.warning("Unrecognized incoming event (%i) from Arduino.", ArduinoTrigger)

    if ArduinoTrigger != 0:
        ArduinoTrigger = 0

    if not ExitingApp:
        arduino_after = win.after(10, arduino_listen_loop)


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
    global TempInFahrenheit
    global temp_in_fahrenheit_checkbox
    global PersistedDataLoaded
    global camera

    for item in SessionData:
        logging.debug("%s=%s", item, str(SessionData[item]))
    if PersistedDataLoaded:
        logging.debug("SessionData loaded from disk:")
        if 'TempInFahrenheit' in SessionData:
            TempInFahrenheit = eval(SessionData["TempInFahrenheit"])
            if TempInFahrenheit:
                temp_in_fahrenheit_checkbox.select()
        if ExpertMode:
            if 'MatchWaitMargin' in SessionData:
                aux = int(SessionData["MatchWaitMargin"])
                match_wait_margin_value.set(aux)
            else:
                match_wait_margin_value.set(50)
            if 'CaptureStabilizationDelay' in SessionData:
                aux = float(SessionData["CaptureStabilizationDelay"])
                stabilization_delay_value.set(round(aux * 1000))
            else:
                stabilization_delay_value.set(100)

        if ExperimentalMode:
            if 'SharpnessValue' in SessionData:
                SharpnessValue = int(SessionData["SharpnessValue"])     # In case it is stored as string
                sharpness_control_value.set(SharpnessValue)
                if not SimulatedRun and not CameraDisabled:
                    camera.set_controls({"Sharpness": SharpnessValue})
            else:
                sharpness_control_value.set(1)


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


def arrange_custom_spinboxes_status(widget):
    widgets = widget.winfo_children()
    for widget in widgets:
        if isinstance(widget, DynamicSpinbox):
            widget.set_custom_state('block_kbd_entry' if ScanOngoing else 'normal')
        elif isinstance(widget, tk.Frame) or isinstance(widget, tk.LabelFrame):
            arrange_custom_spinboxes_status(widget)



def load_session_data():
    global SessionData
    global CurrentDir
    global CurrentFrame, FramesToGo
    global folder_frame_target_dir
    global hdr_btn
    global AwbPause
    global awb_red_wait_checkbox, awb_blue_wait_checkbox
    global auto_exp_wait_checkbox
    global PersistedDataLoaded
    global MinFrameStepsS8, MinFrameStepsR8
    global PTLevelS8, PTLevelR8
    global hdr_capture_active_checkbox, HdrCaptureActive
    global hdr_viewx4_active_checkbox, HdrViewX4Active
    global hdr_bracket_width_auto_checkbox
    global HdrBracketAuto, hdr_bracket_auto, hdr_max_exp_spinbox, hdr_min_exp_spinbox
    global HdrMergeInPlace, hdr_merge_in_place
    global exposure_btn, wb_red_btn, wb_blue_btn, exposure_spinbox, wb_red_spinbox, wb_blue_spinbox
    global frames_to_go_str
    global max_inactivity_delay
    global Scanned_Images_number_str

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
                Scanned_Images_number_str.set(SessionData["CurrentFrame"])
            if 'FramesToGo' in SessionData:
                if SessionData["FramesToGo"] != -1:
                    FramesToGo = int(SessionData["FramesToGo"])
                    frames_to_go_str.set(str(FramesToGo))
            if 'FilmType' in SessionData:
                film_type.set(SessionData["FilmType"])
                if SessionData["FilmType"] == "R8":
                    set_r8()
                elif SessionData["FilmType"] == "S8":
                    set_s8()
            if 'FileType' in SessionData:
                file_type_dropdown_selected.set(SessionData["FileType"])
            if 'CaptureResolution' in SessionData:
                valid_resolution_list = camera_resolutions.get_list()
                selected_resolution = SessionData["CaptureResolution"]
                if selected_resolution not in valid_resolution_list:
                    if selected_resolution+' *'  in valid_resolution_list:
                        selected_resolution = selected_resolution + ' *'
                    else:
                        selected_resolution = valid_resolution_list[0]
                resolution_dropdown_selected.set(selected_resolution)
                if resolution_dropdown_selected.get() =="4056x3040":
                    max_inactivity_delay = reference_inactivity_delay * 2
                else:
                    max_inactivity_delay = reference_inactivity_delay
                send_arduino_command(CMD_SET_STALL_TIME, max_inactivity_delay)
                logging.debug(f"max_inactivity_delay: {max_inactivity_delay}")
                PiCam2_change_resolution()
            if 'NegativeCaptureActive' in SessionData:
                negative_image.set(SessionData["NegativeCaptureActive"])
                set_negative_image()
            if 'AutoStopType' in SessionData:
                autostop_type.set(SessionData["AutoStopType"])
            if 'AutoStopActive' in SessionData:
                auto_stop_enabled.set(SessionData["AutoStopActive"])
                set_auto_stop_enabled()
            if ExperimentalMode:
                if 'HdrCaptureActive' in SessionData:
                    HdrCaptureActive = eval(SessionData["HdrCaptureActive"])
                    hdr_set_controls()
                    if HdrCaptureActive:
                        max_inactivity_delay = reference_inactivity_delay * 2
                        send_arduino_command(CMD_SET_STALL_TIME, max_inactivity_delay)
                        logging.debug(f"max_inactivity_delay: {max_inactivity_delay}")
                        hdr_capture_active_checkbox.select()
                if 'HdrViewX4Active' in SessionData:
                    HdrViewX4Active = eval(SessionData["HdrViewX4Active"])
                    if HdrViewX4Active and ExpertMode:
                        hdr_viewx4_active_checkbox.select()
                if 'HdrMinExp' in SessionData:
                    aux = int(SessionData["HdrMinExp"])
                    if ExpertMode:
                        hdr_min_exp_value.set(aux)
                elif ExpertMode:
                    hdr_min_exp_value.set(hdr_lower_exp)
                if 'HdrMaxExp' in SessionData:
                    aux = int(SessionData["HdrMaxExp"])
                    if ExpertMode:
                        hdr_max_exp_value.set(aux)
                elif ExpertMode:
                    hdr_max_exp_value.set(hdr_higher_exp)
                if 'HdrBracketAuto' in SessionData:
                    HdrBracketAuto = SessionData["HdrBracketAuto"]
                    hdr_bracket_auto.set(HdrBracketAuto)
                elif ExpertMode:
                    hdr_bracket_auto.set(hdr_higher_exp-hdr_lower_exp)
                if 'HdrMergeInPlace' in SessionData:
                    HdrMergeInPlace = SessionData["HdrMergeInPlace"]
                    hdr_merge_in_place.set(HdrMergeInPlace)
                if 'HdrBracketWidth' in SessionData:
                    aux = int(SessionData["HdrBracketWidth"])
                    hdr_bracket_width_value.set(aux)
                if 'HdrBracketShift' in SessionData:
                    aux = SessionData["HdrBracketShift"]
                    hdr_bracket_shift_value.set(aux)
            if ExpertMode:
                if 'CurrentExposure' in SessionData:
                    aux = SessionData["CurrentExposure"]
                    if isinstance(aux, str) and (aux == "Auto" or aux == "0") or isinstance(aux, int) and aux == 0:
                        aux = 0
                        AE_enabled.set(True)
                        auto_exp_wait_checkbox.config(state=NORMAL)
                    else:
                        if isinstance(aux, str):
                            aux = int(float(aux))
                        AE_enabled.set(False)
                        auto_exp_wait_checkbox.config(state=DISABLED)
                    if not SimulatedRun and not CameraDisabled:
                        camera.controls.ExposureTime = int(aux)
                    exposure_value.set(aux/1000)
                if 'ExposureAdaptPause' in SessionData:
                    if isinstance(SessionData["ExposureAdaptPause"], bool):
                        aux = SessionData["ExposureAdaptPause"]
                    else:
                        aux = eval(SessionData["ExposureAdaptPause"])
                    auto_exposure_change_pause.set(aux)
                    auto_exp_wait_checkbox.config(state=NORMAL if exposure_value.get() == 0 else DISABLED)
                    ###if auto_exposure_change_pause.get():
                    ###    auto_exp_wait_checkbox.select()
                if 'CurrentAwbAuto' in SessionData:
                    if isinstance(SessionData["CurrentAwbAuto"], bool):
                        AWB_enabled.set(SessionData["CurrentAwbAuto"])
                    else:
                        AWB_enabled.set(eval(SessionData["CurrentAwbAuto"]))
                    wb_blue_spinbox.config(state='readonly' if AWB_enabled.get() else NORMAL)
                    wb_red_spinbox.config(state='readonly' if AWB_enabled.get() else NORMAL)
                    awb_red_wait_checkbox.config(state=NORMAL if AWB_enabled.get() else DISABLED)
                    ###awb_blue_wait_checkbox.config(state=NORMAL if AWB_enabled.get() else DISABLED)
                    ###arrange_widget_state(AWB_enabled.get(), [wb_blue_btn, wb_blue_spinbox])
                    arrange_widget_state(AWB_enabled.get(), [wb_red_btn, wb_red_spinbox])
                    '''
                    if AWB_enabled.get():
                        wb_red_btn.config(fg="white", text="AUTO AWB Red:")
                        wb_blue_btn.config(fg="white", text="AUTO AWB Blue:")
                    else:
                        wb_red_btn.config(fg="black", text="AWB Red:")
                        wb_blue_btn.config(fg="black", text="AWB Blue:")
                    '''
                if 'AwbPause' in SessionData:
                    AwbPause = eval(SessionData["AwbPause"])
                    if AwbPause:
                        awb_red_wait_checkbox.select()
                        ###awb_blue_wait_checkbox.select()
                if 'GainRed' in SessionData:
                    aux = float(SessionData["GainRed"])
                    wb_red_value.set(round(aux,1))
                if 'GainBlue' in SessionData:
                    aux = float(SessionData["GainBlue"])
                    wb_blue_value.set(round(aux,1))
                # Recover frame alignment values
                if 'MinFrameSteps' in SessionData:
                    MinFrameSteps = int(SessionData["MinFrameSteps"])
                    steps_per_frame_value.set(MinFrameSteps)
                    send_arduino_command(CMD_SET_MIN_FRAME_STEPS, MinFrameSteps)
                if 'FrameStepsAuto' in SessionData:
                    auto_framesteps_enabled.set(SessionData["FrameStepsAuto"])
                    if auto_framesteps_enabled.get():
                        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0)
                    else:
                        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, steps_per_frame_value.get())
                if 'MinFrameStepsS8' in SessionData:
                    MinFrameStepsS8 = SessionData["MinFrameStepsS8"]
                if 'MinFrameStepsR8' in SessionData:
                    MinFrameStepsR8 = SessionData["MinFrameStepsR8"]
                if 'FrameFineTune' in SessionData:
                    aux = SessionData["FrameFineTune"]
                    frame_fine_tune_value.set(aux)
                    send_arduino_command(CMD_SET_FRAME_FINE_TUNE, aux)
                if 'FrameExtraSteps' in SessionData:
                    aux = SessionData["FrameExtraSteps"]
                    aux = min(aux, 20)
                    frame_extra_steps_value.set(aux)
                    send_arduino_command(CMD_SET_EXTRA_STEPS, aux)
                if 'PTLevelAuto' in SessionData:
                    auto_pt_level_enabled.set(SessionData["PTLevelAuto"])
                    if auto_pt_level_enabled.get():
                        send_arduino_command(CMD_SET_PT_LEVEL, 0)
                    else:
                        send_arduino_command(CMD_SET_PT_LEVEL, pt_level_value.get())
                if 'PTLevel' in SessionData:
                    PTLevel = int(SessionData["PTLevel"])
                    pt_level_value.set(PTLevel)
                    if not auto_pt_level_enabled.get():
                        send_arduino_command(CMD_SET_PT_LEVEL, PTLevel)
                if 'PTLevelS8' in SessionData:
                    PTLevelS8 = SessionData["PTLevelS8"]
                if 'PTLevelR8' in SessionData:
                    PTLevelR8 = SessionData["PTLevelR8"]
                if 'ScanSpeed' in SessionData:
                    aux = int(SessionData["ScanSpeed"])
                    scan_speed_value.set(aux)
                    send_arduino_command(CMD_SET_SCAN_SPEED, aux)

    # Update widget state whether or not config loaded (to honor app default values)
    if ExpertMode:
        arrange_widget_state(AE_enabled.get(), [exposure_btn, exposure_spinbox])
        arrange_widget_state(auto_pt_level_enabled.get(), [pt_level_btn, pt_level_spinbox])
        arrange_widget_state(auto_framesteps_enabled.get(), [steps_per_frame_btn, steps_per_frame_spinbox])
    if ExperimentalMode:
        hdr_set_controls()
        if HdrCaptureActive:  # If HDR enabled, handle automatic control settings for widgets
            arrange_widget_state(HdrBracketAuto, [hdr_max_exp_spinbox, hdr_min_exp_spinbox])


def reinit_controller():
    if not ExpertMode:
        return

    if auto_pt_level_enabled.get():
        send_arduino_command(CMD_SET_PT_LEVEL, 0)
    else:
        send_arduino_command(CMD_SET_PT_LEVEL, pt_level_value.get())

    if auto_framesteps_enabled.get():
        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0)
    else:
        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, steps_per_frame_value.get())

    if 'FilmType' in SessionData:
        if SessionData["FilmType"] == "R8":
            send_arduino_command(CMD_SET_REGULAR_8)
        else:
            send_arduino_command(CMD_SET_SUPER_8)

    send_arduino_command(CMD_SET_FRAME_FINE_TUNE, frame_fine_tune_value.get())
    send_arduino_command(CMD_SET_EXTRA_STEPS, frame_extra_steps_value.get())
    send_arduino_command(CMD_SET_SCAN_SPEED, scan_speed_value.get())


def PiCam2_change_resolution():
    global camera, capture_config, preview_config, camera_resolutions

    target_res = resolution_dropdown_selected.get()
    camera_resolutions.set_active(target_res)
    if SimulatedRun or CameraDisabled:
        return      # Skip camera specific part

    capture_config["main"]["size"] = camera_resolutions.get_image_resolution()
    #capture_config["main"]["format"] = camera_resolutions.get_format()
    capture_config["raw"]["size"] = camera_resolutions.get_sensor_resolution()
    capture_config["raw"]["format"] = camera_resolutions.get_format()
    camera.stop()
    camera.configure(capture_config)
    camera.start()


def PiCam2_configure():
    global camera, capture_config, preview_config, camera_resolutions

    camera.stop()
    capture_config = camera.create_still_configuration(main={"size": camera_resolutions.get_sensor_resolution()},
                        raw={"size": camera_resolutions.get_sensor_resolution(), "format": camera_resolutions.get_format()},
                        transform=Transform(hflip=True))

    preview_config = camera.create_preview_configuration({"size": (2028, 1520)}, transform=Transform(hflip=True))
    # Camera preview window is not saved in configuration, so always off on start up (we start in capture mode)
    camera.configure(capture_config)
    camera.set_controls({"ExposureTime": 0})    # Auto exposure by default, overridden by configuration if any
    camera.set_controls({"AnalogueGain": 1.0})
    camera.set_controls({"AwbEnable": 0})
    camera.set_controls({"ColourGains": (2.2, 2.2)})  # Red 2.2, Blue 2.2 seem to be OK
    # In PiCamera2, '1' is the standard sharpness
    # It can be a floating point number from 0.0 to 16.0
    camera.set_controls({"Sharpness": 1})   # Set default, overridden by configuration if any
    # draft.NoiseReductionModeEnum.HighQuality not defined, yet
    # However, looking at the PiCamera2 Source Code, it seems the default value for still configuration
    # is already HighQuality, so not much to worry about
    # camera.set_controls({"NoiseReductionMode": draft.NoiseReductionModeEnum.HighQuality})
    # No preview by default
    camera.options['quality'] = 100  # jpeg quality: values from 0 to 100. Reply from David Plowman in PiCam2 list. Test with 60?
    camera.start(show_preview=False)


def hdr_init():
    global hdr_step_value, hdr_exp_list, hdr_rev_exp_list, hdr_num_exposures, hdr_view_4_image

    hdr_view_4_image = Image.new("RGB", (PreviewWidth, PreviewHeight))
    hdr_reinit()

def hdr_reinit():
    global hdr_step_value, hdr_exp_list, hdr_rev_exp_list, hdr_best_exp, hdr_num_exposures, hdr_view_4_image

    if not ExperimentalMode:
        return
    if hdr_num_exposures == 3:
        hdr_exp_list.clear()
        hdr_exp_list += [hdr_min_exp_value.get(), hdr_best_exp, hdr_max_exp_value.get()]
    elif hdr_num_exposures == 5:
        hdr_exp_list.clear()
        hdr_exp_list += [hdr_min_exp_value.get(), hdr_min_exp_value.get() + int((hdr_best_exp-hdr_min_exp_value.get())/2), hdr_best_exp, hdr_best_exp + int((hdr_max_exp_value.get()-hdr_best_exp)/2), hdr_max_exp_value.get()]

    hdr_exp_list.sort()
    logging.debug("hdr_exp_list=%s",hdr_exp_list)
    hdr_rev_exp_list = list(reversed(hdr_exp_list))


def create_main_window():
    global win
    global plotter_width, plotter_height
    global PreviewWinX, PreviewWinY, app_width, app_height, PreviewWidth, PreviewHeight
    global ForceSmallSize, ForceBigSize, FontSize, BigSize
    global TopWinX, TopWinY
    global WinInitDone, as_tooltips

    win = tkinter.Tk()  # creating the main window and storing the window object in 'win'
    if SimulatedRun:
        win.wm_title(string='ALT-Scann8 v' + __version__ + ' ***  SIMULATED RUN, NOT OPERATIONAL ***')
    else:
        win.title('ALT-Scann8 v' + __version__)  # setting title of the window
    # Get screen size - maxsize gives the usable screen size
    screen_width, screen_height = win.maxsize()
    # Set plotter default dimensions
    plotter_width = 240
    plotter_height = 180
    # Set dimensions of UI elements adapted to screen size
    if (screen_height >= 1000 and not ForceSmallSize) or ForceBigSize:
        BigSize = True
        FontSize = 11
        PreviewWidth = 844
        PreviewHeight = int(PreviewWidth/(4/3))
        app_width = PreviewWidth + 500
        app_height = PreviewHeight + 50
        plotter_width += 50
    else:
        BigSize = False
        FontSize = 8
        PreviewWidth = 650
        PreviewHeight = int(PreviewWidth/(4/3))
        app_width = PreviewWidth + 430
        app_height = PreviewHeight + 50
        plotter_height -= 55
    if ExpertMode or ExperimentalMode:
        app_height += 220 if BigSize else 170
    # Prevent window resize
    win.minsize(app_width, app_height)
    win.maxsize(app_width, app_height)
    win.geometry(f'{app_width}x{app_height-20}')  # setting the size of the window
    if 'WindowPos' in SessionData:
        win.geometry(f"+{SessionData['WindowPos'].split('+', 1)[1]}")

    # Init ToolTips
    as_tooltips = Tooltips(FontSize)

    create_widgets()

    # Get Top window coordinates
    TopWinX = win.winfo_x()
    TopWinY = win.winfo_y()

    # Change preview coordinated for PiCamera2 to avoid confusion with overlay mode in PiCamera legacy
    PreviewWinX = 250
    PreviewWinY = 150
    WinInitDone = True


def tscann8_init():
    global camera
    global i2c
    global CurrentDir, CurrentFrame
    global ZoomSize
    global capture_config, preview_config
    global LogLevel, ExperimentalMode, PlotterMode
    global capture_display_queue, capture_display_event
    global capture_save_queue, capture_save_event
    global MergeMertens, camera_resolutions
    global active_threads
    global time_save_image, time_preview_display, time_awb, time_autoexp


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
    logging.info("Config file: %s", PersistedDataFilename)

    if SimulatedRun:
        logging.info("Not running on Raspberry Pi, simulated run for UI debugging purposes only")
    else:
        logging.info("Running on Raspberry Pi")

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

    if not SimulatedRun and not CameraDisabled: # Init PiCamera2 here, need resolution list for drop down
        camera = Picamera2()
        camera_resolutions = CameraResolutions(camera.sensor_modes)
        logging.info(f"Camera Sensor modes: {camera.sensor_modes}")
        PiCam2_configure()
        ZoomSize = camera.capture_metadata()['ScalerCrop'][2:]
    if SimulatedRun:
        camera_resolutions = CameraResolutions(simulated_sensor_modes)   # Initializes resolution list from a hardcoded sensor_modes

    # Initialize rolling average objects
    time_save_image = RollingAverage(50)
    time_preview_display = RollingAverage(50)
    time_awb = RollingAverage(50)
    time_autoexp = RollingAverage(50)

    create_main_window()

    # Init HDR variables
    hdr_init()
    # Create MergeMertens Object for HDR
    MergeMertens = cv2.createMergeMertens()

    reset_controller()

    get_controller_version()

    send_arduino_command(CMD_REPORT_PLOTTER_INFO, PlotterMode)

    win.update_idletasks()

    if not SimulatedRun and not CameraDisabled:
        # JRE 20/09/2022: Attempt to speed up overall process in PiCamera2 by having captured images
        # displayed in the preview area by a dedicated thread, so that time consumed in this task
        # does not impact the scan process speed
        capture_display_queue = queue.Queue(maxsize=MaxQueueSize)
        capture_display_event = threading.Event()
        capture_save_queue = queue.Queue(maxsize=MaxQueueSize)
        capture_save_event = threading.Event()
        display_thread = threading.Thread(target=capture_display_thread, args=(capture_display_queue, capture_display_event,0))
        save_thread_1 = threading.Thread(target=capture_save_thread, args=(capture_save_queue, capture_save_event,1))
        save_thread_2 = threading.Thread(target=capture_save_thread, args=(capture_save_queue, capture_save_event,2))
        save_thread_3 = threading.Thread(target=capture_save_thread, args=(capture_save_queue, capture_save_event,3))
        active_threads += 4
        display_thread.start()
        save_thread_1.start()
        save_thread_2.start()
        save_thread_3.start()
        logging.debug("Threads initialized")

    logging.debug("ALT-Scann 8 initialized")

# **************************************************
# ********** Widget entries validation *************
# **************************************************
def value_normalize(var, min_value, max_value):
    try:
        value = var.get()
    except tk.TclError as e:
        var.set(int((max_value+min_value)/2))
        return min_value
    value = max(value, min_value)
    value = min(value, max_value)
    var.set(value)
    return value


def value_validation(new_value, widget, min, max, is_double=False):
    try:
        if new_value == '':
            new_value = 0
        if is_double:
            aux = float(new_value)
        else:
            aux = int(new_value)
        if min <= aux <= max:
            widget.config(fg='black')
            return True
        elif aux < min or aux > max:
            widget.config(fg='red')
            return True
        else:
            return False
    except (ValueError, TypeError):
        return False



def exposure_spinbox_auto():
    if AE_enabled.get():  # Not in automatic mode, activate auto
        SessionData["CurrentExposure"] = 0
        exposure_value.set(0)
        ###exposure_btn.config(fg="white", text="AUTO Exposure:")
        auto_exp_wait_checkbox.config(state=NORMAL)
        # Do not set 'exposure_value', since ti will be updated dynamically with the current AE value from camera
        if not SimulatedRun and not CameraDisabled:
            camera.controls.ExposureTime = 0  # Set auto exposure (maybe will not work, check pag 26 of picamera2 specs)
    else:
        if not SimulatedRun and not CameraDisabled:
            # Do not retrieve current gain values from Camera (capture_metadata) to prevent conflicts
            # Since we update values in the UI regularly, use those.
            aux = int(exposure_value.get() * 1000)
            camera.set_controls({"ExposureTime": aux})
        else:
            aux = 3500  # Arbitrary Value for Simulated run
        SessionData["CurrentExposure"] = aux

    auto_exp_wait_checkbox.config(state=NORMAL if AE_enabled.get() else DISABLED)
    arrange_widget_state(AE_enabled.get(), [exposure_btn, exposure_spinbox])


def auto_exposure_change_pause_selection():
    SessionData["ExposureAdaptPause"] = auto_exposure_change_pause.get()


def exposure_selection():
    if not ExpertMode or AE_enabled.get():  # Do not allow spinbox changes when in auto mode (should not happen as spinbox is readonly)
        return
    aux = value_normalize(exposure_value, camera_resolutions.get_min_exp()/1000, camera_resolutions.get_max_exp()/1000)
    aux = aux * 1000
    if aux <= 0:
        aux = camera_resolutions.get_min_exp()     # Minimum exposure is 1µs, zero means automatic
    SessionData["CurrentExposure"] = aux

    if not SimulatedRun and not CameraDisabled:
        camera.controls.ExposureTime = int(aux)  # maybe will not work, check pag 26 of picamera2 specs


def exposure_validation(new_value):
    # Use zero instead if minimum exposure from PiCamera2 to prevent flagging in red when selection auto exposure
    #return value_validation(new_value, exposure_spinbox, camera_resolutions.get_min_exp()/1000, camera_resolutions.get_max_exp()/1000, True)
    return value_validation(new_value, exposure_spinbox, 0, camera_resolutions.get_max_exp() / 1000, True)


def wb_red_selection():
    if not ExpertMode or AWB_enabled.get():  # Do not allow spinbox changes when in auto mode (should not happen as spinbox is readonly)
        return

    aux = value_normalize(wb_red_value, 0, 32)
    SessionData["GainRed"] = aux

    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"ColourGains": (aux, wb_blue_value.get())})


def wb_red_validation(new_value):
    return value_validation(new_value, wb_red_spinbox, 0, 32, True)


def wb_blue_selection():
    if not ExpertMode or AWB_enabled.get():  # Do not allow spinbox changes when in auto mode (should not happen as spinbox is readonly)
        return

    aux = value_normalize(wb_blue_value, 0, 32)
    SessionData["GainBlue"] = aux

    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"ColourGains": (wb_red_value.get(), aux)})


def wb_blue_validation(new_value):
    return value_validation(new_value, wb_blue_spinbox, 0, 32, True)


def match_wait_margin_selection():
    if not ExpertMode:
        return
    aux = value_normalize(match_wait_margin_value, 0, 100)
    SessionData["MatchWaitMargin"] = aux


def match_wait_margin_validation(new_value):
    return value_validation(new_value, match_wait_margin_spinbox, 0, 100)


def steps_per_frame_auto():
    arrange_widget_state(auto_framesteps_enabled.get(), [steps_per_frame_btn, steps_per_frame_spinbox])

    SessionData["FrameStepsAuto"] = auto_framesteps_enabled.get()
    send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0 if auto_framesteps_enabled.get() else steps_per_frame_value.get())


def steps_per_frame_selection():
    if auto_framesteps_enabled.get():
        return
    MinFrameSteps = value_normalize(steps_per_frame_value, 100, 600)
    SessionData["MinFrameSteps"] = MinFrameSteps
    SessionData["MinFrameSteps" + SessionData["FilmType"]] = MinFrameSteps
    send_arduino_command(CMD_SET_MIN_FRAME_STEPS, MinFrameSteps)


def steps_per_frame_validation(new_value):
    return value_validation(new_value, steps_per_frame_spinbox, 100, 600)


def pt_level_spinbox_auto():
    arrange_widget_state(auto_pt_level_enabled.get(), [pt_level_btn, pt_level_spinbox])

    SessionData["PTLevelAuto"] = auto_pt_level_enabled.get()
    send_arduino_command(CMD_SET_PT_LEVEL, 0 if auto_pt_level_enabled.get() else pt_level_value.get())


def pt_level_selection():
    if auto_pt_level_enabled.get():
        return
    PTLevel = value_normalize(pt_level_value, 20, 900)
    SessionData["PTLevel"] = PTLevel
    SessionData["PTLevel" + SessionData["FilmType"]] = PTLevel
    send_arduino_command(CMD_SET_PT_LEVEL, PTLevel)


def pt_level_validation(new_value):
    return value_validation(new_value, pt_level_spinbox, 20, 900)


def frame_fine_tune_selection():
    aux = value_normalize(frame_fine_tune_value, 5, 95)
    SessionData["FrameFineTune"] = aux
    SessionData["FrameFineTune" + SessionData["FilmType"]] = aux
    send_arduino_command(CMD_SET_FRAME_FINE_TUNE, aux)


def fine_tune_validation(new_value):
    return value_validation(new_value, frame_fine_tune_spinbox, 5, 95)


def extra_steps_validation(new_value):
    return value_validation(new_value, frame_extra_steps_spinbox, -30, 30)


def scan_speed_selection():
    aux = value_normalize(scan_speed_value, 1, 10)
    SessionData["ScanSpeed"] = aux
    send_arduino_command(CMD_SET_SCAN_SPEED, aux)


def scan_speed_validation(new_value):
    return value_validation(new_value, scan_speed_spinbox, 1, 10)


def stabilization_delay_selection():
    if not ExpertMode:
        return
    aux = value_normalize(stabilization_delay_value, 0, 1000)
    aux = aux/1000
    SessionData["CaptureStabilizationDelay"] = aux


def stabilization_delay_validation(new_value):
    return value_validation(new_value, stabilization_delay_spinbox, 0, 1000)


def hdr_min_exp_selection():
    global force_adjust_hdr_bracket, recalculate_hdr_exp_list

    if not ExpertMode:
        return

    min_exp = value_normalize(hdr_min_exp_value, hdr_lower_exp, 999)
    bracket = hdr_bracket_width_value.get()
    max_exp = min_exp + bracket     # New max based on new min
    if max_exp > 1000:
        bracket -= max_exp -1000    # Reduce bracket in max over the top
        max_exp = 1000
        force_adjust_hdr_bracket = True
    hdr_min_exp_value.set(min_exp)
    hdr_max_exp_value.set(max_exp)
    hdr_bracket_width_value.set(bracket)
    recalculate_hdr_exp_list = True
    SessionData["HdrMinExp"] = min_exp
    SessionData["HdrMaxExp"] = max_exp
    SessionData["HdrBracketWidth"] = bracket


def hdr_min_exp_validation(new_value):
    return value_validation(new_value, hdr_min_exp_spinbox, hdr_lower_exp, 999)


def hdr_max_exp_selection():
    global recalculate_hdr_exp_list
    global force_adjust_hdr_bracket

    if not ExpertMode:
        return

    max_exp = value_normalize(hdr_max_exp_value, 2, 1000)
    bracket = hdr_bracket_width_value.get()
    min_exp = max_exp - bracket
    if min_exp < hdr_lower_exp:
        min_exp = hdr_lower_exp
        bracket = max_exp - min_exp    # Reduce bracket in min below absolute min
        force_adjust_hdr_bracket = True
    hdr_min_exp_value.set(min_exp)
    hdr_max_exp_value.set(max_exp)
    hdr_bracket_width_value.set(bracket)
    recalculate_hdr_exp_list = True
    SessionData["HdrMinExp"] = min_exp
    SessionData["HdrMaxExp"] = max_exp
    SessionData["HdrBracketWidth"] = bracket


def hdr_max_exp_validation(new_value):
    return value_validation(new_value, hdr_max_exp_spinbox, 2, 1000)


def hdr_bracket_width_selection():
    global force_adjust_hdr_bracket

    if not ExpertMode:
        return

    aux_bracket = value_normalize(hdr_bracket_width_value, hdr_min_bracket_width, hdr_max_bracket_width)

    middle_exp = int((hdr_min_exp_value.get() + (hdr_max_exp_value.get()-hdr_min_exp_value.get()))/2)
    hdr_min_exp_value.set(int(middle_exp - (aux_bracket/2)))
    if hdr_min_exp_value.get() < hdr_lower_exp:
        hdr_min_exp_value.set(hdr_lower_exp)
        hdr_max_exp_value.set(hdr_min_exp_value.get() + aux_bracket)
    else:
        hdr_max_exp_value.set(int(middle_exp + (aux_bracket/2)))
    SessionData["HdrMinExp"] = hdr_min_exp_value.get()
    SessionData["HdrMaxExp"] = hdr_max_exp_value.get()
    SessionData["HdrBracketWidth"] = hdr_bracket_width_value.get()
    force_adjust_hdr_bracket = True


def hdr_bracket_width_validation(new_value):
    return value_validation(new_value, hdr_bracket_width_spinbox, hdr_min_bracket_width, hdr_max_bracket_width)


def hdr_bracket_shift_selection():
    value_normalize(hdr_bracket_shift_value, -100, 100)


def hdr_bracket_shift_validation(new_value):
    return value_validation(new_value, hdr_bracket_shift_spinbox, -100, 100)


def sharpness_control_selection():
    global sharpness_control_label
    global sharpness_control_spinbox
    global SimulatedRun

    if not ExpertMode:
        return

    aux = value_normalize(sharpness_control_value, 0, 16)
    SessionData["SharpnessValue"] = aux
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"Sharpness": aux})


def sharpness_validation(new_value):
    return value_validation(new_value, sharpness_control_spinbox, 0, 16)


def rwnd_speed_control_selection():
    if not ExpertMode:
        return

    value_normalize(rwnd_speed_control_value, 40, 800)
    '''
    if event == 'Up':
        print("Telling arduino to speed up")
        rwnd_speed_up()
    elif event == 'Down':
        print("Telling arduino to slow down")
        rwnd_speed_down()
    '''

def rewind_speed_validation(new_value):
    return value_validation(new_value, rwnd_speed_control_spinbox, 40, 800)


# ***************
# Widget creation
# ***************
def create_widgets():
    global win
    global ExperimentalMode
    global app_width
    global AdvanceMovie_btn
    global SingleStep_btn
    global Snapshot_btn
    global negative_image_checkbox, negative_image
    global Rewind_btn
    global FastForward_btn
    global Free_btn
    global RPi_temp_value_label
    global Exit_btn
    global Start_btn
    global folder_frame_target_dir
    global exposure_frame
    global film_type_S8_rb, film_type_R8_rb, film_type
    global save_bg, save_fg
    global PreviewStatus
    global auto_exposure_change_pause
    global auto_exp_wait_checkbox
    global decrease_exp_btn, increase_exp_btn
    global temp_in_fahrenheit
    global TempInFahrenheit
    global colour_gains_auto_btn, awb_frame
    global colour_gains_red_btn_plus, colour_gains_red_btn_minus
    global colour_gains_blue_btn_plus, colour_gains_blue_btn_minus
    global auto_white_balance_change_pause
    global awb_red_wait_checkbox, awb_blue_wait_checkbox
    global film_hole_frame_1, film_hole_frame_2, FilmHoleY1, FilmHoleY2
    global temp_in_fahrenheit_checkbox
    global rwnd_speed_control_delay
    global real_time_display_checkbox, real_time_display
    global real_time_zoom_checkbox, real_time_zoom
    global auto_stop_enabled_checkbox, auto_stop_enabled
    global focus_lf_btn, focus_up_btn, focus_dn_btn, focus_rt_btn, focus_plus_btn, focus_minus_btn
    global draw_capture_canvas
    global hdr_btn
    global steps_per_frame_value, frame_fine_tune_value
    global pt_level_spinbox
    global steps_per_frame_spinbox, frame_fine_tune_spinbox, pt_level_spinbox, pt_level_value
    global frame_extra_steps_spinbox, frame_extra_steps_value
    global scan_speed_spinbox, scan_speed_value
    global exposure_value
    global wb_red_spinbox, wb_blue_spinbox, wb_red_value, wb_blue_value
    global match_wait_margin_spinbox, match_wait_margin_value
    global stabilization_delay_spinbox, stabilization_delay_value
    global sharpness_control_spinbox, sharpness_control_value
    global rwnd_speed_control_spinbox, rwnd_speed_control_value
    global Manual_scan_activated, ManualScanEnabled, manual_scan_advance_fraction_5_btn, manual_scan_advance_fraction_20_btn, manual_scan_take_snap_btn
    global plotter_canvas
    global hdr_capture_active_checkbox, hdr_capture_active, hdr_viewx4_active
    global hdr_viewx4_active_checkbox, hdr_min_exp_label, hdr_min_exp_spinbox, hdr_max_exp_label, hdr_max_exp_spinbox, hdr_max_exp_value, hdr_min_exp_value
    global steps_per_frame_btn, auto_framesteps_enabled, pt_level_btn, auto_pt_level_enabled
    global exposure_btn, wb_red_btn, wb_blue_btn, exposure_spinbox, wb_red_spinbox, wb_blue_spinbox
    global hdr_bracket_width_spinbox, hdr_bracket_shift_spinbox, hdr_bracket_width_label, hdr_bracket_shift_label
    global hdr_bracket_width_value, hdr_bracket_shift_value
    global hdr_bracket_auto, hdr_bracket_width_auto_checkbox
    global hdr_merge_in_place, hdr_bracket_width_auto_checkbox, hdr_merge_in_place_checkbox
    global frames_to_go_str, FramesToGo, time_to_go_str
    global RetreatMovie_btn
    # global file_type_jpg_rb, file_type_png_rb
    global file_type_dropdown, file_type_dropdown_selected
    global resolution_dropdown, resolution_dropdown_selected
    global Scanned_Images_number_str, Scanned_Images_time_str, Scanned_Images_Fpm_str
    global resolution_label, resolution_dropdown, file_type_label, file_type_dropdown
    global existing_folder_btn, new_folder_btn
    global autostop_no_film_rb, autostop_counter_zero_rb, autostop_type
    global full_ui_checkbox, toggle_ui_small
    global AE_enabled, AWB_enabled
    global expert_frame, experimental_frame
    global time_save_image_value, time_preview_display_value, time_awb_value, time_autoexp_value

    # Create a frame to contain the top area (preview + Right buttons) ***************
    top_area_frame = Frame(win)
    top_area_frame.pack(side=TOP, anchor=NW)
    # Create a frame to contain the top right area (buttons) ***************
    top_left_area_frame = Frame(top_area_frame)
    top_left_area_frame.pack(side=LEFT, anchor=NW, padx=(5, 0), pady=(20, 0), fill=Y)
    # Create a LabelFrame to act as a border
    draw_capture_frame = tk.LabelFrame(top_area_frame, bd=2, relief=tk.GROOVE)
    draw_capture_frame.pack(side=LEFT, anchor=N, padx=(15, 0), pady=(20, 0))
    # Create the canvas
    draw_capture_canvas = Canvas(draw_capture_frame, bg='dark grey',
                                 width=PreviewWidth, height=PreviewHeight)
    draw_capture_canvas.pack(side=TOP, anchor=N, padx=(20,0))
    # Create a frame to contain the top right area (buttons) ***************
    top_right_area_frame = Frame(top_area_frame)
    top_right_area_frame.pack(side=LEFT, anchor=NW, padx=(5, 0), pady=(20, 0), fill=Y)

    # Advance movie button (slow forward through filmgate)
    bottom_area_column = 0
    bottom_area_row = 0
    AdvanceMovie_btn = Button(top_left_area_frame, text="Movie Forward", width=12, height=3, command=advance_movie,
                              activebackground='#f0f0f0', wraplength=80, relief=RAISED, font=("Arial", FontSize))
    AdvanceMovie_btn.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=(5,0), pady=(0,4), sticky='NSEW')
    as_tooltips.add(AdvanceMovie_btn, "Advance film (can be used with real-time view enabled).")
    bottom_area_row += 1
    # Once first button created, get default colors, to revert when we change them
    save_bg = AdvanceMovie_btn['bg']
    save_fg = AdvanceMovie_btn['fg']

    # Frame for single step/snapshot
    sstep_area_frame = Frame(top_left_area_frame, width=50, height=50)
    sstep_area_frame.grid_forget()
    # Advance one single frame
    SingleStep_btn = Button(sstep_area_frame, text="Single Step", width=6, height=1, command=single_step_movie,
                            activebackground='#f0f0f0', wraplength=80, font=("Arial", FontSize))
    SingleStep_btn.grid_forget()
    Snapshot_btn = Button(sstep_area_frame, text="Snapshot", width=6, height=1, command=capture_single_step,
                            activebackground='#f0f0f0', wraplength=80, font=("Arial", FontSize))
    Snapshot_btn.grid_forget()

    # Rewind movie (via upper path, outside of film gate)
    Rewind_btn = Button(top_left_area_frame, text="<<", font=("Arial", FontSize+3), height=2, command=rewind_movie,
                        activebackground='#f0f0f0', wraplength=80, relief=RAISED)
    Rewind_btn.grid(row=bottom_area_row, column=bottom_area_column, padx=(5,0), pady=4, sticky='NSEW')
    as_tooltips.add(Rewind_btn, "Rewind film. Make sure film is routed via upper rolls.")
    # Fast Forward movie (via upper path, outside of film gate)
    FastForward_btn = Button(top_left_area_frame, text=">>", font=("Arial", FontSize+3), height=2, command=fast_forward_movie,
                             activebackground='#f0f0f0', wraplength=80, relief=RAISED)
    FastForward_btn.grid(row=bottom_area_row, column=bottom_area_column+1, padx=(5,0), pady=4, sticky='NSEW')
    as_tooltips.add(FastForward_btn, "Fast-forward film. Make sure film is routed via upper rolls.")
    bottom_area_row += 1

    # Switch Positive/negative modes
    negative_image = tk.BooleanVar(value=False)
    #toggle_btn = tk.Checkbutton(root, text="Toggle", variable=var, command=toggle_button, indicatoron=False)
    negative_image_checkbox = tk.Checkbutton(top_left_area_frame, text='Negative film', height=1,
                                                 variable=negative_image, onvalue=True, offvalue=False,
                                                 font=("Arial", FontSize), command=set_negative_image,
                                                 indicatoron=False, selectcolor="sea green")
    negative_image_checkbox.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=2, pady=1, ipadx=5, ipady=5, sticky='NSEW')
    as_tooltips.add(negative_image_checkbox, "Enable negative film capture (untested with real negative film)")
    bottom_area_row += 1

    # Real time view to allow focus
    real_time_display = tk.BooleanVar(value=False)
    real_time_display_checkbox = tk.Checkbutton(top_left_area_frame, text='Focus view', height=1,
                                                variable=real_time_display, onvalue=True, offvalue=False,
                                                font=("Arial", FontSize), command=set_real_time_display,
                                                indicatoron=False, selectcolor="sea green")
    real_time_display_checkbox.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=2, pady=1, ipadx=5, ipady=5, sticky='NSEW')
    as_tooltips.add(real_time_display_checkbox, "Enable real-time film preview. Cannot be used while scanning, useful mainly to focus the film.")
    bottom_area_row += 1

    # Activate focus zoom, to facilitate focusing the camera
    real_time_zoom = tk.BooleanVar(value=False)
    real_time_zoom_checkbox = tk.Checkbutton(top_left_area_frame, text='Zoom view', height=1,
                                             variable=real_time_zoom, onvalue=True, offvalue=False,
                                             font=("Arial", FontSize), command=set_focus_zoom, indicatoron=False,
                                             selectcolor="sea green", state=DISABLED)
    real_time_zoom_checkbox.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=2, pady=1, ipadx=5, ipady=5, sticky='NSEW')
    as_tooltips.add(real_time_zoom_checkbox, "Zoom in on the real-time film preview. Useful to focus the film")
    bottom_area_row += 1

    # Focus zoom control (in out, up, down, left, right)
    Focus_frame = LabelFrame(top_left_area_frame, text='Zoom control', height=3, font=("Arial", FontSize-2))
    Focus_frame.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, pady=4, ipady=2, sticky='NSEW')
    bottom_area_row += 1

    Focus_btn_grid_frame = Frame(Focus_frame, width=10, height=10)
    Focus_btn_grid_frame.pack()

    # focus zoom displacement buttons, to further facilitate focusing the camera
    focus_plus_btn = Button(Focus_btn_grid_frame, text="+", height=1, command=set_focus_plus,
                            activebackground='#f0f0f0', state=DISABLED, font=("Arial", FontSize-2))
    focus_plus_btn.grid(row=0, column=2, sticky='NSEW')
    as_tooltips.add(focus_plus_btn, "Increase zoom level.")
    focus_minus_btn = Button(Focus_btn_grid_frame, text="-", height=1, command=set_focus_minus,
                             activebackground='#f0f0f0', state=DISABLED, font=("Arial", FontSize-2))
    focus_minus_btn.grid(row=0, column=0, sticky='NSEW')
    as_tooltips.add(focus_minus_btn, "Decrease zoom level.")
    focus_lf_btn = Button(Focus_btn_grid_frame, text="←", height=1, command=set_focus_left,
                          activebackground='#f0f0f0', state=DISABLED, font=("Arial", FontSize-2))
    focus_lf_btn.grid(row=1, column=0, sticky='NSEW')
    as_tooltips.add(focus_lf_btn, "Move zoom view to the left.")
    focus_up_btn = Button(Focus_btn_grid_frame, text="↑", height=1, command=set_focus_up,
                          activebackground='#f0f0f0', state=DISABLED, font=("Arial", FontSize-2))
    focus_up_btn.grid(row=0, column=1, sticky='NSEW')
    as_tooltips.add(focus_up_btn, "Move zoom view up.")
    focus_dn_btn = Button(Focus_btn_grid_frame, text="↓", height=1, command=set_focus_down,
                          activebackground='#f0f0f0', state=DISABLED, font=("Arial", FontSize-2))
    focus_dn_btn.grid(row=1, column=1, sticky='NSEW')
    as_tooltips.add(focus_dn_btn, "Move zoom view down.")
    focus_rt_btn = Button(Focus_btn_grid_frame, text="→", height=1, command=set_focus_right,
                          activebackground='#f0f0f0', state=DISABLED, font=("Arial", FontSize-2))
    focus_rt_btn.grid(row=1, column=2, sticky='NSEW')
    as_tooltips.add(focus_rt_btn, "Move zoom view to the right.")
    bottom_area_row += 1

    # Frame for automatic stop & methods
    autostop_frame = Frame(top_left_area_frame)
    autostop_frame.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=2, pady=1, sticky='WE')

    # Activate focus zoom, to facilitate focusing the camera
    auto_stop_enabled = tk.BooleanVar(value=False)
    auto_stop_enabled_checkbox = tk.Checkbutton(autostop_frame, text='Auto-stop if', height=1,
                                                 variable=auto_stop_enabled, onvalue=True, offvalue=False,
                                                 font=("Arial", FontSize), command=set_auto_stop_enabled)
    #auto_stop_enabled_checkbox.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=2, pady=1, sticky='W')
    auto_stop_enabled_checkbox.pack(side = TOP, anchor=W)
    as_tooltips.add(auto_stop_enabled_checkbox, "Stop scanning when end of film detected")

    # Radio buttons to select auto-stop method
    autostop_type = tk.StringVar()
    autostop_type.set('No_film')
    autostop_no_film_rb = tk.Radiobutton(autostop_frame, text="No film", variable=autostop_type,
                                  value='No_film', font=("Arial", FontSize), command=set_auto_stop_enabled)
    autostop_no_film_rb.pack(side=TOP, anchor=W, padx=10)
    as_tooltips.add(autostop_no_film_rb, "Stop when film is not detected by PT")
    autostop_counter_zero_rb = tk.Radiobutton(autostop_frame, text="Count zero", variable=autostop_type,
                                  value='counter_to_zero', font=("Arial", FontSize), command=set_auto_stop_enabled)
    autostop_counter_zero_rb.pack(side=TOP, anchor=W, padx=10)
    as_tooltips.add(autostop_counter_zero_rb, "Stop scan when frames-to-go counter reaches zero")
    autostop_no_film_rb.config(state = DISABLED)
    autostop_counter_zero_rb.config(state = DISABLED)

    bottom_area_row += 1

    # Toggle UI size
    if ExpertMode:
        toggle_ui_small = tk.BooleanVar(value=False)
        full_ui_checkbox = tk.Checkbutton(top_left_area_frame, text='Toggle UI', height=1,
                                                 variable=toggle_ui_small, onvalue=True, offvalue=False,
                                                 font=("Arial", FontSize), command=toggle_ui_size, indicatoron=False,
                                                 selectcolor="sea green")

        full_ui_checkbox.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=2, pady=1, ipadx=5, ipady=5, sticky='NSEW')
        as_tooltips.add(full_ui_checkbox, "Toggle between full/restricted user interface")
        bottom_area_row += 1

    # Create vertical button column at right *************************************
    # Application Exit button
    top_right_area_row = 0
    Exit_btn = Button(top_right_area_frame, text="Exit", height=5, command=exit_app, activebackground='red',
                      activeforeground='white', font=("Arial", FontSize))
    Exit_btn.grid(row=top_right_area_row, column=0, padx=4, pady=(0,3), sticky='EW')
    as_tooltips.add(Exit_btn, "Exit ALT-Scann8.")

    # Start scan button
    if SimulatedRun:
        Start_btn = Button(top_right_area_frame, text="START Scan", height=5, command=start_scan_simulated,
                           activebackground='#f0f0f0', font=("Arial", FontSize))
    else:
        Start_btn = Button(top_right_area_frame, text="START Scan", height=5, command=start_scan,
                           activebackground='#f0f0f0', font=("Arial", FontSize))
    Start_btn.grid(row=top_right_area_row, column=1, pady=(0,3), sticky='EW')
    as_tooltips.add(Start_btn, "Start scanning process.")
    top_right_area_row += 1

    # Create frame to select target folder
    folder_frame = LabelFrame(top_right_area_frame, text='Target Folder', height=8, font=("Arial", FontSize-2))
    folder_frame.grid(row=top_right_area_row, column=0, columnspan=2, padx=4, pady=4, sticky='EW')

    folder_frame_target_dir = Label(folder_frame, text=CurrentDir, width=50 if BigSize else 55, height=3, font=("Arial", FontSize-3),
                                    wraplength=200)
    folder_frame_target_dir.pack(side=TOP)

    folder_frame_buttons = Frame(folder_frame, width=16, height=4, bd=2)
    folder_frame_buttons.pack()
    new_folder_btn = Button(folder_frame_buttons, text='New', width=10, height=1, command=set_new_folder,
                            activebackground='#f0f0f0', wraplength=80, font=("Arial", FontSize-2))
    new_folder_btn.pack(side=LEFT)
    as_tooltips.add(new_folder_btn, "Create new folder to store frames generated during the scan.")
    existing_folder_btn = Button(folder_frame_buttons, text='Existing', width=10, height=1, command=set_existing_folder,
                                 activebackground='#f0f0f0', wraplength=80, font=("Arial", FontSize-2))
    existing_folder_btn.pack(side=LEFT)
    as_tooltips.add(existing_folder_btn, "Select existing folder to store frames generated during the scan.")
    top_right_area_row += 1

    # Create frame to select target file specs
    file_type_frame = LabelFrame(top_right_area_frame, text='Capture resolution & file type', height=8, font=("Arial", FontSize-2))
    file_type_frame.grid(row=top_right_area_row, column=0, columnspan=2, padx=4, pady=4, sticky='EW')

    # Capture resolution Dropdown
    # Drop down to select capture resolution
    # Dropdown menu options
    resolution_list = camera_resolutions.get_list()
    resolution_dropdown_selected = tk.StringVar()
    resolution_dropdown_selected.set(resolution_list[1])  # Set the initial value
    resolution_label = Label(file_type_frame, text='Resolution:', font=("Arial", FontSize))
    resolution_label.pack(side=LEFT)
    #resolution_label.config(state=DISABLED)
    resolution_dropdown = OptionMenu(file_type_frame,
                                    resolution_dropdown_selected, *resolution_list, command=set_resolution)
    resolution_dropdown.config(takefocus=1, font=("Arial", FontSize))
    resolution_dropdown.pack(side=LEFT)
    # resolution_dropdown.config(state=DISABLED)
    if ExperimentalMode:
        as_tooltips.add(resolution_dropdown, "Select the resolution to use when capturing the frames. Modes flagged with * are cropped, requiring lens adjustment")
    else:
        as_tooltips.add(resolution_dropdown, "Select the resolution to use when capturing the frames")

    # File format (JPG or PNG)
    # Drop down to select file type
    # Dropdown menu options
    file_type_list = ["jpg", "png", "dng"]
    file_type_dropdown_selected = tk.StringVar()
    file_type_dropdown_selected.set(file_type_list[0])  # Set the initial value

    # No label for now
    file_type_label = Label(file_type_frame, text='Type:', font=("Arial", FontSize))
    file_type_label.pack(side=LEFT)
    # file_type_label.config(state=DISABLED)
    file_type_dropdown = OptionMenu(file_type_frame,
                                    file_type_dropdown_selected, *file_type_list, command=set_file_type)
    file_type_dropdown.config(takefocus=1, font=("Arial", FontSize))
    file_type_dropdown.pack(side=LEFT)
    #file_type_dropdown.config(state=DISABLED)
    as_tooltips.add(file_type_dropdown, "Select format to safe film frames (JPG or PNG)")

    top_right_area_row += 1

    # Create frame to display number of scanned images, and frames per minute
    scanned_images_frame = LabelFrame(top_right_area_frame, text='Scanned frames', height=4, font=("Arial", FontSize-2))
    scanned_images_frame.grid(row=top_right_area_row, column=0, padx=4, pady=4, sticky='NSEW')

    Scanned_Images_number_str = tk.StringVar(value=str(CurrentFrame))
    Scanned_Images_number_label = Label(scanned_images_frame, textvariable=Scanned_Images_number_str, font=("Arial", FontSize+6), width=5,
                                        height=1)
    Scanned_Images_number_label.pack(side=TOP)
    as_tooltips.add(Scanned_Images_number_label, "Number of film frames scanned so far.")

    scanned_images_fpm_frame = Frame(scanned_images_frame, width=14, height=2)
    scanned_images_fpm_frame.pack(side=TOP)
    Scanned_Images_time_str = tk.StringVar(value="Film time:")
    Scanned_Images_time_label = Label(scanned_images_fpm_frame, textvariable=Scanned_Images_time_str, font=("Arial", FontSize-2), width=20,
                               height=1)
    Scanned_Images_time_label.pack(side=BOTTOM)
    as_tooltips.add(Scanned_Images_time_label, "Film time in min:sec")

    Scanned_Images_Fpm_str = tk.StringVar(value="Frames/Min:")
    scanned_images_fpm_label = Label(scanned_images_fpm_frame, textvariable=Scanned_Images_Fpm_str, font=("Arial", FontSize-2), width=20,
                                     height=1)
    scanned_images_fpm_label.pack(side=LEFT)
    as_tooltips.add(scanned_images_fpm_label, "Scan speed in frames per minute.")

    # Create frame to display number of frames to go, and estimated time to finish
    frames_to_go_frame = LabelFrame(top_right_area_frame, text='Frames to go', height=4, font=("Arial", FontSize-2))
    frames_to_go_frame.grid(row=top_right_area_row, column=1, padx=4, pady=4, sticky='NSEW')
    top_right_area_row += 1

    frames_to_go_str = tk.StringVar(value='')
    frames_to_go_entry = tk.Entry(frames_to_go_frame, textvariable=frames_to_go_str, width=14, font=("Arial", FontSize-2), justify="right")
    # Bind the KeyRelease event to the entry widget
    frames_to_go_entry.bind("<KeyPress>", frames_to_go_key_press)
    frames_to_go_entry.pack(side=TOP, pady=6)
    as_tooltips.add(frames_to_go_entry, "Enter estimated number of frames to scan in order to get an estimation of remaining time to finish.")
    time_to_go_str = tk.StringVar(value='')
    time_to_go_time = Label(frames_to_go_frame, textvariable=time_to_go_str, font=("Arial", FontSize-2), width=18 if BigSize else 24, height=1)
    time_to_go_time.pack(side=TOP, pady=6)

    # Create frame to select S8/R8 film
    film_type_frame = LabelFrame(top_right_area_frame, text='Film type', height=1, font=("Arial", FontSize-2))
    film_type_frame.grid(row=top_right_area_row, column=0, padx=4, pady=4, sticky='NSEW')

    # Radio buttons to select R8/S8. Required to select adequate pattern, and match position
    film_type = tk.StringVar()
    film_type_S8_rb = tk.Radiobutton(film_type_frame, text="S8", variable=film_type, command=set_s8,
                                  value='S8', font=("Arial", FontSize),
                                  indicatoron=0, width=8, height=2,
                                  compound='left', padx=0, pady=0,
                                  relief="raised", borderwidth=3)
    film_type_S8_rb.pack(side=LEFT, padx=2)
    as_tooltips.add(film_type_S8_rb, "Handle as Super 8 film")
    film_type_R8_rb = tk.Radiobutton(film_type_frame, text="R8", variable=film_type, command=set_r8,
                                  value='R8', font=("Arial", FontSize),
                                  indicatoron=0, width=8, height=2,
                                  compound='left', padx=0, pady=0,
                                  relief="raised", borderwidth=3)
    film_type_R8_rb.pack(side=RIGHT, padx=2)
    as_tooltips.add(film_type_R8_rb, "Handle as 8mm (Regular 8) film")

    # Create frame to display RPi temperature
    rpi_temp_frame = LabelFrame(top_right_area_frame, text='RPi Temp.', height=1, font=("Arial", FontSize-2))
    rpi_temp_frame.grid(row=top_right_area_row, column=1, padx=4, pady=4, sticky='NSEW')
    temp_str = str(RPiTemp)+'º'
    RPi_temp_value_label = Label(rpi_temp_frame, text=temp_str, font=("Arial", FontSize+4), width=10, height=1)
    RPi_temp_value_label.pack(side=TOP, padx=4)
    as_tooltips.add(RPi_temp_value_label, "Raspberry Pi Temperature.")

    temp_in_fahrenheit = tk.BooleanVar(value=TempInFahrenheit)
    temp_in_fahrenheit_checkbox = tk.Checkbutton(rpi_temp_frame, text='Fahrenheit', height=1,
                                                 variable=temp_in_fahrenheit, onvalue=True, offvalue=False,
                                                 command=temp_in_fahrenheit_selection, font=("Arial", FontSize))
    temp_in_fahrenheit_checkbox.pack(side=TOP)
    as_tooltips.add(temp_in_fahrenheit_checkbox, "Display Raspberry Pi Temperature in Fahrenheit.")
    top_right_area_row += 1

    # Integrated plotter
    if PlotterMode:
        integrated_plotter_frame = LabelFrame(top_right_area_frame, text='Plotter Area', height=5,
                                              font=("Arial", FontSize - 1))
        integrated_plotter_frame.grid(row=top_right_area_row, column=0, columnspan=2, padx=4, pady=4, sticky='NSEW')
        plotter_canvas = Canvas(integrated_plotter_frame, bg='white',
                                width=plotter_width, height=plotter_height)
        plotter_canvas.pack(side=TOP, anchor=N)
    top_right_area_row += 1

    # Create extended frame for expert and experimental areas
    if ExpertMode or ExperimentalMode:
        extended_frame = Frame(win)
        extended_frame.pack(side=TOP, anchor=W, padx=5)
    if ExpertMode:
        expert_frame = LabelFrame(extended_frame, text='Expert Area', width=8, font=("Arial", FontSize-1))
        expert_frame.pack(side=LEFT, padx=5, pady=5, ipadx=5, ipady=5, expand=True, fill='both')

        # *********************************
        # Exposure / white balance
        exp_wb_frame = LabelFrame(expert_frame, text='Auto Exposure / White Balance ', font=("Arial", FontSize-1))
        exp_wb_frame.grid(row=0, column=0, padx=5, ipady=5, sticky='NSEW')
        exp_wb_row = 0

        exp_wb_auto_label = tk.Label(exp_wb_frame, text='Auto', font=("Arial", FontSize-1))
        exp_wb_auto_label.grid(row=exp_wb_row, column=3, padx=5, pady=1)

        catch_up_delay_label = tk.Label(exp_wb_frame, text='Catch-up\ndelay', font=("Arial", FontSize-1))
        catch_up_delay_label.grid(row=exp_wb_row, column=4, padx=5, pady=1)
        exp_wb_row += 1

        # Automatic exposure
        exposure_label = tk.Label(exp_wb_frame, text='Exposure:', font=("Arial", FontSize-1))
        exposure_label.grid(row=exp_wb_row, column=0, padx=5, pady=1, sticky=E)

        exposure_value = tk.DoubleVar(value=0)  # Auto exposure by default, overriden by configuration if any
        exposure_spinbox = DynamicSpinbox(exp_wb_frame, command=exposure_selection, width=8, textvariable=exposure_value,
                                      from_=0.001, to=10000, increment=1, font=("Arial", FontSize-1), readonlybackground='pale green')
        exposure_spinbox.grid(row=exp_wb_row, column=1, padx=5, pady=1)
        exposure_validation_cmd = exposure_spinbox.register(exposure_validation)
        exposure_spinbox.configure(validate="key", validatecommand=(exposure_validation_cmd, '%P'))
        as_tooltips.add(exposure_spinbox, "When manual exposure enabled, select wished exposure.")
        exposure_spinbox.bind("<FocusOut>", lambda event: exposure_selection())

        AE_enabled = tk.BooleanVar(value=False)
        exposure_btn = tk.Checkbutton(exp_wb_frame, variable=AE_enabled, onvalue=True, offvalue=False,
                                      font=("Arial", FontSize-1), command=exposure_spinbox_auto)
        exposure_btn.grid(row=exp_wb_row, column=3, pady=1)
        as_tooltips.add(exposure_btn, "Toggle automatic exposure status (on/off).")

        auto_exposure_change_pause = tk.BooleanVar(value=True)  # Default value, to be overriden by configuration
        auto_exp_wait_checkbox = tk.Checkbutton(exp_wb_frame, state=DISABLED, variable=auto_exposure_change_pause,
                                                onvalue=True, offvalue=False, font=("Arial", FontSize-1),
                                                command=auto_exposure_change_pause_selection)
        auto_exp_wait_checkbox.grid(row=exp_wb_row, column=4, pady=1)
        as_tooltips.add(auto_exp_wait_checkbox, "When automatic exposure enabled, select to wait for it to stabilize before capturing frame.")
        arrange_widget_state(AE_enabled.get(), [exposure_btn, exposure_spinbox])
        exp_wb_row += 1

        # Automatic White Balance red
        wb_red_label = tk.Label(exp_wb_frame, text='WB Red:', font=("Arial", FontSize-1))
        wb_red_label.grid(row=exp_wb_row, column=0, padx=5, pady=1, sticky=E)

        wb_red_value = tk.DoubleVar(value=2.2)  # Default value, overriden by configuration
        wb_red_spinbox = DynamicSpinbox(exp_wb_frame, command=wb_red_selection, width=8, readonlybackground='pale green',
            textvariable=wb_red_value, from_=0, to=32, increment=0.1, font=("Arial", FontSize-1))
        wb_red_spinbox.grid(row=exp_wb_row, column=1, padx=5, pady=1, sticky=W)
        wb_red_validation_cmd = wb_red_spinbox.register(wb_red_validation)
        wb_red_spinbox.configure(validate="key", validatecommand=(wb_red_validation_cmd, '%P'))
        as_tooltips.add(wb_red_spinbox, "When manual white balance enabled, select wished level (for red channel).")
        wb_red_spinbox.bind("<FocusOut>", lambda event: wb_red_selection())

        wb_join_label = tk.Label(exp_wb_frame, text='}', width=1, font=("Arial", FontSize*2))   # ⎬ } ﹜
        wb_join_label.grid(row=exp_wb_row, rowspan=2, column=2, padx=0, pady=1, sticky=W)

        AWB_enabled = tk.BooleanVar(value=False)
        wb_red_btn = tk.Checkbutton(exp_wb_frame, variable=AWB_enabled, onvalue=True, offvalue=False,
                                    font=("Arial", FontSize-1), command=wb_spinbox_auto)
        wb_red_btn.grid(row=exp_wb_row, rowspan=2, column=3, pady=1)
        as_tooltips.add(wb_red_btn, "Toggle automatic white balance for red channel (on/off).")

        auto_white_balance_change_pause = tk.BooleanVar(value=AwbPause)
        awb_red_wait_checkbox = tk.Checkbutton(exp_wb_frame, state=DISABLED, variable=auto_white_balance_change_pause,
                                               onvalue=True, offvalue=False, font=("Arial", FontSize-1),
                                                command=auto_white_balance_change_pause_selection)
        awb_red_wait_checkbox.grid(row=exp_wb_row, rowspan=2, column=4, pady=1)
        as_tooltips.add(awb_red_wait_checkbox, "When automatic white balance enabled, select to wait for it to stabilize before capturing frame.")
        exp_wb_row += 1

        # Automatic White Balance blue
        wb_blue_label = tk.Label(exp_wb_frame, text='WB Blue:', font=("Arial", FontSize-1))
        wb_blue_label.grid(row=exp_wb_row, column=0, pady=1, sticky=E)

        wb_blue_value = tk.DoubleVar(value=2.2)  # Default value, overriden by configuration
        wb_blue_spinbox = DynamicSpinbox(exp_wb_frame, command=wb_blue_selection, width=8, readonlybackground='pale green',
            textvariable=wb_blue_value, from_=0, to=32, increment=0.1, font=("Arial", FontSize-1))
        wb_blue_spinbox.grid(row=exp_wb_row, column=1, padx=5, pady=1, sticky=W)
        wb_blue_validation_cmd = wb_blue_spinbox.register(wb_blue_validation)
        wb_blue_spinbox.configure(validate="key", validatecommand=(wb_blue_validation_cmd, '%P'))
        as_tooltips.add(wb_blue_spinbox, "When manual white balance enabled, select wished level (for blue channel).")
        wb_blue_spinbox.bind("<FocusOut>", lambda event: wb_blue_selection())
        exp_wb_row+= 1

        # Match wait (exposure & AWB) margin allowance (0%, wait for same value, 100%, any value will do)
        match_wait_margin_label = tk.Label(exp_wb_frame, text='Match margin (%):', font=("Arial", FontSize-1))
        match_wait_margin_label.grid(row=exp_wb_row, column=0, padx=5, pady=1, sticky=E)

        match_wait_margin_value = tk.IntVar(value=50)  # Default value, overriden by configuration
        match_wait_margin_spinbox = DynamicSpinbox(exp_wb_frame, command=match_wait_margin_selection, width=8, readonlybackground='pale green',
            textvariable=match_wait_margin_value, from_=0, to=100, increment=5, font=("Arial", FontSize-1))
        match_wait_margin_spinbox.grid(row=exp_wb_row, column=1, padx=5, pady=1, sticky=W)
        match_wait_margin_validation_cmd = match_wait_margin_spinbox.register(match_wait_margin_validation)
        match_wait_margin_spinbox.configure(validate="key", validatecommand=(match_wait_margin_validation_cmd, '%P'))
        as_tooltips.add(match_wait_margin_spinbox, "When automatic exposure/WB enabled, and catch-up delay is selected, the tolerance for the match (0%, no tolerance, exact match required, 100% any value will match)")
        match_wait_margin_spinbox.bind("<FocusOut>", lambda event: match_wait_margin_selection())

        # Display markers for film hole reference
        film_hole_frame_1 = Frame(win, width=1, height=1, bg='black')
        film_hole_frame_1.pack(side=TOP, padx=1, pady=1)
        film_hole_frame_1.place(x=150 if BigSize else 130, y=FilmHoleY1, height=140 if BigSize else 100)
        film_hole_label_1 = Label(film_hole_frame_1, justify=LEFT, font=("Arial", FontSize), width=2, height=11,
                                bg='white', fg='white')
        film_hole_label_1.pack(side=TOP)

        film_hole_frame_2 = Frame(win, width=1, height=1, bg='black')
        film_hole_frame_2.pack(side=TOP, padx=1, pady=1)
        film_hole_frame_2.place(x=150 if BigSize else 130, y=FilmHoleY2, height=140 if BigSize else 100)
        film_hole_label_2 = Label(film_hole_frame_2, justify=LEFT, font=("Arial", FontSize), width=2, height=11,
                                bg='white', fg='white')
        film_hole_label_2.pack(side=TOP)

        # *********************************
        # Frame to add frame align controls
        frame_alignment_frame = LabelFrame(expert_frame, text="Frame align", font=("Arial", FontSize-1))
        frame_alignment_frame.grid(row=0, column=2, padx=4, sticky='NSEW')
        frame_align_row = 0

        exp_wb_auto_label = tk.Label(frame_alignment_frame, text='Auto', width=4, font=("Arial", FontSize-1))
        exp_wb_auto_label.grid(row=frame_align_row, column=2, padx=5, pady=1)
        frame_align_row += 1

        # Spinbox to select MinFrameSteps on Arduino
        steps_per_frame_label = tk.Label(frame_alignment_frame, text='Steps/frame:', font=("Arial", FontSize-1))
        steps_per_frame_label.grid(row=frame_align_row, column=0, padx=5, pady=1, sticky=E)

        steps_per_frame_value = tk.IntVar(value=250)    # Default to be overridden by configuration
        steps_per_frame_spinbox = DynamicSpinbox(frame_alignment_frame, command=steps_per_frame_selection, width=8, readonlybackground='pale green',
                                                 textvariable=steps_per_frame_value, from_=100, to=600, font=("Arial", FontSize-1))
        steps_per_frame_spinbox.grid(row=frame_align_row, column=1, padx=2, pady=3, sticky=W)
        steps_per_frame_validation_cmd = steps_per_frame_spinbox.register(steps_per_frame_validation)
        steps_per_frame_spinbox.configure(validate="key", validatecommand=(steps_per_frame_validation_cmd, '%P'))
        as_tooltips.add(steps_per_frame_spinbox, "If automatic steps/frame is disabled, enter the number of motor steps required to advance one frame.")
        steps_per_frame_spinbox.bind("<FocusOut>", lambda event: steps_per_frame_selection())

        auto_framesteps_enabled = tk.BooleanVar(value=False)
        steps_per_frame_btn = tk.Checkbutton(frame_alignment_frame, variable=auto_framesteps_enabled, onvalue=True,
                                             offvalue=False, font=("Arial", FontSize-1), command=steps_per_frame_auto)
        steps_per_frame_btn.grid(row=frame_align_row, column=2, pady=3)
        as_tooltips.add(steps_per_frame_btn, "Toggle automatic steps/frame calculation.")

        frame_align_row += 1

        # Spinbox to select PTLevel on Arduino
        pt_level_label = tk.Label(frame_alignment_frame, text='PT Level:', font=("Arial", FontSize-1))
        pt_level_label.grid(row=frame_align_row, column=0, padx=5, pady=1, sticky=E)

        pt_level_value = tk.IntVar(value=200)   # To be overridden by config
        pt_level_spinbox = DynamicSpinbox(frame_alignment_frame, command=pt_level_selection, width=8, readonlybackground='pale green',
            textvariable=pt_level_value, from_=20, to=900, font=("Arial", FontSize-1))
        pt_level_spinbox.grid(row=frame_align_row, column=1, padx=2, pady=3, sticky=W)
        pt_level_validation_cmd = pt_level_spinbox.register(pt_level_validation)
        pt_level_spinbox.configure(validate="key", validatecommand=(pt_level_validation_cmd, '%P'))
        as_tooltips.add(pt_level_spinbox, "If automatic photo-transistor is disabled, enter the level to be reached to determine detection of sprocket hole.")
        pt_level_spinbox.bind("<FocusOut>", lambda event: pt_level_selection())

        auto_pt_level_enabled = tk.BooleanVar(value=False)
        pt_level_btn = tk.Checkbutton(frame_alignment_frame, variable=auto_pt_level_enabled,
                                      onvalue=True, offvalue=False, font=("Arial", FontSize-1),
                                      command=pt_level_spinbox_auto)
        pt_level_btn.grid(row=frame_align_row, column=2, pady=3)
        as_tooltips.add(pt_level_btn, "Toggle automatic photo-transistor level calculation.")

        frame_align_row += 1

        # Spinbox to select Frame Fine Tune on Arduino
        frame_fine_tune_label = tk.Label(frame_alignment_frame, text='Fine tune:', font=("Arial", FontSize-1))
        frame_fine_tune_label.grid(row=frame_align_row, column=0, padx=5, pady=1, sticky=E)

        frame_fine_tune_value = tk.IntVar(value=50)   # To be overridden by config
        frame_fine_tune_spinbox = DynamicSpinbox(frame_alignment_frame, command=frame_fine_tune_selection, width=8, readonlybackground='pale green',
                        textvariable=frame_fine_tune_value, from_=5, to=95, increment=5, font=("Arial", FontSize-1))
        frame_fine_tune_spinbox.grid(row=frame_align_row, column=1, padx=2, pady=3, sticky=W)
        fine_tune_validation_cmd = frame_fine_tune_spinbox.register(fine_tune_validation)
        frame_fine_tune_spinbox.configure(validate="key", validatecommand=(fine_tune_validation_cmd, '%P'))
        as_tooltips.add(frame_fine_tune_spinbox, "Fine tune of frame detection: Can move the frame slightly up or down at detection time.")
        frame_fine_tune_spinbox.bind("<FocusOut>", lambda event: frame_fine_tune_selection())
        frame_align_row += 1

        # Spinbox to select Extra Steps on Arduino
        frame_extra_steps_label = tk.Label(frame_alignment_frame, text='Extra Steps:', font=("Arial", FontSize-1))
        frame_extra_steps_label.grid(row=frame_align_row, column=0, padx=5, pady=1, sticky=E)

        frame_extra_steps_value = tk.IntVar(value=0)  # To be overridden by config
        frame_extra_steps_spinbox = DynamicSpinbox(frame_alignment_frame, command=frame_extra_steps_selection, width=8, readonlybackground='pale green',
                        textvariable=frame_extra_steps_value, from_=-30, to=30, font=("Arial", FontSize-1))
        frame_extra_steps_spinbox.grid(row=frame_align_row, column=1, padx=2, pady=3, sticky=W)
        extra_steps_validation_cmd = frame_extra_steps_spinbox.register(extra_steps_validation)
        frame_extra_steps_spinbox.configure(validate="key", validatecommand=(extra_steps_validation_cmd, '%P'))
        as_tooltips.add(frame_extra_steps_spinbox, "Unconditionally advances the frame n steps after detection. Can be useful only in rare cases, 'Fine tune' should be enough.")
        frame_extra_steps_spinbox.bind("<FocusOut>", lambda event: frame_extra_steps_selection())

        # *********************************
        # Frame to add scan speed control
        speed_quality_frame = LabelFrame(expert_frame, text="Stabilization", font=("Arial", FontSize-1))
        speed_quality_frame.grid(row=0, column=3, padx=4, sticky='NSEW')

        # Spinbox to select Speed on Arduino (1-10)
        scan_speed_label = tk.Label(speed_quality_frame,
                                         text='Scan Speed:',
                                         font=("Arial", FontSize-1))
        scan_speed_label.grid(row=0, column=0, padx=3, pady=(20, 10), sticky=E)
        scan_speed_value = tk.IntVar(value=5)   # Default value, overriden by configuration
        scan_speed_spinbox = DynamicSpinbox(speed_quality_frame, command=scan_speed_selection, width=3,
                    textvariable=scan_speed_value, from_=1, to=10, font=("Arial", FontSize-1))
        scan_speed_spinbox.grid(row=0, column=1, padx=4, pady=4, sticky=W)
        scan_speed_validation_cmd = scan_speed_spinbox.register(scan_speed_validation)
        scan_speed_spinbox.configure(validate="key", validatecommand=(scan_speed_validation_cmd, '%P'))
        as_tooltips.add(scan_speed_spinbox, "Select scan speed from 1 (slowest) to 10 (fastest).A speed of 5 is usually a good compromise between speed and good frame position detection.")
        scan_speed_spinbox.bind("<FocusOut>", lambda event: scan_speed_selection())

        # Display entry to adjust capture stabilization delay (100 ms by default)
        stabilization_delay_label = tk.Label(speed_quality_frame,
                                         text='Stabilization\ndelay (ms):',
                                         font=("Arial", FontSize-1))
        stabilization_delay_label.grid(row=1, column=0, padx=4, pady=4, sticky=E)
        stabilization_delay_value = tk.IntVar(value=100)    # default value, overriden by configuration
        stabilization_delay_spinbox = DynamicSpinbox(speed_quality_frame, command=stabilization_delay_selection, width=4,
                    textvariable=stabilization_delay_value, from_=0, to=1000, increment=10, font=("Arial", FontSize-1))
        stabilization_delay_spinbox.grid(row=1, column=1, padx=4, sticky='W')
        stabilization_delay_validation_cmd = stabilization_delay_spinbox.register(stabilization_delay_validation)
        stabilization_delay_spinbox.configure(validate="key", validatecommand=(stabilization_delay_validation_cmd, '%P'))
        as_tooltips.add(stabilization_delay_spinbox, "Delay between frame detection and snapshot trigger. 100ms is a good compromise, lower values might cause blurry captures.")
        stabilization_delay_spinbox.bind("<FocusOut>", lambda event: stabilization_delay_selection())

    if ExperimentalMode:
        experimental_frame = LabelFrame(extended_frame, text='Experimental Area', font=("Arial", FontSize-1))
        experimental_frame.pack(side=LEFT, padx=5, ipadx=5, pady=5, fill='both', expand=True)

        # Frame to add HDR controls (on/off, exp. bracket, position, auto-adjust)
        hdr_frame = LabelFrame(experimental_frame, text="Multi-exposure fusion", font=("Arial", FontSize-1))
        #hdr_frame.grid(row=0, column=1, padx=4, pady=4, sticky='NSEW')
        hdr_frame.pack(side=LEFT, padx=5, pady=2, ipady=5, fill='both', expand=True)
        hdr_row = 0
        hdr_capture_active = tk.BooleanVar(value=HdrCaptureActive)
        hdr_capture_active_checkbox = tk.Checkbutton(hdr_frame, text=' Active', height=1,
                                                     variable=hdr_capture_active, onvalue=True, offvalue=False,
                                                     command=switch_hdr_capture, font=("Arial", FontSize-1))
        hdr_capture_active_checkbox.grid(row=hdr_row, column=0, padx=2, pady=1, sticky=W)
        as_tooltips.add(hdr_capture_active_checkbox, "Activate multi-exposure scan. Three snapshots of each frame will be taken with different exposures, to be merged later by AfterScan.")
        hdr_viewx4_active = tk.BooleanVar(value=HdrViewX4Active)
        hdr_viewx4_active_checkbox = tk.Checkbutton(hdr_frame, text=' View X4', height=1,
                                                     variable=hdr_viewx4_active, onvalue=True, offvalue=False,
                                                     command=switch_hdr_viewx4, font=("Arial", FontSize-1), state=DISABLED)
        hdr_viewx4_active_checkbox.grid(row=hdr_row, column=1, padx=2, pady=1, sticky=W)
        as_tooltips.add(hdr_viewx4_active_checkbox, "Alternate frame display during capture. Instead of displaying a single frame (the one in the middle), all three frames will be displayed sequentially.")
        hdr_row += 1

        hdr_min_exp_label = tk.Label(hdr_frame, text='Lower exp. (ms):', font=("Arial", FontSize-1), state=DISABLED)
        hdr_min_exp_label.grid(row=hdr_row, column=0, padx=2, pady=1, sticky=E)
        hdr_min_exp_value = tk.IntVar(value=hdr_lower_exp)
        hdr_min_exp_spinbox = DynamicSpinbox(hdr_frame, command=hdr_min_exp_selection, width=8, readonlybackground='pale green',
            textvariable=hdr_min_exp_value, from_=hdr_lower_exp, to=999, increment=1, font=("Arial", FontSize-1), state=DISABLED)
        hdr_min_exp_spinbox.grid(row=hdr_row, column=1, padx=2, pady=1, sticky=W)
        hdr_min_exp_validation_cmd = hdr_min_exp_spinbox.register(hdr_min_exp_validation)
        hdr_min_exp_spinbox.configure(validate="key", validatecommand=(hdr_min_exp_validation_cmd, '%P'))
        as_tooltips.add(hdr_min_exp_spinbox, "When multi-exposure enabled, lower value of the exposure bracket.")
        hdr_min_exp_spinbox.bind("<FocusOut>", lambda event: hdr_min_exp_selection())
        hdr_row +=1

        hdr_max_exp_label = tk.Label(hdr_frame, text='Higher exp. (ms):', font=("Arial", FontSize-1), state=DISABLED)
        hdr_max_exp_label.grid(row=hdr_row, column=0, padx=2, pady=1, sticky=E)
        hdr_max_exp_value = tk.IntVar(value=hdr_higher_exp)
        hdr_max_exp_spinbox = DynamicSpinbox(hdr_frame, command=hdr_max_exp_selection, width=8, readonlybackground='pale green',
            textvariable=hdr_max_exp_value, from_=2, to=1000, increment=1, font=("Arial", FontSize-1), state=DISABLED)
        hdr_max_exp_spinbox.grid(row=hdr_row, column=1, padx=2, pady=1, sticky=W)
        hdr_max_exp_validation_cmd = hdr_max_exp_spinbox.register(hdr_max_exp_validation)
        hdr_max_exp_spinbox.configure(validate="key", validatecommand=(hdr_max_exp_validation_cmd, '%P'))
        as_tooltips.add(hdr_max_exp_spinbox, "When multi-exposure enabled, upper value of the exposure bracket.")
        hdr_max_exp_spinbox.bind("<FocusOut>", lambda event: hdr_max_exp_selection())
        hdr_row += 1

        hdr_bracket_width_label = tk.Label(hdr_frame, text='Bracket width (ms):', font=("Arial", FontSize-1), state=DISABLED)
        hdr_bracket_width_label.grid(row=hdr_row, column=0, padx=2, pady=1, sticky=E)
        hdr_bracket_width_value = tk.IntVar(value=50)
        hdr_bracket_width_spinbox = DynamicSpinbox(hdr_frame, command=hdr_bracket_width_selection, width=8,
            textvariable=hdr_bracket_width_value, from_=hdr_min_bracket_width, to=hdr_max_bracket_width, increment=1, font=("Arial", FontSize-1), state=DISABLED)
        hdr_bracket_width_spinbox.grid(row=hdr_row, column=1, padx=2, pady=1, sticky=W)
        hdr_bracket_width_validation_cmd = hdr_bracket_width_spinbox.register(hdr_bracket_width_validation)
        hdr_bracket_width_spinbox.configure(validate="key", validatecommand=(hdr_bracket_width_validation_cmd, '%P'))
        as_tooltips.add(hdr_bracket_width_spinbox, "When multi-exposure enabled, width of the exposure bracket (useful for automatic mode).")
        hdr_bracket_width_spinbox.bind("<FocusOut>", lambda event: hdr_bracket_width_selection())
        hdr_row += 1

        hdr_bracket_shift_label = tk.Label(hdr_frame, text='Bracket shift (ms):', font=("Arial", FontSize-1), state=DISABLED)
        hdr_bracket_shift_label.grid(row=hdr_row, column=0, padx=2, pady=1, sticky=E)
        hdr_bracket_shift_value = tk.IntVar(value=0)
        hdr_bracket_shift_spinbox = DynamicSpinbox(hdr_frame, command=hdr_bracket_shift_selection, width=8,
            textvariable=hdr_bracket_shift_value, from_=-100, to=100, increment=10, font=("Arial", FontSize-1), state=DISABLED)
        hdr_bracket_shift_spinbox.grid(row=hdr_row, column=1, padx=2, pady=1, sticky=W)
        hdr_bracket_shift_validation_cmd = hdr_bracket_shift_spinbox.register(hdr_bracket_shift_validation)
        hdr_bracket_shift_spinbox.configure(validate="key", validatecommand=(hdr_bracket_shift_validation_cmd, '%P'))
        as_tooltips.add(hdr_bracket_shift_spinbox, "When multi-exposure enabled, shift exposure bracket up or down from default position.")
        hdr_bracket_shift_spinbox.bind("<FocusOut>", lambda event: hdr_bracket_shift_selection())
        hdr_row += 1

        hdr_bracket_auto = tk.BooleanVar(value=HdrBracketAuto)
        hdr_bracket_width_auto_checkbox = tk.Checkbutton(hdr_frame, text='Auto bracket', height=1,
                                              variable=hdr_bracket_auto, onvalue=True, offvalue=False,
                                              command=adjust_hdr_bracket_auto, font=("Arial", FontSize-1))
        hdr_bracket_width_auto_checkbox.grid(row=hdr_row, column=0, padx=2, pady=1, sticky=W)
        as_tooltips.add(hdr_bracket_width_auto_checkbox, "Enable automatic multi-exposure: For each frame, ALT-Scann8 will retrieve the auto-exposure level reported by the RPi HQ camera, adn will use it for the middle exposure, calculating the lower/upper values according to the bracket defined.")
        hdr_row += 1

        hdr_merge_in_place = tk.BooleanVar(value=HdrMergeInPlace)
        hdr_merge_in_place_checkbox = tk.Checkbutton(hdr_frame, text='Merge in place', height=1,
                                              variable=hdr_merge_in_place, onvalue=True, offvalue=False,
                                              command=adjust_merge_in_place, font=("Arial", FontSize-1))
        hdr_merge_in_place_checkbox.grid(row=hdr_row, column=0, padx=2, pady=1, sticky=W)
        as_tooltips.add(hdr_merge_in_place_checkbox, "Enable to perform Mertens merge on the Raspberry Pi, while encoding. Allow to make some use of the time spent waiting for the camera to adapt the exposure.")

        # Experimental miscellaneous sub-frame
        experimental_miscellaneous_frame = LabelFrame(experimental_frame, text='Miscellaneous', font=("Arial", FontSize-1))
        experimental_miscellaneous_frame.pack(side=LEFT, padx=5, pady=2, ipady=5, fill='both', expand=True)

        # Sharpness, control to allow playing with the values and see the results
        sharpness_control_label = tk.Label(experimental_miscellaneous_frame,
                                             text='Sharpness:',
                                             font=("Arial", FontSize-1))
        sharpness_control_label.grid(row=0, column=0, padx=2, sticky=E)
        sharpness_control_value = tk.IntVar(value=1)    # Default value, overridden by configuration if any
        sharpness_control_spinbox = DynamicSpinbox(experimental_miscellaneous_frame, command=sharpness_control_selection,
                                               width=8, textvariable=sharpness_control_value, from_=0, to=16,
                                               increment=1, font=("Arial", FontSize-1))
        sharpness_control_spinbox.grid(row=0, column=1, padx=2, sticky=W)
        sharpness_validation_cmd = sharpness_control_spinbox.register(sharpness_validation)
        sharpness_control_spinbox.configure(validate="key", validatecommand=(sharpness_validation_cmd, '%P'))
        as_tooltips.add(sharpness_control_spinbox,
                      "Sets the RPi HQ camera 'Sharpness' property to the selected value.")
        sharpness_control_spinbox.bind("<FocusOut>", lambda event: sharpness_control_selection())
        # Display entry to throttle Rwnd/FF speed
        rwnd_speed_control_label = tk.Label(experimental_miscellaneous_frame,
                                             text='RW/FF speed rpm):',
                                             font=("Arial", FontSize-1))
        rwnd_speed_control_label.grid(row=1, column=0, padx=2, sticky=E)
        rwnd_speed_control_value = tk.IntVar(value=round(60 / (rwnd_speed_delay * 375 / 1000000)))
        rwnd_speed_control_spinbox = DynamicSpinbox(experimental_miscellaneous_frame, state='readonly', width=8,
                                                command=rwnd_speed_control_selection, from_=40, to=800, increment=50,
                                                textvariable=rwnd_speed_control_value, font=("Arial", FontSize-1))
        rwnd_speed_control_spinbox.grid(row=1, column=1, padx=2, sticky=W)
        rewind_speed_validation_cmd = rwnd_speed_control_spinbox.register(rewind_speed_validation)
        rwnd_speed_control_spinbox.configure(validate="key", validatecommand=(rewind_speed_validation_cmd, '%P'))
        as_tooltips.add(rwnd_speed_control_spinbox, "Speed up/slow down the RWND/FF speed.")
        # No need to validate on FocusOut, since no keyboard entry is allowed in this one

        # Damaged film helpers, to help handling damaged film (broken perforations)
        Damaged_film_frame = LabelFrame(experimental_miscellaneous_frame, text='Damaged film', font=("Arial", FontSize-1))
        Damaged_film_frame.grid(row=2, column=0, columnspan=2, padx=4, sticky='')
        # Checkbox to enable/disable manual scan
        Manual_scan_activated = tk.BooleanVar(value=ManualScanEnabled)
        Manual_scan_checkbox = tk.Checkbutton(Damaged_film_frame, text='Enable manual scan', width=20, height=1,
                                               variable=Manual_scan_activated, onvalue=True,
                                               offvalue=False,
                                               command=Manual_scan_activated_selection, font=("Arial", FontSize-1))
        Manual_scan_checkbox.pack(side=TOP)
        as_tooltips.add(Manual_scan_checkbox, "Enable manual scan (for films with very damaged sprocket holes). Lots of manual work, use it if everything else fails.")
        # Common area for buttons
        Manual_scan_btn_frame = Frame(Damaged_film_frame, width=18, height=2)
        Manual_scan_btn_frame.pack(side=TOP)

        # Manual scan buttons
        manual_scan_advance_fraction_5_btn = Button(Manual_scan_btn_frame, text="+5", width=1, height=1, command=manual_scan_advance_frame_fraction_5,
                                state=DISABLED, font=("Arial", FontSize-1))
        manual_scan_advance_fraction_5_btn.pack(side=LEFT, ipadx=5, fill=Y)
        as_tooltips.add(manual_scan_advance_fraction_5_btn, "Advance film by 5 motor steps.")
        manual_scan_advance_fraction_20_btn = Button(Manual_scan_btn_frame, text="+20", width=1, height=1, command=manual_scan_advance_frame_fraction_20,
                                state=DISABLED, font=("Arial", FontSize-1))
        manual_scan_advance_fraction_20_btn.pack(side=LEFT, ipadx=5, fill=Y)
        as_tooltips.add(manual_scan_advance_fraction_20_btn, "Advance film by 20 motor steps.")
        manual_scan_take_snap_btn = Button(Manual_scan_btn_frame, text="Snap", width=1, height=1, command=manual_scan_take_snap,
                                 state=DISABLED, font=("Arial", FontSize-1))
        manual_scan_take_snap_btn.pack(side=RIGHT, ipadx=5, fill=Y)
        as_tooltips.add(manual_scan_take_snap_btn, "Take snapshot of frame at current position, then tries to advance to next frame.")

        # Retreat movie button (slow backward through filmgate)
        RetreatMovie_btn = Button(experimental_miscellaneous_frame, text="Movie Backward", width=20, height=1, command=retreat_movie,
                                  activebackground='#f0f0f0', wraplength=100, relief=RAISED, font=("Arial", FontSize-1))
        RetreatMovie_btn.grid(row=3, column=0, columnspan=2, padx=4, sticky='')
        as_tooltips.add(RetreatMovie_btn, "Moves the film backwards. BEWARE: Requires manually rotating the source reels in left position in order to avoid film jamming at film gate.")

        # Unlock reels button (to load film, rewind, etc.)
        Free_btn = Button(experimental_miscellaneous_frame, text="Unlock Reels", width=20, height=1, command=set_free_mode,
                          activebackground='#f0f0f0', wraplength=100, relief=RAISED, font=("Arial", FontSize-1))
        Free_btn.grid(row=4, column=0, columnspan=2, padx=4, sticky='')
        as_tooltips.add(Free_btn, "Used to be a standard button in ALT-Scann8, removed since now motors are always unlocked when not performing any specific operation.")

        # Experimental statictics sub-frame
        experimental_stats_frame = LabelFrame(experimental_frame, text='Average times (ms)', font=("Arial", FontSize-1))
        experimental_stats_frame.pack(side=LEFT, padx=5, pady=2, ipady=5, fill='both', expand=True)
        # Average Time to save image
        time_save_image_label = tk.Label(experimental_stats_frame, text='Save:', font=("Arial", FontSize-1))
        time_save_image_label.grid(row=0, column=0, padx=6, sticky=E)
        time_save_image_value = tk.IntVar(value=0)
        time_save_image_value_label = tk.Label(experimental_stats_frame, textvariable=time_save_image_value, font=("Arial", FontSize-1))
        time_save_image_value_label.grid(row=0, column=1, padx=2, sticky=W)
        # Average Time to display preview
        time_preview_display_label = tk.Label(experimental_stats_frame, text='Prvw:', font=("Arial", FontSize-1))
        time_preview_display_label.grid(row=1, column=0, padx=6, sticky=E)
        time_preview_display_value = tk.IntVar(value=0)
        time_preview_display_value_label = tk.Label(experimental_stats_frame, textvariable=time_preview_display_value, font=("Arial", FontSize-1))
        time_preview_display_value_label.grid(row=1, column=1, padx=2, sticky=W)
        # Average Time spent waiting for AWB to adjust
        time_awb_label = tk.Label(experimental_stats_frame, text='AWB:', font=("Arial", FontSize-1))
        time_awb_label.grid(row=2, column=0, padx=6, sticky=E)
        time_awb_value = tk.IntVar(value=0)
        time_awb_value_label = tk.Label(experimental_stats_frame, textvariable=time_awb_value, font=("Arial", FontSize-1))
        time_awb_value_label.grid(row=2, column=1, padx=2, sticky=W)
        # Average Time spent waiting for AE to adjust
        time_autoexp_label = tk.Label(experimental_stats_frame, text='AE:', font=("Arial", FontSize-1))
        time_autoexp_label.grid(row=3, column=0, padx=6, sticky=E)
        time_autoexp_value = tk.IntVar(value=0)
        time_autoexp_value_label = tk.Label(experimental_stats_frame, textvariable=time_autoexp_value, font=("Arial", FontSize-1))
        time_autoexp_value_label.grid(row=3, column=1, padx=2, sticky=W)




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
    global CameraDisabled, DisableThreads
    global ForceSmallSize, ForceBigSize


    opts, args = getopt.getopt(argv, "sexl:ph12nt")

    for opt, arg in opts:
        if opt == '-s':
            SimulatedRun = True
        elif opt == '-e':
            ExpertMode = not ExpertMode
        elif opt == '-x':
            ExperimentalMode = not ExperimentalMode
        elif opt == '-d':
            CameraDisabled = True
        elif opt == '-l':
            LoggingMode = arg
        elif opt == '-1':
            ForceSmallSize = True
        elif opt == '-2':
            ForceBigSize = True
        elif opt == '-n':
            disable_tooltips()
        elif opt == '-t':
            DisableThreads = True
        elif opt == '-p':
            PlotterMode = not PlotterMode
        elif opt == '-h':
            print("ALT-Scann 8 Command line parameters")
            print("  -s             Start Simulated session")
            print("  -e             Activate expert mode")
            print("  -x             Activate experimental mode")
            print("  -p             Activate integrated plotter")
            print("  -d             Disable camera (for development purposes)")
            print("  -n             Disable Tooltips")
            print("  -t             Disable multi-threading")
            print("  -1             Initiate on 'small screen' mode (resolution lower than than Full HD)")
            print("  -l <log mode>  Set log level (standard Python values (DEBUG, INFO, WARNING, ERROR)")
            exit()


    # ExpertMode = True   # Expert mode becomes default
    LogLevel = getattr(logging, LoggingMode.upper(), None)
    if not isinstance(LogLevel, int):
        raise ValueError('Invalid log level: %s' % LogLevel)

    ALT_scann_init_done = False

    load_persisted_data_from_disk()     # Read json file in memory, to be processed by 'load_session_data'

    tscann8_init()

    load_config_data()
    load_session_data()

    if SimulatedRun:
        logging.debug("Starting in simulated mode.")
    if ExpertMode:
        logging.debug("Toggle expert mode.")
    if ExperimentalMode:
        logging.debug("Toggle experimental mode.")
    if CameraDisabled:
        logging.debug("Camera disabled.")
    if ForceSmallSize:
        logging.debug("Forces restricted window mode.")
    if ForceBigSize:
        logging.debug("Forces full window mode.")
    if DisableThreads:
        logging.debug("Threads disabled.")
    if PlotterMode:
        logging.debug("Toggle ploter mode.")

    if not SimulatedRun:
        arduino_listen_loop()

    ALT_scann_init_done = True

    onesec_periodic_checks()

    # Main Loop
    win.mainloop()  # running3 the loop that works as a trigger

    '''
    if not SimulatedRun and not CameraDisabled:
        capture_display_event.set()
        capture_save_event.set()
        capture_display_queue.put(END_TOKEN)
        capture_save_queue.put(END_TOKEN)
        capture_save_queue.put(END_TOKEN)
        capture_save_queue.put(END_TOKEN)
    '''

    if not SimulatedRun and not CameraDisabled:
        camera.close()


if __name__ == '__main__':
    main(sys.argv[1:])

