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
__copyright__ = "Copyright 2022-25, Juan Remirez de Esparza"
__credits__ = ["Juan Remirez de Esparza"]
__license__ = "MIT"
__module__ = "ALT-Scann8"
__version__ = "1.12.02"
__date__ = "2025-02-20"
__version_highlight__ = "Few bugfixes (exceptions due to referencing unaccesible widgets)"
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

from PIL import ImageTk, Image, __version__ as PIL_Version

import os
import time
import locale
import json

from datetime import datetime
import logging
import sys
import getopt

try:
    import numpy as np
    numpy_loaded = True
except ImportError:
    numpy_loaded = False


try:
    import psutil
    check_disk_space = True
except ImportError:
    check_disk_space = False

try:
    import smbus
    from picamera2 import Picamera2, Preview
    from libcamera import Transform
    from libcamera import controls

    # Global variable to isolate camera specific code (Picamera vs PiCamera2)
    IsPiCamera2 = True
    # Global variable to allow basic UI testing on PC (where PiCamera imports should fail)
    SimulatedRun = False
except ImportError:
    SimulatedRun = True
    SimulatedArduinoVersion = None

try:
    import qrcode
    qr_lib_installed = True
#except ImportError:
except Exception as e:
    print(f"Qr import issue: {e}")
    qr_lib_installed = False

hw_panel_installed = False
#try:
#    from hw_panel import HwPanel
#    hw_panel_installed = True
#except Exception as e:
#    print(f"Hw panel import issue: {e}")
#    hw_panel_installed = False

import threading
import queue
import cv2
import re

from camera_resolutions import CameraResolutions
from dynamic_spinbox import DynamicSpinbox
from tooltip import Tooltips
from rolling_average import RollingAverage

try:
    import rawpy
    can_check_dng_frames_for_misalignment = True
except ImportError:
    can_check_dng_frames_for_misalignment = False

#  ######### Global variable definition ##########
win = None
as_tooltips = None
ExitingApp = False
Controller_Id = 0  # 1 - Arduino, 2 - RPi Pico
Controller_version = "Unknown"
FocusState = True
lastFocus = True
FocusZoomPosX = 0.35
FocusZoomPosY = 0.35
FocusZoomFactorX = 0.2
FocusZoomFactorY = 0.2
FreeWheelActive = False
ManualUvLedOn = False
BaseFolder = os.environ['HOME']
CurrentDir = ''
NewBaseFolder = ''
saved_locale = locale.getlocale(locale.LC_NUMERIC)   # Save current locale to restore it after displaying preview

FrameFilenamePattern = "picture-%05d.%s"
HdrFrameFilenamePattern = "picture-%05d.%1d.%s"  # HDR frames using standard filename (2/12/2023)
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
rwnd_speed_delay = 200  # informational only, should be in sync with Arduino, but for now we do not secure it
FastForwardActive = False
FastForwardErrorOutstanding = False
FastForwardEndOutstanding = False
ScanOngoing = False  # PlayState in original code from Torulf (opposite meaning)
ScanStopRequested = False  # To handle stopping scan process asynchronously, with same button as start scan
NewFrameAvailable = False  # To be set to true upon reception of Arduino event
ScanProcessError = False  # To be set to true upon reception of Arduino event
ScanProcessError_LastTime = 0
# Directory where python scrips run, to store the json file with persistent data
ScriptDir = os.path.dirname(os.path.realpath(__file__))
ConfigurationDataFilename = os.path.join(ScriptDir, "ALT-Scann8.json")
ConfigurationDataLoaded = False
# Variables to deal with remaining disk space
available_space_mb = 0
disk_space_error_to_notify = False

ArduinoTrigger = 0
last_frame_time = 0
reference_inactivity_delay = 6  # Max time (in sec) we wait for next frame. If expired, we force next frame again
max_inactivity_delay = reference_inactivity_delay
# Minimum number of steps per frame, to be passed to Arduino
MinFrameStepsS8 = 290
MinFrameStepsR8 = 240
CapstanDiameter = 14.3
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
PreviewWidth = 0
PreviewHeight = 0
FilmHoleY_Top = 0
FilmHoleY_Bottom = 0
FilmHoleHeightTop = 0
FilmHoleHeightBottom = 0
DeltaX = 0
DeltaY = 0
WinInitDone = False
FolderProcess = 0
draw_capture_canvas = 0

PiCam2PreviewEnabled = False
PostviewCounter = 0
FramesPerMinute = 0
FramesToGo = 0
RPiTemp = 0
last_temp = 1  # Needs to be different from RPiTemp the first time
LastTempInFahrenheit = False
save_bg = 'gray'
save_fg = 'black'
ZoomSize = 0
simulated_captured_frame_list = [None] * 1000
simulated_capture_image = ''
simulated_images_in_list = 0
scan_error_counter = 0  # Number of RSP_SCAN_ERROR received
scan_error_total_frames_counter = 0  # Number of frames received since error counter set to zero
scan_error_log_fullpath = ''

# Commands (RPI to Arduino)
CMD_VERSION_ID = 1
CMD_GET_CNT_STATUS = 2
CMD_RESET_CONTROLLER = 3
CMD_ADJUST_MIN_FRAME_STEPS = 4
CMD_START_SCAN = 10
CMD_TERMINATE = 11
CMD_GET_NEXT_FRAME = 12
CMD_STOP_SCAN = 13
CMD_SET_REGULAR_8 = 18
CMD_SET_SUPER_8 = 19
CMD_SWITCH_REEL_LOCK_STATUS = 20
CMD_MANUAL_UV_LED = 22
CMD_FILM_FORWARD = 30
CMD_FILM_BACKWARD = 31
CMD_SINGLE_STEP = 40
CMD_ADVANCE_FRAME = 41
CMD_ADVANCE_FRAME_FRACTION = 42
CMD_SET_PT_LEVEL = 50
CMD_SET_MIN_FRAME_STEPS = 52
CMD_SET_FRAME_FINE_TUNE = 54
CMD_SET_EXTRA_STEPS = 56
CMD_SET_UV_LEVEL = 58
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

# Options variables
ExpertMode = True
ExperimentalMode = True
PlotterEnabled = True
PlotterScroll = False
SimplifiedMode = False
UIScrollbars = False
DetectMisalignedFrames = True
MisalignedFrameTolerance = 8
FontSize = 0
LoggingMode = "INFO"
LogLevel = 20
DisableToolTips = False
ColorCodedButtons = True
WidgetsEnabledWhileScanning = True
TempInFahrenheit = False
CaptureResolution = '2028x1520'
FileType = 'jpg'
# Other options (experimental, expert...)
PreviewModuleValue = 1
NegativeImage = False
RealTimeDisplay = False
RealTimeZoom = False
AutoStopEnabled = False
AutoExpEnabled = True
AutoWbEnabled = False
AutoFrameStepsEnabled = True
AutoPtLevelEnabled = True
HdrBracketAuto = False
HdrMergeInPlace = False
MatchWaitMarginValue = 50
StepsPerFrame = 250
PtLevelValue = 200
FrameFineTuneValue = 20
FrameExtraStepsValue = 0
ScanSpeedValue = 5
StabilizationDelayValue = 100
ExposureWbAdaptPause = False
# HDR, min/max exposure range. Used to be from 10 to 150, but original values found elsewhere (1-56) are better
# Finally set to 4-104
HdrMinExp = 8
HdrMaxExp = 104
HdrBracketWidth = 50
HdrBracketShift = 0
FilmType = ''

# Categories of dependent widget groups (to enable disable them)
id_HdrCaptureActive = 1
id_HdrBracketAuto = 2
id_RealTimeDisplay = 3
id_RealTimeZoom = 4
id_AutoStopEnabled = 5
id_AutoWbEnabled = 6
id_AutoExpEnabled = 7
id_ManualScanEnabled = 8
id_AutoPtLevelEnabled = 9
id_AutoFrameStepsEnabled = 10
id_ExposureWbAdaptPause = 11

plotter_canvas = None
plotter_width = 20
plotter_height = 10
PrevPTValue = 0
PrevThresholdLevel = 0
PlotterWindowPos = 0
MaxPT = 100
MinPT = 800
Tolerance_AE = 8000
Tolerance_AWB = 1
manual_exposure_value = 55
manual_wb_red_value = 2.2
manual_wb_blue_value = 2.2
PreviousCurrentExposure = 0  # Used to spot changes in exposure, and cause a delay to allow camera to adapt
PreviousGainRed = 1
PreviousGainBlue = 1
ManualScanEnabled = False
CameraDisabled = False  # To allow testing scanner without a camera installed
KeepManualValues = False    # In case we want to keep manual values when switching to auto
# QR code to display debug info
qr_image = None

# Dictionaries for additional exposure control with PiCamera2
if not SimulatedRun and not CameraDisabled:
    AeConstraintMode_dict = {
        "Normal": controls.AeConstraintModeEnum.Normal,
        "Highlight": controls.AeConstraintModeEnum.Highlight,
        "Shadows": controls.AeConstraintModeEnum.Shadows
    }
    AeMeteringMode_dict = {
        "CentreWgt": controls.AeMeteringModeEnum.CentreWeighted,
        "Spot": controls.AeMeteringModeEnum.Spot,
        "Matrix": controls.AeMeteringModeEnum.Matrix
    }
    AeExposureMode_dict = {
        "Normal": controls.AeExposureModeEnum.Normal,
        "Long": controls.AeExposureModeEnum.Long,
        "Short": controls.AeExposureModeEnum.Short
    }
    AwbMode_dict = {
        "Auto": controls.AwbModeEnum.Auto,
        "Tungsten": controls.AwbModeEnum.Tungsten,
        "Fluorescent": controls.AwbModeEnum.Fluorescent,
        "Indoor": controls.AwbModeEnum.Indoor,
        "Daylight": controls.AwbModeEnum.Daylight,
        "Cloudy": controls.AwbModeEnum.Cloudy
    }
else:
    AeConstraintMode_dict = {
        "Normal": 1,
        "Highlight": 2,
        "Shadows": 3
    }
    AeMeteringMode_dict = {
        "CentreWgt": 1,
        "Spot": 2,
        "Matrix": 3
    }
    AeExposureMode_dict = {
        "Normal": 1,
        "Long": 2,
        "Short": 3
    }
    AwbMode_dict = {
        "Auto": 1,
        "Tungsten": 2,
        "Fluorescent": 3,
        "Indoor": 4,
        "Daylight": 5,
        "Cloudy": 6
    }

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
session_frames = 0
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
hdr_best_exp = 0
hdr_num_exposures = 3  # Changed from 4 exposures to 3, probably an odd number is better (and 3 faster than 4)
hdr_step_value = 1
hdr_exp_list = []
hdr_rev_exp_list = []
HdrViewX4Active = False
recalculate_hdr_exp_list = False
force_adjust_hdr_bracket = False
hdr_auto_bracket_frames = 8  # Every n frames, bracket is recalculated
hdr_view_4_image = None
# HDR Constants
HDR_MIN_EXP = 1
HDR_MAX_EXP = 1000
HDR_MIN_BRACKET = 4
HDR_MAX_BRACKET = HDR_MAX_EXP - HDR_MIN_EXP

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

# Configuration data
ConfigData = {
    "CurrentDate": str(datetime.now()),
    "CurrentDir": CurrentDir,
    "CurrentFrame": str(CurrentFrame),
    "CurrentExposure": 0,
    "NegativeCaptureActive": False,
    "HdrCaptureActive": HdrCaptureActive,
    "FilmType": '',
    "MinFrameStepsS8": 290,
    "MinFrameStepsR8": 240,
    "MinFrameSteps": 290,
    "FrameFineTune": 20,
    "FrameExtraSteps": 0,
    "PTLevelS8": 80,
    "PTLevelR8": 200,
    "PTLevel": 80,
    "AutoPtLevelEnabled": True,
    "AutoFrameStepsEnabled": True,
    "HdrMinExp": HdrMinExp,
    "HdrMaxExp": HdrMaxExp,
    "HdrBracketWidth": 50,
    "HdrBracketShift": 0,
    "HdrBracketAuto": HdrBracketAuto,
    "HdrMergeInPlace": HdrMergeInPlace,
    "FramesToGo": FramesToGo
}

Simulated_PT_Levels = [(546, 373),(382, 373),(52, 373),(14, 373),(59, 373),(41, 373),(151, 373),(269, 371),
                        (371, 370),(408, 370),(548, 370),(420, 370),(37, 370),(31, 370),(43, 370),(26, 370),
                        (94, 380),(291, 378),(395, 377),(465, 377),(546, 377),(313, 377),(39, 377),(6, 377),
                        (33, 377),(37, 377),(68, 375),(283, 373),(380, 372),(432, 372),(548, 372),(356, 372),
                        (41, 372),(8, 372),(31, 372),(33, 372),(189, 370),(370, 368),(458, 368),(544, 368),
                        (323, 368),(34, 368),(52, 368),(24, 368),(25, 368),(248, 384),(400, 383),(467, 383),
                        (548, 383),(342, 383),(41, 383),(16, 383),(39, 383),(18, 383),(196, 368),(358, 367),
                        (369, 367),(425, 367),(561, 367),(376, 367),(42, 367),(31, 367),(33, 367),(47, 367),
                        (190, 376),(393, 375),(533, 375),(504, 375),(119, 375),(16, 375),(53, 375),(35, 375),
                        (26, 375),(249, 363),(483, 408),(544, 408),(528, 408),(300, 408),(51, 408),(12, 408),
                        (71, 408),(34, 408),(167, 369),(367, 368),(401, 368),(434, 368),(551, 368),(385, 368),
                        (68, 368),(15, 368),(53, 368),(24, 368),(64, 373),(216, 371),(299, 370),(370, 369),
                        (408, 369),(542, 369),(376, 369),(27, 369),(22, 369)]
Simulated_PT_Levels_idx = 0
Simulated_Frame_detected = False
Simulated_Frame_displayed = False

# ********************************************************
# ALT-Scann8 code
# ********************************************************

def cmd_app_emergency_exit():
    confirm = tk.messagebox.askyesno(title='Exit without saving',
                                        message=f"Are you sure you want to exit ALT-Scann8 without saving your current settings?")
    if confirm:
        exit_app(False)


def cmd_app_standard_exit():
    exit_app(True)


def exit_app(do_save):  # Exit Application
    global win
    global ExitingApp

    # *** ALT-Scann8 shutdown starts ***
    if hw_panel_installed:
        hw_panel.ALT_Scann8_shutdown_started()

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
        send_arduino_command(CMD_TERMINATE)  # Tell Arduino we stop (to turn off uv led
        # Close preview if required
        if not CameraDisabled:
            if PiCam2PreviewEnabled:
                camera.stop_preview()
            camera.close()
    # Set window position for next run
    ConfigData["WindowPos"] = win.geometry()
    ConfigData["AutoStopActive"] = AutoStopEnabled
    ConfigData["AutoStopType"] = autostop_type.get()
    if frames_to_go_str.get() == '':
        ConfigData["FramesToGo"] = -1
    # Write session data upon exit
    if do_save:
        with open(ConfigurationDataFilename, 'w') as f:
            json.dump(ConfigData, f)

    win.config(cursor="")

    win.destroy()


def cmd_set_free_mode():
    global FreeWheelActive

    if not FreeWheelActive:
        free_btn.config(text='Lock Reels', bg='red', fg='white', relief=SUNKEN)
    else:
        free_btn.config(text='Unlock Reels', bg=save_bg, fg=save_fg, relief=RAISED)

    if not SimulatedRun:
        send_arduino_command(CMD_SWITCH_REEL_LOCK_STATUS)

    FreeWheelActive = not FreeWheelActive

    # Enable/Disable related buttons
    except_widget_global_enable(free_btn, not FreeWheelActive)


def cmd_manual_uv():
    global ManualUvLedOn

    ManualUvLedOn = not ManualUvLedOn

    if ManualUvLedOn:
        manual_uv_btn.config(text='Plotter OFF', bg='red', fg='white', relief=SUNKEN)
    else:
        manual_uv_btn.config(text='Plotter ON', bg=save_bg, fg=save_fg, relief=RAISED)

    if not SimulatedRun:
        send_arduino_command(CMD_MANUAL_UV_LED)

    # Enable/Disable related buttons
    except_widget_global_enable(manual_uv_btn, not ManualUvLedOn)


def cmd_set_auto_stop_enabled():
    global AutoStopEnabled
    if AutoStopEnabled != auto_stop_enabled.get():
        AutoStopEnabled = auto_stop_enabled.get()
    widget_list_enable([id_AutoStopEnabled])
    if not SimulatedRun:
        send_arduino_command(CMD_SET_AUTO_STOP, AutoStopEnabled and autostop_type.get() == 'No_film')
        logging.debug(f"Sent Auto Stop to Arduino: {AutoStopEnabled and autostop_type.get() == 'No_film'}")
    logging.debug(f"Set Auto Stop: {AutoStopEnabled}, {autostop_type.get()}")


# Enable/Disable camera zoom to facilitate focus
def cmd_set_focus_zoom():
    global RealTimeZoom, ZoomSize
    RealTimeZoom = real_time_zoom.get()
    if RealTimeZoom:
        widget_enable(real_time_display_checkbox, False)
    else:
        widget_enable(real_time_display_checkbox, True)

    if not SimulatedRun and not CameraDisabled:
        if RealTimeZoom:
            ZoomSize = camera.capture_metadata()['ScalerCrop']
            logging.debug(f"ScalerCrop: {ZoomSize}")
            camera.set_controls(
                {"ScalerCrop": (int(FocusZoomPosX * ZoomSize[2]), int(FocusZoomPosY * ZoomSize[3])) +
                               (int(FocusZoomFactorX * ZoomSize[2]), int(FocusZoomFactorY * ZoomSize[3]))})
        else:
            camera.set_controls({"ScalerCrop": ZoomSize})

    time.sleep(.2)

    # Enable disable buttons for focus move
    widget_enable(focus_lf_btn, RealTimeZoom)
    widget_enable(focus_up_btn, RealTimeZoom)
    widget_enable(focus_dn_btn, RealTimeZoom)
    widget_enable(focus_rt_btn, RealTimeZoom)
    widget_enable(focus_plus_btn, RealTimeZoom)
    widget_enable(focus_minus_btn, RealTimeZoom)


def adjust_focus_zoom():
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"ScalerCrop": (int(FocusZoomPosX * ZoomSize[2]), int(FocusZoomPosY * ZoomSize[3])) +
                                           (int(FocusZoomFactorX * ZoomSize[2]), int(FocusZoomFactorY * ZoomSize[3]))})


def cmd_set_focus_up():
    global FocusZoomPosY
    if FocusZoomPosY >= 0.05:
        FocusZoomPosY = round(FocusZoomPosY - 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom up (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX,
                      FocusZoomFactorY)


def cmd_set_focus_left():
    global FocusZoomPosX
    if FocusZoomPosX >= 0.05:
        FocusZoomPosX = round(FocusZoomPosX - 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom left (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX,
                      FocusZoomFactorY)


def cmd_set_focus_right():
    global FocusZoomPosX
    if FocusZoomPosX <= (1 - (FocusZoomFactorX - 0.05)):
        FocusZoomPosX = round(FocusZoomPosX + 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom right (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX,
                      FocusZoomFactorY)


def cmd_set_focus_down():
    global FocusZoomPosY
    if FocusZoomPosY <= (1 - (FocusZoomFactorY - 0.05)):
        FocusZoomPosY = round(FocusZoomPosY + 0.05, 2)
        adjust_focus_zoom()
        logging.debug("Zoom down (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX,
                      FocusZoomFactorY)


def cmd_set_focus_plus():
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
        logging.debug("Zoom plus (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX,
                      FocusZoomFactorY)


def cmd_set_focus_minus():
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
        logging.debug("Zoom plus (%.2f,%.2f) (%.2f,%.2f)", FocusZoomPosX, FocusZoomPosY, FocusZoomFactorX,
                      FocusZoomFactorY)


def cmd_set_new_folder():
    global BaseFolder, CurrentDir, CurrentFrame
    global scan_error_counter, scan_error_total_frames_counter, scan_error_log_fullpath, scan_error_counter_value

    requested_dir = ""
    success = False

    while requested_dir == "" or requested_dir is None:
        requested_dir = tk.simpledialog.askstring(title="Enter new folder name",
                                                  prompt=f"Enter new folder name (to be created under {BaseFolder}):")
        if requested_dir is None:
            return
        if requested_dir == "":
            tk.messagebox.showerror("Error!", "Please specify a name for the folder to be created.")

    newly_created_dir = os.path.join(BaseFolder, requested_dir)

    if not os.path.isdir(newly_created_dir):
        try:
            os.mkdir(newly_created_dir)
            CurrentFrame = 0
            CurrentDir = newly_created_dir
            success = True
        except FileExistsError:
            tk.messagebox.showerror("Error", f"Folder {requested_dir} already exists.")
        except PermissionError:
            tk.messagebox.showerror("Error", f"Folder {requested_dir}, "
                                             "permission denied to create directory.")
        except OSError as e:
            tk.messagebox.showerror("Error", f"While creating folder {requested_dir}, OS error: {e}.")
        except Exception as e:
            tk.messagebox.showerror("Error", f"While creating folder {requested_dir}, "
                                             f"unexpected error: {e}.")
    else:
        tk.messagebox.showerror("Error!", "Folder " + requested_dir + " already exists.")

    if success:
        folder_frame_target_dir.config(text=CurrentDir)
        Scanned_Images_number.set(CurrentFrame)
        scan_error_counter = scan_error_total_frames_counter = 0
        scan_error_counter_value.set(f"0 (0%)")
        with open(scan_error_log_fullpath, 'a') as f:
            f.write(f"Starting scan error log for {CurrentDir}\n")
        ConfigData["CurrentDir"] = str(CurrentDir)
        ConfigData["CurrentFrame"] = str(CurrentFrame)


def cmd_detect_misaligned_frames():
    global DetectMisalignedFrames, misaligned_tolerance_label
    DetectMisalignedFrames = detect_misaligned_frames.get()
    scan_error_counter_value_label.config(state = NORMAL if DetectMisalignedFrames and (FileType != "dng" or can_check_dng_frames_for_misalignment) else DISABLED)


def cmd_select_file_type(selected):
    global FileType
    misaligned_tolerance_label.config(state = NORMAL if detect_misaligned_frames.get() and (file_type_dropdown_selected.get() != "dng" or can_check_dng_frames_for_misalignment) else DISABLED)
    misaligned_tolerance_spinbox.config(state = NORMAL if detect_misaligned_frames.get() and (file_type_dropdown_selected.get() != "dng" or can_check_dng_frames_for_misalignment) else DISABLED)



def cmd_settings_popup_dismiss():
    global options_dlg
    global BaseFolder, CurrentDir

    options_dlg.grab_release()
    options_dlg.destroy()


def cmd_settings_popup_accept():
    global options_dlg
    global ExpertMode, ExperimentalMode, PlotterEnabled, SimplifiedMode, UIScrollbars, DetectMisalignedFrames, MisalignedFrameTolerance, FontSize, DisableToolTips
    global WidgetsEnabledWhileScanning, LoggingMode, LogLevel, ColorCodedButtons, TempInFahrenheit
    global CaptureResolution, FileType, AutoExpEnabled, AutoWbEnabled, AutoFrameStepsEnabled, AutoPtLevelEnabled
    global FrameFineTuneValue, ScanSpeedValue
    global qr_code_frame
    global CapstanDiameter, capstan_diameter_float
    global ConfigData, BaseFolder

    ConfigData["PopupPos"] = options_dlg.geometry()

    refresh_ui = False
    if SimplifiedMode != simplified_mode.get():
        refresh_ui = True
        SimplifiedMode = simplified_mode.get()
        ConfigData["SimplifiedMode"] = SimplifiedMode
        # If no expert mode, set automated settings
        if SimplifiedMode:
            ExpertMode = False
            ExperimentalMode = False
            PlotterEnabled = False
            AutoExpEnabled = True
            AutoWbEnabled = True
            AutoFrameStepsEnabled = True
            AutoPtLevelEnabled = True
            FrameFineTuneValue = 20
            ScanSpeedValue = 5
        else:
            ExpertMode = ConfigData['ExpertMode'] = True
            ExperimentalMode = ConfigData['ExperimentalMode'] = True
            PlotterEnabled = ConfigData['PlotterEnabled'] = True
            AutoExpEnabled = ConfigData['AutoExpEnabled']
            AutoWbEnabled = ConfigData['AutoWbEnabled']
            AutoFrameStepsEnabled = ConfigData['AutoFrameStepsEnabled']  # FrameStepsAuto
            AutoPtLevelEnabled = ConfigData['AutoPtLevelEnabled']  # PTLevelAuto
            FrameFineTuneValue = ConfigData["FrameFineTune"]
            ScanSpeedValue = ConfigData["ScanSpeed"]
        if not SimulatedRun and not CameraDisabled:
            camera.set_controls({"AeEnable": AutoExpEnabled})
            camera.set_controls({"AwbEnable": AutoWbEnabled})
            send_arduino_command(CMD_SET_PT_LEVEL, 0)
            send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0)
            send_arduino_command(CMD_SET_FRAME_FINE_TUNE, FrameFineTuneValue)
            send_arduino_command(CMD_SET_SCAN_SPEED, ScanSpeedValue)
            send_arduino_command(CMD_REPORT_PLOTTER_INFO, PlotterEnabled)
    if UIScrollbars != ui_scrollbars.get():
        refresh_ui = True
        UIScrollbars = ui_scrollbars.get()
        ConfigData["UIScrollbars"] = UIScrollbars
    if MisalignedFrameTolerance != misaligned_tolerance_int.get():
        MisalignedFrameTolerance = misaligned_tolerance_int.get()
        ConfigData["MisalignedFrameTolerance"] = MisalignedFrameTolerance
    if DisableToolTips != disable_tooltips.get():
        DisableToolTips = disable_tooltips.get()
        ConfigData["DisableToolTips"] = DisableToolTips
    if WidgetsEnabledWhileScanning != widgets_enabled_while_scanning.get():
        WidgetsEnabledWhileScanning = widgets_enabled_while_scanning.get()
        ConfigData["WidgetsEnabledWhileScanning"] = WidgetsEnabledWhileScanning
    if FontSize != font_size_int.get():
        refresh_ui = True
        FontSize = font_size_int.get()
        ConfigData["FontSize"] = FontSize
    if CapstanDiameter != capstan_diameter_float.get():
        CapstanDiameter = capstan_diameter_float.get()
        ConfigData["CapstanDiameter"] = CapstanDiameter
        send_arduino_command(CMD_ADJUST_MIN_FRAME_STEPS, int(CapstanDiameter*10))
    if LoggingMode != debug_level_selected.get():
        LoggingMode = debug_level_selected.get()
        if not SimplifiedMode:
            if LoggingMode == 'DEBUG':
                refresh_ui = True   # To display qr code
            elif qr_code_frame != None:
                destroy_widgets(qr_code_frame)
                qr_code_frame.destroy()
                qr_code_frame = None
        LogLevel = getattr(logging, LoggingMode.upper(), None)
        if not isinstance(LogLevel, int):
            raise ValueError('Invalid log level: %s' % LogLevel)
        ConfigData["LogLevel"] = LogLevel
        logging.getLogger().setLevel(LogLevel)
    if ColorCodedButtons != color_coded_buttons.get():
        refresh_ui = True
        ColorCodedButtons = color_coded_buttons.get()
        ConfigData["ColorCodedButtons"] = ColorCodedButtons
    if TempInFahrenheit != temp_in_fahrenheit.get():
        TempInFahrenheit = temp_in_fahrenheit.get()
        ConfigData["TempInFahrenheit"] = TempInFahrenheit
    if CaptureResolution != resolution_dropdown_selected.get():
        CaptureResolution = resolution_dropdown_selected.get()
        ConfigData["CaptureResolution"] = CaptureResolution
        camera_resolutions.set_active(CaptureResolution)
        if resolution_dropdown_selected.get() == "4056x3040":
            max_inactivity_delay = reference_inactivity_delay * 2
        else:
            max_inactivity_delay = reference_inactivity_delay
        send_arduino_command(CMD_SET_STALL_TIME, max_inactivity_delay)
        logging.debug(f"Set max_inactivity_delay as {max_inactivity_delay}")
        PiCam2_change_resolution()
    if FileType != file_type_dropdown_selected.get():
        FileType = file_type_dropdown_selected.get()
        ConfigData["FileType"] = FileType
    if NewBaseFolder != BaseFolder:
        BaseFolder = NewBaseFolder
        ConfigData["BaseFolder"] = str(BaseFolder)

    capture_info_str.set(f"{FileType} - {CaptureResolution}")

    if refresh_ui:
        create_main_window()
        refresh_qr_code()
        widget_list_enable([id_RealTimeDisplay, id_RealTimeZoom, id_AutoStopEnabled])
        if ExpertMode:
            widget_list_enable([id_AutoWbEnabled, id_AutoExpEnabled, id_AutoPtLevelEnabled, id_AutoFrameStepsEnabled,
                                id_ExposureWbAdaptPause])
        if ExperimentalMode:
            widget_list_enable([id_HdrCaptureActive, id_HdrBracketAuto, id_ManualScanEnabled])

    if not SimplifiedMode:
        detect_misaligned_frames_btn.config(state = NORMAL if (FileType != "dng" or can_check_dng_frames_for_misalignment) else DISABLED)
        scan_error_counter_value_label.config(state = NORMAL if DetectMisalignedFrames and (FileType != "dng" or can_check_dng_frames_for_misalignment) else DISABLED)

    if DisableToolTips:
        as_tooltips.disable()
    else:
        as_tooltips.enable()

    options_dlg.grab_release()
    options_dlg.destroy()


def cmd_settings_popup():
    global options_dlg, win
    global ExpertMode, ExperimentalMode, PlotterEnabled, UIScrollbars, DetectMisalignedFrames, MisalignedFrameTolerance, FontSize, DisableToolTips
    global WidgetsEnabledWhileScanning, LoggingMode, ColorCodedButtons, TempInFahrenheit
    global CaptureResolution, FileType
    global simplified_mode, ui_scrollbars, misaligned_tolerance_int, font_size_int, disable_tooltips
    global widgets_enabled_while_scanning, debug_level_selected, color_coded_buttons, temp_in_fahrenheit
    global resolution_dropdown_selected, file_type_dropdown_selected
    global base_folder_btn
    global NewBaseFolder
    global CapstanDiameter, capstan_diameter_float
    global misaligned_tolerance_label, misaligned_tolerance_spinbox, detect_misaligned_frames_btn

    # Make working copy of base folder
    NewBaseFolder = BaseFolder

    options_row = 0

    options_dlg = tk.Toplevel(win)

    if 'PopupPos' in ConfigData:
        options_dlg.geometry(f"+{ConfigData['PopupPos'].split('+', 1)[1]}")

    options_dlg.title("Settings ALT-Scann8")
    # options_dlg.geometry(f"300x100")
    options_dlg.rowconfigure(0, weight=1)
    options_dlg.columnconfigure(0, weight=1)

    # Expert Mode
    simplified_mode = tk.BooleanVar(value=SimplifiedMode)
    simplified_mode_btn = tk.Checkbutton(options_dlg, variable=simplified_mode, onvalue=True, offvalue=False,
                                       font=("Arial", FontSize - 1), text="Simplified UI")
    simplified_mode_btn.grid(row=options_row, column=0, columnspan=3, sticky="W")
    as_tooltips.add(simplified_mode_btn, "Enable simplified UI")
    options_row += 1

    # Disable tootilps
    disable_tooltips = tk.BooleanVar(value=DisableToolTips)
    disable_tooltips_btn = tk.Checkbutton(options_dlg, variable=disable_tooltips, onvalue=True, offvalue=False,
                                       font=("Arial", FontSize - 1), text="Disable tooltips")
    disable_tooltips_btn.grid(row=options_row, column=0, columnspan=3, sticky="W")
    as_tooltips.add(disable_tooltips_btn, "Disable tooltips")
    options_row += 1

    # Widgets enabled while scanning
    widgets_enabled_while_scanning = tk.BooleanVar(value=WidgetsEnabledWhileScanning)
    widgets_enabled_while_scanning_btn = tk.Checkbutton(options_dlg, variable=widgets_enabled_while_scanning,
                                                        onvalue=True, offvalue=False, font=("Arial", FontSize - 1),
                                                        text="Keep widgets enabled")
    widgets_enabled_while_scanning_btn.grid(row=options_row, column=0, columnspan=3, sticky="W")
    as_tooltips.add(widgets_enabled_while_scanning_btn, "Keep widgets enabled while scanning")
    options_row += 1

    # Color coded buttons
    color_coded_buttons = tk.BooleanVar(value=ColorCodedButtons)
    color_coded_buttons_btn = tk.Checkbutton(options_dlg, variable=color_coded_buttons, text="Color coded buttons",
                                             onvalue=True, offvalue=False, font=("Arial", FontSize - 1))
    color_coded_buttons_btn.grid(row=options_row, column=0, columnspan=3, sticky="W")
    as_tooltips.add(color_coded_buttons_btn, "Use colors to highlight button status")
    options_row += 1

    temp_in_fahrenheit = tk.BooleanVar(value=TempInFahrenheit)
    temp_in_fahrenheit_checkbox = tk.Checkbutton(options_dlg, variable=temp_in_fahrenheit, text='Fahrenheit',
                                                 onvalue=True, offvalue=False, font=("Arial", FontSize - 1))
    temp_in_fahrenheit_checkbox.grid(row=options_row, column=0, columnspan=3, sticky="W")
    as_tooltips.add(temp_in_fahrenheit_checkbox, "Display Raspberry Pi Temperature in Fahrenheit.")
    options_row += 1

    # Display scrollbars
    ui_scrollbars = tk.BooleanVar(value=UIScrollbars)
    ui_scrollbars_btn = tk.Checkbutton(options_dlg, variable=ui_scrollbars, onvalue=True, offvalue=False,
                                       font=("Arial", FontSize - 1), text="Display scrollbars")
    ui_scrollbars_btn.grid(row=options_row, column=0, columnspan=3, sticky="W")
    as_tooltips.add(ui_scrollbars_btn, "Display scrollbars in main window (useful for lower resolutions)")
    options_row += 1

    # Misaligned frame detection tolerance (percentage, 5 by default)
    misaligned_tolerance_label = tk.Label(options_dlg, text="Misalign tolerance:", font=("Arial", FontSize-1))
    misaligned_tolerance_label.grid(row=options_row, column=0, columnspan=1, sticky='W', padx=(2*FontSize,0))
    as_tooltips.add(misaligned_tolerance_label, "Tolerance for frame misalignment detection (8% default)")
    misaligned_tolerance_int = tk.IntVar(value=MisalignedFrameTolerance)
    misaligned_tolerance_spinbox = DynamicSpinbox(options_dlg, width=2, from_=0, to=100,
                                      textvariable=misaligned_tolerance_int, increment=1, font=("Arial", FontSize - 1))
    misaligned_tolerance_spinbox.grid(row=options_row, column=1, sticky='W')
    options_row += 1

    # Font Size
    font_size_label = tk.Label(options_dlg, text="Main UI font size:", font=("Arial", FontSize-1))
    font_size_label.grid(row=options_row, column=0, columnspan=1, sticky='W', padx=(2*FontSize,0))
    as_tooltips.add(font_size_label, "Base font size used in main window")
    font_size_int = tk.IntVar(value=12)
    font_size_int.set(FontSize)
    font_size_spinbox = DynamicSpinbox(options_dlg, width=2, from_=6, to=20,
                                      textvariable=font_size_int, increment=1, font=("Arial", FontSize - 1))
    font_size_spinbox.grid(row=options_row, column=1, sticky='W')
    options_row += 1

    # Capstan diameter
    capstan_diameter_label = tk.Label(options_dlg, text="Capstan diameter:", font=("Arial", FontSize-1))
    capstan_diameter_label.grid(row=options_row, column=0, columnspan=1, sticky='W', padx=(2*FontSize,0))
    as_tooltips.add(capstan_diameter_label, "Base font size used in main window")
    capstan_diameter_frame = Frame(options_dlg, name='capstan_diameter_frame')
    capstan_diameter_frame.grid(row=options_row, column=1, sticky='W')

    capstan_diameter_float = tk.DoubleVar(value=CapstanDiameter)
    capstan_diameter_spinbox = DynamicSpinbox(capstan_diameter_frame, width=4, from_=8, to=30,
                                      format="%.1f", textvariable=capstan_diameter_float, increment=0.1, font=("Arial", FontSize - 1))
    capstan_diameter_spinbox.pack(side=LEFT)
    capstan_diameter_mm_label = tk.Label(capstan_diameter_frame, text="mm", font=("Arial", FontSize-1))
    capstan_diameter_mm_label.pack(side=LEFT)
    options_row += 1

    # Capture resolution Dropdown
    # Drop down to select capture resolution
    # Dropdown menu options
    resolution_list = camera_resolutions.get_list()
    resolution_dropdown_selected = tk.StringVar()
    resolution_label = Label(options_dlg, text='Resolution:', font=("Arial", FontSize-1))
    resolution_label.grid(row=options_row, column=0, sticky="W", padx=(2*FontSize,0))
    resolution_dropdown = OptionMenu(options_dlg, resolution_dropdown_selected, *resolution_list)
    resolution_dropdown.config(takefocus=1, font=("Arial", FontSize-1))
    resolution_dropdown_selected.set(CaptureResolution)
    resolution_dropdown.grid(row=options_row, column=1, sticky='W')
    as_tooltips.add(resolution_label, "Select the resolution to use when capturing the frames. Modes flagged with "
                                         "* are cropped, requiring lens adjustment")
    options_row += 1

    # File format (JPG or PNG)
    # Drop down to select file type
    # Dropdown menu options
    file_type_list = ["jpg", "png", "dng"]
    file_type_dropdown_selected = tk.StringVar()

    # Target file type
    file_type_label = Label(options_dlg, text='Type:', font=("Arial", FontSize-1))
    file_type_label.grid(row=options_row, column=0, sticky="W", padx=(2*FontSize,0))
    file_type_dropdown = OptionMenu(options_dlg, file_type_dropdown_selected, *file_type_list, command=cmd_select_file_type)
    file_type_dropdown.config(takefocus=1, font=("Arial", FontSize-1))
    file_type_dropdown_selected.set(FileType)  # Set the initial value
    file_type_dropdown.grid(row=options_row, column=1, sticky='W')
    # file_type_dropdown.config(state=DISABLED)
    as_tooltips.add(file_type_label, "Select format to safe film frames (JPG, PNG, DNG)")

    options_row += 1

    # Base ALT-Scann8 folder
    base_folder_label = Label(options_dlg, text='Base folder:', font=("Arial", FontSize-1))
    base_folder_label.grid(row=options_row, column=0, sticky="W", padx=(2*FontSize,0))
    base_folder_btn = Button(options_dlg, text=NewBaseFolder, command=set_base_folder,
                                 activebackground='#f0f0f0', font=("Arial", FontSize-1))
    base_folder_btn.grid(row=options_row, column=1, sticky='W')
    as_tooltips.add(base_folder_label, "Select existing folder as base folder for ALT-Scann8.")

    options_row += 1

    # Debug dropdown menu options
    debug_level_list = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    debug_level_selected = tk.StringVar()
    debug_level_label = Label(options_dlg, text='Debug level:', font=("Arial", FontSize-1))
    debug_level_label.grid(row=options_row, column=0, sticky='W', padx=(2*FontSize,0))
    debug_level_dropdown = OptionMenu(options_dlg, debug_level_selected, *debug_level_list)
    debug_level_dropdown.config(takefocus=1, font=("Arial", FontSize-1))
    debug_level_selected.set(logging.getLevelName(LogLevel))  # Set the initial value
    debug_level_dropdown.grid(row=options_row, column=1, sticky='W')
    as_tooltips.add(debug_level_label, "Select logging level, for troubleshooting. Use DEBUG when reporting an issue in Github.")

    options_row += 1

    options_cancel_btn = tk.Button(options_dlg, text="Cancel", command=cmd_settings_popup_dismiss, width=8,
                                   font=("Arial", FontSize))
    options_cancel_btn.grid(row=options_row, column=0, padx=10, pady=5, sticky='W')
    options_ok_btn = tk.Button(options_dlg, text="OK", command=cmd_settings_popup_accept, width=8,
                               font=("Arial", FontSize))
    options_ok_btn.grid(row=options_row, column=1, padx=10, pady=5, sticky='E')

    # arrange status for multidependent widgets. Initially enabled, increase counter for each disable condition   
    misaligned_tolerance_label.config(state = NORMAL if DetectMisalignedFrames and (FileType != "dng" or can_check_dng_frames_for_misalignment) else DISABLED)
    misaligned_tolerance_spinbox.config(state = NORMAL if DetectMisalignedFrames and (FileType != "dng" or can_check_dng_frames_for_misalignment) else DISABLED)

    options_dlg.protocol("WM_DELETE_WINDOW", cmd_settings_popup_dismiss)  # intercept close button
    options_dlg.transient(win)  # dialog window is related to main
    options_dlg.wait_visibility()  # can't grab until window appears, so we wait
    options_dlg.grab_set()  # ensure all input goes to our window
    options_dlg.wait_window()  # block until window is destroyed


def get_last_frame_popup_dismiss():
    last_frame_dlg.grab_release()
    last_frame_dlg.destroy()


def get_last_frame_popup(last_frame):
    global win
    global last_frame_dlg
    last_frame_dlg = tk.Toplevel(win)
    last_frame_dlg.title("Last frame")
    # last_frame_dlg.geometry(f"300x100")
    last_frame_dlg.rowconfigure(0, weight=1)
    last_frame_dlg.columnconfigure(0, weight=1)

    last_frame_label = tk.Label(last_frame_dlg, text="Enter number of last captured frame")
    last_frame_label.grid(row=0, column=0, columnspan=2, sticky='nsew', padx=10, pady=5)
    last_frame_int = tk.IntVar(value=0)
    last_frame_int.set(last_frame)
    last_frame_entry = tk.Entry(last_frame_dlg, textvariable=last_frame_int, width=6, font=("Arial", FontSize),
                                justify="right")
    last_frame_entry.grid(row=1, column=0, columnspan=2, padx=10, pady=5)
    last_frame_ok_btn = tk.Button(last_frame_dlg, text="OK", command=get_last_frame_popup_dismiss)
    last_frame_ok_btn.grid(row=2, column=0, padx=10, pady=5)
    last_frame_dlg.protocol("WM_DELETE_WINDOW", get_last_frame_popup_dismiss)  # intercept close button
    last_frame_dlg.transient(win)  # dialog window is related to main
    last_frame_dlg.wait_visibility()  # can't grab until window appears, so we wait
    last_frame_dlg.grab_set()  # ensure all input goes to our window
    last_frame_dlg.wait_window()  # block until window is destroyed
    return last_frame_int.get()


def generate_qr_code_info():
    data = (f"ALT-Scann8:{__version__}\n"
            f"Controller:{Controller_version}\n"
            f"Python:{sys.version}\n"
            f"TkInter:{tk.TkVersion}\n"
            f"PIL:{PIL_Version}\n"
            f"Numpy:{np.__version__}\n"
            f"OpenCV:{cv2.__version__}\n"
            f"Res:{CaptureResolution}\n"
            f"File:{FileType}\n"
            f"Font:{FontSize}\n"
            f"Cpst:{CapstanDiameter}\n")
    return data


def generate_qr_code_image():
    qr_code = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    data = generate_qr_code_info()
    qr_code.add_data(data)
    qr_code.make(fit=True)

    # Create an image from the QR Code instance
    qr_img = qr_code.make_image(fill_color="black", back_color="white")
    return qr_img


def display_qr_code_info_dismiss():
    qr_display_dlg.grab_release()
    qr_display_dlg.destroy()


def copy_qr_code_info(event=None):
    global win
    qr_info_text.tag_add("sel", "1.0", "end")
    selected_text = qr_info_text.selection_get()
    if selected_text:
        win.clipboard_clear()
        win.clipboard_append(selected_text)
    qr_info_text.tag_remove("sel", "1.0", "end")


def display_qr_code_info(event=None):
    global win
    global qr_display_dlg, qr_info_text

    qr_display_dlg = tk.Toplevel(win)

    if 'QrPos' in ConfigData:
        qr_display_dlg.geometry(f"+{ConfigData['QrPos'].split('+', 1)[1]}")

    qr_display_dlg.title("Debug info")
    qr_display_dlg.rowconfigure(0, weight=1)
    qr_display_dlg.columnconfigure(0, weight=1)

    data = generate_qr_code_info()
    lines = data.split('\n')
    num_lines = len(lines)
    max_length = 0
    for line in lines:
        line_length = len(line)
        if line_length > max_length:
            max_length = line_length
    qr_info_text = tk.Text(qr_display_dlg, wrap="word", font=("Arial", FontSize - 6),
                                     name='qr_info_text', height=num_lines, width=max_length)
    qr_info_text.insert("end", data)
    qr_info_text.config(state = DISABLED)
    qr_info_text.pack(side=TOP, padx=5, pady=5)

    qr_info_dismiss_btn = tk.Button(qr_display_dlg, text="Dismiss", command=display_qr_code_info_dismiss)
    qr_info_dismiss_btn.pack(side=LEFT, fill="x", expand=True, pady=5)

    qr_info_copy_btn = tk.Button(qr_display_dlg, text="Copy", command=copy_qr_code_info)
    qr_info_copy_btn.pack(side=RIGHT, fill="x", expand=True, pady=5)

    qr_display_dlg.protocol("WM_DELETE_WINDOW", display_qr_code_info_dismiss)  # intercept close button

    qr_display_dlg.transient(win)  # dialog window is related to main
    qr_display_dlg.wait_visibility()
    qr_display_dlg.grab_set()
    #qr_display_dlg.wait_window()  # block until window is destroyed


def refresh_qr_code():
    global win
    global qr_image

    if SimplifiedMode or LoggingMode != 'DEBUG':
        return
    
    win.update_idletasks()

    if qr_lib_installed:
        qr_img = generate_qr_code_image()

        size = min(qr_code_canvas.winfo_width(), qr_code_canvas.winfo_height())

        # Get Pillow version number
        major_version = int(PIL_Version.split('.')[0])
        minor_version = int(PIL_Version.split('.')[1])

        # Choose resampling method based on Pillow version
        if major_version > 8 or major_version == 8 and minor_version > 1:
            resampling_method = Image.Resampling.LANCZOS
        else:
            resampling_method = Image.ANTIALIAS
        # Resize the image to fit within the canvas
        qr_img = qr_img.resize((size, size), resampling_method)

        qr_image = ImageTk.PhotoImage(qr_img)
        # Convert the Image object into a Tkinter-compatible image object

        # Draw the image on the canvas
        qr_code_canvas.create_image(int((qr_code_canvas.winfo_width()-size)/2),
                                    int((qr_code_canvas.winfo_height()-size)/2), anchor=tk.NW, image=qr_image)
    else:
        qr_code_canvas.delete("all")
        data = generate_qr_code_info()
        qr_code_canvas.create_text(10, 10, anchor=tk.NW, text=data, font=f"Helvetica {7}")

def set_base_folder():
    global BaseFolder, CurrentDir, NewBaseFolder
    options_dlg.withdraw()  # Hide the root window
    TmpBaseFolder = filedialog.askdirectory(initialdir=BaseFolder, title="Select base ALT-Scann8 folder", parent=None)
    if not os.path.isdir(TmpBaseFolder):
        tk.messagebox.showerror("Error!", f"Folder {TmpBaseFolder} does not exist. Please specify an existing folder name.")
    else:
        NewBaseFolder = TmpBaseFolder
        if CurrentDir == '':
            CurrentDir = NewBaseFolder
        base_folder_btn.config(text=NewBaseFolder)

    options_dlg.deiconify()


def cmd_set_existing_folder():
    global CurrentDir, CurrentFrame
    global scan_error_counter, scan_error_total_frames_counter, scan_error_counter_value

    if CurrentDir == '':
        CurrentDir = BaseFolder

    if not SimulatedRun:
        NewDir = filedialog.askdirectory(initialdir=CurrentDir, title="Select existing folder for capture")
    else:
        NewDir = filedialog.askdirectory(initialdir=CurrentDir,
                                         title="Select existing folder with snapshots for simulated run")
    if not NewDir:
        return

    # Get number of files and highest frame number in selected folder
    filecount = 0
    last_frame = 0
    for name in os.listdir(NewDir):
        if os.path.isfile(os.path.join(NewDir, name)):
            # Extract frame number using regular expression
            frame_number = re.findall(r'\d+', name)
            if len(frame_number) > 0:
                last_frame = max(last_frame, int(frame_number[0]))  # Only one number in the filename, so we take the first
                filecount += 1

    NewCurrentFrame = get_last_frame_popup(last_frame)

    if filecount > 0 and NewCurrentFrame < last_frame:
        confirm = tk.messagebox.askyesno(title='Files exist in target folder',
                                         message=f"Newly selected folder already contains {filecount} files."
                                                 f"\r\nSetting {NewCurrentFrame} as last captured frame will overwrite "
                                                 f"{last_frame - NewCurrentFrame} frames."
                                                 "Are you sure you want to continue?")
    else:
        confirm = True

    if confirm:
        CurrentFrame = NewCurrentFrame
        CurrentDir = NewDir
        scan_error_counter = scan_error_total_frames_counter = 0
        scan_error_counter_value.set(f"0 (0%)")
        with open(scan_error_log_fullpath, 'a') as f:
            f.write(f"Starting scan error log for {CurrentDir}\n")

        Scanned_Images_number.set(CurrentFrame)
        ConfigData["CurrentFrame"] = str(CurrentFrame)

        folder_frame_target_dir.config(text=CurrentDir)
        ConfigData["CurrentDir"] = str(CurrentDir)


def cmd_set_auto_wb():
    global manual_wb_red_value, manual_wb_blue_value, AutoWbEnabled

    if not ExpertMode:
        return

    AutoWbEnabled = AWB_enabled.get()
    ConfigData["AutoWbEnabled"] = AutoWbEnabled
    widget_list_enable([id_AutoWbEnabled])
    wb_blue_spinbox.config(state='readonly' if AutoWbEnabled else NORMAL)
    wb_red_spinbox.config(state='readonly' if AutoWbEnabled else NORMAL)

    if AutoWbEnabled:
        if KeepManualValues:
            manual_wb_red_value = wb_red_value.get()
            manual_wb_blue_value = wb_blue_value.get()
        auto_wb_red_btn.config(text="AWB Red:")
        auto_wb_blue_btn.config(text="AWB Blue:")
    else:
        if KeepManualValues:
            ConfigData["GainRed"] = manual_wb_red_value
            ConfigData["GainBlue"] = manual_wb_blue_value
            wb_red_value.set(manual_wb_red_value)
            wb_blue_value.set(manual_wb_blue_value)
        auto_wb_red_btn.config(text="WB Red:")
        auto_wb_blue_btn.config(text="WB Blue:")

    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"AwbEnable": AutoWbEnabled})
        if not AutoWbEnabled and KeepManualValues:
            camera_colour_gains = (wb_red_value.get(), wb_blue_value.get())
            camera.set_controls({"ColourGains": camera_colour_gains})


def cmd_Manual_scan_activated_selection():
    global ManualScanEnabled
    ManualScanEnabled = Manual_scan_activated.get()
    widget_enable(manual_scan_advance_fraction_5_btn, ManualScanEnabled)
    widget_enable(manual_scan_advance_fraction_20_btn, ManualScanEnabled)
    widget_enable(manual_scan_take_snap_btn, ManualScanEnabled)


def manual_scan_advance_frame_fraction(steps):
    if not ExperimentalMode:
        return
    if not SimulatedRun:
        send_arduino_command(CMD_ADVANCE_FRAME_FRACTION, steps)
        time.sleep(0.2)
        capture('normal')
        time.sleep(0.2)


def cmd_manual_scan_advance_frame_fraction_5():
    manual_scan_advance_frame_fraction(5)


def cmd_manual_scan_advance_frame_fraction_20():
    manual_scan_advance_frame_fraction(20)


def cmd_manual_scan_take_snap():
    if not ExperimentalMode:
        return
    if not SimulatedRun:
        capture('manual')
        time.sleep(0.2)
        send_arduino_command(CMD_ADVANCE_FRAME)
        time.sleep(0.2)
        capture('normal')
        time.sleep(0.2)


def rwnd_speed_down():
    global rwnd_speed_delay

    if not SimulatedRun:
        send_arduino_command(CMD_INCREASE_WIND_SPEED)
    if rwnd_speed_delay + rwnd_speed_delay * 0.1 < 4000:
        rwnd_speed_delay += rwnd_speed_delay * 0.1
    else:
        rwnd_speed_delay = 4000
    rwnd_speed_control_spinbox.config(text=str(round(60 / (rwnd_speed_delay * 375 / 1000000))) + 'rpm')


def rwnd_speed_up():
    global rwnd_speed_delay

    if not SimulatedRun:
        send_arduino_command(CMD_DECREASE_WIND_SPEED)
    if rwnd_speed_delay - rwnd_speed_delay * 0.1 > 200:
        rwnd_speed_delay -= rwnd_speed_delay * 0.1
    else:
        rwnd_speed_delay = 200
    rwnd_speed_control_spinbox.config(text=str(round(60 / (rwnd_speed_delay * 375 / 1000000))) + 'rpm')


def cmd_frame_extra_steps_selection():
    global FrameExtraStepsValue
    FrameExtraStepsValue = value_normalize(frame_extra_steps_value, -30, 30, 0)
    ConfigData["FrameExtraSteps"] = FrameExtraStepsValue
    send_arduino_command(CMD_SET_EXTRA_STEPS, FrameExtraStepsValue)


def cmd_advance_movie(from_arduino=False):
    global AdvanceMovieActive

    # Update button text
    if not AdvanceMovieActive:  # Advance movie is about to start...
        AdvanceMovie_btn.config(text='>|', bg='red',
                                fg='white', relief=SUNKEN)  # ...so now we propose to stop it in the button test
    else:
        AdvanceMovie_btn.config(text='>', bg=save_bg,
                                fg=save_fg, relief=RAISED)  # Otherwise change to default text to start the action
    AdvanceMovieActive = not AdvanceMovieActive
    # Send instruction to Arduino
    if not SimulatedRun and not from_arduino:  # Do not send Arduino command if triggered by Arduino response
        send_arduino_command(CMD_FILM_FORWARD)

    # Enable/Disable related buttons
    except_widget_global_enable(AdvanceMovie_btn, not AdvanceMovieActive)


def cmd_retreat_movie():
    global RetreatMovieActive

    # Update button text
    if not RetreatMovieActive:  # Advance movie is about to start...
        retreat_movie_btn.config(text='|<', bg='red',
                                fg='white', relief=SUNKEN)  # ...so now we propose to stop it in the button test
    else:
        retreat_movie_btn.config(text='<', bg=save_bg,
                                fg=save_fg, relief=RAISED)  # Otherwise change to default text to start the action
    RetreatMovieActive = not RetreatMovieActive
    # Send instruction to Arduino
    if not SimulatedRun:
        send_arduino_command(CMD_FILM_BACKWARD)

    # Enable/Disable related buttons
    except_widget_global_enable(retreat_movie_btn, not RetreatMovieActive)


def cmd_rewind_movie():
    global win
    global RewindMovieActive
    global RewindErrorOutstanding, RewindEndOutstanding

    if SimulatedRun and RewindMovieActive:  # no callback from Arduino in simulated mode
        RewindEndOutstanding = True

    # Before proceeding, get confirmation from user that fild is correctly routed
    if not RewindMovieActive:  # Ask only when rewind is not ongoing
        RewindMovieActive = True
        # Update button text
        rewind_btn.config(text='|<<', bg='red', fg='white',
                          relief=SUNKEN)  # ...so now we propose to stop it in the button test
        # Enable/Disable related buttons
        except_widget_global_enable(rewind_btn, not RewindMovieActive)
        # Invoke rewind_loop to continue processing until error or end event
        win.after(5, rewind_loop)
    elif RewindErrorOutstanding:
        confirm = tk.messagebox.askyesno(title='Error during rewind',
                                         message='It seems there is film loaded via filmgate. \
                                         \r\nAre you sure you want to proceed?')
        if confirm:
            time.sleep(0.2)
            if not SimulatedRun:
                send_arduino_command(CMD_UNCONDITIONAL_REWIND)  # Forced rewind, no filmgate check
                # Invoke fast_forward_loop a first time when fast-forward starts
                win.after(5, rewind_loop)
        else:
            RewindMovieActive = False
    elif RewindEndOutstanding:
        RewindMovieActive = False

    if not RewindMovieActive:
        rewind_btn.config(text='<<', bg=save_bg, fg=save_fg,
                          relief=RAISED)  # Otherwise change to default text to start the action
        # Enable/Disable related buttons
        except_widget_global_enable(rewind_btn, not RewindMovieActive)

    if not RewindErrorOutstanding and not RewindEndOutstanding:  # invoked from button
        time.sleep(0.2)
        if not SimulatedRun:
            send_arduino_command(CMD_REWIND)

    if RewindErrorOutstanding:
        RewindErrorOutstanding = False
    if RewindEndOutstanding:
        RewindEndOutstanding = False


def rewind_loop():
    global win
    if RewindMovieActive:
        # Invoke rewind_loop one more time, as long as rewind is ongoing
        if not RewindErrorOutstanding and not RewindEndOutstanding:
            win.after(5, rewind_loop)
        else:
            cmd_rewind_movie()


def cmd_fast_forward_movie():
    global win
    global FastForwardActive
    global FastForwardErrorOutstanding, FastForwardEndOutstanding

    if SimulatedRun and FastForwardActive:  # no callback from Arduino in simulated mode
        FastForwardEndOutstanding = True

    # Before proceeding, get confirmation from user that fild is correctly routed
    if not FastForwardActive:  # Ask only when rewind is not ongoing
        FastForwardActive = True
        # Update button text
        fast_forward_btn.config(text='>>|', bg='red', fg='white', relief=SUNKEN)
        # Enable/Disable related buttons
        except_widget_global_enable(fast_forward_btn, not FastForwardActive)
        # Invoke fast_forward_loop a first time when fast-forward starts
        win.after(5, fast_forward_loop)
    elif FastForwardErrorOutstanding:
        confirm = tk.messagebox.askyesno(title='Error during fast forward',
                                         message='It seems there is film loaded via filmgate. \
                                         \r\nAre you sure you want to proceed?')
        if confirm:
            time.sleep(0.2)
            if not SimulatedRun:
                send_arduino_command(CMD_UNCONDITIONAL_FAST_FORWARD)  # Forced FF, no filmgate check
                # Invoke fast_forward_loop a first time when fast-forward starts
                win.after(5, fast_forward_loop)
        else:
            FastForwardActive = False
    elif FastForwardEndOutstanding:
        FastForwardActive = False

    if not FastForwardActive:
        fast_forward_btn.config(text='>>', bg=save_bg, fg=save_fg, relief=RAISED)
        # Enable/Disable related buttons
        except_widget_global_enable(fast_forward_btn, not FastForwardActive)

    if not FastForwardErrorOutstanding and not FastForwardEndOutstanding:  # invoked from button
        time.sleep(0.2)
        if not SimulatedRun:
            send_arduino_command(CMD_FAST_FORWARD)

    if FastForwardErrorOutstanding:
        FastForwardErrorOutstanding = False
    if FastForwardEndOutstanding:
        FastForwardEndOutstanding = False


def fast_forward_loop():
    global win
    if FastForwardActive:
        # Invoke fast_forward_loop one more time, as long as rewind is ongoing
        if not FastForwardErrorOutstanding and not FastForwardEndOutstanding:
            win.after(5, fast_forward_loop)
        else:
            cmd_fast_forward_movie()


# *******************************************************************
# ********************** Capture functions **************************
# *******************************************************************
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


def is_frame_in_file_centered(image_path, film_type ='S8', threshold=10, slice_width=10):
    # Read the image
    if image_path.lower().endswith('.dng'):
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
        curframe = message[2]
        hdr_idx = message[3]

        # If too many items in queue the skip display
        if (MaxQueueSize - queue.qsize() <= 5):
            logging.warning("Display queue almost full: Skipping frame display")
        else:
            draw_preview_image(image, curframe, hdr_idx)
            logging.debug("Display thread complete: %s ms", str(round((time.time() - curtime) * 1000, 1)))
    active_threads -= 1
    logging.debug("Exiting capture_display_thread")


def capture_save_thread(queue, event, id):
    global ScanStopRequested
    global active_threads
    global total_wait_time_save_image
    global scan_error_counter, scan_error_total_frames_counter, DetectMisalignedFrames, MisalignedFrameTolerance
    global FilmType

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
        is_dng = FileType == 'dng'
        is_png = FileType == 'png'
        # Extract info from message
        type = message[0]
        if type == REQUEST_TOKEN:
            request = message[1]
        elif type == IMAGE_TOKEN:
            if is_dng:
                logging.error("Cannot save plain image to DNG file.")
                ScanStopRequested = True  # If target dir does not exist, stop scan
                return
            captured_image = message[1]
        else:
            logging.error(f"Invalid message type received: {type}")
        frame_idx = message[2]
        hdr_idx = message[3]
        if is_dng:
            # Saving DNG/PNG implies passing a request, not an image, therefore no additional checks (no negative allowed)
            if hdr_idx > 1:  # Hdr frame 1 has standard filename
                request.save_dng(HdrFrameFilenamePattern % (frame_idx, hdr_idx, FileType))
            else:  # Non HDR
                request.save_dng(FrameFilenamePattern % (frame_idx, FileType))                    
                if DetectMisalignedFrames and can_check_dng_frames_for_misalignment:
                    captured_image = request.make_array('main')[:,:,0]
            request.release()   # Release request ASAP (delay frame alignment check)
            if DetectMisalignedFrames and can_check_dng_frames_for_misalignment and hdr_idx <= 1:
                if not is_frame_centered(captured_image, FilmType, MisalignedFrameTolerance)[0]:
                    scan_error_counter += 1
                    scan_error_counter_value.set(f"{scan_error_counter} ({scan_error_counter*100/scan_error_total_frames_counter:.1f}%)")
                    with open(scan_error_log_fullpath, 'a') as f:
                        f.write(f"Misaligned frame, {CurrentFrame}\n")
            logging.debug("Thread %i saved request DNG image: %s ms", id,
                          str(round((time.time() - curtime) * 1000, 1)))
        else:
            # If not is_dng AND negative_image AND request: Convert to image now, and do a PIL save
            if type == REQUEST_TOKEN:
                if NegativeImage:   # Warning  case
                    logging.warning("Cannot reverse a PiCamera2 request, saving as captured.")
                if hdr_idx > 1:  # Hdr frame 1 has standard filename
                    request.save('main',
                                 HdrFrameFilenamePattern % (frame_idx, hdr_idx, FileType))
                else:  # Non HDR
                    request.save('main', FrameFilenamePattern % (frame_idx, FileType))
                    if DetectMisalignedFrames:
                        captured_image = request.make_array('main')[:,:,0]
                request.release()
                logging.debug("Thread %i saved request image: %s ms", id,
                              str(round((time.time() - curtime) * 1000, 1)))
            else:
                if hdr_idx > 1:  # Hdr frame 1 has standard filename
                    logging.debug("Saving HDR frame n.%i", hdr_idx)
                    captured_image.save(
                        HdrFrameFilenamePattern % (frame_idx, hdr_idx, FileType), quality=95)
                else:
                    captured_image.save(FrameFilenamePattern % (frame_idx, FileType),
                                        quality=95)
                    # Once the PIL Image has been saved, convert it to an array, as expected by is_frame_centered
                    captured_image = np.array(captured_image.convert('L'))
                logging.debug("Thread %i saved image: %s ms", id,
                              str(round((time.time() - curtime) * 1000, 1)))
            if DetectMisalignedFrames and hdr_idx <= 1 and not is_frame_centered(captured_image, FilmType, MisalignedFrameTolerance)[0]:
                scan_error_counter += 1
                scan_error_counter_value.set(f"{scan_error_counter} ({scan_error_counter*100/scan_error_total_frames_counter:.1f}%)")
                with open(scan_error_log_fullpath, 'a') as f:
                    f.write(f"Misaligned frame, {CurrentFrame}\n")
            logging.debug("Thread %i after checking misaligned frames", id)
        aux = time.time() - curtime
        total_wait_time_save_image += aux
        time_save_image.add_value(aux)
    active_threads -= 1
    logging.debug("Exiting capture_save_thread n.%i", id)


def draw_preview_image(preview_image, curframe, idx):
    global total_wait_time_preview_display, PreviewModuleValue

    curtime = time.time()

    if curframe % PreviewModuleValue == 0 and preview_image is not None:
        if idx == 0 or (idx == 2 and not HdrViewX4Active):
            preview_image = preview_image.resize((PreviewWidth, PreviewHeight))
            PreviewAreaImage = ImageTk.PhotoImage(preview_image)
        elif HdrViewX4Active:
            # if using View4X mode and there are 5 exposures, we do not display the 5th
            # and if there are 3, 4th position will always be empty
            quarter_image = preview_image.resize((int(PreviewWidth / 2), int(PreviewHeight / 2)))
            if idx == 1:
                hdr_view_4_image.paste(quarter_image, (0, 0))
            elif idx == 2:
                hdr_view_4_image.paste(quarter_image, (int(PreviewWidth / 2), 0))
            elif idx == 3:
                hdr_view_4_image.paste(quarter_image, (0, int(PreviewHeight / 2)))
            elif idx == 4:
                hdr_view_4_image.paste(quarter_image, (int(PreviewWidth / 2), int(PreviewHeight / 2)))
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


def cmd_capture_single_step():
    if not SimulatedRun:
        capture('still')


def cmd_single_step_movie():
    global camera

    if not SimulatedRun:
        send_arduino_command(CMD_SINGLE_STEP)

        if not CameraDisabled:
            # If no camera preview, capture frame in memory and display it
            # Single step is not a critical operation, waiting 100ms for it to happen should be enough
            # No need to implement confirmation from Arduino, as we have for regular capture during scan
            time.sleep(0.5)
            single_step_image = camera.capture_image("main")
            draw_preview_image(single_step_image, 0, 0)


def emergency_stop():
    if not SimulatedRun:
        send_arduino_command(90)


def update_rpi_temp():
    global RPiTemp
    if not SimulatedRun:
        file = open('/sys/class/thermal/thermal_zone0/temp', 'r')
        temp_str = file.readline()
        file.close()
        RPiTemp = int(int(temp_str) / 100) / 10
    else:
        RPiTemp = 64.5


def disk_space_available():
    global available_space_mb, disk_space_error_to_notify

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


def cmd_switch_hdr_capture():
    global HdrCaptureActive
    global max_inactivity_delay
    global AutoExpEnabled

    HdrCaptureActive = hdr_capture_active.get()
    ConfigData["HdrCaptureActive"] = HdrCaptureActive
    widget_list_enable([id_HdrCaptureActive])

    if HdrCaptureActive:  # If HDR enabled, handle automatic control settings for widgets
        max_inactivity_delay = max_inactivity_delay * 2
    else:  # If disabling HDR, need to set standard exposure as set in UI
        max_inactivity_delay = int(max_inactivity_delay / 2)
        if not AutoExpEnabled:  # Automatic mode
            if not SimulatedRun and not CameraDisabled:
                # Since we are in auto exposure mode, retrieve current value to start from there
                metadata = camera.capture_metadata()
                CurrentExposure = metadata["ExposureTime"]
                camera.set_controls({"AeEnable": AutoExpEnabled})
            else:
                CurrentExposure = 3500  # Arbitrary Value for Simulated run
            ConfigData["CurrentExposure"] = CurrentExposure
            exposure_value.set(CurrentExposure/1000)
    send_arduino_command(CMD_SET_STALL_TIME, max_inactivity_delay)
    logging.debug(f"max_inactivity_delay: {max_inactivity_delay}")


def cmd_switch_hdr_viewx4():
    global HdrViewX4Active
    HdrViewX4Active = hdr_viewx4_active.get()
    ConfigData["HdrViewX4Active"] = str(HdrViewX4Active)


def cmd_set_negative_image():
    global NegativeImage
    NegativeImage = negative_image.get()
    ConfigData["NegativeCaptureActive"] = NegativeImage


# Function to enable 'real' preview with PiCamera2
# Even if it is useless for capture (slow and imprecise) it is still needed for other tasks like:
#  - Focus
#  - Color adjustment
#  - Exposure adjustment
def cmd_set_real_time_display():
    global RealTimeDisplay
    global camera, ZoomSize
    global saved_locale
    RealTimeDisplay = real_time_display.get()
    if RealTimeDisplay:
        logging.debug("Real time display enabled")
    else:
        logging.debug("Real time display disabled")
    if not SimulatedRun and not CameraDisabled:
        if RealTimeDisplay:
            ZoomSize = camera.capture_metadata()['ScalerCrop']
            time.sleep(0.1)
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
            time.sleep(0.1)
            camera.set_controls({"ScalerCrop": ZoomSize})
            # Restore the saved locale
            locale.setlocale(locale.LC_NUMERIC, saved_locale)

    # Do not allow scan to start while PiCam2 preview is active
    widget_enable(start_btn, not RealTimeDisplay)
    widget_enable(real_time_zoom_checkbox, RealTimeDisplay)
    real_time_zoom_checkbox.deselect()


def cmd_set_s8():
    global FilmHoleY_Top, FilmHoleY_Bottom, StepsPerFrame, PtLevelValue, FilmType

    FilmType = "S8"
    ConfigData["FilmType"] = "S8"
    time.sleep(0.2)

    PTLevel = PTLevelS8
    MinFrameSteps = MinFrameStepsS8
    if ALT_scann_init_done:
        ConfigData["PTLevel"] = PTLevel
        ConfigData["MinFrameSteps"] = MinFrameSteps
    if ExpertMode:
        pt_level_value.set(PTLevel)
        PtLevelValue = PTLevel
        StepsPerFrame = MinFrameSteps
        steps_per_frame_value.set(MinFrameSteps)
    # Size and position of hole markers
    FilmHoleY_Top = int(PreviewHeight / 2.6)
    FilmHoleY_Bottom = FilmHoleY_Top
    film_hole_frame_top.place(x=0, y=FilmHoleY_Top, height=FilmHoleHeightTop)
    film_hole_frame_bottom.place(x=0, y=FilmHoleY_Bottom, height=FilmHoleHeightBottom)
    if not SimulatedRun:
        send_arduino_command(CMD_SET_SUPER_8)
        send_arduino_command(CMD_SET_PT_LEVEL, 0 if AutoPtLevelEnabled else PTLevel)
        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0 if AutoFrameStepsEnabled else MinFrameSteps)


def cmd_set_r8():
    global FilmHoleY_Top, FilmHoleY_Bottom, StepsPerFrame, PtLevelValue, FilmType

    FilmType = "R8"
    ConfigData["FilmType"] = "R8"
    time.sleep(0.2)

    PTLevel = PTLevelR8
    MinFrameSteps = MinFrameStepsR8
    if ALT_scann_init_done:
        ConfigData["PTLevel"] = PTLevel
        ConfigData["MinFrameSteps"] = MinFrameSteps
    if ExpertMode:
        pt_level_value.set(PTLevel)
        PtLevelValue = PTLevel
        StepsPerFrame = MinFrameSteps
        steps_per_frame_value.set(MinFrameSteps)
    # Size and position of hole markers
    FilmHoleY_Top = 6
    FilmHoleY_Bottom = int(PreviewHeight / 1.25)
    film_hole_frame_top.place(x=0, y=FilmHoleY_Top, height=FilmHoleHeightTop)
    film_hole_frame_bottom.place(x=0, y=FilmHoleY_Bottom, height=FilmHoleHeightBottom)
    if not SimulatedRun:
        send_arduino_command(CMD_SET_REGULAR_8)
        send_arduino_command(CMD_SET_PT_LEVEL, 0 if AutoPtLevelEnabled else PTLevel)
        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0 if AutoFrameStepsEnabled else MinFrameSteps)


def register_frame():
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
    while FPM_LastMinuteFrameTimes[0] <= frame_time - 60:
        FPM_LastMinuteFrameTimes.remove(FPM_LastMinuteFrameTimes[0])
    # Calculate current value, only if current count has been going for more than 10 seconds
    if frame_time - FPM_StartTime > 60:  # no calculations needed, frames in list are all in the last 60 seconds
        FPM_CalculatedValue = len(FPM_LastMinuteFrameTimes)
    elif frame_time - FPM_StartTime > 10:  # some  calculations needed if less than 60 sec
        FPM_CalculatedValue = int((len(FPM_LastMinuteFrameTimes) * 60) / (frame_time - FPM_StartTime))


def cmd_adjust_hdr_bracket_auto():
    global HdrBracketAuto
    if not HdrCaptureActive:
        return

    HdrBracketAuto = hdr_bracket_auto.get()
    ConfigData["HdrBracketAuto"] = HdrBracketAuto

    widget_list_enable([id_HdrBracketAuto])


def cmd_adjust_merge_in_place():
    global HdrMergeInPlace

    if not HdrCaptureActive:
        return

    HdrMergeInPlace = hdr_merge_in_place.get()
    ConfigData["HdrMergeInPlace"] = HdrMergeInPlace


def adjust_hdr_bracket():
    global recalculate_hdr_exp_list
    global hdr_best_exp, HdrMinExp
    global PreviousCurrentExposure
    global force_adjust_hdr_bracket
    global AutoExpEnabled

    if not HdrCaptureActive:
        return

    if SimulatedRun or CameraDisabled:
        aux_current_exposure = 20
    else:
        camera.set_controls({"AeEnable": True})
        for i in range(1, dry_run_iterations * 2):
            camera.capture_image("main")

        # Since we are in auto exposure mode, retrieve current value to start from there
        metadata = camera.capture_metadata()
        aux_current_exposure = int(metadata["ExposureTime"] / 1000)
        camera.set_controls({"AeEnable": AutoExpEnabled})

    # Adjust only if auto exposure changes
    if aux_current_exposure != PreviousCurrentExposure or force_adjust_hdr_bracket:
        logging.debug(f"Adjusting bracket, prev/cur exp: {PreviousCurrentExposure} -> {aux_current_exposure}")
        force_adjust_hdr_bracket = False
        PreviousCurrentExposure = aux_current_exposure
        hdr_best_exp = aux_current_exposure
        HdrMinExp = max(hdr_best_exp - int(HdrBracketWidth / 2), HdrMinExp)
        hdr_min_exp_value.set(HdrMinExp)
        hdr_max_exp_value.set(HdrMinExp + HdrBracketWidth)
        ConfigData["HdrMinExp"] = HdrMinExp
        ConfigData["HdrMaxExp"] = HdrMaxExp
        recalculate_hdr_exp_list = True
        logging.debug(f"Adjusting bracket: {HdrMinExp}, {HdrMaxExp}")


def capture_hdr(mode):
    global recalculate_hdr_exp_list, PreviewModuleValue

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
    # For following frames, we can skip dry run for the first capture since we alternate the sense of the exposures
    # on each frame
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
    is_dng = FileType == 'dng'
    is_png = FileType == 'png'
    for exp in work_list:
        exp = max(1, exp + HdrBracketShift)  # Apply bracket shift
        logging.debug("capture_hdr: exp %.2f", exp)
        if perform_dry_run:
            camera.set_controls({"ExposureTime": int(exp * 1000)})
        else:
            time.sleep(StabilizationDelayValue/1000)  # Allow time to stabilize image only if no dry run
        if perform_dry_run:
            for i in range(1, dry_run_iterations):  # Perform a few dummy captures to allow exposure stabilization
                camera.capture_image("main")
        # We skip dry run only for the first capture of each frame,
        # as it is the same exposure as the last capture of the previous one
        perform_dry_run = True
        # For PiCamera2, preview and save to file are handled in asynchronous threads
        if HdrMergeInPlace and not is_dng:  # For now we do not even try to merge DNG images in place
            captured_image = camera.capture_image("main")  # If merge in place, Capture snapshot (no DNG allowed)
            # Convert Pillow image to NumPy array
            img_np = np.array(captured_image)
            # Convert the NumPy array to a format suitable for MergeMertens (e.g., float32)
            img_np_float32 = img_np.astype(np.float32)
            images_to_merge.append(img_np_float32)  # Add frame
        else:
            if is_dng or is_png:  # If not using DNG we can still use multithread (if not disabled)
                # DNG + HDR, save threads not possible due to request conflicting with retrieve metadata
                request = camera.capture_request(capture_config)
                if CurrentFrame % PreviewModuleValue == 0:
                    captured_image = request.make_image('main')
                    # Display preview using thread, not directly
                    queue_item = tuple((IMAGE_TOKEN, captured_image, CurrentFrame, idx))
                    capture_display_queue.put(queue_item)
                curtime = time.time()
                if idx > 1:  # Hdr frame 1 has standard filename
                    request.save_dng(HdrFrameFilenamePattern % (CurrentFrame, idx, FileType))
                else:  # Non HDR
                    request.save_dng(FrameFilenamePattern % (CurrentFrame, FileType))
                request.release()
                logging.debug(f"Capture hdr, saved request image ({CurrentFrame}, {idx}: "
                              f"{round((time.time() - curtime) * 1000, 1)}")
            else:
                captured_image = camera.capture_image("main")
                if NegativeImage:
                    captured_image = reverse_image(captured_image)
                if DisableThreads:  # Save image in main loop
                    curtime = time.time()
                    draw_preview_image(captured_image, CurrentFrame, idx)
                    if idx > 1:  # Hdr frame 1 has standard filename
                        captured_image.save(
                            HdrFrameFilenamePattern % (CurrentFrame, idx, FileType))
                    else:
                        captured_image.save(FrameFilenamePattern % (CurrentFrame, FileType))
                    logging.debug(f"Capture hdr, saved image ({CurrentFrame}, {idx}): "
                                  f"{round((time.time() - curtime) * 1000, 1)} ms")
                else:  # send image to threads
                    if mode == 'normal' or mode == 'manual':  # Do not save in preview mode, only display
                        # In HDR we cannot really pass a request to the thread since it will interfere with the
                        # dry run captures done in the main capture loop. Maybe with synchronization it could be
                        # made to work, but then the small advantage offered by threads would be lost
                        queue_item = tuple((IMAGE_TOKEN, captured_image, CurrentFrame, idx))
                        if CurrentFrame % PreviewModuleValue == 0:
                            # Display preview using thread, not directly
                            capture_display_queue.put(queue_item)
                        capture_save_queue.put(queue_item)
                        logging.debug(f"Queueing hdr image ({CurrentFrame}, {idx})")
        idx += idx_inc
    if HdrMergeInPlace and not is_dng:
        # Perform merge of the HDR image list
        img = MergeMertens.process(images_to_merge)
        # Convert the result back to PIL
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
        img = Image.fromarray(img)
        if CurrentFrame % PreviewModuleValue == 0:
            # Display preview using thread, not directly
            queue_item = tuple((IMAGE_TOKEN, img, CurrentFrame, 0))
            capture_display_queue.put(queue_item)
        img.save(FrameFilenamePattern % (CurrentFrame, FileType), quality=95)


def capture_single(mode):
    global CurrentFrame
    global total_wait_time_save_image, PreviewModuleValue

    # *** ALT-Scann8 capture frame ***
    if hw_panel_installed:
        hw_panel.ALT_Scann8_captured_frame()

    is_dng = FileType == 'dng'
    is_png = FileType == 'png'
    curtime = time.time()
    if not DisableThreads:
        if is_dng or is_png:  # Save as request only for DNG captures
            request = camera.capture_request(capture_config)
            # For PiCamera2, preview and save to file are handled in asynchronous threads
            if CurrentFrame % PreviewModuleValue == 0:
                captured_image = request.make_image('main')
                # Display preview using thread, not directly
                queue_item = tuple((IMAGE_TOKEN, captured_image, CurrentFrame, 0))
                capture_display_queue.put(queue_item)
            else:
                time_preview_display.add_value(0)
            if mode == 'normal' or mode == 'manual':  # Do not save in preview mode, only display
                save_queue_item = tuple((REQUEST_TOKEN, request, CurrentFrame, 0))
                capture_save_queue.put(save_queue_item)
                logging.debug(f"Queueing frame ({CurrentFrame}")
        else:
            captured_image = camera.capture_image("main")
            if NegativeImage:
                captured_image = reverse_image(captured_image)
            queue_item = tuple((IMAGE_TOKEN, captured_image, CurrentFrame, 0))
            # For PiCamera2, preview and save to file are handled in asynchronous threads
            if CurrentFrame % PreviewModuleValue == 0:
                # Display preview using thread, not directly
                capture_display_queue.put(queue_item)
            else:
                time_preview_display.add_value(0)
            if mode == 'normal' or mode == 'manual':  # Do not save in preview mode, only display
                capture_save_queue.put(queue_item)
                logging.debug(f"Queuing frame {CurrentFrame}")
        if mode == 'manual':  # In manual mode, increase CurrentFrame
            CurrentFrame += 1
            # Update number of captured frames
            Scanned_Images_number.set(CurrentFrame)
    else:
        if is_dng or is_png:
            request = camera.capture_request(capture_config)
            if CurrentFrame % PreviewModuleValue == 0:
                captured_image = request.make_image('main')
            else:
                captured_image = None
            draw_preview_image(captured_image, CurrentFrame, 0)
            if mode == 'normal' or mode == 'manual':  # Do not save in preview mode, only display
                request.save_dng(FrameFilenamePattern % (CurrentFrame, FileType))
                logging.debug(f"Saving DNG frame ({CurrentFrame}: {round((time.time() - curtime) * 1000, 1)}")
            request.release()
        else:
            captured_image = camera.capture_image("main")
            if NegativeImage:
                captured_image = reverse_image(captured_image)
            draw_preview_image(captured_image, CurrentFrame, 0)
            captured_image.save(FrameFilenamePattern % (CurrentFrame, FileType), quality=95)
            logging.debug(
                f"Saving image ({CurrentFrame}: {round((time.time() - curtime) * 1000, 1)}")
        aux = time.time() - curtime
        total_wait_time_save_image += aux
        time_save_image.add_value(aux)
        if mode == 'manual':  # In manual mode, increase CurrentFrame
            CurrentFrame += 1
            # Update number of captured frames
            Scanned_Images_number.set(CurrentFrame)


# 4 possible modes:
# 'normal': Standard capture during automated scan (display and save)
# 'manual': Manual capture during manual scan (display and save)
# 'still': Button to capture still (specific filename)
# 'preview': Manual scan, display only, do not save
def capture(mode):
    global PreviousCurrentExposure, PreviewModuleValue
    global PreviousGainRed, PreviousGainBlue
    global total_wait_time_autoexp, total_wait_time_awb
    global CurrentStill

    if SimulatedRun or CameraDisabled:
        return

    os.chdir(CurrentDir)

    # Wait for auto exposure to adapt only if allowed (and if not using HDR)
    # If AE disabled, only enter as per preview_module to refresh values
    if AutoExpEnabled and not HdrCaptureActive and (
            ExposureWbAdaptPause or CurrentFrame % PreviewModuleValue == 0):
        curtime = time.time()
        wait_loop_count = 0
        while True:  # In case of exposure change, give time for the camera to adapt
            metadata = camera.capture_metadata()
            aux_current_exposure = metadata["ExposureTime"]
            if ExposureWbAdaptPause:
                # With PiCamera2, exposure was changing too often, so level changed from 1000 to 2000, then to 4000
                # Finally changed to allow a percentage of the value used previously
                # As we initialize this percentage to 50%, we start with double the original value
                if abs(aux_current_exposure - PreviousCurrentExposure) > (
                        MatchWaitMarginValue * Tolerance_AE) / 100:
                    if (wait_loop_count % 10 == 0):
                        logging.debug(
                            f"AE match: ({aux_current_exposure / 1000},Auto {PreviousCurrentExposure / 1000})")
                    wait_loop_count += 1
                    PreviousCurrentExposure = aux_current_exposure
                    time.sleep(0.2)
                    if (time.time() - curtime) * 1000 > max_wait_time:  # Never wait more than 5 seconds
                        break;
                else:
                    break
            else:
                break
        if wait_loop_count >= 0:
            if ExpertMode:
                exposure_value.set(aux_current_exposure / 1000)
            aux = time.time() - curtime
            total_wait_time_autoexp += aux
            time_autoexp.add_value(aux)
            logging.debug("AE match delay: %s ms", str(round((time.time() - curtime) * 1000, 1)))
    else:
        time_autoexp.add_value(0)

    # Wait for auto white balance to adapt only if allowed
    # If AWB disabled, only enter as per preview_module to refresh values
    if AutoWbEnabled and (ExposureWbAdaptPause or CurrentFrame % PreviewModuleValue == 0):
        curtime = time.time()
        wait_loop_count = 0
        while True:  # In case of exposure change, give time for the camera to adapt
            metadata = camera.capture_metadata()
            camera_colour_gains = metadata["ColourGains"]
            aux_gain_red = camera_colour_gains[0]
            aux_gain_blue = camera_colour_gains[1]
            if ExposureWbAdaptPause:
                # Same as for exposure, difference allowed is a percentage of the maximum value
                if abs(aux_gain_red - PreviousGainRed) >= (MatchWaitMarginValue * Tolerance_AWB / 100) or \
                        abs(aux_gain_blue - PreviousGainBlue) >= (MatchWaitMarginValue * Tolerance_AWB / 100):
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
            else:
                break
        if wait_loop_count >= 0:
            if ExpertMode:
                wb_red_value.set(round(aux_gain_red, 1))
                wb_blue_value.set(round(aux_gain_blue, 1))
            aux = time.time() - curtime
            total_wait_time_awb += aux
            time_awb.add_value(aux)
            logging.debug("AWB Match delay: %s ms", str(round((time.time() - curtime) * 1000, 1)))
    else:
        time_awb.add_value(0)

    if PiCam2PreviewEnabled:
        if mode == 'still':
            camera.switch_mode_and_capture_file(capture_config,
                                                StillFrameFilenamePattern % (CurrentFrame, CurrentStill))
            CurrentStill += 1
        else:
            # This one should not happen, will not allow PiCam2 scan in preview mode
            camera.switch_mode_and_capture_file(capture_config, FrameFilenamePattern % CurrentFrame)
    else:
        # Allow time to stabilize image, it can get too fast with PiCamera2
        time.sleep(StabilizationDelayValue/1000)
        if mode == 'still':
            captured_image = camera.capture_image("main")
            captured_image.save(StillFrameFilenamePattern % (CurrentFrame, CurrentStill))
            CurrentStill += 1
        else:
            if HdrCaptureActive:
                # Stabilization delay for HDR managed inside capture_hdr
                capture_hdr(mode)
            else:
                capture_single(mode)

    ConfigData["CurrentDate"] = str(datetime.now())
    ConfigData["CurrentFrame"] = str(CurrentFrame)

def simulate_pt():
    global Simulated_PT_Levels_idx, Simulated_Frame_detected, Simulated_Frame_displayed
    if ScanOngoing:
        # Retrieve the current item using the current index
        pt_value = Simulated_PT_Levels[Simulated_PT_Levels_idx]
        uv_level = pt_value[0]*uv_brightness_value.get()//255
        pt_level = (150 + pt_value[1]*FrameFineTuneValue//100) * uv_brightness_value.get()//255
        if Simulated_Frame_detected and not Simulated_Frame_displayed:
            # Call simulated scan
            capture_loop_simulated()
            Simulated_Frame_displayed = True
        if PlotterEnabled:
            UpdatePlotterWindow(uv_level, pt_level, (10-ScanSpeedValue)//2)
        if not Simulated_Frame_detected and uv_level > pt_level:
            Simulated_Frame_detected = True # Display in next slot, to allow plotter to update correctly
        elif Simulated_Frame_detected  and uv_level < pt_level:
            Simulated_Frame_detected = False
            Simulated_Frame_displayed = False
        # Move to the next item, wrapping around to 0 when we reach the end
        Simulated_PT_Levels_idx = (Simulated_PT_Levels_idx + 1) % len(Simulated_PT_Levels)
        win.after(15, simulate_pt)


def cmd_start_scan_simulated():
    global win
    global ScanOngoing
    global CurrentScanStartFrame, CurrentScanStartTime
    global simulated_captured_frame_list, simulated_images_in_list
    global ScanStopRequested
    global total_wait_time_autoexp, total_wait_time_awb, total_wait_time_preview_display, session_start_time
    global total_wait_time_save_image
    global session_frames
    global last_frame_time

    if film_type.get() == '':
        tk.messagebox.showerror("Error!",
                                "Please specify film type (S8/R8) before starting scan process")
        return

    if ScanOngoing:
        ScanStopRequested = True  # Ending the scan process will be handled in the next (or ongoing) capture loop
    else:
        if BaseFolder == CurrentDir:
            tk.messagebox.showerror("Error!",
                                    "Please specify a folder where to retrieve captured images for "
                                    "scan simulation.")
            return

        start_btn.config(text="STOP Scan", bg='red', fg='white', relief=SUNKEN)
        ConfigData["CurrentDate"] = str(datetime.now())
        ConfigData["CurrentDir"] = CurrentDir
        ConfigData["CurrentFrame"] = str(CurrentFrame)
        CurrentScanStartTime = datetime.now()
        CurrentScanStartFrame = CurrentFrame

        capture_info_str.set(f"{FileType} - {CaptureResolution}")

        ScanOngoing = True
        custom_spinboxes_kbd_lock(win)
        last_frame_time = time.time() + 3

        # Enable/Disable related buttons
        except_widget_global_enable(start_btn, not ScanOngoing)

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
            ScanOngoing = False
        else:
            refresh_qr_code()
            simulated_captured_frame_list = os.listdir(CurrentDir)
            simulated_captured_frame_list.sort()
            simulated_images_in_list = len(simulated_captured_frame_list)
            if simulated_images_in_list == 0:
                logging.error("No frames exist in folder, cannot simulate scan.")
                tk.messagebox.showerror("Error!", "Folder " + CurrentDir + " does not contain any frames to simulate scan.")
                ScanStopRequested = True
            # Invoke simulate pt to start simulation
            win.after(10, simulate_pt)

def stop_scan_simulated():
    global win
    global ScanOngoing

    start_btn.config(text="START Scan", bg=save_bg, fg=save_fg, relief=RAISED)

    ScanOngoing = False
    custom_spinboxes_kbd_lock(win)

    # Enable/Disable related buttons
    except_widget_global_enable(start_btn, not ScanOngoing)


def capture_loop_simulated():
    global win
    global CurrentFrame
    global FramesPerMinute, FramesToGo
    global simulated_capture_image
    global session_frames
    global disk_space_error_to_notify
    global ScanStopRequested

    if ScanStopRequested:
        stop_scan_simulated()
        ScanStopRequested = False
        curtime = time.time()
        if session_frames > 0:
            logging.debug("Total session time: %s seg for %i frames (%i ms per frame)",
                          str(round((curtime - session_start_time), 1)),
                          session_frames,
                          round(((curtime - session_start_time) * 1000 / session_frames), 1))
            logging.debug("Total time to save images: %s seg, (%i ms per frame)",
                          str(round((total_wait_time_save_image), 1)),
                          round((total_wait_time_save_image * 1000 / session_frames), 1))
            logging.debug("Total time to display preview image: %s seg, (%i ms per frame)",
                          str(round((total_wait_time_preview_display), 1)),
                          round((total_wait_time_preview_display * 1000 / session_frames), 1))
            logging.debug("Total time waiting for AWB adjustment: %s seg, (%i ms per frame)",
                          str(round((total_wait_time_awb), 1)),
                          round((total_wait_time_awb * 1000 / session_frames), 1))
            logging.debug("Total time waiting for AE adjustment: %s seg, (%i ms per frame)",
                          str(round((total_wait_time_autoexp), 1)),
                          round((total_wait_time_autoexp * 1000 / session_frames), 1))
        if disk_space_error_to_notify:
            tk.messagebox.showwarning("Disk space low",
                                      f"Running out of disk space, only {int(available_space_mb)} MB remain. "
                                      "Please delete some files before continuing current scan.")
            disk_space_error_to_notify = False
    if ScanOngoing:
        os.chdir(CurrentDir)
        frame_to_display = CurrentFrame % simulated_images_in_list
        filename, ext = os.path.splitext(simulated_captured_frame_list[frame_to_display])
        if ext == '.jpg':
            simulated_capture_image = Image.open(simulated_captured_frame_list[frame_to_display])
            if NegativeImage:
                simulated_capture_image = reverse_image(simulated_capture_image)
            draw_preview_image(simulated_capture_image, CurrentFrame, 0)
            # Allow time to stabilize image, it can get too fast with PiCamera2
            time.sleep((StabilizationDelayValue+(10-ScanSpeedValue)*100)/1000)

        # Update remaining time
        aux = frames_to_go_str.get()
        if aux.isdigit() and time.time() > frames_to_go_key_press_time:
            FramesToGo = int(aux)
            if FramesToGo > 0:
                FramesToGo -= 1
                frames_to_go_str.set(str(FramesToGo))
                ConfigData["FramesToGo"] = FramesToGo
                if FramesPerMinute != 0:
                    minutes_pending = FramesToGo // FramesPerMinute
                    frames_to_go_time_str.set(f"{(minutes_pending // 60):02}h {(minutes_pending % 60):02}m")

        CurrentFrame += 1
        session_frames += 1
        register_frame()
        ConfigData["CurrentFrame"] = str(CurrentFrame)

        # Update number of captured frames
        Scanned_Images_number.set(CurrentFrame)
        # Update film time
        fps = 18 if ConfigData["FilmType"] == "S8" else 16
        film_time = f"{(CurrentFrame // fps) // 60:02}:{(CurrentFrame // fps) % 60:02}"
        scanned_Images_time_value.set(film_time)
        # Update Frames per Minute
        scan_period_frames = CurrentFrame - CurrentScanStartFrame
        if FPM_CalculatedValue == -1:  # FPM not calculated yet, display some indication
            aux_str = ''.join([char * int(min(5, scan_period_frames)) for char in '.'])
            scanned_Images_fps_value.set(aux_str)
        else:
            FramesPerMinute = FPM_CalculatedValue
            scanned_Images_fps_value.set(f"{FPM_CalculatedValue / 60:.2f}")

        # display rolling averages
        if ExpertMode:
            time_save_image_value.set(
                int(time_save_image.get_average() * 1000) if time_save_image.get_average() is not None else 0)
            time_preview_display_value.set(
                int(time_preview_display.get_average() * 1000) if time_preview_display.get_average() is not None else 0)
            time_awb_value.set(int(time_awb.get_average() * 1000) if time_awb.get_average() is not None else 0)
            time_autoexp_value.set(int(time_autoexp.get_average() * 1000) if time_autoexp.get_average() is not None else 0)

        if session_frames % 50 == 0 and not disk_space_available():  # Only every 50 frames (500MB buffer exist)
            logging.error("No disk space available, stopping scan process.")
            if ScanOngoing:
                ScanStopRequested = True  # Stop in next capture loop


def start_scan():
    global win
    global ScanOngoing
    global CurrentScanStartFrame, CurrentScanStartTime
    global ScanStopRequested
    global NewFrameAvailable
    global total_wait_time_autoexp, total_wait_time_awb, total_wait_time_preview_display, session_start_time
    global total_wait_time_save_image
    global session_frames
    global last_frame_time
    global AutoExpEnabled, AutoWbEnabled

    if film_type.get() == '':
        tk.messagebox.showerror("Error!",
                                "Please specify film type (S8/R8) before starting scan process")
        return

    if ScanOngoing:
        ScanStopRequested = True  # Ending the scan process will be handled in the next (or ongoing) capture loop
    else:
        if BaseFolder == CurrentDir or not os.path.isdir(CurrentDir):
            tk.messagebox.showerror("Error!", "Please specify target folder where captured frames will be stored.")
            return

        start_btn.config(text="STOP Scan", bg='red', fg='white', relief=SUNKEN)
        ConfigData["CurrentDate"] = str(datetime.now())
        ConfigData["CurrentDir"] = CurrentDir
        ConfigData["CurrentFrame"] = str(CurrentFrame)
        CurrentScanStartTime = datetime.now()
        CurrentScanStartFrame = CurrentFrame

        capture_info_str.set(f"{FileType} - {CaptureResolution}")

        is_dng = FileType == 'dng'
        is_png = FileType == 'png'
        if (is_dng or is_png) and NegativeImage:  # Incompatible choices, display error and quit
            tk.messagebox.showerror("Error!",
                                    "Cannot scan negative images to DNG or PNG files. "
                                    "Please correct and retry.")
            logging.debug("Cannot scan negative images to DNG file. Please correct and retry.")
            return

        ScanOngoing = True
        custom_spinboxes_kbd_lock(win)
        last_frame_time = time.time() + 3

        # Set new frame indicator to false, in case this is the cause of the strange
        # behaviour after stopping/restarting the scan process
        NewFrameAvailable = False

        # Enable/Disable related buttons
        except_widget_global_enable(start_btn, not ScanOngoing)

        # Reset time counters
        total_wait_time_save_image = 0
        total_wait_time_preview_display = 0
        total_wait_time_awb = 0
        total_wait_time_autoexp = 0
        session_start_time = time.time()
        session_frames = 0

        # Send command to Arduino to start scan (as applicable, Arduino keeps its own status)
        if not SimulatedRun and not CameraDisabled:
            camera.set_controls({"AeEnable": AutoExpEnabled})
            camera.set_controls({"AwbEnable": AutoWbEnabled})
            if not AutoExpEnabled:
                camera.set_controls({"ExposureTime": int(int(exposure_value.get() * 1000))})
            logging.debug("Sending CMD_START_SCAN")
            send_arduino_command(CMD_START_SCAN)

        refresh_qr_code()

        # Invoke capture_loop a first time when scan starts
        win.after(5, capture_loop)


def stop_scan():
    global win
    global ScanOngoing

    if ScanOngoing:  # Scanner session to be stopped
        start_btn.config(text="START Scan", bg=save_bg, fg=save_fg, relief=RAISED)

    ScanOngoing = False
    custom_spinboxes_kbd_lock(win)

    # Send command to Arduino to stop scan (as applicable, Arduino keeps its own status)
    if not SimulatedRun:
        logging.debug("Sending CMD_STOP_SCAN")
        send_arduino_command(CMD_STOP_SCAN)

    # Enable/Disable related buttons
    except_widget_global_enable(start_btn, not ScanOngoing)


def capture_loop():
    global win
    global CurrentFrame
    global FramesPerMinute, FramesToGo
    global NewFrameAvailable
    global ScanProcessError, ScanProcessError_LastTime
    global ScanStopRequested
    global session_frames, CurrentStill
    global disk_space_error_to_notify
    global AutoStopEnabled

    if ScanStopRequested:
        stop_scan()
        ScanStopRequested = False
        curtime = time.time()
        if session_frames > 0:
            logging.debug("Total session time: %s seg for %i frames (%i ms per frame)",
                          str(round((curtime - session_start_time), 1)),
                          session_frames,
                          round(((curtime - session_start_time) * 1000 / session_frames), 1))
            logging.debug("Total time to save images: %s seg, (%i ms per frame)",
                          str(round((total_wait_time_save_image), 1)),
                          round((total_wait_time_save_image * 1000 / session_frames), 1))
            logging.debug("Total time to display preview image: %s seg, (%i ms per frame)",
                          str(round((total_wait_time_preview_display), 1)),
                          round((total_wait_time_preview_display * 1000 / session_frames), 1))
            logging.debug("Total time waiting for AWB adjustment: %s seg, (%i ms per frame)",
                          str(round((total_wait_time_awb), 1)),
                          round((total_wait_time_awb * 1000 / session_frames), 1))
            logging.debug("Total time waiting for AE adjustment: %s seg, (%i ms per frame)",
                          str(round((total_wait_time_autoexp), 1)),
                          round((total_wait_time_autoexp * 1000 / session_frames), 1))
        if disk_space_error_to_notify:
            tk.messagebox.showwarning("Disk space low",
                                      f"Running out of disk space, only {int(available_space_mb)} MB remain. "
                                      "Please delete some files before continuing current scan.")
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
                    ConfigData["FramesToGo"] = FramesToGo
                    if FramesPerMinute != 0:
                        minutes_pending = FramesToGo // FramesPerMinute
                        frames_to_go_time_str.set(f"{(minutes_pending // 60):02}h {(minutes_pending % 60):02}m")
                else:
                    if AutoStopEnabled and autostop_type.get() == "counter_to_zero":
                        ScanStopRequested = True  # Stop in next capture loop
                    ConfigData["FramesToGo"] = -1
                    frames_to_go_str.set('')  # clear frames to go box to prevent it stops again in next scan
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

            ConfigData["CurrentDate"] = str(datetime.now())
            ConfigData["CurrentDir"] = CurrentDir
            ConfigData["CurrentFrame"] = str(CurrentFrame)
            # with open(ConfigurationDataFilename, 'w') as f:
            #     json.dump(ConfigData, f)

            # Update number of captured frames
            Scanned_Images_number.set(CurrentFrame)
            # Update film time
            fps = 18 if ConfigData["FilmType"] == "S8" else 16
            film_time = f"{(CurrentFrame // fps) // 60:02}:{(CurrentFrame // fps) % 60:02}"
            scanned_Images_time_value.set(film_time)
            # Update Frames per Minute
            scan_period_frames = CurrentFrame - CurrentScanStartFrame
            if FPM_CalculatedValue == -1:  # FPM not calculated yet, display some indication
                aux_str = ''.join([char * int(min(5, scan_period_frames)) for char in '.'])
                scanned_Images_fps_value.set(aux_str)
            else:
                FramesPerMinute = FPM_CalculatedValue
                scanned_Images_fps_value.set(f"{FPM_CalculatedValue / 60:.2f}")
            if session_frames % 50 == 0 and not disk_space_available():  # Only every 50 frames (500MB buffer exist)
                logging.error("No disk space available, stopping scan process.")
                if ScanOngoing:
                    ScanStopRequested = True  # Stop in next capture loop
        elif ScanProcessError:
            if ScanProcessError_LastTime != 0:
                if time.time() - ScanProcessError_LastTime <= 5:  # Second error in less than 5 seconds: Stop
                    curtime = time.ctime()
                    logging.error("Too many errors during scan process, stopping.")
                    ScanProcessError = False
                    if ScanOngoing:
                        ScanStopRequested = True  # Stop in next capture loop
            ScanProcessError_LastTime = time.time()
            ScanProcessError = False
            if not ScanStopRequested:
                NewFrameAvailable = True  # Simulate new frame to continue scan
                logging.warning(
                    f"Error during scan process, frame {CurrentFrame}, simulating new frame. Maybe misaligned.")

        # display rolling averages
        if ExpertMode:
            time_save_image_value.set(
                int(time_save_image.get_average() * 1000) if time_save_image.get_average() is not None else 0)
            time_preview_display_value.set(
                int(time_preview_display.get_average() * 1000) if time_preview_display.get_average() is not None else 0)
            time_awb_value.set(int(time_awb.get_average() * 1000) if time_awb.get_average() is not None else 0)
            time_autoexp_value.set(
                int(time_autoexp.get_average() * 1000) if time_autoexp.get_average() is not None else 0)

        # Invoke capture_loop one more time, as long as scan is ongoing
        win.after(5, capture_loop)


def temperature_check():
    global last_temp
    global LastTempInFahrenheit

    update_rpi_temp()
    if last_temp != RPiTemp or LastTempInFahrenheit != TempInFahrenheit:
        if TempInFahrenheit:
            rounded_temp = round(RPiTemp * 1.8 + 32, 1)
            temp_str = str(rounded_temp) + 'ºF'
        else:
            rounded_temp = round(RPiTemp, 1)
            temp_str = str(rounded_temp) + 'º'
        rpi_temp_value_label.config(text=str(temp_str))
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
        frames_to_go_key_press_time = time.time() + 5  # 5 sec guard time to allow typing entire number


def preview_check():
    if SimulatedRun or CameraDisabled:
        return

    if RealTimeDisplay and not camera._preview:
        real_time_display.set(False)
        cmd_set_real_time_display()
        cmd_set_focus_zoom()


def onesec_periodic_checks():  # Update RPi temperature every 10 seconds
    global win
    global onesec_after

    temperature_check()
    preview_check()

    if not ExitingApp:
        onesec_after = win.after(1000, onesec_periodic_checks)



def UpdatePlotterWindow(PTValue, ThresholdLevel, extra_shift = 0):
    global MaxPT, MinPT, PrevPTValue, PrevThresholdLevel, PlotterScroll, PlotterWindowPos

    if plotter_canvas == None:
        logging.error("Plotter canvas does not exist, exiting...")
        return

    if PTValue > MaxPT * 10:
        logging.warning("PT level too high, ignoring it")
        return

    MaxPT = max(MaxPT, PTValue)
    MinPT = min(MinPT, PTValue)
    top_label = plotter_canvas.create_text(10, 5, text=str(MaxPT), anchor='nw', font=f"Helvetica {12}")
    bottom_label = plotter_canvas.create_text(10, plotter_height - 15, text=str(MinPT), anchor='nw', font=f"Helvetica {12}")
    
    if not PlotterScroll:
        bg_top_label = plotter_canvas.create_rectangle(plotter_canvas.bbox(top_label),fill="white", outline="white")
        plotter_canvas.tag_lower(bg_top_label,top_label)
        bg_bottom_label = plotter_canvas.create_rectangle(plotter_canvas.bbox(bottom_label),fill="white", outline="white")
        plotter_canvas.tag_lower(bg_bottom_label,bottom_label)

    if PlotterScroll:
        # Shift the graph to the left
        for item in plotter_canvas.find_all():
            plotter_canvas.move(item, -(5 + extra_shift), 0)

    usable_height = plotter_height - 15
    if PlotterScroll:
        # Delete lines moving out of the canvas
        for item in plotter_canvas.find_overlapping(-10, 0, 0, usable_height):
            plotter_canvas.delete(item)
    else:
        # Delete lines we are about to overwrite
        for item in plotter_canvas.find_overlapping(PlotterWindowPos+1, 0, PlotterWindowPos+6+extra_shift, plotter_height-1):
            plotter_canvas.delete(item)
    if PlotterScroll:
        # Draw the new line segment for PT Level
        plotter_canvas.create_line(plotter_width - (6 + extra_shift), 15 + usable_height - (PrevPTValue / (MaxPT / usable_height)),
                                   plotter_width - 1, 15 + usable_height - (PTValue / (MaxPT / usable_height)), width=1,
                                   fill="blue")
    else:
        plotter_canvas.create_line(PlotterWindowPos, 15 + usable_height - (PrevPTValue / (MaxPT / usable_height)),
                                PlotterWindowPos + 5 + extra_shift, 15 + usable_height - (PTValue / (MaxPT / usable_height)), width=1,
                                fill="blue")
        plotter_canvas.create_line(PlotterWindowPos + 6 + extra_shift, 0,
                                PlotterWindowPos + 6 + extra_shift, 15 + usable_height,
                                fill="black")

    # Draw the new line segment for threshold
    if (ThresholdLevel > MaxPT):
        logging.debug(f"ThresholdLevel value is wrong ({ThresholdLevel}), replacing by previous ({PrevThresholdLevel})")
        # Swap by previous if bigger than MaxPT, sometimes I2C losses second parameter, no idea why
        ThresholdLevel = PrevThresholdLevel

    if PlotterScroll:
        plotter_canvas.create_line(plotter_width - (6 + extra_shift), 15 + usable_height - (PrevThresholdLevel / (MaxPT / usable_height)),
                                   plotter_width - 1, 15 + usable_height - (ThresholdLevel / (MaxPT / usable_height)),
                                   width=1, fill="red")
    else:
        plotter_canvas.create_line(PlotterWindowPos, 15 + usable_height - (PrevThresholdLevel / (MaxPT / usable_height)),
                                PlotterWindowPos + 5 + extra_shift, 15 + usable_height - (ThresholdLevel / (MaxPT / usable_height)),
                                width=1, fill="red")
    PrevPTValue = PTValue
    PrevThresholdLevel = ThresholdLevel
    if not PlotterScroll:
        PlotterWindowPos = (PlotterWindowPos + 5 + extra_shift) % plotter_width


# send_arduino_command: No response expected
def send_arduino_command(cmd, param=0):
    if not SimulatedRun:
        time.sleep(0.0001)  # wait 100 µs, to avoid I/O errors
        try:
            i2c.write_i2c_block_data(16, cmd, [int(param % 256), int(param >> 8)])  # Send command to Arduino
        except IOError:
            logging.warning(
                f"Error while sending command {cmd} (param {param}) to Arduino while handling frame {CurrentFrame}. "
                f"Retrying...")
            time.sleep(0.2)  # wait 100 µs, to avoid I/O errors
            i2c.write_i2c_block_data(16, cmd, [int(param % 256), int(param >> 8)])  # Send command to Arduino

        time.sleep(0.0001)  # wait 100 µs, same


def arduino_listen_loop():  # Waits for Arduino communicated events and dispatches accordingly
    global win
    global NewFrameAvailable
    global RewindErrorOutstanding, RewindEndOutstanding
    global FastForwardErrorOutstanding, FastForwardEndOutstanding
    global ArduinoTrigger
    global ScanProcessError
    global last_frame_time
    global Controller_Id, Controller_version
    global ScanStopRequested
    global arduino_after
    global PtLevelValue, StepsPerFrame
    global scan_error_counter, scan_error_total_frames_counter, scan_error_counter_value


    if not SimulatedRun:
        try:
            ArduinoData = i2c.read_i2c_block_data(16, CMD_GET_CNT_STATUS, 5)
            ArduinoTrigger = ArduinoData[0]
            ArduinoParam1 = ArduinoData[1] * 256 + ArduinoData[2]
            ArduinoParam2 = ArduinoData[3] * 256 + ArduinoData[
                4]  # Sometimes this part arrives as 255, 255, no idea why
        except IOError as e:
            ArduinoTrigger = 0
            # Log error to console
            # When error is 121, not really an error, means Arduino has nothing to data available for us
            if e.errno != 121:
                logging.warning(
                    f"Non-critical IOError ({e}) while checking incoming event from Arduino. Will check again.")

    if ScanOngoing and time.time() > last_frame_time:
        # If scan is ongoing, and more than 3 seconds have passed since last command, maybe one
        # command from/to Arduino (frame received/go to next frame) has been lost.
        # In such case, we force a 'fake' new frame command to allow process to continue
        # This means a duplicate frame might be generated.
        last_frame_time = time.time() + int(
            max_inactivity_delay * 0.34)  # Delay shared with arduino, 1/3rd less to avoid conflict with end reel
        NewFrameAvailable = True
        logging.warning("More than %i sec. since last command: Forcing new "
                        "frame event (frame %i).", int(max_inactivity_delay * 0.34), CurrentFrame)

    if ArduinoTrigger == 0:  # Do nothing
        pass
    elif ArduinoTrigger == RSP_VERSION_ID:  # New Frame available
        Controller_Id = ArduinoParam1%256
        if Controller_Id == 1:
            logging.info("Arduino controller detected")
            Controller_version = "Nano "
        elif Controller_Id == 2:
            logging.info("Raspberry Pi Pico controller detected")
            Controller_version = "Pico "
        Controller_version += f"{ArduinoParam1//256}.{ArduinoParam2//256}.{ArduinoParam2%256}"
        win.title(f"ALT-Scann8 v{__version__} (Nano {Controller_version})")  # setting title of the window
        refresh_qr_code()
    elif ArduinoTrigger == RSP_FORCE_INIT:  # Controller reloaded, sent init sequence again
        logging.debug("Controller requested to reinit")
        reinit_controller()
    elif ArduinoTrigger == RSP_FRAME_AVAILABLE:  # New Frame available
        # Delay shared with arduino, 2 seconds less to avoid conflict with end reel
        last_frame_time = time.time() + max_inactivity_delay - 2
        NewFrameAvailable = True
        scan_error_total_frames_counter += 1
        scan_error_counter_value.set(f"{scan_error_counter} ({scan_error_counter*100/scan_error_total_frames_counter:.1f}%)")

    elif ArduinoTrigger == RSP_SCAN_ERROR:  # Error during scan
        logging.warning("Received scan error from Arduino (%i, %i)", ArduinoParam1, ArduinoParam2)
        ScanProcessError = True
        scan_error_counter += 1
        scan_error_counter_value.set(f"{scan_error_counter} ({scan_error_counter*100/scan_error_total_frames_counter:.1f}%)")
        with open(scan_error_log_fullpath, 'a') as f:
            f.write(f"No Frame detected, {CurrentFrame}, {ArduinoParam1}, {ArduinoParam2}\n")
    elif ArduinoTrigger == RSP_SCAN_ENDED:  # Scan arrived at the end of the reel
        logging.warning("End of reel reached: Scan terminated")
        ScanStopRequested = True
    elif ArduinoTrigger == RSP_REPORT_AUTO_LEVELS:  # Get auto levels from Arduino, to be displayed in UI, if auto on
        if ExpertMode:
            if (AutoPtLevelEnabled):
                PtLevelValue = ArduinoParam1
                pt_level_value.set(ArduinoParam1)
            if (AutoFrameStepsEnabled):
                StepsPerFrame = ArduinoParam2
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
        if PlotterEnabled:
            UpdatePlotterWindow(ArduinoParam1, ArduinoParam2)
    elif ArduinoTrigger == RSP_FILM_FORWARD_ENDED:
        logging.warning("Received film forward end from Arduino")
        cmd_advance_movie(True)
    else:
        logging.warning("Unrecognized incoming event (%i) from Arduino.", ArduinoTrigger)

    if ArduinoTrigger != 0:
        ArduinoTrigger = 0

    if not ExitingApp:
        arduino_after = win.after(10, arduino_listen_loop)


# Base function for widget enable/disable/refresh
def widget_update(cmd, widget, enabled, inc):
    if cmd == 'enable':
        if hasattr(widget, "disabled_counter"):
            counter = widget.disabled_counter
        else:
            counter = 1 if enabled else 0  # If attribute dos not exist, initialize to 1 or 0
        if enabled:
            counter -= inc
        else:
            counter += inc
        widget.config(state=DISABLED if counter > 0 else NORMAL)
        if hasattr(widget, "disabled_counter"):
            widget.disabled_counter = counter
    elif cmd == 'refresh':
        if hasattr(widget, "disabled_counter"):
            counter = widget.disabled_counter
            widget.config(state=DISABLED if counter > 0 else NORMAL)
    """# Debug enable/disable widgets
    print(f"Widget {cmd}, {enabled}, {widget.winfo_name()}")
    if hasattr(widget, "disabled_counter"):
        print(f"   *** counter {counter}")
    """


# Updates widget disabled counter (to have a consistent state when disabled from various sources)
def widget_enable(widget, enabled, inc=1):
    widget_update('enable', widget, enabled, inc)


# Refreshes widget atatus based on counter value
def widget_refresh(widget):
    widget_update('refresh', widget, None, 0)


# Enable/diable/refresh widgets in predefined list of dependent widgets
def widget_list_update(cmd, category_list):
    global win
    global dependent_widget_dict

    # Dependent widget lists (in a dictionary)
    # Key is an id of the boolean var used to determine widget status
    # The value for each keys is a list of lists (2 lists)
    # First list contains the widgets to enable when boolean key is true
    # Second list contains the widgets to enable when boolean key is false
    dependent_widget_dict = {
        id_RealTimeDisplay: [[real_time_zoom_checkbox],
                             []],
        id_RealTimeZoom: [[focus_plus_btn, focus_minus_btn, focus_lf_btn, focus_up_btn, focus_dn_btn, focus_rt_btn],
                          []],
        id_AutoStopEnabled: [[autostop_no_film_rb, autostop_counter_zero_rb],
                             []]
    }
    if ExpertMode:
        dependent_widget_dict[id_AutoExpEnabled] = [[ae_constraint_mode_label, AeConstraintMode_dropdown,
                                                     ae_metering_mode_label, AeMeteringMode_dropdown,
                                                     ae_exposure_mode_label, AeExposureMode_dropdown,
                                                     auto_exp_wb_wait_btn],
                                                    [exposure_spinbox]]
        dependent_widget_dict[id_AutoWbEnabled] = [[awb_mode_label,AwbMode_dropdown,auto_exp_wb_wait_btn],
                                                   [wb_red_spinbox,wb_blue_spinbox]]
        dependent_widget_dict[id_AutoPtLevelEnabled] = [[],
                                                        [pt_level_spinbox]]
        dependent_widget_dict[id_AutoFrameStepsEnabled] = [[frame_extra_steps_label, frame_extra_steps_spinbox],
                                                           [steps_per_frame_spinbox]]
        dependent_widget_dict[id_ExposureWbAdaptPause] = [[match_wait_margin_spinbox],
                                                          []]
    if ExperimentalMode:
        dependent_widget_dict[id_HdrCaptureActive] = [[hdr_viewx4_active_checkbox, hdr_min_exp_label,
                                                       hdr_min_exp_spinbox, hdr_max_exp_label, hdr_max_exp_spinbox,
                                                       hdr_bracket_width_label, hdr_bracket_width_spinbox,
                                                       hdr_bracket_shift_label, hdr_bracket_shift_spinbox,
                                                       hdr_bracket_width_auto_checkbox, hdr_merge_in_place_checkbox],
                                                      []]
        dependent_widget_dict[id_HdrBracketAuto] = [[],
                                                    [hdr_max_exp_spinbox, hdr_min_exp_spinbox, hdr_max_exp_label,
                                                     hdr_min_exp_label]]
        dependent_widget_dict[id_ManualScanEnabled] = [[manual_scan_advance_fraction_5_btn,
                                                        manual_scan_advance_fraction_20_btn,manual_scan_take_snap_btn],
                                                       []]

    for category in category_list:
        if category in dependent_widget_dict:
            if category == id_HdrCaptureActive:
                state = HdrCaptureActive
            elif category == id_HdrBracketAuto:
                state = HdrBracketAuto
            elif category == id_RealTimeDisplay:
                state = RealTimeDisplay
            elif category == id_RealTimeZoom:
                state = RealTimeZoom
            elif category == id_AutoStopEnabled:
                state = AutoStopEnabled
            elif category == id_AutoWbEnabled:
                state = AutoWbEnabled
            elif category == id_AutoExpEnabled:
                state = AutoExpEnabled
            elif category == id_ManualScanEnabled:
                state = ManualScanEnabled
            elif category == id_AutoPtLevelEnabled:
                state = AutoPtLevelEnabled
            elif category == id_AutoFrameStepsEnabled:
                state = AutoFrameStepsEnabled
            elif category == id_ExposureWbAdaptPause:
                state = ExposureWbAdaptPause
            items = dependent_widget_dict[category]
            if cmd == 'enable':
                for widget in items[0]:
                    widget_enable(widget, state)
                for widget in items[1]:
                    widget_enable(widget, not state)
            elif cmd == 'refresh':
                for widget in items[0]:
                    widget_refresh(widget)
                for widget in items[1]:
                    widget_refresh(widget)

# Enable/disale list of widgets
def widget_list_enable(category_list):
    widget_list_update('enable', category_list)


# Enable/disale list of widgets
def widget_list_refresh(category_list):
    widget_list_update('refresh', category_list)


# Sets readonly custom property 'block_kbd_entry' for all custom spinboxes
def custom_spinboxes_kbd_lock(widget):
    global win
    if widget == win and UIScrollbars:
        widget = scrolled_canvas
    widgets = widget.winfo_children()
    for widget in widgets:
        if isinstance(widget, DynamicSpinbox):
            widget.set_custom_state('block_kbd_entry' if ScanOngoing else 'normal')
        elif isinstance(widget, tk.Frame) or isinstance(widget, tk.LabelFrame):
            custom_spinboxes_kbd_lock(widget)


# Disables/enables all widgets except one
def except_widget_global_enable(except_button, enabled):
    global win
    except_widget_global_enable_aux(except_button, enabled, win)
    widget_list_enable([id_ManualScanEnabled, id_AutoStopEnabled, id_ExposureWbAdaptPause, 
                        id_HdrCaptureActive, id_HdrBracketAuto])


def except_widget_global_enable_aux(except_button, enabled, widget):
    global win
    if widget == win and UIScrollbars:
        widget = scrolled_canvas

    widgets = widget.winfo_children()
    for widget in widgets:
        if isinstance(widget, tk.Frame) or isinstance(widget, tk.LabelFrame):
            except_widget_global_enable_aux(except_button, enabled, widget)
        elif hasattr(widget, "widget_type"):
            if widget.widget_type == "control" and not WidgetsEnabledWhileScanning:
                if except_button != widget:
                    widget_enable(widget, enabled, 5)
            elif widget.widget_type == "hdr" and not WidgetsEnabledWhileScanning and hdr_capture_active:
                if except_button != widget:
                    widget_enable(widget, enabled, 5)
            elif widget.widget_type == "general" or widget.widget_type == "experimental":
                if except_button != widget:
                    widget_enable(widget, enabled, 5)

def load_configuration_data_from_disk():
    global ConfigData
    global ConfigurationDataLoaded

    # Check if configuration data file exist: If it does, load it
    if os.path.isfile(ConfigurationDataFilename):
        configuration_data_file = open(ConfigurationDataFilename)
        ConfigData = json.load(configuration_data_file)
        configuration_data_file.close()
        ConfigurationDataLoaded = True
        logging.debug("Config data loaded from %s", ConfigurationDataFilename)
    else:
        logging.debug("Config data not loaded, file %s does not exist", ConfigurationDataFilename)



def validate_config_folders():
    retvalue = True
    if ConfigurationDataLoaded:
        if 'BaseFolder' in ConfigData:
            if not os.path.isdir(ConfigData["BaseFolder"]):
                retvalue = tk.messagebox.askyesno(title='Drive not mounted?',
                                                  message='Base folder defined in configuration file is not accessible. '
                                                          'Do you want to proceed using the current user home folder? '
                                                          'Otherwise ALT-Scann8 startup will be aborted.')
        if retvalue and 'CurrentDir' in ConfigData:
            if CurrentDir != '' and not os.path.isdir(ConfigData["CurrentDir"]):
                retvalue = tk.messagebox.askyesno(title='Drive not mounted?',
                                                  message='Target folder used in previous session is not accessible. '
                                                          'Do you want to proceed using the current user home folder? '
                                                          'Otherwise ALT-Scann8 startup will be aborted.')
    return retvalue


def load_config_data_pre_init():
    global ExpertMode, ExperimentalMode, PlotterEnabled, SimplifiedMode, UIScrollbars, DetectMisalignedFrames, MisalignedFrameTolerance, FontSize, DisableToolTips, BaseFolder
    global WidgetsEnabledWhileScanning, LogLevel, LoggingMode, ColorCodedButtons, TempInFahrenheit, LogLevel

    for item in ConfigData:
        logging.debug("%s=%s", item, str(ConfigData[item]))
    if ConfigurationDataLoaded:
        logging.debug("ConfigData loaded from disk:")
        if 'SimplifiedMode' in ConfigData:
            SimplifiedMode = ConfigData["SimplifiedMode"]
        if SimplifiedMode:
            ExpertMode = False
            ExperimentalMode = False
            PlotterEnabled = False
        else:
            if 'ExpertMode' in ConfigData:
                ExpertMode = ConfigData["ExpertMode"]
            if 'ExperimentalMode' in ConfigData:
                ExperimentalMode = ConfigData["ExperimentalMode"]
            if 'PlotterEnabled' in ConfigData:
                PlotterEnabled = ConfigData["PlotterEnabled"]
            elif 'PlotterMode' in ConfigData:       # legacy tag for plotter window enabled
                PlotterEnabled = ConfigData["PlotterMode"]
        if 'UIScrollbars' in ConfigData:
            UIScrollbars = ConfigData["UIScrollbars"]
        if 'DetectMisalignedFrames' in ConfigData:
            DetectMisalignedFrames = ConfigData["DetectMisalignedFrames"]
        if 'MisalignedFrameTolerance' in ConfigData:
            MisalignedFrameTolerance = ConfigData["MisalignedFrameTolerance"]
        if 'DisableToolTips' in ConfigData:
            DisableToolTips = ConfigData["DisableToolTips"]
        if 'WidgetsEnabledWhileScanning' in ConfigData:
            WidgetsEnabledWhileScanning = ConfigData["WidgetsEnabledWhileScanning"]
        if 'FontSize' in ConfigData:
            FontSize = ConfigData["FontSize"]
        if 'ColorCodedButtons' in ConfigData:
            ColorCodedButtons = ConfigData["ColorCodedButtons"]
        if 'TempInFahrenheit' in ConfigData:
            if isinstance(ConfigData["TempInFahrenheit"], bool):
                TempInFahrenheit = ConfigData["TempInFahrenheit"]
            else:
                TempInFahrenheit = eval(ConfigData["TempInFahrenheit"])
        if 'BaseFolder' in ConfigData:
            if os.path.isdir(ConfigData["BaseFolder"]):
                BaseFolder = ConfigData["BaseFolder"]
        if 'LogLevel' in ConfigData:
            LogLevel = ConfigData["LogLevel"]
            LoggingMode = logging.getLevelName(LogLevel)
            logging.getLogger().setLevel(LogLevel)


def load_session_data_post_init():
    global CurrentDir
    global CurrentFrame, FramesToGo
    global MinFrameStepsS8, MinFrameStepsR8
    global PTLevelS8, PTLevelR8
    global HdrCaptureActive
    global HdrViewX4Active
    global max_inactivity_delay
    global manual_wb_red_value, manual_wb_blue_value
    global manual_exposure_value
    global PreviewModuleValue
    global NegativeImage
    global AutoExpEnabled, AutoWbEnabled
    global AutoFrameStepsEnabled, AutoPtLevelEnabled
    global HdrBracketAuto
    global MatchWaitMarginValue
    global StepsPerFrame, PtLevelValue, FrameFineTuneValue, FrameExtraStepsValue, ScanSpeedValue
    global StabilizationDelayValue
    global HdrMinExp, HdrMaxExp, HdrBracketWidth, HdrBracketShift, HdrMergeInPlace
    global ExposureWbAdaptPause
    global FileType, FilmType, CapstanDiameter
    global CaptureResolution
    global AutoExpEnabled, AutoWbEnabled

    if ConfigurationDataLoaded:
        logging.debug("ConfigData loaded from disk:")
        confirm = tk.messagebox.askyesno(title='Load previous session status',
                                         message='Do you want to restore the status of the previous ALT-Scann8 session?')
        if confirm:
            if 'NegativeCaptureActive' in ConfigData:
                NegativeImage = ConfigData["NegativeCaptureActive"]
                negative_image.set(NegativeImage)
                cmd_set_negative_image()
            if 'FilmType' in ConfigData:
                FilmType = ConfigData["FilmType"]
                film_type.set(FilmType)
                if ConfigData["FilmType"] == "R8":
                    cmd_set_r8()
                elif ConfigData["FilmType"] == "S8":
                    cmd_set_s8()
            if 'CurrentFrame' in ConfigData:
                if isinstance(ConfigData["CurrentFrame"], str):
                    ConfigData["CurrentFrame"] = int(ConfigData["CurrentFrame"])
                CurrentFrame = ConfigData["CurrentFrame"]
                Scanned_Images_number.set(ConfigData["CurrentFrame"])
            if 'FramesToGo' in ConfigData:
                if ConfigData["FramesToGo"] != -1:
                    FramesToGo = int(ConfigData["FramesToGo"])
                    frames_to_go_str.set(str(FramesToGo))
                else:
                    frames_to_go_str.set('')
            if 'FileType' in ConfigData:
                FileType = ConfigData["FileType"]
                logging.debug(f"Retrieved from config: FileType = {FileType} ({ConfigData['FileType']})")
            if 'CurrentDir' in ConfigData:
                CurrentDir = ConfigData["CurrentDir"]
                if CurrentDir != '':    # Respect empty currentdir in case no tyet set after very first run
                    # If directory in configuration does not exist we set the current working dir
                    if not os.path.isdir(CurrentDir):
                        CurrentDir = os.getcwd()
                    folder_frame_target_dir.config(text=CurrentDir)
                    with open(scan_error_log_fullpath, 'a') as f:
                        f.write(f"Starting scan error log for {CurrentDir}\n")

            if ExperimentalMode:
                if 'HdrCaptureActive' in ConfigData:
                    if isinstance(ConfigData["HdrCaptureActive"], str):
                        HdrCaptureActive = eval(ConfigData["HdrCaptureActive"])
                        ConfigData["HdrCaptureActive"] = HdrCaptureActive  # Save as boolean for next time
                    else:
                        HdrCaptureActive = ConfigData["HdrCaptureActive"]
                    if HdrCaptureActive:
                        max_inactivity_delay = reference_inactivity_delay * 2
                        send_arduino_command(CMD_SET_STALL_TIME, max_inactivity_delay)
                        logging.debug(f"max_inactivity_delay: {max_inactivity_delay}")
                        hdr_capture_active_checkbox.select()
                if 'HdrViewX4Active' in ConfigData:
                    if isinstance(ConfigData["HdrViewX4Active"], str):
                        HdrViewX4Active = eval(ConfigData["HdrViewX4Active"])
                        ConfigData["HdrViewX4Active"] = HdrViewX4Active  # Save as boolean for next time
                    else:
                        HdrViewX4Active = ConfigData["HdrViewX4Active"]
                    if HdrViewX4Active:
                        hdr_viewx4_active_checkbox.select()
                    else:
                        hdr_viewx4_active_checkbox.deselect()
                if 'HdrMinExp' in ConfigData:
                    HdrMinExp = int(ConfigData["HdrMinExp"])
                hdr_min_exp_value.set(HdrMinExp)
                if 'HdrMaxExp' in ConfigData:
                    HdrMaxExp = int(ConfigData["HdrMaxExp"])
                hdr_max_exp_value.set(HdrMaxExp)
                if 'HdrBracketAuto' in ConfigData:
                    HdrBracketAuto = ConfigData["HdrBracketAuto"]
                    hdr_bracket_auto.set(HdrBracketAuto)
                if 'HdrMergeInPlace' in ConfigData:
                    HdrMergeInPlace = ConfigData["HdrMergeInPlace"]
                    hdr_merge_in_place.set(HdrMergeInPlace)
                if 'HdrBracketWidth' in ConfigData:
                    HdrBracketWidth = int(ConfigData["HdrBracketWidth"])
                    hdr_bracket_width_value.set(HdrBracketWidth)
                if 'HdrBracketShift' in ConfigData:
                    HdrBracketShift = ConfigData["HdrBracketShift"]
                    hdr_bracket_shift_value.set(HdrBracketShift)
        else:   # If not loading previous session status, restore to default
            ConfigData["NegativeCaptureActive"] = NegativeImage
            ConfigData["FilmType"] = FilmType
            ConfigData["CurrentFrame"] = CurrentFrame
            ConfigData["FramesToGo"] = ''
            ConfigData["FileType"] = FileType
            ConfigData["CurrentDir"] = CurrentDir
            ConfigData["CaptureResolution"] = CaptureResolution
            ConfigData["HdrCaptureActive"] = HdrCaptureActive
            ConfigData["HdrViewX4Active"] = HdrViewX4Active
            ConfigData["HdrMinExp"] = HdrMinExp
            ConfigData["HdrMaxExp"] = HdrMaxExp
            ConfigData["HdrBracketAuto"] = HdrBracketAuto
            ConfigData["HdrMergeInPlace"] = HdrMergeInPlace
            ConfigData["HdrBracketWidth"] = HdrBracketWidth
            ConfigData["HdrBracketShift"] = HdrBracketShift

        if 'CaptureResolution' in ConfigData:
            valid_resolution_list = camera_resolutions.get_list()
            selected_resolution = ConfigData["CaptureResolution"]
            if selected_resolution not in valid_resolution_list:
                if selected_resolution + ' *' in valid_resolution_list:
                    selected_resolution = selected_resolution + ' *'
                else:
                    selected_resolution = valid_resolution_list[2]
            CaptureResolution = selected_resolution
            if CaptureResolution == "4056x3040":
                max_inactivity_delay = reference_inactivity_delay * 2
            else:
                max_inactivity_delay = reference_inactivity_delay
            send_arduino_command(CMD_SET_STALL_TIME, max_inactivity_delay)
            logging.debug(f"max_inactivity_delay: {max_inactivity_delay}")
        if 'CapstanDiameter' in ConfigData:
            CapstanDiameter = ConfigData["CapstanDiameter"]
            logging.debug(f"Retrieved from config: CapstanDiameter = {CapstanDiameter} ({ConfigData['CapstanDiameter']})")
            send_arduino_command(CMD_ADJUST_MIN_FRAME_STEPS, int(CapstanDiameter * 10))
        if 'AutoStopType' in ConfigData:
            autostop_type.set(ConfigData["AutoStopType"])
        if 'AutoStopActive' in ConfigData:
            auto_stop_enabled.set(ConfigData["AutoStopActive"])
            cmd_set_auto_stop_enabled()
        # Experimental mode options
        if ExperimentalMode:
            if 'PreviewModule' in ConfigData:
                aux = int(ConfigData["PreviewModule"])
                PreviewModuleValue = aux
                preview_module_value.set(aux)
            if 'UVBrightness' in ConfigData:
                aux = int(ConfigData["UVBrightness"])
                send_arduino_command(CMD_SET_UV_LEVEL, aux)
                uv_brightness_value.set(aux)
        # Expert mode options
        if ExpertMode:
            if 'ExposureWbAdaptPause' in ConfigData:
                ExposureWbAdaptPause = ConfigData["ExposureWbAdaptPause"]
                auto_exp_wb_change_pause.set(ExposureWbAdaptPause)
                if ExposureWbAdaptPause:
                    auto_exp_wb_wait_btn.select()
                else:
                    auto_exp_wb_wait_btn.deselect()
            if 'MatchWaitMargin' in ConfigData:
                MatchWaitMarginValue = ConfigData["MatchWaitMargin"]
            else:
                MatchWaitMarginValue = 50
            aux = int(MatchWaitMarginValue)
            match_wait_margin_value.set(aux)
            if 'CaptureStabilizationDelay' in ConfigData:
                aux = float(ConfigData["CaptureStabilizationDelay"])
                StabilizationDelayValue = round(aux)
            else:
                StabilizationDelayValue = 100
            stabilization_delay_value.set(StabilizationDelayValue)
            if 'CurrentExposure' in ConfigData:
                aux = ConfigData["CurrentExposure"]
                if isinstance(aux, str):
                    aux = int(float(aux))
                manual_exposure_value = aux
                if not SimulatedRun and not CameraDisabled:
                    camera.set_controls({"ExposureTime": int(aux)})
                exposure_value.set(aux / 1000)
            if 'AutoExpEnabled' in ConfigData:
                AutoExpEnabled = ConfigData["AutoExpEnabled"]
                AE_enabled.set(AutoExpEnabled)
                cmd_set_auto_exposure()
            if 'CurrentAwbAuto' in ConfigData:     # Delete legacy name, replace with new
                ConfigData['AutoWbEnabled'] = ConfigData['CurrentAwbAuto']
                del ConfigData['CurrentAwbAuto']
            if 'AutoWbEnabled' in ConfigData:
                if isinstance(ConfigData["AutoWbEnabled"], bool):
                    aux = ConfigData["AutoWbEnabled"]
                else:
                    aux = eval(ConfigData["AutoWbEnabled"])
                AutoWbEnabled = aux
                AWB_enabled.set(AutoWbEnabled)
                cmd_set_auto_wb()
            # Set initial value of auto_exp_wb_wait_btn, as it depends of two variables
            if not AutoExpEnabled and not AutoWbEnabled:
                auto_exp_wb_wait_btn.disabled_counter = 1
            elif AutoExpEnabled != AutoWbEnabled:
                auto_exp_wb_wait_btn.disabled_counter = 0
            elif AutoExpEnabled and AutoWbEnabled:
                auto_exp_wb_wait_btn.disabled_counter = -1
            widget_enable(auto_exp_wb_wait_btn, True)
            widget_enable(auto_exp_wb_wait_btn, False)
            if 'GainRed' in ConfigData:
                aux = float(ConfigData["GainRed"])
                wb_red_value.set(round(aux, 1))
                manual_wb_red_value = aux
            if 'GainBlue' in ConfigData:
                aux = float(ConfigData["GainBlue"])
                wb_blue_value.set(round(aux, 1))
                manual_wb_blue_value = aux
            if not (SimulatedRun or CameraDisabled):
                camera_colour_gains = (manual_wb_red_value, manual_wb_blue_value)
                camera.set_controls({"ColourGains": camera_colour_gains})
            # Recover miscellaneous PiCamera2 controls
            if "AeConstraintMode" in ConfigData:
                aux = ConfigData["AeConstraintMode"]
                AeConstraintMode_dropdown_selected.set(aux)
                if not SimulatedRun and not CameraDisabled:
                    camera.set_controls({"AeConstraintMode": AeConstraintMode_dict[aux]})
            if "AeMeteringMode" in ConfigData:
                aux = ConfigData["AeMeteringMode"]
                if aux == "CentreWeighted": # Change on 9th Feb 2025: Legacy name, convert to new name
                    aux = "CentreWgt"
                AeMeteringMode_dropdown_selected.set(aux)
                if not SimulatedRun and not CameraDisabled:
                    camera.set_controls({"AeMeteringMode": AeMeteringMode_dict[aux]})
            if "AeExposureMode" in ConfigData:
                aux = ConfigData["AeExposureMode"]
                AeExposureMode_dropdown_selected.set(aux)
                if not SimulatedRun and not CameraDisabled:
                    camera.set_controls({"AeExposureMode": AeExposureMode_dict[aux]})
            if "AwbMode" in ConfigData:
                aux = ConfigData["AwbMode"]
                AwbMode_dropdown_selected.set(aux)
                if not SimulatedRun and not CameraDisabled:
                    camera.set_controls({"AwbMode": AwbMode_dict[aux]})
            # Recover frame alignment values
            if 'MinFrameSteps' in ConfigData:
                MinFrameSteps = int(ConfigData["MinFrameSteps"])
                StepsPerFrame = MinFrameSteps
                steps_per_frame_value.set(MinFrameSteps)
                send_arduino_command(CMD_SET_MIN_FRAME_STEPS, MinFrameSteps)
            if 'FrameStepsAuto' in ConfigData:     # Delete legacy name, replace with new
                ConfigData['AutoFrameStepsEnabled'] = ConfigData['FrameStepsAuto']
                del ConfigData['FrameStepsAuto']
            if 'AutoFrameStepsEnabled' in ConfigData:
                AutoFrameStepsEnabled = ConfigData["AutoFrameStepsEnabled"]
                auto_framesteps_enabled.set(AutoFrameStepsEnabled)
                cmd_steps_per_frame_auto()
                if AutoFrameStepsEnabled:
                    send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0)
                else:
                    send_arduino_command(CMD_SET_MIN_FRAME_STEPS, StepsPerFrame)
            if 'MinFrameStepsS8' in ConfigData:
                MinFrameStepsS8 = ConfigData["MinFrameStepsS8"]
            if 'MinFrameStepsR8' in ConfigData:
                MinFrameStepsR8 = ConfigData["MinFrameStepsR8"]
            if 'FrameFineTune' in ConfigData:
                FrameFineTuneValue = ConfigData["FrameFineTune"]
                frame_fine_tune_value.set(FrameFineTuneValue)
                send_arduino_command(CMD_SET_FRAME_FINE_TUNE, FrameFineTuneValue)
            if 'FrameExtraSteps' in ConfigData:
                FrameExtraStepsValue = ConfigData["FrameExtraSteps"]
                FrameExtraStepsValue = min(FrameExtraStepsValue, 20)
                frame_extra_steps_value.set(FrameExtraStepsValue)
                send_arduino_command(CMD_SET_EXTRA_STEPS, FrameExtraStepsValue)
            if 'PTLevelAuto' in ConfigData:     # Delete legacy name, replace with new
                ConfigData['AutoPtLevelEnabled'] = ConfigData['PTLevelAuto']
                del ConfigData['PTLevelAuto']
            if 'AutoPtLevelEnabled' in ConfigData:
                AutoPtLevelEnabled = ConfigData["AutoPtLevelEnabled"]
                auto_pt_level_enabled.set(AutoPtLevelEnabled)
                cmd_set_auto_pt_level()
                if AutoPtLevelEnabled:
                    send_arduino_command(CMD_SET_PT_LEVEL, 0)
                else:
                    send_arduino_command(CMD_SET_PT_LEVEL, PtLevelValue)
            if 'PTLevel' in ConfigData:
                PTLevel = int(ConfigData["PTLevel"])
                pt_level_value.set(PTLevel)
                PtLevelValue = PTLevel
                if not AutoPtLevelEnabled:
                    send_arduino_command(CMD_SET_PT_LEVEL, PTLevel)
            if 'PTLevelS8' in ConfigData:
                PTLevelS8 = ConfigData["PTLevelS8"]
            if 'PTLevelR8' in ConfigData:
                PTLevelR8 = ConfigData["PTLevelR8"]
            if 'ScanSpeed' in ConfigData:
                ScanSpeedValue = int(ConfigData["ScanSpeed"])
                scan_speed_value.set(ScanSpeedValue)
                send_arduino_command(CMD_SET_SCAN_SPEED, ScanSpeedValue)
            if 'Brightness' in ConfigData:
                aux = ConfigData["Brightness"]
                brightness_value.set(aux)
                if not SimulatedRun and not CameraDisabled:
                    camera.set_controls({"Brightness": aux})
            if 'Contrast' in ConfigData:
                aux = ConfigData["Contrast"]
                contrast_value.set(aux)
                if not SimulatedRun and not CameraDisabled:
                    camera.set_controls({"Contrast": aux})
            if 'Saturation' in ConfigData:
                aux = ConfigData["Saturation"]
                saturation_value.set(aux)
                if not SimulatedRun and not CameraDisabled:
                    camera.set_controls({"Saturation": aux})
            if 'AnalogueGain' in ConfigData:
                aux = ConfigData["AnalogueGain"]
                analogue_gain_value.set(aux)
                if not SimulatedRun and not CameraDisabled:
                    camera.set_controls({"AnalogueGain": aux})
            if 'ExposureCompensation' in ConfigData:
                aux = ConfigData["ExposureCompensation"]
                exposure_compensation_value.set(aux)
                if not SimulatedRun and not CameraDisabled:
                    camera.set_controls({"ExposureValue": aux})
            if 'SharpnessValue' in ConfigData:
                aux = int(ConfigData["SharpnessValue"])  # In case it is stored as string
                sharpness_value.set(aux)
                if not SimulatedRun and not CameraDisabled:
                    camera.set_controls({"Sharpness": aux})
        else:
            # If expert mode not enabled, activate automated options
            # (but do not set in session data to keep configuration options)
            AutoExpEnabled = True
            AutoWbEnabled = True
            AutoFrameStepsEnabled = True
            AutoPtLevelEnabled = True
            FrameFineTuneValue = 20
            ScanSpeedValue = 5
            if not SimulatedRun and not CameraDisabled:
                camera.set_controls({"AeEnable": AutoExpEnabled})
                camera.set_controls({"AwbEnable": AutoWbEnabled})
                send_arduino_command(CMD_SET_PT_LEVEL, 0)
                send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0)
                send_arduino_command(CMD_SET_FRAME_FINE_TUNE, FrameFineTuneValue)
                send_arduino_command(CMD_SET_SCAN_SPEED, ScanSpeedValue)

        # Refresh plotter mode in Arduino here since when reading from config I2C has not been enabled yet
        send_arduino_command(CMD_REPORT_PLOTTER_INFO, PlotterEnabled)

        widget_list_enable([id_ManualScanEnabled, id_AutoStopEnabled, id_ExposureWbAdaptPause, 
                            id_HdrCaptureActive, id_HdrBracketAuto])
        if not SimplifiedMode:
            detect_misaligned_frames_btn.config(state=NORMAL if DetectMisalignedFrames else DISABLED)
            scan_error_counter_value_label.config(state=NORMAL if DetectMisalignedFrames else DISABLED)

        # Display current capture settings as loaded from file
        capture_info_str.set(f"{FileType} - {CaptureResolution}")

    # Initialize camera resolution with value set, whether default or from configuration
    PiCam2_change_resolution()


def reinit_controller():
    if not ExpertMode:
        return

    if AutoPtLevelEnabled:
        send_arduino_command(CMD_SET_PT_LEVEL, 0)
    else:
        send_arduino_command(CMD_SET_PT_LEVEL, PtLevelValue)

    if AutoFrameStepsEnabled:
        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0)
    else:
        send_arduino_command(CMD_SET_MIN_FRAME_STEPS, StepsPerFrame)

    if 'FilmType' in ConfigData:
        if ConfigData["FilmType"] == "R8":
            send_arduino_command(CMD_SET_REGULAR_8)
        else:
            send_arduino_command(CMD_SET_SUPER_8)

    send_arduino_command(CMD_SET_FRAME_FINE_TUNE, FrameFineTuneValue)
    send_arduino_command(CMD_SET_EXTRA_STEPS, FrameExtraStepsValue)
    send_arduino_command(CMD_SET_SCAN_SPEED, ScanSpeedValue)


def PiCam2_change_resolution():
    global CaptureResolution

    camera_resolutions.set_active(CaptureResolution)
    if SimulatedRun or CameraDisabled:
        return  # Skip camera specific part

    capture_config["main"]["size"] = camera_resolutions.get_image_resolution()
    # capture_config["main"]["format"] = camera_resolutions.get_format()
    capture_config["raw"]["size"] = camera_resolutions.get_sensor_resolution()
    capture_config["raw"]["format"] = camera_resolutions.get_format()
    camera.stop()
    camera.configure(capture_config)
    camera.start()

    logging.debug(f"Camera resolution set at: {CaptureResolution}")



def PiCam2_configure():
    global capture_config, preview_config

    camera.stop()
    capture_config = camera.create_still_configuration(main={"size": camera_resolutions.get_sensor_resolution()},
                                                       raw={"size": camera_resolutions.get_sensor_resolution(),
                                                            "format": camera_resolutions.get_format()},
                                                       transform=Transform(hflip=True))

    preview_config = camera.create_preview_configuration({"size": (2028, 1520)}, transform=Transform(hflip=True))
    # Camera preview window is not saved in configuration, so always off on start up (we start in capture mode)
    camera.configure(capture_config)
    # WB controls
    camera.set_controls({"AwbEnable": False})
    camera.set_controls({"ColourGains": (2.2, 2.2)})  # 0.0 to 32.0, Red 2.2, Blue 2.2 seem to be OK
    # Exposure controls
    camera.set_controls({"AeEnable": True})
    camera.set_controls(
        {"AeConstraintMode": controls.AeConstraintModeEnum.Normal})  # Normal, Highlight, Shadows, Custom
    camera.set_controls(
        {"AeMeteringMode": controls.AeMeteringModeEnum.CentreWeighted})  # CentreWeighted, Spot, Matrix, Custom
    camera.set_controls({"AeExposureMode": controls.AeExposureModeEnum.Normal})  # Normal, Long, Short, Custom
    # Other generic controls
    camera.set_controls({"AnalogueGain": 1.0})
    camera.set_controls({"Contrast": 1})  # 0.0 to 32.0
    camera.set_controls({"Brightness": 0})  # -1.0 to 1.0
    camera.set_controls({"Saturation": 1})  # Color saturation, 0.0 to 32.0
    # camera.set_controls({"NoiseReductionMode": draft.NoiseReductionModeEnum.HighQuality})   # Off, Fast, HighQuality
    camera.set_controls({"Sharpness": 1})  # It can be a floating point number from 0.0 to 16.0
    # draft.NoiseReductionModeEnum.HighQuality not defined, yet
    # However, looking at the PiCamera2 Source Code, it seems the default value for still configuration
    # is already HighQuality, so not much to worry about
    # camera.set_controls({"NoiseReductionMode": draft.NoiseReductionModeEnum.HighQuality})
    # No preview by default
    camera.options[
        'quality'] = 100  # jpeg quality: values from 0 to 100. Reply from David Plowman in PiCam2 list. Test with 60?
    camera.start(show_preview=False)


def hdr_init():
    global hdr_view_4_image

    if hdr_view_4_image is None:
        hdr_view_4_image = Image.new("RGB", (PreviewWidth, PreviewHeight))
    hdr_reinit()


def hdr_reinit():
    global hdr_exp_list, hdr_rev_exp_list, hdr_num_exposures

    if not ExperimentalMode:
        return
    if hdr_num_exposures == 3:
        hdr_exp_list.clear()
        hdr_exp_list += [HdrMinExp, hdr_best_exp, HdrMaxExp]
    elif hdr_num_exposures == 5:
        hdr_exp_list.clear()
        hdr_exp_list += [HdrMinExp,
                         HdrMinExp + int((hdr_best_exp - HdrMinExp) / 2), hdr_best_exp,
                         hdr_best_exp + int((HdrMaxExp - hdr_best_exp) / 2), HdrMaxExp]

    hdr_exp_list.sort()
    logging.debug("hdr_exp_list=%s", hdr_exp_list)
    hdr_rev_exp_list = list(reversed(hdr_exp_list))


def on_configure_scrolled_canvas(event):
    scrolled_canvas.configure(scrollregion=scrolled_canvas.bbox("all"))


# Initialize widgets with multiple dependencies
def init_multidependent_widgets():
    if HdrCaptureActive == HdrBracketAuto and HdrBracketAuto:
        hdr_min_exp_label.disabled_counter = 1
        hdr_max_exp_label.disabled_counter = 1
        hdr_min_exp_spinbox.disabled_counter = 1
        hdr_max_exp_spinbox.disabled_counter = 1

        widget_list_refresh([id_HdrBracketAuto])


def create_main_window():
    global win
    global plotter_width, plotter_height
    global PreviewWinX, PreviewWinY, app_width, app_height, original_app_height, PreviewWidth, PreviewHeight
    global FontSize
    global TopWinX, TopWinY
    global WinInitDone, as_tooltips
    global FilmHoleY_Top, FilmHoleY_Bottom, FilmHoleHeightTop, FilmHoleHeightBottom
    global screen_width, screen_height
    resolution_font = [(590, 6), (628, 7), (672, 8), (718, 9), (771, 10), (823, 11), (882, 12), (932, 13), (974, 14),
                       (1022, 15), (1087, 16), (1149, 17), (1195, 18)]

    if win is None:
        win = tkinter.Tk()  # creating the main window and storing the window object in 'win'
    else:
        destroy_widgets(win)
        win.deiconify()
    if SimulatedRun:
        if SimulatedArduinoVersion == None:
            win.title(f'ALT-Scann8 v{__version__} ***  SIMULATED RUN, NOT OPERATIONAL ***')
        else:
            win.title(f"ALT-Scann8 v{__version__} (Nano {SimulatedArduinoVersion})") # Real title for snapshots
    else:
        win.title(f"ALT-Scann8 v{__version__} (Nano {Controller_version})")  # setting title of the window
    # Get screen size - maxsize gives the usable screen size
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()
    #screen_width, screen_height = win.maxsize()
    logging.info(f"Screen size: {screen_width}x{screen_height}")

    # Determine optimal font size
    if FontSize == 0:
        FontSize = 5
        for resfont in resolution_font:
            if resfont[0] + 128 < screen_height:
                FontSize = resfont[1]
            else:
                break
        logging.info(f"Font size: {FontSize}")
    PreviewWidth = 700
    PreviewHeight = int(PreviewWidth / (4 / 3))
    app_width = PreviewWidth + 420
    app_height = PreviewHeight + 50
    # Set minimum plotter size, to be adjusted later based on left frame width
    plotter_width = 20
    plotter_height = 10
    # Size and position of hole markers
    FilmHoleHeightTop = int(PreviewHeight / 5.9)
    FilmHoleHeightBottom = int(PreviewHeight / 3.7)
    FilmHoleY_Top = 6
    FilmHoleY_Bottom = int(PreviewHeight / 1.25)
    if ExpertMode or ExperimentalMode:
        app_height += 325
    # Check if window fits on screen, otherwise reduce and add scroll bar
    if app_height > screen_height:
        app_height = screen_height - 128
    # Save original ap height for toggle UI button
    original_app_height = app_height
    # Prevent window resize
    win.minsize(app_width, app_height)
    win.maxsize(app_width, app_height)
    win.geometry(f'{app_width}x{app_height - 20}')  # setting the size of the window
    if 'WindowPos' in ConfigData:
        win.geometry(f"+{ConfigData['WindowPos'].split('+', 1)[1]}")

    # Catch closing with 'X' button
    win.protocol("WM_DELETE_WINDOW", cmd_app_standard_exit)

    # Init ToolTips
    as_tooltips = Tooltips(FontSize)

    create_widgets()

    logging.info(f"Window size: {app_width}x{app_height + 20}")

    # Get Top window coordinates
    TopWinX = win.winfo_x()
    TopWinY = win.winfo_y()

    # Change preview coordinated for PiCamera2 to avoid confusion with overlay mode in PiCamera legacy
    PreviewWinX = 250
    PreviewWinY = 150
    WinInitDone = True


# Define a custom exception hook to log uncaught exceptions
def exception_hook(exctype, value, tb):
    logging.exception(f"Uncaught exception {repr(value)}", exc_info=(exctype, value, tb))


def log_thread_exception(args):
    logging.exception(f"Thread exception occurred: {args.exc_type.__name__}: {args.exc_value}", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


def init_logging():
    global scan_error_log_fullpath

    # Initialize logging
    log_path = os.path.dirname(__file__)
    if log_path == "":
        log_path = os.getcwd()
    log_path = log_path + "/Logs"
    if not os.path.isdir(log_path):
        os.mkdir(log_path)
    log_file_fullpath = log_path + "/ALT-Scann8." + time.strftime("%Y%m%d") + ".log"
    logging.basicConfig(
        level=LogLevel,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file_fullpath),
            logging.StreamHandler(sys.stdout)
        ]
    )
    # Initialize scan error logging
    scan_error_log_fullpath = log_path + "/ScanErrors." + time.strftime("%Y%m%d") + ".log"

    # Override Python's default exception hook with our custom one
    sys.excepthook = exception_hook
    threading.excepthook = log_thread_exception

    logging.info("ALT-Scann8 %s (%s)", __version__, __date__)
    logging.info("Log file: %s", log_file_fullpath)
    logging.info("Scan error log file: %s", scan_error_log_fullpath)
    logging.info("Config file: %s", ConfigurationDataFilename)


def tscann8_init():
    global win
    global camera
    global i2c
    global CurrentDir
    global ZoomSize
    global capture_display_queue, capture_display_event
    global capture_save_queue, capture_save_event
    global MergeMertens, camera_resolutions
    global active_threads
    global time_save_image, time_preview_display, time_awb, time_autoexp
    global hw_panel, hw_panel_installed

    if SimulatedRun:
        logging.info("Not running on Raspberry Pi, simulated run for UI debugging purposes only")
    else:
        logging.info("Running on Raspberry Pi")

    if not can_check_dng_frames_for_misalignment:
        logging.warning("Frame alignment for DNG files is disabled. To enable it please install rawpy library")

    logging.debug("BaseFolder=%s", BaseFolder)

    if not SimulatedRun:
        i2c = smbus.SMBus(1)
        # Set the I2C clock frequency to 400 kHz
        i2c.write_byte_data(16, 0x0F, 0x46)  # I2C_SCLL register
        i2c.write_byte_data(16, 0x10, 0x47)  # I2C_SCLH register

    if not SimulatedRun and not CameraDisabled:  # Init PiCamera2 here, need resolution list for drop down
        camera = Picamera2()
        camera_resolutions = CameraResolutions(camera.sensor_modes)
        logging.info(f"Camera Sensor modes: {camera.sensor_modes}")
        PiCam2_configure()
        ZoomSize = camera.capture_metadata()['ScalerCrop']
        logging.debug(f"ScalerCrop: {ZoomSize}")
    if SimulatedRun:
        # Initializes resolution list from a hardcoded sensor_modes
        camera_resolutions = CameraResolutions(simulated_sensor_modes)

    # Initialize rolling average objects
    time_save_image = RollingAverage(50)
    time_preview_display = RollingAverage(50)
    time_awb = RollingAverage(50)
    time_autoexp = RollingAverage(50)

    create_main_window()

    # Check if hw panel module available
    if SimulatedRun:
        hw_panel_installed = False

    if hw_panel_installed:
        hw_panel = HwPanel(win, i2c)
    else:
        hw_panel = None

    # Init HDR variables
    hdr_init()
    # Create MergeMertens Object for HDR
    MergeMertens = cv2.createMergeMertens()

    reset_controller()

    get_controller_version()

    send_arduino_command(CMD_REPORT_PLOTTER_INFO, PlotterEnabled)

    win.update_idletasks()

    if not SimulatedRun and not CameraDisabled:
        # JRE 20/09/2022: Attempt to speed up overall process in PiCamera2 by having captured images
        # displayed in the preview area by a dedicated thread, so that time consumed in this task
        # does not impact the scan process speed
        capture_display_queue = queue.Queue(maxsize=MaxQueueSize)
        capture_display_event = threading.Event()
        capture_save_queue = queue.Queue(maxsize=MaxQueueSize)
        capture_save_event = threading.Event()
        display_thread = threading.Thread(target=capture_display_thread, args=(capture_display_queue,
                                                                               capture_display_event, 0))
        save_thread_1 = threading.Thread(target=capture_save_thread, args=(capture_save_queue, capture_save_event, 1))
        save_thread_2 = threading.Thread(target=capture_save_thread, args=(capture_save_queue, capture_save_event, 2))
        save_thread_3 = threading.Thread(target=capture_save_thread, args=(capture_save_queue, capture_save_event, 3))
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
def value_normalize(var, min_value, max_value, default):
    try:
        value = var.get()
    except tk.TclError as e:
        var.set(default)
        return min_value
    if value > max_value:
        value = max_value
    if value < min_value:
        value = min_value
    var.set(value)
    return value


def value_validation(new_value, widget, min, max, default, is_double=False):
    try:
        if new_value == '':
            new_value = default
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


def cmd_set_auto_exposure():
    global AutoExpEnabled, manual_exposure_value

    AutoExpEnabled = AE_enabled.get()
    ConfigData["AutoExpEnabled"] = AutoExpEnabled
    widget_list_enable([id_AutoExpEnabled])
    exposure_spinbox.config(state='readonly' if AutoExpEnabled else NORMAL)

    if AutoExpEnabled:
        if KeepManualValues:
            manual_exposure_value = int(exposure_value.get() * 1000)
        auto_exposure_btn.config(text="Auto Exp:")
    else:
        if KeepManualValues:
            exposure_value.set(int(manual_exposure_value/1000))
        auto_exposure_btn.config(text="Exposure:")

    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"AeEnable": AutoExpEnabled})
        if KeepManualValues:
            camera.set_controls({"ExposureTime": int(manual_exposure_value)})
        elif not AutoExpEnabled:
            camera.set_controls({"ExposureTime": int(int(exposure_value.get() * 1000))})


def cmd_auto_exp_wb_change_pause_selection():
    global ExposureWbAdaptPause
    ExposureWbAdaptPause = auto_exp_wb_change_pause.get()
    ConfigData["ExposureWbAdaptPause"] = ExposureWbAdaptPause
    widget_list_enable([id_ExposureWbAdaptPause])


def cmd_exposure_selection():
    global manual_exposure_value
    if AutoExpEnabled:  # Do not allow spinbox changes when in auto mode (should not happen as spinbox is readonly)
        return
    aux = value_normalize(exposure_value, camera_resolutions.get_min_exp() / 1000,
                          camera_resolutions.get_max_exp() / 1000,
                          100)
    aux = aux * 1000
    if aux <= 0:
        aux = camera_resolutions.get_min_exp()  # Minimum exposure is 1µs, zero means automatic
    else:
        manual_exposure_value = aux
        ConfigData["CurrentExposure"] = manual_exposure_value

    if not SimulatedRun and not CameraDisabled:
        camera.controls.ExposureTime = int(aux)  # maybe will not work, check pag 26 of picamera2 specs


def exposure_validation(new_value):
    # Use zero instead if minimum exposure from PiCamera2 to prevent flagging in red when selection auto exposure
    return value_validation(new_value, exposure_spinbox, 0, camera_resolutions.get_max_exp() / 1000,
                            100, True)


def cmd_wb_red_selection():
    global manual_wb_red_value
    if AutoWbEnabled:  # Do not allow spinbox changes when in auto mode (should not happen as spinbox is readonly)
        return

    aux = value_normalize(wb_red_value, 0, 32, 2.2)
    manual_wb_red_value = aux
    ConfigData["GainRed"] = aux

    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"ColourGains": (aux, wb_blue_value.get())})


def wb_red_validation(new_value):
    return value_validation(new_value, wb_red_spinbox, 0, 32, 2.2, True)


def cmd_wb_blue_selection():
    global manual_wb_blue_value
    if AutoWbEnabled:  # Do not allow spinbox changes when in auto mode (should not happen as spinbox is readonly)
        return

    aux = value_normalize(wb_blue_value, 0, 32, 2.2)
    manual_wb_blue_value = aux
    ConfigData["GainBlue"] = aux

    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"ColourGains": (wb_red_value.get(), aux)})


def wb_blue_validation(new_value):
    return value_validation(new_value, wb_blue_spinbox, 0, 32, 2.2, True)


def cmd_match_wait_margin_selection():
    global MatchWaitMarginValue

    MatchWaitMarginValue = value_normalize(match_wait_margin_value, 5, 100, 50)
    ConfigData["MatchWaitMargin"] = MatchWaitMarginValue


def match_wait_margin_validation(new_value):
    return value_validation(new_value, match_wait_margin_spinbox, 5, 100, 50)


def cmd_set_AeConstraintMode(selected):
    ConfigData["AeConstraintMode"] = selected
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"AeConstraintMode": AeConstraintMode_dict[selected]})


def cmd_set_AeMeteringMode(selected):
    ConfigData["AeMeteringMode"] = selected
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"AeMeteringMode": AeMeteringMode_dict[selected]})


def cmd_set_AeExposureMode(selected):
    ConfigData["AeExposureMode"] = selected
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"AeExposureMode": AeExposureMode_dict[selected]})


def cmd_set_AwbMode(selected):
    ConfigData["AwbMode"] = selected
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"AwbMode": AwbMode_dict[selected]})


def cmd_steps_per_frame_auto():
    global AutoFrameStepsEnabled
    AutoFrameStepsEnabled = auto_framesteps_enabled.get()
    widget_list_enable([id_AutoFrameStepsEnabled])
    steps_per_frame_btn.config(text="Steps/Frame AUTO:" if AutoFrameStepsEnabled else "Steps/Frame:")
    ConfigData["AutoFrameStepsEnabled"] = AutoFrameStepsEnabled
    send_arduino_command(CMD_SET_MIN_FRAME_STEPS, 0 if AutoFrameStepsEnabled else StepsPerFrame)


def cmd_steps_per_frame_selection():
    global StepsPerFrame
    if AutoFrameStepsEnabled:
        return
    MinFrameSteps = value_normalize(steps_per_frame_value, 100, 600, 250)
    StepsPerFrame = MinFrameSteps
    ConfigData["MinFrameSteps"] = MinFrameSteps
    ConfigData["MinFrameSteps" + ConfigData["FilmType"]] = MinFrameSteps
    send_arduino_command(CMD_SET_MIN_FRAME_STEPS, MinFrameSteps)


def steps_per_frame_validation(new_value):
    return value_validation(new_value, steps_per_frame_spinbox, 100, 600, 250)


def cmd_set_auto_pt_level():
    global AutoPtLevelEnabled
    AutoPtLevelEnabled = auto_pt_level_enabled.get()
    widget_list_enable([id_AutoPtLevelEnabled])
    pt_level_btn.config(text="PT Level AUTO:" if AutoPtLevelEnabled else "PT Level:")
    ConfigData["AutoPtLevelEnabled"] = AutoPtLevelEnabled
    send_arduino_command(CMD_SET_PT_LEVEL, 0 if AutoPtLevelEnabled else PtLevelValue)


def cmd_pt_level_selection():
    global PtLevelValue
    if AutoPtLevelEnabled:
        return
    PTLevel = value_normalize(pt_level_value, 20, 900, 500)
    PtLevelValue = PTLevel
    ConfigData["PTLevel"] = PTLevel
    ConfigData["PTLevel" + ConfigData["FilmType"]] = PTLevel
    send_arduino_command(CMD_SET_PT_LEVEL, PTLevel)


def pt_level_validation(new_value):
    return value_validation(new_value, pt_level_spinbox, 20, 900, 500)


def cmd_frame_fine_tune_selection():
    global FrameFineTuneValue
    FrameFineTuneValue = value_normalize(frame_fine_tune_value, 5, 95, 25)
    ConfigData["FrameFineTune"] = FrameFineTuneValue
    ConfigData["FrameFineTune" + ConfigData["FilmType"]] = FrameFineTuneValue
    send_arduino_command(CMD_SET_FRAME_FINE_TUNE, FrameFineTuneValue)


def fine_tune_validation(new_value):
    return value_validation(new_value, frame_fine_tune_spinbox, 5, 95, 25)


def extra_steps_validation(new_value):
    return value_validation(new_value, frame_extra_steps_spinbox, -30, 30, 0)


def cmd_scan_speed_selection():
    global ScanSpeedValue
    ScanSpeedValue = value_normalize(scan_speed_value, 1, 10, 5)
    ConfigData["ScanSpeed"] = ScanSpeedValue
    send_arduino_command(CMD_SET_SCAN_SPEED, ScanSpeedValue)


def scan_speed_validation(new_value):
    return value_validation(new_value, scan_speed_spinbox, 1, 10, 5)


def cmd_preview_module_selection():
    global PreviewModuleValue
    PreviewModuleValue = value_normalize(preview_module_value, 1, 50, 1)
    ConfigData["PreviewModule"] = PreviewModuleValue


def cmd_uv_brightness_selection():
    aux = value_normalize(uv_brightness_value, 1, 255, 255)
    ConfigData["UVBrightness"] = aux
    send_arduino_command(CMD_SET_UV_LEVEL, aux)


def preview_module_validation(new_value):
    return value_validation(new_value, preview_module_spinbox, 1, 50, 1)


def uv_brightness_validation(new_value):
    return value_validation(new_value, uv_brightness_spinbox, 1, 255, 255)


def cmd_stabilization_delay_selection():
    global StabilizationDelayValue
    StabilizationDelayValue = value_normalize(stabilization_delay_value, 0, 1000, 150)
    ConfigData["CaptureStabilizationDelay"] = StabilizationDelayValue


def stabilization_delay_validation(new_value):
    return value_validation(new_value, stabilization_delay_spinbox, 0, 1000, 150)


def cmd_hdr_min_exp_selection():
    global force_adjust_hdr_bracket, recalculate_hdr_exp_list, HdrMinExp, HdrMaxExp, HdrBracketWidth

    min_exp = value_normalize(hdr_min_exp_value, HDR_MIN_EXP, HDR_MAX_EXP-1, 100)
    max_exp = min_exp + HdrBracketWidth  # New max based on new min
    if max_exp > HDR_MAX_EXP:
        max_exp = HDR_MAX_EXP
        if HdrBracketWidth > HDR_MIN_BRACKET:
            HdrMinExp = min_exp
            HdrBracketWidth = max_exp - HdrMinExp  # Reduce bracket in max over the top
            force_adjust_hdr_bracket = True
    else:
        HdrMinExp = min_exp
    HdrMaxExp = max_exp
    hdr_min_exp_value.set(HdrMinExp)
    hdr_max_exp_value.set(HdrMaxExp)
    hdr_bracket_width_value.set(HdrBracketWidth)
    recalculate_hdr_exp_list = True
    ConfigData["HdrMinExp"] = HdrMinExp
    ConfigData["HdrMaxExp"] = HdrMaxExp
    ConfigData["HdrBracketWidth"] = HdrBracketWidth


def hdr_min_exp_validation(new_value):
    return value_validation(new_value, hdr_min_exp_spinbox, 1, 999, 100)


def cmd_hdr_max_exp_selection():
    global recalculate_hdr_exp_list, force_adjust_hdr_bracket, HdrMinExp, HdrMaxExp, HdrBracketWidth

    max_exp = value_normalize(hdr_max_exp_value, HDR_MIN_EXP+1, HDR_MAX_EXP, 200)
    min_exp = max_exp - HdrBracketWidth
    if min_exp < HDR_MIN_EXP:
        min_exp = HDR_MIN_EXP
        if HdrBracketWidth > HDR_MIN_BRACKET:
            HdrMaxExp = max_exp
            HdrBracketWidth = HdrMaxExp - min_exp  # Reduce bracket in min below absolute min
            force_adjust_hdr_bracket = True
    else:
        HdrMaxExp = max_exp
    HdrMinExp = min_exp
    hdr_min_exp_value.set(HdrMinExp)
    hdr_max_exp_value.set(HdrMaxExp)
    hdr_bracket_width_value.set(HdrBracketWidth)
    recalculate_hdr_exp_list = True
    ConfigData["HdrMinExp"] = HdrMinExp
    ConfigData["HdrMaxExp"] = HdrMaxExp
    ConfigData["HdrBracketWidth"] = HdrBracketWidth


def hdr_max_exp_validation(new_value):
    return value_validation(new_value, hdr_max_exp_spinbox, 2, 1000, 200)


def cmd_hdr_bracket_width_selection(event=None):
    global force_adjust_hdr_bracket, HdrMinExp, HdrMaxExp, HdrBracketWidth

    aux = value_normalize(hdr_bracket_width_value, HDR_MIN_BRACKET, HDR_MAX_BRACKET, 200)
    if aux < HDR_MIN_BRACKET:
        return
    else:
        HdrBracketWidth = aux

    middle_exp = int(HdrMinExp + (HdrMaxExp - HdrMinExp)/2)
    HdrMinExp = max(HDR_MIN_EXP, int(middle_exp - (HdrBracketWidth / 2)))
    hdr_min_exp_value.set(HdrMinExp)
    HdrMaxExp = HdrMinExp + HdrBracketWidth
    if event is None and HdrMaxExp < HDR_MAX_EXP and HdrBracketWidth % 2 == 0:
        HdrMinExp += 1
        HdrMaxExp += 1
    hdr_min_exp_value.set(HdrMinExp)
    hdr_max_exp_value.set(HdrMaxExp)
    ConfigData["HdrMinExp"] = HdrMinExp
    ConfigData["HdrMaxExp"] = HdrMaxExp
    ConfigData["HdrBracketWidth"] = HdrBracketWidth
    force_adjust_hdr_bracket = True


def hdr_bracket_width_validation(new_value):
    return value_validation(new_value, hdr_bracket_width_spinbox, HDR_MIN_BRACKET, HDR_MAX_BRACKET,100)


def cmd_hdr_bracket_shift_selection():
    global HdrBracketShift
    HdrBracketShift = value_normalize(hdr_bracket_shift_value, -100, 100, 0)


def hdr_bracket_shift_validation(new_value):
    return value_validation(new_value, hdr_bracket_shift_spinbox, -100, 100, 0)


def cmd_exposure_compensation_selection():
    aux = value_normalize(exposure_compensation_value, -8, 8, 0)
    ConfigData["ExposureCompensation"] = aux
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"ExposureValue": aux})


def exposure_compensation_validation(new_value):
    return value_validation(new_value, exposure_compensation_spinbox, -8, 8, 0)


def cmd_brightness_selection():
    aux = value_normalize(brightness_value, -1, 1, 0)
    ConfigData["Brightness"] = aux
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"Brightness": aux})


def brightness_validation(new_value):
    return value_validation(new_value, brightness_spinbox, -1, 1, 0)


def cmd_contrast_selection():
    aux = value_normalize(contrast_value, 0, 32, 1)
    ConfigData["Contrast"] = aux
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"Contrast": aux})


def contrast_validation(new_value):
    return value_validation(new_value, contrast_spinbox, 0, 32, 1)


def cmd_saturation_selection():
    aux = value_normalize(saturation_value, 0, 32, 1)
    ConfigData["Saturation"] = aux
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"Saturation": aux})


def saturation_validation(new_value):
    return value_validation(new_value, saturation_spinbox, 0, 32, 1)


def cmd_analogue_gain_selection():
    aux = value_normalize(analogue_gain_value, 0, 32, 0)
    ConfigData["AnalogueGain"] = aux
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"AnalogueGain": aux})


def analogue_gain_validation(new_value):
    return value_validation(new_value, analogue_gain_spinbox, 0, 32, 0)


def cmd_sharpness_selection():
    aux = value_normalize(sharpness_value, 0, 16, 1)
    ConfigData["SharpnessValue"] = aux
    if not SimulatedRun and not CameraDisabled:
        camera.set_controls({"Sharpness": aux})


def sharpness_validation(new_value):
    return value_validation(new_value, sharpness_spinbox, 0, 16, 1)


def cmd_rwnd_speed_control_selection():
    value_normalize(rwnd_speed_control_value, 40, 800, 800)


def rewind_speed_validation(new_value):
    return value_validation(new_value, rwnd_speed_control_spinbox, 40, 800, 800)


def update_target_dir_wraplength(event):
    folder_frame_target_dir.config(wraplength=event.width - 20)  # Adjust the padding as needed


def cmd_plotter_canvas_click(event):
    global PlotterEnabled, PlotterScroll, PlotterWindowPos
    if PlotterEnabled:
        if not PlotterScroll:
            PlotterScroll = True
            logging.debug("Enable Plotter Scroll")
        else:
            PlotterEnabled = False
            PlotterWindowPos = 0
            logging.debug("Disable Plotter")
    else:
        PlotterEnabled = True
        PlotterScroll = False
        PlotterWindowPos = 0
        logging.debug("Enable Plotter, without scroll")
        

# ***************
# Widget creation
# ***************

def destroy_widgets(container):
    for widget in container.winfo_children():
        destroy_widgets(widget)
        widget.destroy()


def create_widgets():
    global win
    global AdvanceMovie_btn
    global negative_image_checkbox, negative_image
    global fast_forward_btn, rewind_btn
    global free_btn, manual_uv_btn
    global rpi_temp_value_label
    global start_btn
    global folder_frame_target_dir
    global film_type_S8_rb, film_type_R8_rb, film_type
    global save_bg, save_fg
    global auto_exp_wb_change_pause
    global auto_exp_wb_wait_btn
    global film_hole_frame_top, film_hole_frame_bottom
    global FilmHoleHeightTop, FilmHoleHeightBottom, FilmHoleY_Top, FilmHoleY_Bottom
    global real_time_display_checkbox, real_time_display
    global real_time_zoom_checkbox, real_time_zoom
    global auto_stop_enabled_checkbox, auto_stop_enabled
    global focus_lf_btn, focus_up_btn, focus_dn_btn, focus_rt_btn, focus_plus_btn, focus_minus_btn
    global draw_capture_canvas
    global steps_per_frame_value, frame_fine_tune_value
    global pt_level_spinbox
    global steps_per_frame_spinbox, frame_fine_tune_spinbox, pt_level_spinbox, pt_level_value
    global frame_extra_steps_spinbox, frame_extra_steps_value, frame_extra_steps_label
    global scan_speed_spinbox, scan_speed_value
    global exposure_value
    global wb_red_spinbox, wb_blue_spinbox, wb_red_value, wb_blue_value
    global match_wait_margin_spinbox, match_wait_margin_value
    global stabilization_delay_spinbox, stabilization_delay_value
    global sharpness_spinbox, sharpness_value
    global rwnd_speed_control_spinbox, rwnd_speed_control_value
    global Manual_scan_activated, ManualScanEnabled, manual_scan_take_snap_btn
    global manual_scan_advance_fraction_5_btn, manual_scan_advance_fraction_20_btn
    global plotter_canvas
    global hdr_capture_active_checkbox, hdr_capture_active, hdr_viewx4_active
    global hdr_viewx4_active_checkbox, hdr_min_exp_label, hdr_min_exp_spinbox, hdr_max_exp_label, hdr_max_exp_spinbox
    global hdr_max_exp_value, hdr_min_exp_value
    global steps_per_frame_btn, auto_framesteps_enabled, pt_level_btn, auto_pt_level_enabled
    global auto_exposure_btn, auto_wb_red_btn, auto_wb_blue_btn, exposure_spinbox
    global hdr_bracket_width_spinbox, hdr_bracket_shift_spinbox, hdr_bracket_width_label, hdr_bracket_shift_label
    global hdr_bracket_width_value, hdr_bracket_shift_value
    global hdr_bracket_auto, hdr_merge_in_place, hdr_bracket_width_auto_checkbox, hdr_merge_in_place_checkbox
    global frames_to_go_str, FramesToGo, frames_to_go_time_str
    global retreat_movie_btn, manual_scan_checkbox
    global file_type_dropdown_selected
    global Scanned_Images_number, scanned_Images_time_value, scanned_Images_fps_value, scanned_images_number_label
    global existing_folder_btn, new_folder_btn
    global autostop_no_film_rb, autostop_counter_zero_rb, autostop_type
    global AE_enabled, AWB_enabled
    global extended_frame, expert_frame, experimental_frame
    global time_save_image_value, time_preview_display_value, time_awb_value, time_autoexp_value
    global AeConstraintMode_dropdown_selected, AeMeteringMode_dropdown_selected, AeExposureMode_dropdown_selected
    global AwbMode_dropdown_selected
    global AeConstraintMode_dropdown, AeMeteringMode_dropdown, AeExposureMode_dropdown, AwbMode_dropdown
    global ae_constraint_mode_label, ae_metering_mode_label, ae_exposure_mode_label, awb_mode_label
    global brightness_value, contrast_value, saturation_value, analogue_gain_value, exposure_compensation_value
    global preview_module_value
    global brightness_spinbox, contrast_spinbox, saturation_spinbox, analogue_gain_spinbox
    global exposure_compensation_spinbox, preview_module_spinbox
    global scrolled_canvas
    global PreviewWidth, PreviewHeight
    global plotter_width, plotter_height
    global app_width, app_height
    global options_btn
    global match_wait_margin_spinbox
    global qr_code_canvas, qr_code_frame
    global uv_brightness_value, uv_brightness_spinbox
    global scan_error_counter_value, scan_error_counter_value_label, detect_misaligned_frames_btn, detect_misaligned_frames
    global capture_info_str

    # Global value for separations between widgets
    y_pad = 2
    x_pad = 2

    # Check if vertical scrollbar required
    if UIScrollbars:
        # Create a canvas widget
        scrolled_canvas = tk.Canvas(win)

        # Add a horizontal scrollbar to the canvas
        scrolled_canvas_scrollbar_h = tk.Scrollbar(win, orient=tk.HORIZONTAL, command=scrolled_canvas.xview)
        scrolled_canvas_scrollbar_h.pack(side=BOTTOM, fill=tk.X)

        scrolled_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add a vertical scrollbar to the canvas
        scrolled_canvas_scrollbar_v = tk.Scrollbar(win, command=scrolled_canvas.yview)
        scrolled_canvas_scrollbar_v.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure the canvas to use the scrollbar
        scrolled_canvas.configure(xscrollcommand=scrolled_canvas_scrollbar_h.set,
                                  yscrollcommand=scrolled_canvas_scrollbar_v.set)

        # Create a frame inside the canvas to hold the content
        scrolled_frame = tk.Frame(scrolled_canvas, name='scrollable_canvas')
        scrolled_canvas.create_window((0, 0), window=scrolled_frame, anchor="nw")

        # Bind the frame to the canvas so it resizes properly
        scrolled_frame.bind("<Configure>", on_configure_scrolled_canvas)

        main_container = scrolled_frame
    else:
        scrolled_canvas = None
        main_container = win

    # Create a frame to contain the top area (preview + Right buttons) ***************
    top_area_frame = Frame(main_container, name='main_container')
    top_area_frame.pack(side=TOP, pady=(8, 0), anchor=NW, fill='both')

    # Create a frame to contain the top right area (buttons) ***************
    top_left_area_frame = Frame(top_area_frame, name='top_left_area_frame')
    top_left_area_frame.pack(side=LEFT, anchor=N, padx=(10, 0))
    # Create a LabelFrame to act as a border of preview canvas
    draw_capture_frame = tk.LabelFrame(top_area_frame, bd=2, relief=tk.GROOVE, name='draw_capture_frame')
    draw_capture_frame.pack(side=LEFT, anchor=N, padx=(10, 0), pady=(2, 0))  # Pady+=2 to compensate
    # Create the canvas
    draw_capture_canvas = Canvas(draw_capture_frame, bg='dark grey', width=PreviewWidth, height=PreviewHeight,
                                 name='draw_capture_canvas')
    draw_capture_canvas.pack(padx=(20, 5), pady=5)
    # Create a frame to contain the top right area (buttons) ***************
    top_right_area_frame = Frame(top_area_frame, name='top_right_area_frame')
    top_right_area_frame.pack(side=LEFT, anchor=N, padx=(10, 0))

    # ***************************************
    # Display markers for film hole reference
    # Size & postition of markers relative to preview height
    film_hole_frame_top = Frame(draw_capture_frame, width=1, height=1, bg='black', name='film_hole_frame_top')
    film_hole_frame_top.pack(side=TOP, padx=1, pady=1)
    film_hole_frame_top.place(x=0, y=FilmHoleY_Top, height=FilmHoleHeightTop)
    film_hole_label_1 = Label(film_hole_frame_top, justify=LEFT, font=("Arial", FontSize), width=2, height=11,
                              bg='white', fg='white')
    film_hole_label_1.pack(side=TOP)

    film_hole_frame_bottom = Frame(draw_capture_frame, width=1, height=1, bg='black', name='film_hole_frame_bottom')
    film_hole_frame_bottom.pack(side=TOP, padx=1, pady=1)
    film_hole_frame_bottom.place(x=0, y=FilmHoleY_Bottom, height=FilmHoleHeightBottom)
    film_hole_label_2 = Label(film_hole_frame_bottom, justify=LEFT, font=("Arial", FontSize), width=2, height=11,
                              bg='white', fg='white')
    film_hole_label_2.pack(side=TOP)

    # Set initial positions for widgets in this frame
    bottom_area_column = 0
    bottom_area_row = 0

    # Retreat movie button (slow backward through filmgate)
    retreat_movie_btn = Button(top_left_area_frame, text="<", command=cmd_retreat_movie,
                                activebackground='#f0f0f0', relief=RAISED, font=("Arial", FontSize+3),
                                name='retreat_movie_btn')
    retreat_movie_btn.widget_type = "general"
    retreat_movie_btn.grid(row=bottom_area_row, column=bottom_area_column, padx=x_pad, pady=y_pad,
                          sticky='NSEW')
    as_tooltips.add(retreat_movie_btn, "Moves the film backwards. BEWARE!!!: Requires manually rotating the source "
                                        "reels in left position in order to avoid film jamming at film gate.")

    # Advance movie button (slow forward through filmgate)
    AdvanceMovie_btn = Button(top_left_area_frame, text=">", command=cmd_advance_movie,
                              activebackground='#f0f0f0', relief=RAISED, font=("Arial", FontSize+3),
                              name='advanceMovie_btn')
    AdvanceMovie_btn.widget_type = "general"
    AdvanceMovie_btn.grid(row=bottom_area_row, column=bottom_area_column + 1, padx=x_pad, pady=y_pad,
                          sticky='NSEW')
    as_tooltips.add(AdvanceMovie_btn, "Advance film (can be used with real-time view enabled).")
    bottom_area_row += 1
    # Once first button created, get default colors, to revert when we change them
    save_bg = AdvanceMovie_btn['bg']
    save_fg = AdvanceMovie_btn['fg']

    # Frame for single step/snapshot
    sstep_area_frame = Frame(top_left_area_frame, name='sstep_area_frame')
    sstep_area_frame.grid_forget()
    # Advance one single frame
    singleStep_btn = Button(sstep_area_frame, text="Single Step", command=cmd_single_step_movie,
                            activebackground='#f0f0f0', font=("Arial", FontSize), name='singleStep_btn')
    singleStep_btn.widget_type = "general"
    singleStep_btn.grid_forget()
    snapshot_btn = Button(sstep_area_frame, text="Snapshot", command=cmd_capture_single_step,
                          activebackground='#f0f0f0', font=("Arial", FontSize), name='snapshot_btn')
    snapshot_btn.widget_type = "general"
    snapshot_btn.grid_forget()

    # Rewind movie (via upper path, outside of film gate)
    rewind_btn = Button(top_left_area_frame, text="<<", font=("Arial", FontSize + 3), height=2, command=cmd_rewind_movie,
                        activebackground='#f0f0f0', relief=RAISED, name='rewind_btn')
    rewind_btn.widget_type = "general"
    rewind_btn.grid(row=bottom_area_row, column=bottom_area_column, padx=x_pad, pady=y_pad, sticky='NSEW')
    as_tooltips.add(rewind_btn, "Rewind film. Make sure film is routed via upper rolls.")
    # Fast Forward movie (via upper path, outside of film gate)
    fast_forward_btn = Button(top_left_area_frame, text=">>", font=("Arial", FontSize + 3), height=2,
                             command=cmd_fast_forward_movie, activebackground='#f0f0f0', relief=RAISED,
                             name='fast_forward_btn')
    fast_forward_btn.widget_type = "general"
    fast_forward_btn.grid(row=bottom_area_row, column=bottom_area_column + 1, padx=x_pad, pady=y_pad, sticky='NSEW')
    as_tooltips.add(fast_forward_btn, "Fast-forward film. Make sure film is routed via upper rolls.")
    bottom_area_row += 1

    # Real time view to allow focus
    real_time_display = tk.BooleanVar(value=RealTimeDisplay)
    real_time_display_checkbox = tk.Checkbutton(top_left_area_frame, text='Focus view', height=1,
                                                variable=real_time_display, onvalue=True, offvalue=False,
                                                font=("Arial", FontSize), command=cmd_set_real_time_display,
                                                indicatoron=False, name='real_time_display_checkbox')
    real_time_display_checkbox.widget_type = "general"
    if ColorCodedButtons:
        real_time_display_checkbox.config(selectcolor="pale green")
    real_time_display_checkbox.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=x_pad,
                                    pady=y_pad, sticky='NSEW')
    as_tooltips.add(real_time_display_checkbox, "Enable real-time film preview. Cannot be used while scanning, "
                                                "useful mainly to focus the film.")
    bottom_area_row += 1

    # Activate focus zoom, to facilitate focusing the camera
    real_time_zoom = tk.BooleanVar(value=RealTimeZoom)
    real_time_zoom_checkbox = tk.Checkbutton(top_left_area_frame, text='Zoom view', height=1,
                                             variable=real_time_zoom, onvalue=True, offvalue=False,
                                             font=("Arial", FontSize), command=cmd_set_focus_zoom, indicatoron=False,
                                             state='disabled', name='real_time_zoom_checkbox')
    if ColorCodedButtons:
        real_time_zoom_checkbox.config(selectcolor="pale green")
    real_time_zoom_checkbox.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=x_pad, pady=y_pad,
                                 sticky='NSEW')
    as_tooltips.add(real_time_zoom_checkbox, "Zoom in on the real-time film preview. Useful to focus the film")
    bottom_area_row += 1

    # Focus zoom control (in out, up, down, left, right)
    focus_frame = LabelFrame(top_left_area_frame, text='Zoom control', height=3, font=("Arial", FontSize - 2),
                             name='focus_frame')
    focus_frame.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=x_pad, pady=y_pad,
                     sticky='NSEW')
    bottom_area_row += 1

    Focus_btn_grid_frame = Frame(focus_frame)
    Focus_btn_grid_frame.pack(padx=x_pad, pady=y_pad)

    # focus zoom displacement buttons, to further facilitate focusing the camera
    focus_plus_btn = Button(Focus_btn_grid_frame, text="➕", height=1, command=cmd_set_focus_plus, state='disabled',
                            activebackground='#f0f0f0', font=("Arial", FontSize - 2), name='focus_plus_btn')
    focus_plus_btn.grid(row=0, column=2, sticky='NSEW')
    as_tooltips.add(focus_plus_btn, "Increase zoom level.")
    focus_minus_btn = Button(Focus_btn_grid_frame, text="➖", height=1, command=cmd_set_focus_minus, state='disabled',
                             activebackground='#f0f0f0', font=("Arial", FontSize - 2), name='focus_minus_btn')
    focus_minus_btn.grid(row=0, column=0, sticky='NSEW')
    as_tooltips.add(focus_minus_btn, "Decrease zoom level.")
    focus_lf_btn = Button(Focus_btn_grid_frame, text="⇐", height=1, command=cmd_set_focus_left, state='disabled',
                          activebackground='#f0f0f0', font=("Arial", FontSize - 2), name='focus_lf_btn')
    focus_lf_btn.grid(row=1, column=0, sticky='NSEW')
    as_tooltips.add(focus_lf_btn, "Move zoom view to the left.")
    focus_up_btn = Button(Focus_btn_grid_frame, text="⇑", height=1, command=cmd_set_focus_up, state='disabled',
                          activebackground='#f0f0f0', font=("Arial", FontSize), name='focus_up_btn')
    focus_up_btn.grid(row=0, column=1, sticky='NSEW')
    as_tooltips.add(focus_up_btn, "Move zoom view up.")
    focus_dn_btn = Button(Focus_btn_grid_frame, text="⇓", height=1, command=cmd_set_focus_down, state='disabled',
                          activebackground='#f0f0f0', font=("Arial", FontSize), name='focus_dn_btn')
    focus_dn_btn.grid(row=1, column=1, sticky='NSEW')
    as_tooltips.add(focus_dn_btn, "Move zoom view down.")
    focus_rt_btn = Button(Focus_btn_grid_frame, text="⇒", height=1, command=cmd_set_focus_right, state='disabled',
                          activebackground='#f0f0f0', font=("Arial", FontSize - 2), name='focus_rt_btn')
    focus_rt_btn.grid(row=1, column=2, sticky='NSEW')
    as_tooltips.add(focus_rt_btn, "Move zoom view to the right.")
    bottom_area_row += 1

    # Switch Positive/negative modes
    negative_image = tk.BooleanVar(value=NegativeImage)
    negative_image_checkbox = tk.Checkbutton(top_left_area_frame, text='Negative film',
                                             variable=negative_image, onvalue=True, offvalue=False,
                                             font=("Arial", FontSize), command=cmd_set_negative_image,
                                             indicatoron=False, name='negative_image_checkbox')
    negative_image_checkbox.widget_type = "general"
    if ColorCodedButtons:
        negative_image_checkbox.config(selectcolor="pale green")
    negative_image_checkbox.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=x_pad, pady=y_pad,
                                 sticky='NSEW')
    as_tooltips.add(negative_image_checkbox, "Enable negative film capture (untested with real negative film)")
    bottom_area_row += 1

    # Create frame to display RPi temperature
    rpi_temp_frame = LabelFrame(top_left_area_frame, text='RPi Temp.', height=1, font=("Arial", FontSize - 2),
                                name='rpi_temp_frame')
    rpi_temp_frame.grid(row=bottom_area_row, column=0, columnspan=2, padx=x_pad, pady=y_pad, sticky='NSEW')
    temp_str = str(RPiTemp) + 'º'
    rpi_temp_value_label = Label(rpi_temp_frame, text=temp_str, font=("Arial", FontSize + 4),
                                 name='rpi_temp_value_label')
    rpi_temp_value_label.pack(side=TOP)
    as_tooltips.add(rpi_temp_value_label, "Raspberry Pi Temperature.")
    bottom_area_row += 1

    # Toggle UI size & stats only in expert mode
    if ExpertMode:
        # Statictics sub-frame
        statistics_frame = LabelFrame(top_left_area_frame, text='Avrg time (ms)', font=("Arial", FontSize - 1),
                                      name='statistics_frame')
        statistics_frame.grid(row=bottom_area_row, column=bottom_area_column, columnspan=2, padx=x_pad, pady=y_pad,
                              sticky='NSEW')
        # Average Time to save image
        time_save_image_label = tk.Label(statistics_frame, text='Save:', font=("Arial", FontSize - 1),
                                         name='time_save_image_label')
        time_save_image_label.grid(row=0, column=0, sticky=E)
        as_tooltips.add(time_save_image_label, "Average time spent in saving each frame (in milliseconds)")
        time_save_image_value = tk.IntVar(value=0)
        time_save_image_value_label = tk.Label(statistics_frame, textvariable=time_save_image_value,
                                               font=("Arial", FontSize - 1), name='time_save_image_value_label')
        time_save_image_value_label.grid(row=0, column=1, sticky=W)
        as_tooltips.add(time_save_image_value_label, "Average time spent in saving each frame (in milliseconds)")
        time_save_image_label_ms = tk.Label(statistics_frame, text='ms', font=("Arial", FontSize - 1),
                                            name='time_save_image_label_ms')
        time_save_image_label_ms.grid(row=0, column=2, sticky=E)
        # Average Time to display preview
        time_preview_display_label = tk.Label(statistics_frame, text='Prvw:', font=("Arial", FontSize - 1),
                                              name='time_preview_display_label')
        time_preview_display_label.grid(row=1, column=0, sticky=E)
        as_tooltips.add(time_preview_display_label, "Average time spent in displaying a preview of each frame (in "
                                                    "milliseconds)")
        time_preview_display_value = tk.IntVar(value=0)
        time_preview_display_value_label = tk.Label(statistics_frame, textvariable=time_preview_display_value,
                                                    font=("Arial", FontSize - 1),
                                                    name='time_preview_display_value_label')
        time_preview_display_value_label.grid(row=1, column=1, sticky=W)
        as_tooltips.add(time_preview_display_value_label, "Average time spent in displaying a preview of each frame ("
                                                          "in milliseconds)")
        time_preview_display_label_ms = tk.Label(statistics_frame, text='ms', font=("Arial", FontSize - 1),
                                                 name='time_preview_display_label_ms')
        time_preview_display_label_ms.grid(row=1, column=2, sticky=E)
        # Average Time spent waiting for AWB to adjust
        time_awb_label = tk.Label(statistics_frame, text='AWB:', font=("Arial", FontSize - 1), name='time_awb_label')
        time_awb_label.grid(row=2, column=0, sticky=E)
        as_tooltips.add(time_awb_label, "Average time spent waiting for white balance to match automatic value (in "
                                        "milliseconds)")
        time_awb_value = tk.IntVar(value=0)
        time_awb_value_label = tk.Label(statistics_frame, textvariable=time_awb_value, font=("Arial", FontSize - 1),
                                        name='time_awb_value_label')
        time_awb_value_label.grid(row=2, column=1, sticky=W)
        as_tooltips.add(time_awb_value_label, "Average time spent waiting for white balance to match automatic value "
                                              "(in milliseconds)")
        time_awb_label_ms = tk.Label(statistics_frame, text='ms', font=("Arial", FontSize - 1),
                                     name='time_awb_label_ms')
        time_awb_label_ms.grid(row=2, column=2, sticky=E)
        # Average Time spent waiting for AE to adjust
        time_autoexp_label = tk.Label(statistics_frame, text='AE:', font=("Arial", FontSize - 1),
                                      name='time_autoexp_label')
        time_autoexp_label.grid(row=3, column=0, sticky=E)
        as_tooltips.add(time_autoexp_label, "Average time spent waiting for exposure to match automatic value (in "
                                            "milliseconds)")
        time_autoexp_value = tk.IntVar(value=0)
        time_autoexp_value_label = tk.Label(statistics_frame, textvariable=time_autoexp_value,
                                            font=("Arial", FontSize - 1), name='time_autoexp_value_label')
        time_autoexp_value_label.grid(row=3, column=1, sticky=W)
        as_tooltips.add(time_autoexp_value_label, "Average time spent waiting for exposure to match automatic value ("
                                                  "in milliseconds)")
        time_autoexp_label_ms = tk.Label(statistics_frame, text='ms', font=("Arial", FontSize - 1),
                                         name='time_autoexp_label_ms')
        time_autoexp_label_ms.grid(row=3, column=2, sticky=E)
        bottom_area_row += 1

    # Settings button, at the bottom of top left area
    options_btn = Button(top_left_area_frame, text="Settings", command=cmd_settings_popup, 
                         activebackground='#f0f0f0', relief=RAISED, font=("Arial", FontSize - 1), name='options_btn')
    options_btn.widget_type = "general"
    options_btn.grid(row=bottom_area_row, column=0, columnspan=2, padx=x_pad, pady=y_pad, sticky='NSEW')
    as_tooltips.add(options_btn, "Set ALT-Scann8 options.")
    bottom_area_row += 1

    # Create vertical button column at right *************************************
    # Application Exit button
    top_right_area_row = 0

    # Emergency exit (exit without saving)
    emergency_exit_btn = Button(top_right_area_frame, text="Exit (do not save)", height=1, command=cmd_app_emergency_exit, 
                                activebackground='red', activeforeground='white', relief=RAISED,
                                font=("Arial", FontSize - 1), name='emergency_exit_btn')
    emergency_exit_btn.widget_type = "general"
    emergency_exit_btn.grid(row=top_right_area_row, column=0, padx=x_pad, pady=y_pad, sticky='NEW')
    as_tooltips.add(emergency_exit_btn, "Exit ALT-Scann8 without saving.")

    exit_btn = Button(top_right_area_frame, text="Exit", height=2, command=cmd_app_standard_exit, activebackground='#f0f0f0',
                      font=("Arial", FontSize), name='exit_btn')
    exit_btn.widget_type = "general"
    exit_btn.grid(row=top_right_area_row, column=0, padx=x_pad, pady=y_pad, sticky='SEW')
    as_tooltips.add(exit_btn, "Exit ALT-Scann8.")

    # Start scan button
    if SimulatedRun:
        start_btn = Button(top_right_area_frame, text="START Scan", height=4, command=cmd_start_scan_simulated,
                           activebackground='#f0f0f0', font=("Arial", FontSize), name='start_btn')
    else:
        start_btn = Button(top_right_area_frame, text="START Scan", height=4, command=start_scan,
                           activebackground='#f0f0f0', font=("Arial", FontSize), name='start_btn')
    start_btn.widget_type = "general"
    start_btn.grid(row=top_right_area_row, column=1, padx=x_pad, pady=y_pad, sticky='EW')
    as_tooltips.add(start_btn, "Start scanning process.")
    top_right_area_row += 1

    # Create frame to select target folder
    folder_frame = LabelFrame(top_right_area_frame, text='Target Folder', height=4, font=("Arial", FontSize - 2),
                              name='folder_frame')
    folder_frame.grid(row=top_right_area_row, column=0, columnspan=2, padx=x_pad, pady=y_pad, sticky='EW')
    # Bind the frame's resize event to the function that updates the wraplength
    folder_frame.bind("<Configure>", update_target_dir_wraplength)

    folder_frame_target_dir = Label(folder_frame, text=CurrentDir, wraplength=150, height=2,
                                    font=("Arial", FontSize - 2), name='folder_frame_target_dir')
    folder_frame_target_dir.pack(side=TOP)

    folder_frame_buttons = Frame(folder_frame, bd=2)
    folder_frame_buttons.pack()
    new_folder_btn = Button(folder_frame_buttons, text='New', command=cmd_set_new_folder,
                            activebackground='#f0f0f0', font=("Arial", FontSize - 2), name='new_folder_btn')
    new_folder_btn.widget_type = "general"
    new_folder_btn.pack(side=LEFT)
    as_tooltips.add(new_folder_btn, "Create new folder to store frames generated during the scan.")
    existing_folder_btn = Button(folder_frame_buttons, text='Existing', command=cmd_set_existing_folder,
                                 activebackground='#f0f0f0', font=("Arial", FontSize - 2), name='existing_folder_btn')
    existing_folder_btn.widget_type = "general"
    existing_folder_btn.pack(side=LEFT)
    as_tooltips.add(existing_folder_btn, "Select existing folder to store frames generated during the scan.")
    top_right_area_row += 1

    # Create frame to display number of scanned images, and frames per minute
    scanned_images_frame = LabelFrame(top_right_area_frame, text='Done', height=4,
                                      font=("Arial", FontSize - 2), name='scanned_images_frame')
    scanned_images_frame.grid(row=top_right_area_row, column=0, padx=x_pad, pady=y_pad, sticky='NSEW')
    scanned_Images_label = Label(scanned_images_frame, text="Frames:", font=("Arial", FontSize-2),
                                 name='scanned_Images_label')
    scanned_Images_label.grid(row=0, column=0, sticky="W")

    Scanned_Images_number = tk.IntVar(value=CurrentFrame)
    scanned_images_number_label = Label(scanned_images_frame, textvariable=Scanned_Images_number, width=5,
                                        font=("Arial", FontSize-2), name='scanned_images_number_label')
    scanned_images_number_label.grid(row=0, column=1, sticky="E")
    as_tooltips.add(scanned_images_number_label, "Number of film frames scanned so far.")

    scanned_images_fps_label = Label(scanned_images_frame, text="Frames/Sec:", font=("Arial", FontSize-2),
                                 name='scanned_images_fps_label')
    scanned_images_fps_label.grid(row=1, column=0, sticky="W")

    scanned_Images_fps_value = tk.StringVar(value="")
    scanned_images_fps_value_label = Label(scanned_images_frame, textvariable=scanned_Images_fps_value, width=5,
                                     font=("Arial", FontSize - 2), name='scanned_images_fps_value_label')
    scanned_images_fps_value_label.grid(row=1, column=1, sticky="E")
    as_tooltips.add(scanned_images_fps_value_label, "Scan speed in frames per minute.")

    scanned_images_time_label = Label(scanned_images_frame, text="Film time:", font=("Arial", FontSize-2),
                                 name='scanned_images_time_label')
    scanned_images_time_label.grid(row=2, column=0, sticky="W")

    scanned_Images_time_value = tk.StringVar(value="")
    scanned_Images_time_value_label = Label(scanned_images_frame, textvariable=scanned_Images_time_value, width=5,
                                      font=("Arial", FontSize - 2), name='scanned_Images_time_value_label')
    scanned_Images_time_value_label.grid(row=2, column=1, sticky="E")
    as_tooltips.add(scanned_Images_time_value_label, "Film time in min:sec")

    # Create frame to display number of frames to go, and estimated time to finish
    frames_to_go_frame = LabelFrame(top_right_area_frame, text='Pending', height=4,
                                    font=("Arial", FontSize - 2), name='frames_to_go_frame')
    frames_to_go_frame.grid(row=top_right_area_row, rowspan = 2, column=1, padx=x_pad, pady=y_pad, sticky='NSEW')

    top_right_area_row += 1

    frames_to_go_area_row = 0

    frames_to_go_label = Label(frames_to_go_frame, text="Frames:", font=("Arial", FontSize-2),
                                 name='frames_to_go_label')
    frames_to_go_label.grid(row=frames_to_go_area_row, column=0, sticky="W")

    frames_to_go_str = tk.StringVar(value='' if FramesToGo <= 0 else str(FramesToGo))
    frames_to_go_entry = tk.Entry(frames_to_go_frame, textvariable=frames_to_go_str, width=5,
                                  font=("Arial", FontSize-2), justify="right", name='frames_to_go_entry')
    # Bind the KeyRelease event to the entry widget
    frames_to_go_entry.bind("<KeyPress>", frames_to_go_key_press)
    frames_to_go_entry.grid(row=frames_to_go_area_row, column=1, sticky="E")
    as_tooltips.add(frames_to_go_entry, "Enter estimated number of frames to scan in order to get an estimation of "
                                        "remaining time to finish.")

    frames_to_go_area_row += 1

    time_to_go_label = Label(frames_to_go_frame, text="Time:", font=("Arial", FontSize-2),
                                 name='time_to_go_label')
    time_to_go_label.grid(row=frames_to_go_area_row, column=0, sticky="W")

    frames_to_go_time_str = tk.StringVar(value='')
    frames_to_go_time = Label(frames_to_go_frame, textvariable=frames_to_go_time_str,  width=8,
                              font=("Arial", FontSize - 2), name='frames_to_go_time')
    frames_to_go_time.grid(row=frames_to_go_area_row, column=1, sticky="E")

    frames_to_go_area_row += 1

    # Automatic stop at the end of the scan
    auto_stop_enabled = tk.BooleanVar(value=AutoStopEnabled)
    auto_stop_enabled_checkbox = tk.Checkbutton(frames_to_go_frame, text='Auto-stop if', height=1,
                                                variable=auto_stop_enabled, onvalue=True, offvalue=False,
                                                font=("Arial", FontSize - 2), command=cmd_set_auto_stop_enabled,
                                                name='auto_stop_enabled_checkbox')
    auto_stop_enabled_checkbox.grid(row=frames_to_go_area_row, column=0, columnspan = 2, sticky="W")
    as_tooltips.add(auto_stop_enabled_checkbox, "Stop scanning when end of film detected")

    frames_to_go_area_row += 1

    # Radio buttons to select auto-stop method
    autostop_type = tk.StringVar()
    autostop_type.set('No_film')
    autostop_no_film_rb = tk.Radiobutton(frames_to_go_frame, text="No film", variable=autostop_type,
                                         value='No_film', font=("Arial", FontSize - 2), command=cmd_set_auto_stop_enabled,
                                         name='autostop_no_film_rb', state='disabled')
    autostop_no_film_rb.grid(row=frames_to_go_area_row, column=0, columnspan = 2, sticky="W") # , padx=(10, 0))
    as_tooltips.add(autostop_no_film_rb, "Stop when film is not detected by PT")
    
    frames_to_go_area_row += 1

    autostop_counter_zero_rb = tk.Radiobutton(frames_to_go_frame, text="Count zero", variable=autostop_type,
                                              value='counter_to_zero', font=("Arial", FontSize - 2),
                                              command=cmd_set_auto_stop_enabled, name='autostop_counter_zero_rb',
                                              state='disabled')
    autostop_counter_zero_rb.grid(row=frames_to_go_area_row, column=0, columnspan = 2, sticky="W") # , padx=(10, 0))
    as_tooltips.add(autostop_counter_zero_rb, "Stop scan when frames-to-go counter reaches zero")

    # Create frame to select S8/R8 film
    film_type_frame = LabelFrame(top_right_area_frame, text='Film type', height=1, font=("Arial", FontSize - 2),
                                 name='film_type_frame')
    film_type_frame.grid(row=top_right_area_row, column=0, padx=x_pad, pady=y_pad, sticky='NSEW')

    # Radio buttons to select R8/S8. Required to select adequate pattern, and match position
    film_type = tk.StringVar(value=FilmType)
    film_type_S8_rb = tk.Radiobutton(film_type_frame, text="S8", variable=film_type, command=cmd_set_s8,
                                     value='S8', font=("Arial", FontSize), indicatoron=0, width=5, height=1,
                                     compound='left', relief="raised", borderwidth=3, name='film_type_S8_rb')
    film_type_S8_rb.widget_type = "general"
    if ColorCodedButtons:
        film_type_S8_rb.config(selectcolor="orange")
    film_type_S8_rb.pack(side=LEFT, padx=2, pady=2, expand=True, fill="both")
    as_tooltips.add(film_type_S8_rb, "Handle as Super 8 film")
    film_type_R8_rb = tk.Radiobutton(film_type_frame, text="R8", variable=film_type, command=cmd_set_r8,
                                     value='R8', font=("Arial", FontSize), indicatoron=0, width=5, height=1,
                                     compound='left', relief="raised", borderwidth=3, name='film_type_R8_rb')
    film_type_R8_rb.widget_type = "general"
    if ColorCodedButtons:
        film_type_R8_rb.config(selectcolor="powder blue")
    film_type_R8_rb.pack(side=RIGHT, padx=2, pady=2, expand=True, fill="both")
    as_tooltips.add(film_type_R8_rb, "Handle as 8mm (Regular 8) film")

    top_right_area_row += 1

    # Create frame to display capture resolution & file type
    capture_info_frame = LabelFrame(top_right_area_frame, text='Capture info', height=1, font=("Arial", FontSize - 2),
                                 name='capture_info_frame')
    capture_info_frame.grid(row=top_right_area_row, column=0, columnspan = 2, padx=x_pad, pady=y_pad, sticky='NSEW')
    capture_info_str = tk.StringVar(value='')
    capture_info_label = Label(capture_info_frame, textvariable=capture_info_str,
                              font=("Arial", FontSize), name='capture_info_label')
    capture_info_label.pack(anchor='center')

    top_right_area_row += 1

    # Integrated plotter
    if PlotterEnabled:
        integrated_plotter_frame = LabelFrame(top_right_area_frame, text='Plotter Area', font=("Arial", FontSize - 1),
                                              name='integrated_plotter_frame')
        integrated_plotter_frame.grid(row=top_right_area_row, column=0, columnspan=2, padx=x_pad, pady=y_pad,
                                      ipadx=2, ipady=2, sticky='NSEW')
        plotter_canvas = Canvas(integrated_plotter_frame, bg='white', width=plotter_width, height=plotter_height,
                                name='plotter_canvas')
        plotter_canvas.pack(side=TOP, anchor=N)
        as_tooltips.add(plotter_canvas, "Plotter canvas, click to disable/enable/scroll.")
        # Bind the mouse click event to the canvas widget
        plotter_canvas.bind("<Button-1>", cmd_plotter_canvas_click)
    top_right_area_row += 1


    # Create extended frame for expert and experimental areas
    if ExpertMode or ExperimentalMode:
        extended_frame = Frame(main_container, name='extended_frame')
        extended_frame.pack(side=LEFT, padx=10, expand=True, fill="y", anchor="center")
    if ExpertMode:
        expert_frame = LabelFrame(extended_frame, text='Expert Area', width=8, font=("Arial", FontSize - 1),
                                  name='expert_frame')
        expert_frame.pack(side=LEFT, padx=x_pad, pady=y_pad, expand=True, fill='y')
        # expert_frame.place(relx=0.25, rely=0.5, anchor="center")
        expert_frame.rowconfigure(0, weight=0)
        expert_frame.rowconfigure(1, weight=20)
        expert_frame.rowconfigure(2, weight=0)
        # *********************************
        # Exposure / white balance
        exp_wb_frame = LabelFrame(expert_frame, text='Auto Exposure / White Balance ', font=("Arial", FontSize - 1),
                                  name='exp_wb_frame')
        exp_wb_frame.grid(row=0, rowspan=3, column=0, padx=x_pad, pady=y_pad, sticky='NSEW')
        exp_wb_row = 0

        # Match wait (exposure & AWB) margin allowance (0%, wait for same value, 100%, any value will do)
        # Default value, to be overriden by configuration
        auto_exp_wb_change_pause = tk.BooleanVar(value=ExposureWbAdaptPause)
        auto_exp_wb_wait_btn = tk.Checkbutton(exp_wb_frame, variable=auto_exp_wb_change_pause,
                                              onvalue=True, offvalue=False, font=("Arial", FontSize - 1),
                                              text='Match margin (%):', command=cmd_auto_exp_wb_change_pause_selection,
                                              name='auto_exp_wb_wait_btn')
        auto_exp_wb_wait_btn.widget_type = "control"
        auto_exp_wb_wait_btn.grid(row=exp_wb_row, column=0, columnspan=2, sticky=W)
        as_tooltips.add(auto_exp_wb_wait_btn, "When automatic exposure/WB enabled, select this checkbox to wait for "
                                              "them to stabilize before capturing frame.")

        match_wait_margin_value = tk.IntVar(value=MatchWaitMarginValue)  # Default value, overriden by configuration
        match_wait_margin_spinbox = DynamicSpinbox(exp_wb_frame, command=cmd_match_wait_margin_selection, width=4,
                                                   readonlybackground='pale green', from_=5, to=100, increment=5,
                                                   textvariable=match_wait_margin_value, font=("Arial", FontSize - 1),
                                                   name='match_wait_margin_spinbox')
        match_wait_margin_spinbox.widget_type = "control"
        match_wait_margin_spinbox.grid(row=exp_wb_row, column=2, padx=x_pad, pady=y_pad, sticky=W)
        cmd_match_wait_margin_validation_cmd = match_wait_margin_spinbox.register(match_wait_margin_validation)
        match_wait_margin_spinbox.configure(validate="key", validatecommand=(cmd_match_wait_margin_validation_cmd, '%P'))
        as_tooltips.add(match_wait_margin_spinbox, "When automatic exposure/WB enabled, and match wait delay is "
                                                   "selected, the tolerance for the match (5%, lowest tolerance, "
                                                   "almost exact match required, 100% any value will match)")
        match_wait_margin_spinbox.bind("<FocusOut>", lambda event: cmd_match_wait_margin_selection())
        exp_wb_row += 1

        # Automatic exposure
        AE_enabled = tk.BooleanVar(value=AutoExpEnabled)
        auto_exposure_btn = tk.Checkbutton(exp_wb_frame, variable=AE_enabled, onvalue=True, offvalue=False,
                                           font=("Arial", FontSize - 1), command=cmd_set_auto_exposure,
                                           indicatoron=False, text="Exposure:", relief="raised",
                                           name='auto_exposure_btn')
        auto_exposure_btn.widget_type = "control"
        if ColorCodedButtons:
            auto_exposure_btn.config(selectcolor="pale green")
        auto_exposure_btn.grid(row=exp_wb_row, column=0, columnspan=2, sticky="EW")
        as_tooltips.add(auto_exposure_btn, "Toggle automatic exposure status (on/off).")

        exposure_spinbox_frame = Frame(exp_wb_frame, name='exposure_spinbox_frame')
        exposure_spinbox_frame.grid(row=exp_wb_row, column=2, padx=x_pad, pady=y_pad, sticky=W)
        exposure_value = tk.DoubleVar(value=0)  # Auto exposure by default, overriden by configuration if any
        exposure_spinbox = DynamicSpinbox(exposure_spinbox_frame, command=cmd_exposure_selection, width=7,
                                          textvariable=exposure_value, from_=0.001, to=10000, increment=1,
                                          font=("Arial", FontSize - 1), name='exposure_spinbox')
        exposure_spinbox.widget_type = "control"
        exposure_spinbox.pack(side=LEFT)
        cmd_exposure_validation_cmd = exposure_spinbox.register(exposure_validation)
        exposure_spinbox.configure(validate="key", validatecommand=(cmd_exposure_validation_cmd, '%P'))
        as_tooltips.add(exposure_spinbox, "When automatic exposure disabled, exposure time for the sensor to use, "
                                          "measured in milliseconds.")
        exposure_spinbox.bind("<FocusOut>", lambda event: cmd_exposure_selection())
        exposure_spinbox_label =  Label(exposure_spinbox_frame, text='ms', font=("Arial", FontSize - 1),
                                       name='exposure_spinbox_label')
        exposure_spinbox_label.pack(side=LEFT)

        exp_wb_row += 1

        # Miscelaneous exposure controls from PiCamera2 - AeConstraintMode
        AeConstraintMode_dropdown_selected = tk.StringVar()
        AeConstraintMode_dropdown_selected.set("Normal")  # Set the initial value
        ae_constraint_mode_label = Label(exp_wb_frame, text='AE Const. mode:', font=("Arial", FontSize - 1),
                                       name='ae_constraint_mode_label')
        ae_constraint_mode_label.widget_type = "control"
        ae_constraint_mode_label.grid(row=exp_wb_row, column=0, columnspan=2, padx=x_pad, pady=y_pad, sticky=E)
        AeConstraintMode_dropdown = OptionMenu(exp_wb_frame, AeConstraintMode_dropdown_selected,
                                               *AeConstraintMode_dict.keys(), command=cmd_set_AeConstraintMode)
        AeConstraintMode_dropdown.widget_type = "control"
        AeConstraintMode_dropdown.config(takefocus=1, font=("Arial", FontSize - 1))
        AeConstraintMode_dropdown.grid(row=exp_wb_row, column=2, padx=x_pad, pady=y_pad, sticky=W)
        as_tooltips.add(AeConstraintMode_dropdown, "Sets the constraint mode of the AEC/AGC algorithm.")
        exp_wb_row += 1

        # Miscelaneous exposure controls from PiCamera2 - AeMeteringMode
        # camera.set_controls({"AeMeteringMode": controls.AeMeteringModeEnum.CentreWeighted})
        AeMeteringMode_dropdown_selected = tk.StringVar()
        AeMeteringMode_dropdown_selected.set("CentreWgt")  # Set the initial value
        ae_metering_mode_label = Label(exp_wb_frame, text='AE Meter mode:', font=("Arial", FontSize - 1),
                                     name='ae_metering_mode_label')
        ae_metering_mode_label.widget_type = "control"
        ae_metering_mode_label.grid(row=exp_wb_row, column=0, columnspan=2, padx=x_pad, pady=y_pad, sticky=E)
        AeMeteringMode_dropdown = OptionMenu(exp_wb_frame, AeMeteringMode_dropdown_selected,
                                             *AeMeteringMode_dict.keys(), command=cmd_set_AeMeteringMode)
        AeMeteringMode_dropdown.widget_type = "control"
        AeMeteringMode_dropdown.config(takefocus=1, font=("Arial", FontSize - 1))
        AeMeteringMode_dropdown.grid(row=exp_wb_row, column=2, padx=x_pad, pady=y_pad, sticky=W)
        as_tooltips.add(AeMeteringMode_dropdown, "Sets the metering mode of the AEC/AGC algorithm.")
        exp_wb_row += 1

        # Miscelaneous exposure controls from PiCamera2 - AeExposureMode
        # camera.set_controls({"AeExposureMode": controls.AeExposureModeEnum.Normal})  # Normal, Long, Short, Custom
        AeExposureMode_dropdown_selected = tk.StringVar()
        AeExposureMode_dropdown_selected.set("Normal")  # Set the initial value
        ae_exposure_mode_label = Label(exp_wb_frame, text='AE Exposure mode:', font=("Arial", FontSize - 1),
                                     name='ae_exposure_mode_label')
        ae_exposure_mode_label.widget_type = "control"
        ae_exposure_mode_label.grid(row=exp_wb_row, column=0, columnspan=2, padx=x_pad, pady=y_pad, sticky=E)
        AeExposureMode_dropdown = OptionMenu(exp_wb_frame, AeExposureMode_dropdown_selected,
                                             *AeExposureMode_dict.keys(), command=cmd_set_AeExposureMode)
        AeExposureMode_dropdown.widget_type = "control"
        AeExposureMode_dropdown.config(takefocus=1, font=("Arial", FontSize - 1))
        AeExposureMode_dropdown.grid(row=exp_wb_row, column=2, padx=x_pad, pady=y_pad, sticky=W)
        as_tooltips.add(AeExposureMode_dropdown, "Sets the exposure mode of the AEC/AGC algorithm.")
        exp_wb_row += 1

        # Automatic White Balance red
        AWB_enabled = tk.BooleanVar(value=AutoWbEnabled)
        auto_wb_red_btn = tk.Checkbutton(exp_wb_frame, variable=AWB_enabled, onvalue=True, offvalue=False,
                                         font=("Arial", FontSize - 1), command=cmd_set_auto_wb, text="WB Red:",
                                         relief="raised", indicatoron=False, name='auto_wb_red_btn')
        auto_wb_red_btn.widget_type = "control"
        if ColorCodedButtons:
            auto_wb_red_btn.config(selectcolor="pale green")
        auto_wb_red_btn.grid(row=exp_wb_row, column=0, columnspan=2, sticky="WE")
        as_tooltips.add(auto_wb_red_btn, "Toggle automatic white balance for both WB channels (on/off).")

        wb_red_value = tk.DoubleVar(value=2.2)  # Default value, overriden by configuration
        wb_red_spinbox = DynamicSpinbox(exp_wb_frame, command=cmd_wb_red_selection, width=4,
                                        textvariable=wb_red_value, from_=0, to=32, increment=0.1,
                                        font=("Arial", FontSize - 1), name='wb_red_spinbox')
        wb_red_spinbox.widget_type = "control"
        wb_red_spinbox.grid(row=exp_wb_row, column=2, padx=x_pad, pady=y_pad, sticky=W)
        cmd_wb_red_validation_cmd = wb_red_spinbox.register(wb_red_validation)
        wb_red_spinbox.configure(validate="key", validatecommand=(cmd_wb_red_validation_cmd, '%P'))
        as_tooltips.add(wb_red_spinbox, "When automatic white balance disabled, sets the red gain (the gain applied "
                                        "to red pixels by the AWB algorithm), between 0.0 to 32.0.")
        wb_red_spinbox.bind("<FocusOut>", lambda event: cmd_wb_red_selection())

        exp_wb_row += 1

        # Automatic White Balance blue
        auto_wb_blue_btn = tk.Checkbutton(exp_wb_frame, variable=AWB_enabled, onvalue=True, offvalue=False,
                                          font=("Arial", FontSize - 1), command=cmd_set_auto_wb, text="WB Blue:",
                                          relief="raised", indicatoron=False, name='auto_wb_blue_btn')
        auto_wb_blue_btn.widget_type = "control"
        if ColorCodedButtons:
            auto_wb_blue_btn.config(selectcolor="pale green")
        auto_wb_blue_btn.grid(row=exp_wb_row, column=0, columnspan=2, sticky="WE")
        as_tooltips.add(auto_wb_blue_btn, "Toggle automatic white balance for both WB channels (on/off).")

        wb_blue_value = tk.DoubleVar(value=2.2)  # Default value, overriden by configuration
        wb_blue_spinbox = DynamicSpinbox(exp_wb_frame, command=cmd_wb_blue_selection, width=4,
                                         textvariable=wb_blue_value, from_=0, to=32, increment=0.1,
                                         font=("Arial", FontSize - 1), name='wb_blue_spinbox')
        wb_blue_spinbox.widget_type = "control"
        wb_blue_spinbox.grid(row=exp_wb_row, column=2, padx=x_pad, pady=y_pad, sticky=W)
        cmd_wb_blue_validation_cmd = wb_blue_spinbox.register(wb_blue_validation)
        wb_blue_spinbox.configure(validate="key", validatecommand=(cmd_wb_blue_validation_cmd, '%P'))
        as_tooltips.add(wb_blue_spinbox, "When automatic white balance disabled, sets the blue gain (the gain applied "
                                         "to blue pixels by the AWB algorithm), between 0.0 to 32.0.")
        wb_blue_spinbox.bind("<FocusOut>", lambda event: cmd_wb_blue_selection())

        exp_wb_row += 1

        # Miscelaneous exposure controls from PiCamera2 - AwbMode
        # camera.set_controls({"AwbMode": controls.AwbModeEnum.Normal})  # Normal, Long, Short, Custom
        AwbMode_dropdown_selected = tk.StringVar()
        AwbMode_dropdown_selected.set("Normal")  # Set the initial value
        awb_mode_label = Label(exp_wb_frame, text='AWB mode:', font=("Arial", FontSize - 1), name='awb_mode_label')
        awb_mode_label.widget_type = "control"
        awb_mode_label.grid(row=exp_wb_row, column=0, columnspan=2, padx=x_pad, pady=y_pad, sticky=E)
        AwbMode_dropdown = OptionMenu(exp_wb_frame, AwbMode_dropdown_selected, *AwbMode_dict.keys(),
                                      command=cmd_set_AwbMode)
        AwbMode_dropdown.widget_type = "control"
        AwbMode_dropdown.config(takefocus=1, font=("Arial", FontSize - 1))
        AwbMode_dropdown.grid(row=exp_wb_row, column=2, padx=x_pad, pady=y_pad, sticky=W)
        as_tooltips.add(AwbMode_dropdown, "Sets the AWB mode of the AEC/AGC algorithm.")
        exp_wb_row += 1

        # *****************************************
        # Frame to add brightness/contrast controls
        brightness_frame = LabelFrame(expert_frame, text="Brightness/Contrast", font=("Arial", FontSize - 1),
                                      name='brightness_frame')
        brightness_frame.grid(row=0, rowspan=2, column=1, padx=x_pad, pady=y_pad, sticky='NSEW')
        brightness_row = 0

        # brightness
        brightness_label = tk.Label(brightness_frame, text='Brightness:', font=("Arial", FontSize - 1),
                                    name='brightness_label')
        brightness_label.widget_type = "control"
        brightness_label.grid(row=brightness_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        brightness_value = tk.DoubleVar(value=0.0)  # Default value, overriden by configuration
        brightness_spinbox = DynamicSpinbox(brightness_frame, command=cmd_brightness_selection, width=4,
                                            textvariable=brightness_value, from_=-1.0, to=1.0, increment=0.1,
                                            font=("Arial", FontSize - 1), name='brightness_spinbox')
        brightness_spinbox.widget_type = "control"
        brightness_spinbox.grid(row=brightness_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        cmd_brightness_validation_cmd = brightness_spinbox.register(brightness_validation)
        brightness_spinbox.configure(validate="key", validatecommand=(cmd_brightness_validation_cmd, '%P'))
        as_tooltips.add(brightness_spinbox, 'Adjusts the image brightness between -1.0 and 1.0, where -1.0 is very '
                                            'dark, 1.0 is very bright, and 0.0 is the default "normal" brightness.')
        brightness_spinbox.bind("<FocusOut>", lambda event: cmd_brightness_selection())
        brightness_row += 1

        # contrast
        contrast_label = tk.Label(brightness_frame, text='Contrast:', font=("Arial", FontSize - 1),
                                  name='contrast_label')
        contrast_label.widget_type = "control"
        contrast_label.grid(row=brightness_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        contrast_value = tk.DoubleVar(value=1)  # Default value, overriden by configuration
        contrast_spinbox = DynamicSpinbox(brightness_frame, command=cmd_contrast_selection, width=4,
                                          textvariable=contrast_value, from_=0, to=32, increment=0.1,
                                          font=("Arial", FontSize - 1), name='contrast_spinbox')
        contrast_spinbox.widget_type = "control"
        contrast_spinbox.grid(row=brightness_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        cmd_contrast_validation_cmd = contrast_spinbox.register(contrast_validation)
        contrast_spinbox.configure(validate="key", validatecommand=(cmd_contrast_validation_cmd, '%P'))
        as_tooltips.add(contrast_spinbox, 'Sets the contrast of the image between 0.0 and 32.0, where zero means "no '
                                          'contrast", 1.0 is the default "normal" contrast, and larger values '
                                          'increase the contrast proportionately.')
        contrast_spinbox.bind("<FocusOut>", lambda event: cmd_contrast_selection())
        brightness_row += 1

        # saturation
        saturation_label = tk.Label(brightness_frame, text='Saturation:', font=("Arial", FontSize - 1),
                                    name='saturation_label')
        saturation_label.widget_type = "control"
        saturation_label.grid(row=brightness_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        saturation_value = tk.DoubleVar(value=1)  # Default value, overriden by configuration
        saturation_spinbox = DynamicSpinbox(brightness_frame, command=cmd_saturation_selection, width=4,
                                            textvariable=saturation_value, from_=0, to=32, increment=0.1,
                                            font=("Arial", FontSize - 1), name='saturation_spinbox')
        saturation_spinbox.widget_type = "control"
        saturation_spinbox.grid(row=brightness_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        cmd_saturation_validation_cmd = saturation_spinbox.register(saturation_validation)
        saturation_spinbox.configure(validate="key", validatecommand=(cmd_saturation_validation_cmd, '%P'))
        as_tooltips.add(saturation_spinbox, 'Amount of colour saturation between 0.0 and 32.0, where zero produces '
                                            'greyscale images, 1.0 represents default "normal" saturation, '
                                            'and higher values produce more saturated colours.')
        saturation_spinbox.bind("<FocusOut>", lambda event: cmd_saturation_selection())
        brightness_row += 1

        # analogue_gain
        analogue_gain_label = tk.Label(brightness_frame, text='Analog. gain:', font=("Arial", FontSize - 1),
                                       name='analogue_gain_label')
        analogue_gain_label.widget_type = "control"
        analogue_gain_label.grid(row=brightness_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        analogue_gain_value = tk.DoubleVar(value=1)  # Default value, overriden by configuration
        analogue_gain_spinbox = DynamicSpinbox(brightness_frame, command=cmd_analogue_gain_selection, width=4,
                                               textvariable=analogue_gain_value, from_=0, to=32, increment=0.1,
                                               font=("Arial", FontSize - 1), name='analogue_gain_spinbox')
        analogue_gain_spinbox.widget_type = "control"
        analogue_gain_spinbox.grid(row=brightness_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        cmd_analogue_gain_validation_cmd = analogue_gain_spinbox.register(analogue_gain_validation)
        analogue_gain_spinbox.configure(validate="key", validatecommand=(cmd_analogue_gain_validation_cmd, '%P'))
        as_tooltips.add(analogue_gain_spinbox, "Analogue gain applied by the sensor.")
        analogue_gain_spinbox.bind("<FocusOut>", lambda event: cmd_analogue_gain_selection())
        brightness_row += 1

        # Sharpness, control to allow playing with the values and see the results
        sharpness_label = tk.Label(brightness_frame, text='Sharpness:', font=("Arial", FontSize - 1),
                                   name='sharpness_label')
        sharpness_label.widget_type = "control"
        sharpness_label.grid(row=brightness_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        sharpness_value = tk.DoubleVar(value=1)  # Default value, overridden by configuration if any
        sharpness_spinbox = DynamicSpinbox(brightness_frame, command=cmd_sharpness_selection, width=4,
                                           textvariable=sharpness_value, from_=0.0, to=16.0, increment=1,
                                           font=("Arial", FontSize - 1), name='sharpness_spinbox')
        sharpness_spinbox.widget_type = "control"
        sharpness_spinbox.grid(row=brightness_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        cmd_sharpness_validation_cmd = sharpness_spinbox.register(sharpness_validation)
        sharpness_spinbox.configure(validate="key", validatecommand=(cmd_sharpness_validation_cmd, '%P'))
        as_tooltips.add(sharpness_spinbox, 'Sets the image sharpness between 0.0 adn 16.0, where zero implies no '
                                           'additional sharpening is performed, 1.0 is the default "normal" level of '
                                           'sharpening, and larger values apply proportionately stronger sharpening.')
        sharpness_spinbox.bind("<FocusOut>", lambda event: cmd_sharpness_selection())
        brightness_row += 1

        # Exposure Compensation ('ExposureValue' in PiCamera2 controls
        exposure_compensation_label = tk.Label(brightness_frame, text='Exp. Comp.:', font=("Arial", FontSize - 1),
                                               name='exposure_compensation_label')
        exposure_compensation_label.widget_type = "control"
        exposure_compensation_label.grid(row=brightness_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        exposure_compensation_value = tk.DoubleVar(value=0)  # Default value, overridden by configuration if any
        exposure_compensation_spinbox = DynamicSpinbox(brightness_frame, command=cmd_exposure_compensation_selection,
                                                       width=4, textvariable=exposure_compensation_value, from_=-8.0,
                                                       to=8.0, increment=0.1, font=("Arial", FontSize - 1),
                                                       name='exposure_compensation_spinbox')
        exposure_compensation_spinbox.widget_type = "control"
        exposure_compensation_spinbox.grid(row=brightness_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        cmd_exposure_compensation_validation_cmd = exposure_compensation_spinbox.register(exposure_compensation_validation)
        exposure_compensation_spinbox.configure(validate="key",
                                                validatecommand=(cmd_exposure_compensation_validation_cmd, '%P'))
        as_tooltips.add(exposure_compensation_spinbox, 'Exposure compensation value in "stops" (-8.0 to 8.0), which '
                                                       'adjusts the target of the AEC/AGC algorithm. Positive values '
                                                       'increase the target brightness, and negative values decrease '
                                                       'it. Zero represents the base or "normal" exposure level.')
        exposure_compensation_spinbox.bind("<FocusOut>", lambda event: cmd_exposure_compensation_selection())

        # QR Code - Create Canvas to display QR code or text info (if QR Code library not available)
        if LoggingMode == 'DEBUG':
            qr_code_frame = LabelFrame(expert_frame, text="Debug Info", font=("Arial", FontSize - 1),
                                            name='qr_code_frame')
            qr_code_frame.grid(row=1, rowspan=2, column=2, padx=x_pad, pady=y_pad, sticky='NSEW')
            qr_code_canvas = Canvas(qr_code_frame, bg='white', name='qr_code_canvas', width=1, height=1)
            qr_code_canvas.pack(side=TOP, expand=True, fill='both')
            qr_code_canvas.bind("<Button-1>", display_qr_code_info)
            as_tooltips.add(qr_code_canvas, "Click to display debug information.")
        else:
            qr_code_canvas = None
            qr_code_frame = None

        # *********************************
        # Frame to add frame align controls
        frame_alignment_frame = LabelFrame(expert_frame, text="Frame align", font=("Arial", FontSize - 1),
                                           name='frame_alignment_frame')
        frame_alignment_frame.grid(row=0, column=2, padx=x_pad, pady=y_pad, sticky='EW')
        frame_align_row = 0

        # Spinbox to select MinFrameSteps on Arduino
        auto_framesteps_enabled = tk.BooleanVar(value=AutoFrameStepsEnabled)
        steps_per_frame_btn = tk.Checkbutton(frame_alignment_frame, variable=auto_framesteps_enabled, onvalue=True,
                                             offvalue=False, font=("Arial", FontSize - 1), command=cmd_steps_per_frame_auto,
                                             text="Steps/Frame AUTO:", relief="raised", indicatoron=False, width=18,
                                             name='steps_per_frame_btn')
        steps_per_frame_btn.widget_type = "control"
        if ColorCodedButtons:
            steps_per_frame_btn.config(selectcolor="pale green")
        steps_per_frame_btn.grid(row=frame_align_row, column=0, columnspan=2, sticky="EW")
        as_tooltips.add(steps_per_frame_btn, "Toggle automatic steps/frame calculation.")

        steps_per_frame_value = tk.IntVar(value=StepsPerFrame)  # Default to be overridden by configuration
        steps_per_frame_spinbox = DynamicSpinbox(frame_alignment_frame, command=cmd_steps_per_frame_selection, width=4,
                                                 textvariable=steps_per_frame_value, from_=100, to=600,
                                                 font=("Arial", FontSize - 1), name='steps_per_frame_spinbox')
        steps_per_frame_spinbox.widget_type = "control"
        steps_per_frame_spinbox.grid(row=frame_align_row, column=2, padx=x_pad, pady=y_pad, sticky=W)
        cmd_steps_per_frame_validation_cmd = steps_per_frame_spinbox.register(steps_per_frame_validation)
        steps_per_frame_spinbox.configure(validate="key", validatecommand=(cmd_steps_per_frame_validation_cmd, '%P'))
        as_tooltips.add(steps_per_frame_spinbox, "If automatic steps/frame is disabled, enter the number of motor "
                                                 "steps required to advance one frame (100 to 600, depends on capstan"
                                                 " diameter).")
        steps_per_frame_spinbox.bind("<FocusOut>", lambda event: cmd_steps_per_frame_selection())

        frame_align_row += 1

        # Spinbox to select PTLevel on Arduino
        auto_pt_level_enabled = tk.BooleanVar(value=AutoPtLevelEnabled)
        pt_level_btn = tk.Checkbutton(frame_alignment_frame, variable=auto_pt_level_enabled, onvalue=True,
                                      offvalue=False, font=("Arial", FontSize - 1), command=cmd_set_auto_pt_level,
                                      text="PT Level AUTO:", relief="raised", indicatoron=False, name='pt_level_btn')
        pt_level_btn.widget_type = "control"
        if ColorCodedButtons:
            pt_level_btn.config(selectcolor="pale green")
        pt_level_btn.grid(row=frame_align_row, column=0, columnspan=2, sticky="EW")
        as_tooltips.add(pt_level_btn, "Toggle automatic photo-transistor level calculation.")

        pt_level_value = tk.IntVar(value=PtLevelValue)  # To be overridden by config
        pt_level_spinbox = DynamicSpinbox(frame_alignment_frame, command=cmd_pt_level_selection, width=4,
                                          textvariable=pt_level_value, from_=20, to=900, font=("Arial", FontSize - 1),
                                          name='pt_level_spinbox')
        pt_level_spinbox.widget_type = "control"
        pt_level_spinbox.grid(row=frame_align_row, column=2, padx=x_pad, pady=y_pad, sticky=W)
        cmd_pt_level_validation_cmd = pt_level_spinbox.register(pt_level_validation)
        pt_level_spinbox.configure(validate="key", validatecommand=(cmd_pt_level_validation_cmd, '%P'))
        as_tooltips.add(pt_level_spinbox, "If automatic photo-transistor is disabled, enter the level to be reached "
                                          "to determine detection of sprocket hole (20 to 900, depends on PT used and"
                                          " size of hole).")
        pt_level_spinbox.bind("<FocusOut>", lambda event: cmd_pt_level_selection())

        frame_align_row += 1

        # Spinbox to select Frame Fine Tune on Arduino
        frame_fine_tune_label = tk.Label(frame_alignment_frame, text='Fine tune:', font=("Arial", FontSize - 1),
                                         name='frame_fine_tune_label')
        frame_fine_tune_label.widget_type = "control"
        frame_fine_tune_label.grid(row=frame_align_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        frame_fine_tune_value = tk.IntVar(value=FrameFineTuneValue)  # To be overridden by config
        frame_fine_tune_spinbox = DynamicSpinbox(frame_alignment_frame, command=cmd_frame_fine_tune_selection, width=4,
                                                 readonlybackground='pale green', textvariable=frame_fine_tune_value,
                                                 from_=5, to=95, increment=5, font=("Arial", FontSize - 1),
                                                 name='frame_fine_tune_spinbox')
        frame_fine_tune_spinbox.widget_type = "control"
        frame_fine_tune_spinbox.grid(row=frame_align_row, column=1, columnspan=2, padx=x_pad, pady=y_pad, sticky=W)
        cmd_fine_tune_validation_cmd = frame_fine_tune_spinbox.register(fine_tune_validation)
        frame_fine_tune_spinbox.configure(validate="key", validatecommand=(cmd_fine_tune_validation_cmd, '%P'))
        as_tooltips.add(frame_fine_tune_spinbox, "Fine tune frame detection: Shift frame detection threshold up of "
                                                 "down (5 to 95% of PT amplitude).")
        frame_fine_tune_spinbox.bind("<FocusOut>", lambda event: cmd_frame_fine_tune_selection())
        frame_align_row += 1

        # Spinbox to select Extra Steps on Arduino
        frame_extra_steps_label = tk.Label(frame_alignment_frame, text='Extra Steps:', font=("Arial", FontSize - 1),
                                           name='frame_extra_steps_label')
        frame_extra_steps_label.widget_type = "control"
        frame_extra_steps_label.grid(row=frame_align_row, column=0, padx=x_pad, pady=y_pad, sticky=E)

        frame_extra_steps_value = tk.IntVar(value=FrameExtraStepsValue)  # To be overridden by config
        frame_extra_steps_spinbox = DynamicSpinbox(frame_alignment_frame, command=cmd_frame_extra_steps_selection, width=4,
                                                   readonlybackground='pale green', from_=-30, to=30,
                                                   textvariable=frame_extra_steps_value, font=("Arial", FontSize - 1),
                                                   name='frame_extra_steps_spinbox')
        frame_extra_steps_spinbox.widget_type = "control"
        frame_extra_steps_spinbox.grid(row=frame_align_row, column=1, columnspan=2, padx=x_pad, pady=y_pad, sticky=W)
        cmd_extra_steps_validation_cmd = frame_extra_steps_spinbox.register(extra_steps_validation)
        frame_extra_steps_spinbox.configure(validate="key", validatecommand=(cmd_extra_steps_validation_cmd, '%P'))
        as_tooltips.add(frame_extra_steps_spinbox, "Unconditionally advances/detects the frame n steps after/before "
                                                   "detection (n between -30 and 30). Negative values can help if "
                                                   "film gate is not correctly positioned.")
        frame_extra_steps_spinbox.bind("<FocusOut>", lambda event: cmd_frame_extra_steps_selection())
        frame_align_row += 1

        # Scan error counter
        detect_misaligned_frames = tk.BooleanVar(value=DetectMisalignedFrames)
        detect_misaligned_frames_btn = tk.Checkbutton(frame_alignment_frame, variable=detect_misaligned_frames, onvalue=True, offvalue=False,
                                        font=("Arial", FontSize - 1), text="Detect misaligned frames", command=cmd_detect_misaligned_frames)
        detect_misaligned_frames_btn.grid(row=frame_align_row, column=0, padx=x_pad, pady=y_pad, sticky=E)
        as_tooltips.add(detect_misaligned_frames_btn, "Misaligned frame detection (might slow down scanning)")
        scan_error_counter_value = tk.StringVar(value="0 (0%)")
        scan_error_counter_value_label = tk.Label(frame_alignment_frame, textvariable=scan_error_counter_value, 
                                  font=("Arial", FontSize-1), justify="right", name='scan_error_counter_value_label')
        scan_error_counter_value_label.grid(row=frame_align_row, column=1, columnspan=2, padx=x_pad, pady=y_pad, sticky=W)
        as_tooltips.add(scan_error_counter_value_label, "Number of frames missed or misaligned during scanning.")
        frame_align_row += 1

        # ***************************************************
        # Frame to add stabilization controls (speed & delay)
        speed_quality_frame = LabelFrame(expert_frame, text="Frame stabilization", font=("Arial", FontSize - 1),
                                         name='speed_quality_frame')
        speed_quality_frame.grid(row=2, column=1, padx=x_pad, pady=y_pad, sticky='NSEW')

        # Spinbox to select Speed on Arduino (1-10)
        scan_speed_label = tk.Label(speed_quality_frame, text='Scan Speed:', font=("Arial", FontSize - 1),
                                    name='scan_speed_label')
        scan_speed_label.widget_type = "control"
        scan_speed_label.grid(row=0, column=0, padx=x_pad, pady=y_pad, sticky=E)
        scan_speed_value = tk.IntVar(value=ScanSpeedValue)  # Default value, overriden by configuration
        scan_speed_spinbox = DynamicSpinbox(speed_quality_frame, command=cmd_scan_speed_selection, width=4,
                                            textvariable=scan_speed_value, from_=1, to=10, font=("Arial", FontSize - 1),
                                            name='scan_speed_spinbox')
        scan_speed_spinbox.widget_type = "control"
        scan_speed_spinbox.grid(row=0, column=1, padx=x_pad, pady=y_pad, sticky=W)
        cmd_scan_speed_validation_cmd = scan_speed_spinbox.register(scan_speed_validation)
        scan_speed_spinbox.configure(validate="key", validatecommand=(cmd_scan_speed_validation_cmd, '%P'))
        as_tooltips.add(scan_speed_spinbox, "Select scan speed from 1 (slowest) to 10 (fastest).A speed of 5 is "
                                            "usually a good compromise between speed and good frame position "
                                            "detection.")
        scan_speed_spinbox.bind("<FocusOut>", lambda event: cmd_scan_speed_selection())

        # Display entry to adjust capture stabilization delay (100 ms by default)
        stabilization_delay_label = tk.Label(speed_quality_frame, text='Stabilization\ndelay (ms):',
                                             font=("Arial", FontSize - 1), name='stabilization_delay_label')
        stabilization_delay_label.widget_type = "control"
        stabilization_delay_label.grid(row=1, column=0, padx=x_pad, pady=y_pad, sticky=E)
        stabilization_delay_value = tk.IntVar(value=StabilizationDelayValue)  # default value, overriden by configuration
        stabilization_delay_spinbox = DynamicSpinbox(speed_quality_frame, command=cmd_stabilization_delay_selection,
                                                     width=4, textvariable=stabilization_delay_value, from_=0, to=1000,
                                                     increment=10, font=("Arial", FontSize - 1),
                                                     name='stabilization_delay_spinbox')
        stabilization_delay_spinbox.widget_type = "control"
        stabilization_delay_spinbox.grid(row=1, column=1, padx=x_pad, pady=y_pad, sticky=W)
        cmd_stabilization_delay_validation_cmd = stabilization_delay_spinbox.register(stabilization_delay_validation)
        stabilization_delay_spinbox.configure(validate="key",
                                              validatecommand=(cmd_stabilization_delay_validation_cmd, '%P'))
        as_tooltips.add(stabilization_delay_spinbox, "Delay between frame detection and snapshot trigger. 100ms is a "
                                                     "good compromise, lower values might cause blurry captures.")
        stabilization_delay_spinbox.bind("<FocusOut>", lambda event: cmd_stabilization_delay_selection())

    if ExperimentalMode:
        experimental_frame = LabelFrame(extended_frame, text='Experimental Area', font=("Arial", FontSize - 1),
                                        name='experimental_frame')
        experimental_frame.pack(side=TOP, padx=x_pad, pady=y_pad, expand=True, fill='y')
        # experimental_frame.place(relx=0.75, rely=0.5, anchor="center")

        # *****************************************
        # Frame to add HDR controls (on/off, exp. bracket, position, auto-adjust)
        hdr_frame = LabelFrame(experimental_frame, text="Multi-exposure fusion", font=("Arial", FontSize - 1),
                               name='hdr_frame')
        hdr_frame.grid(row=0, column=0, sticky='NWE', padx=x_pad, pady=y_pad)
        hdr_row = 0
        hdr_capture_active = tk.BooleanVar(value=HdrCaptureActive)
        hdr_capture_active_checkbox = tk.Checkbutton(hdr_frame, text=' Active', height=1,
                                                     variable=hdr_capture_active, onvalue=True, offvalue=False,
                                                     command=cmd_switch_hdr_capture, font=("Arial", FontSize - 1),
                                                     name='hdr_capture_active_checkbox')
        hdr_capture_active_checkbox.widget_type = "general"
        hdr_capture_active_checkbox.grid(row=hdr_row, column=0, sticky=W)
        as_tooltips.add(hdr_capture_active_checkbox, "Activate multi-exposure scan. Three snapshots of each frame "
                                                     "will be taken with different exposures, to be merged later by "
                                                     "AfterScan.")
        hdr_viewx4_active = tk.BooleanVar(value=HdrViewX4Active)
        hdr_viewx4_active_checkbox = tk.Checkbutton(hdr_frame, text=' View X4', height=1, variable=hdr_viewx4_active,
                                                    onvalue=True, offvalue=False, command=cmd_switch_hdr_viewx4,
                                                    font=("Arial", FontSize - 1), name='hdr_viewx4_active_checkbox')
        hdr_viewx4_active_checkbox.grid(row=hdr_row, column=1, columnspan=2, sticky=W)
        as_tooltips.add(hdr_viewx4_active_checkbox, "Alternate frame display during capture. Instead of displaying a "
                                                    "single frame (the one in the middle), all three frames will be "
                                                    "displayed sequentially.")
        hdr_row += 1

        hdr_min_exp_label = tk.Label(hdr_frame, text='Lower exp. (ms):', font=("Arial", FontSize - 1),
                                     name='hdr_min_exp_label')
        hdr_min_exp_label.widget_type = "hdr"
        hdr_min_exp_label.grid(row=hdr_row, column=0, columnspan=2, padx=x_pad, pady=y_pad, sticky=E)
        hdr_min_exp_value = tk.IntVar(value=HdrMinExp)
        hdr_min_exp_spinbox = DynamicSpinbox(hdr_frame, command=cmd_hdr_min_exp_selection, width=4,
                                             readonlybackground='pale green', textvariable=hdr_min_exp_value,
                                             from_=HDR_MIN_EXP, to=HDR_MAX_EXP,
                                             increment=1, font=("Arial", FontSize - 1), name='hdr_min_exp_spinbox')
        hdr_min_exp_spinbox.widget_type = "hdr"
        hdr_min_exp_spinbox.grid(row=hdr_row, column=2, padx=x_pad, pady=y_pad, sticky=W)
        cmd_hdr_min_exp_validation_cmd = hdr_min_exp_spinbox.register(hdr_min_exp_validation)
        hdr_min_exp_spinbox.configure(validate="key", validatecommand=(cmd_hdr_min_exp_validation_cmd, '%P'))
        as_tooltips.add(hdr_min_exp_spinbox, "When multi-exposure enabled, lower value of the exposure bracket.")
        hdr_min_exp_spinbox.bind("<FocusOut>", lambda event: cmd_hdr_min_exp_selection())
        hdr_row += 1

        hdr_max_exp_label = tk.Label(hdr_frame, text='Higher exp. (ms):', font=("Arial", FontSize - 1),
                                     name='hdr_max_exp_label')
        hdr_max_exp_label.widget_type = "hdr"
        hdr_max_exp_label.grid(row=hdr_row, column=0, columnspan=2, padx=x_pad, pady=y_pad, sticky=E)
        hdr_max_exp_value = tk.IntVar(value=HdrMaxExp)
        hdr_max_exp_spinbox = DynamicSpinbox(hdr_frame, command=cmd_hdr_max_exp_selection, width=4, from_=2, to=1000,
                                             readonlybackground='pale green', textvariable=hdr_max_exp_value,
                                             increment=1, font=("Arial", FontSize - 1), name='hdr_max_exp_spinbox')
        hdr_max_exp_spinbox.widget_type = "hdr"
        hdr_max_exp_spinbox.grid(row=hdr_row, column=2, padx=x_pad, pady=y_pad, sticky=W)
        cmd_hdr_max_exp_validation_cmd = hdr_max_exp_spinbox.register(hdr_max_exp_validation)
        hdr_max_exp_spinbox.configure(validate="key", validatecommand=(cmd_hdr_max_exp_validation_cmd, '%P'))
        as_tooltips.add(hdr_max_exp_spinbox, "When multi-exposure enabled, upper value of the exposure bracket.")
        hdr_max_exp_spinbox.bind("<FocusOut>", lambda event: cmd_hdr_max_exp_selection())
        hdr_row += 1

        hdr_bracket_width_label = tk.Label(hdr_frame, text='Bracket width (ms):', font=("Arial", FontSize - 1),
                                           name='hdr_bracket_width_label')
        hdr_bracket_width_label.widget_type = "hdr"
        hdr_bracket_width_label.grid(row=hdr_row, column=0, columnspan=2, padx=x_pad, pady=y_pad, sticky=E)
        hdr_bracket_width_value = tk.IntVar(value=HdrBracketWidth)
        hdr_bracket_width_spinbox = DynamicSpinbox(hdr_frame, command=cmd_hdr_bracket_width_selection, width=4,
                                                   textvariable=hdr_bracket_width_value, from_=HDR_MIN_BRACKET,
                                                   to=HDR_MAX_BRACKET, increment=1, font=("Arial", FontSize - 1),
                                                   name='hdr_bracket_width_spinbox')
        hdr_bracket_width_spinbox.widget_type = "hdr"
        hdr_bracket_width_spinbox.grid(row=hdr_row, column=2, padx=x_pad, pady=y_pad, sticky=W)
        cmd_hdr_bracket_width_validation_cmd = hdr_bracket_width_spinbox.register(hdr_bracket_width_validation)
        hdr_bracket_width_spinbox.configure(validate="key", validatecommand=(cmd_hdr_bracket_width_validation_cmd, '%P'))
        as_tooltips.add(hdr_bracket_width_spinbox, "When multi-exposure enabled, width of the exposure bracket ("
                                                   "useful for automatic mode).")
        hdr_bracket_width_spinbox.bind("<FocusOut>", cmd_hdr_bracket_width_selection)
        hdr_row += 1

        hdr_bracket_shift_label = tk.Label(hdr_frame, text='Bracket shift (ms):', font=("Arial", FontSize - 1),
                                           name='hdr_bracket_shift_label')
        hdr_bracket_shift_label.widget_type = "hdr"
        hdr_bracket_shift_label.grid(row=hdr_row, column=0, columnspan=2, padx=x_pad, pady=y_pad, sticky=E)
        hdr_bracket_shift_value = tk.IntVar(value=HdrBracketShift)
        hdr_bracket_shift_spinbox = DynamicSpinbox(hdr_frame, command=cmd_hdr_bracket_shift_selection, width=4,
                                                   textvariable=hdr_bracket_shift_value, from_=-100, to=100,
                                                   increment=10, font=("Arial", FontSize - 1),
                                                   name='hdr_bracket_shift_spinbox')
        hdr_bracket_shift_spinbox.widget_type = "hdr"
        hdr_bracket_shift_spinbox.grid(row=hdr_row, column=2, padx=x_pad, pady=y_pad, sticky=W)
        cmd_hdr_bracket_shift_validation_cmd = hdr_bracket_shift_spinbox.register(hdr_bracket_shift_validation)
        hdr_bracket_shift_spinbox.configure(validate="key", validatecommand=(cmd_hdr_bracket_shift_validation_cmd, '%P'))
        as_tooltips.add(hdr_bracket_shift_spinbox, "When multi-exposure enabled, shift exposure bracket up or down "
                                                   "from default position.")
        hdr_bracket_shift_spinbox.bind("<FocusOut>", lambda event: cmd_hdr_bracket_shift_selection())
        hdr_row += 1

        hdr_bracket_auto = tk.BooleanVar(value=HdrBracketAuto)
        hdr_bracket_width_auto_checkbox = tk.Checkbutton(hdr_frame, text='Auto bracket', height=1,
                                                         variable=hdr_bracket_auto, onvalue=True, offvalue=False,
                                                         command=cmd_adjust_hdr_bracket_auto,
                                                         font=("Arial", FontSize - 1),
                                                         name='hdr_bracket_width_auto_checkbox')
        hdr_bracket_width_auto_checkbox.widget_type = "control"
        hdr_bracket_width_auto_checkbox.grid(row=hdr_row, column=0, columnspan=3, sticky=W)
        as_tooltips.add(hdr_bracket_width_auto_checkbox, "Enable automatic multi-exposure: For each frame, ALT-Scann8 "
                                                         "will retrieve the auto-exposure level reported by the RPi "
                                                         "HQ camera, adn will use it for the middle exposure, "
                                                         "calculating the lower/upper values according to the bracket "
                                                         "defined.")
        hdr_row += 1

        hdr_merge_in_place = tk.BooleanVar(value=HdrMergeInPlace)
        hdr_merge_in_place_checkbox = tk.Checkbutton(hdr_frame, text='Merge in place', height=1,
                                                     variable=hdr_merge_in_place, onvalue=True, offvalue=False,
                                                     command=cmd_adjust_merge_in_place, font=("Arial", FontSize - 1),
                                                     name='hdr_merge_in_place_checkbox')
        hdr_merge_in_place_checkbox.widget_type = "hdr"
        hdr_merge_in_place_checkbox.grid(row=hdr_row, column=0, columnspan=3, sticky=W)
        as_tooltips.add(hdr_merge_in_place_checkbox, "Enable to perform Mertens merge on the Raspberry Pi, while "
                                                     "encoding. Allow to make some use of the time spent waiting for "
                                                     "the camera to adapt the exposure.")

        # Damaged film helpers, to help handling damaged film (broken perforations)
        damaged_film_frame = LabelFrame(experimental_frame, text='Damaged film',
                                        font=("Arial", FontSize - 1), name='damaged_film_frame')
        damaged_film_frame.grid(row=1, column=0, sticky='NWE', padx=x_pad, pady=y_pad)

        # Checkbox to enable/disable manual scan
        Manual_scan_activated = tk.BooleanVar(value=ManualScanEnabled)
        manual_scan_checkbox = tk.Checkbutton(damaged_film_frame, text='Enable manual scan',
                                              variable=Manual_scan_activated, onvalue=True,
                                              offvalue=False, command=cmd_Manual_scan_activated_selection,
                                              font=("Arial", FontSize - 1), name='manual_scan_checkbox')
        manual_scan_checkbox.widget_type = "experimental"
        manual_scan_checkbox.pack(side=TOP)
        as_tooltips.add(manual_scan_checkbox, "Enable manual scan (for films with very damaged sprocket holes). Lots "
                                              "of manual work, use it if everything else fails.")
        # Common area for buttons
        Manual_scan_btn_frame = Frame(damaged_film_frame)
        Manual_scan_btn_frame.pack(side=TOP)

        # Manual scan buttons
        manual_scan_advance_fraction_5_btn = Button(Manual_scan_btn_frame, text="+5", height=1,
                                                    command=cmd_manual_scan_advance_frame_fraction_5,
                                                    font=("Arial", FontSize - 1),
                                                    name='manual_scan_advance_fraction_5_btn')
        manual_scan_advance_fraction_5_btn.widget_type = "experimental"
        manual_scan_advance_fraction_5_btn.pack(side=LEFT, fill=Y)
        as_tooltips.add(manual_scan_advance_fraction_5_btn, "Advance film by 5 motor steps.")
        manual_scan_advance_fraction_20_btn = Button(Manual_scan_btn_frame, text="+20", height=1,
                                                     command=cmd_manual_scan_advance_frame_fraction_20,
                                                     font=("Arial", FontSize - 1),
                                                     name='manual_scan_advance_fraction_20_btn')
        manual_scan_advance_fraction_20_btn.widget_type = "experimental"
        manual_scan_advance_fraction_20_btn.pack(side=LEFT, fill=Y)
        as_tooltips.add(manual_scan_advance_fraction_20_btn, "Advance film by 20 motor steps.")
        manual_scan_take_snap_btn = Button(Manual_scan_btn_frame, text="Snap", height=1,
                                           command=cmd_manual_scan_take_snap, font=("Arial", FontSize - 1),
                                           name='manual_scan_take_snap_btn')
        manual_scan_take_snap_btn.widget_type = "experimental"
        manual_scan_take_snap_btn.pack(side=RIGHT, fill=Y)
        as_tooltips.add(manual_scan_take_snap_btn, "Take snapshot of frame at current position, then tries to advance "
                                                   "to next frame.")

        # Experimental miscellaneous sub-frame
        experimental_miscellaneous_frame = LabelFrame(experimental_frame, text='Miscellaneous',
                                                      font=("Arial", FontSize - 1),
                                                      name ='experimental_miscellaneous_frame')
        experimental_miscellaneous_frame.grid(row=0, column=1, rowspan=2, sticky='NWE', padx=x_pad, pady=y_pad)
        experimental_row = 0

        # Display entry to throttle Rwnd/FF speed
        rwnd_speed_control_label = tk.Label(experimental_miscellaneous_frame, text='RW/FF speed:',
                                            font=("Arial", FontSize - 1), name='rwnd_speed_control_label')
        rwnd_speed_control_label.grid(row=experimental_row, column=0, padx=x_pad, pady=y_pad)
        rwnd_speed_control_value = tk.IntVar(value=round(60 / (rwnd_speed_delay * 375 / 1000000)))
        rwnd_speed_control_spinbox = DynamicSpinbox(experimental_miscellaneous_frame, state='readonly', width=4,
                                                    command=cmd_rwnd_speed_control_selection, from_=40, to=800,
                                                    increment=50, textvariable=rwnd_speed_control_value,
                                                    font=("Arial", FontSize - 1), name='rwnd_speed_control_spinbox')
        rwnd_speed_control_spinbox.grid(row=experimental_row, column=1, padx=x_pad, pady=y_pad)
        cmd_rewind_speed_validation_cmd = rwnd_speed_control_spinbox.register(rewind_speed_validation)
        rwnd_speed_control_spinbox.configure(validate="key", validatecommand=(cmd_rewind_speed_validation_cmd, '%P'))
        as_tooltips.add(rwnd_speed_control_spinbox, "Speed up/slow down the RWND/FF speed.")
        # No need to validate on FocusOut, since no keyboard entry is allowed in this one
        experimental_row += 1

        # Unlock reels button (to load film, rewind, etc.)
        free_btn = Button(experimental_miscellaneous_frame, text="Unlock Reels", command=cmd_set_free_mode,
                          activebackground='#f0f0f0', relief=RAISED, font=("Arial", FontSize - 1), name='free_btn')
        free_btn.widget_type = "experimental"
        free_btn.grid(row=experimental_row, column=0, columnspan=2, padx=x_pad, pady=y_pad)
        as_tooltips.add(free_btn, "Used to be a standard button in ALT-Scann8, removed since now motors are always "
                                  "unlocked when not performing any specific operation.")
        experimental_row += 1

        # Spinbox to select Preview module
        preview_module_label = tk.Label(experimental_miscellaneous_frame, text='Preview module:',
                                        font=("Arial", FontSize - 1), name='preview_module_label')
        preview_module_label.grid(row=experimental_row, column=0, padx=x_pad, pady=y_pad)
        preview_module_value = tk.IntVar(value=1)  # Default value, overriden by configuration
        preview_module_spinbox = DynamicSpinbox(experimental_miscellaneous_frame, command=cmd_preview_module_selection,
                                                width=2, textvariable=preview_module_value, from_=1, to=50,
                                                font=("Arial", FontSize - 1), name='preview_module_spinbox')
        preview_module_spinbox.grid(row=experimental_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        cmd_preview_module_validation_cmd = preview_module_spinbox.register(preview_module_validation)
        as_tooltips.add(preview_module_spinbox, "Refresh preview, auto exposure and auto WB values only every 'n' "
                                                "frames. Can speed up scanning significantly")
        preview_module_spinbox.configure(validate="key", validatecommand=(cmd_preview_module_validation_cmd, '%P'))
        preview_module_spinbox.bind("<FocusOut>", lambda event: cmd_preview_module_selection())
        experimental_row += 1

        # Spinbox to select UV led brightness
        uv_brightness_label = tk.Label(experimental_miscellaneous_frame, text='UV brightness:',
                                        font=("Arial", FontSize - 1), name='uv_brightness_label')
        uv_brightness_label.grid(row=experimental_row, column=0, padx=x_pad, pady=y_pad)
        uv_brightness_value = tk.IntVar(value=255)  # Default value, overriden by configuration
        uv_brightness_spinbox = DynamicSpinbox(experimental_miscellaneous_frame, command=cmd_uv_brightness_selection,
                                                width=3, textvariable=uv_brightness_value, from_=1, to=255,
                                                font=("Arial", FontSize - 1), name='uv_brightness_spinbox')
        uv_brightness_spinbox.grid(row=experimental_row, column=1, padx=x_pad, pady=y_pad, sticky=W)
        cmd_uv_brightness_validation_cmd = uv_brightness_spinbox.register(uv_brightness_validation)
        as_tooltips.add(uv_brightness_spinbox, "Adjust UV led brightness (1-255)")
        uv_brightness_spinbox.configure(validate="key", validatecommand=(cmd_uv_brightness_validation_cmd, '%P'))
        uv_brightness_spinbox.bind("<FocusOut>", lambda event: cmd_uv_brightness_selection())
        experimental_row += 1

        # Manual UV Led switch
        manual_uv_btn = Button(experimental_miscellaneous_frame, text="Plotter on", command=cmd_manual_uv,
                          activebackground='#f0f0f0', relief=RAISED, font=("Arial", FontSize - 1), name='manual_uv_btn')
        manual_uv_btn.widget_type = "experimental"
        manual_uv_btn.grid(row=experimental_row, column=0, columnspan=2, padx=x_pad, pady=y_pad)
        as_tooltips.add(manual_uv_btn, "Manually switch UV led (to allow tunning using plotter)")
        experimental_row += 1

    # Adjust plotter size based on right  frames
    win.update_idletasks()
    if PlotterEnabled:
        plotter_width = integrated_plotter_frame.winfo_width() - 10
        plotter_height = int(plotter_width / 2)
        plotter_canvas.config(width=plotter_width, height=plotter_height)
    # Adjust canvas size based on height of lateral frames
    win.update_idletasks()
    PreviewHeight = max(top_left_area_frame.winfo_height(), top_right_area_frame.winfo_height()) - 20  # Compensate pady
    PreviewWidth = int(PreviewHeight * 4 / 3)
    draw_capture_canvas.config(width=PreviewWidth, height=PreviewHeight)
    # Adjust holes size/position
    FilmHoleHeightTop = int(PreviewHeight / 5.9)
    FilmHoleHeightBottom = int(PreviewHeight / 3.7)
    # Adjust main window size
    # Prevent window resize
    # Get screen size - maxsize gives the usable screen size
    main_container.update_idletasks()
    app_width = min(main_container.winfo_reqwidth(), screen_width - 150)
    app_height = min(main_container.winfo_reqheight(), screen_height - 150)
    if ExpertMode and extended_frame.winfo_reqwidth() > top_area_frame.winfo_reqwidth():
        x = int((extended_frame.winfo_reqwidth() - top_area_frame.winfo_reqwidth()) / 2)
        top_area_frame.config(padx=x-1)

    win.minsize(app_width, app_height)
    win.maxsize(app_width, app_height)
    win.geometry(f'{app_width}x{app_height - 20}')  # setting the size of the window
    if FilmType == "R8":
        cmd_set_r8()
    elif FilmType == "S8":
        cmd_set_s8()



def get_controller_version():
    if Controller_Id == 0:
        logging.debug("Requesting controller version")
        send_arduino_command(CMD_VERSION_ID)


def reset_controller():
    logging.debug("Resetting controller")
    send_arduino_command(CMD_RESET_CONTROLLER)
    time.sleep(0.5)


def main(argv):
    global SimulatedRun, SimulatedArduinoVersion
    global ExpertMode, ExperimentalMode, PlotterEnabled
    global LogLevel, LoggingMode
    global ALT_scann_init_done
    global CameraDisabled, DisableThreads
    global FontSize, UIScrollbars
    global WidgetsEnabledWhileScanning
    global DisableToolTips
    global win

    DisableToolTips = False

    opts, args = getopt.getopt(argv, "sexl:phntwf:ba:")

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
        elif  opt == '-a':
            SimulatedArduinoVersion = arg
        elif opt == '-f':
            FontSize = int(arg)
        elif opt == '-b':
            UIScrollbars = True
        elif opt == '-n':
            DisableToolTips = True
        elif opt == '-t':
            DisableThreads = True
        elif opt == '-w':
            WidgetsEnabledWhileScanning = not WidgetsEnabledWhileScanning
        elif opt == '-h':
            print("ALT-Scann 8 Command line parameters")
            print("  -s             Start Simulated session")
            print("  -e             Activate expert mode")
            print("  -x             Activate experimental mode")
            print("  -d             Disable camera (for development purposes)")
            print("  -n             Disable Tooltips")
            print("  -t             Disable multi-threading")
            print("  -f <size>      Set user interface font size (11 by default)")
            print("  -b             Add scrollbars to UI (in case it does not fit)")
            print("  -w             Keep control widgets enabled while scanning")
            print("  -l <log mode>  Set log level (standard Python values (DEBUG, INFO, WARNING, ERROR)")
            exit()

    LogLevel = getattr(logging, LoggingMode.upper(), None)
    if not isinstance(LogLevel, int):
        raise ValueError('Invalid log level: %s' % LogLevel)
    else:
        init_logging()

    ALT_scann_init_done = False

    if not numpy_loaded:
        logging.error("Numpy library could no tbe loaded.\r\nPlease install it with this command 'sudo apt install python3-numpy'.")
        return

    win = tkinter.Tk()  # Create temporary main window to support popups before main window is created
    win.withdraw()  # Hide temporary main window

    load_configuration_data_from_disk()  # Read json file in memory, to be processed by 'load_session_data_post_init'

    if not validate_config_folders():
        return

    load_config_data_pre_init()

    tscann8_init()

    if DisableToolTips:
        as_tooltips.disable()

    load_session_data_post_init()

    init_multidependent_widgets()

    if SimulatedRun:
        logging.debug("Starting in simulated mode.")
    if ExpertMode:
        logging.debug("Toggle expert mode.")
    if ExperimentalMode:
        logging.debug("Toggle experimental mode.")
    if CameraDisabled:
        logging.debug("Camera disabled.")
    if FontSize != 0:
        logging.debug(f"Font size = {FontSize}")
    if DisableThreads:
        logging.debug("Threads disabled.")

    if not SimulatedRun:
        arduino_listen_loop()

    ALT_scann_init_done = True

    refresh_qr_code()

    # Write environment info to log
    data = generate_qr_code_info()
    logging.info(data)

    # *** ALT-Scann8 load complete ***
    if hw_panel_installed:
        hw_panel.ALT_Scann8_init_completed()

    onesec_periodic_checks()

    # Main Loop
    win.mainloop()  # running the loop that works as a trigger

    if not SimulatedRun and not CameraDisabled:
        camera.close()


if __name__ == '__main__':
    main(sys.argv[1:])
