"""
06/08/2022: 2.1.7: JRE: Add Button for EmergencyStop
10/08/2022: JRE: Comment out emergency stop button
10/08/2022: JRE: After capturing image, if exposure has changed since previous capture wait one sec
                 (to allow camera to adapt in automatic mode)
12/08/2022: JRE: Improve automatic exposure adaptation
13/08/2022: JRE Implemented detection of fild loaded via FilmGate, to prevent FF/Rewind
13/08/2022: JRE Move to 2.1.9
14/08/2022: JRE Implemented function to dynamically modify the perforation level threshold
27/08/2022: JRE, first attempt at migrating to picamera2
        - Highlights: Most functionality works fine, but slower (factors to check: SD card, preview
          mode, save to PNG?)
        - Advance Film: OK (not camera related)
        - Rewind: OK (not camera related)
        - Free wheels: OK (not camera related)
        - Negative film: KO, maybe can be done with overlays?
        - Focus zoom: OK
        - Automatic exposure: OK
        - Scan: OK, but slower
29/08/2022: JRE, continue with PiCamera2
        - Preview (QTGL) too slow. DRM/KMS should be faster, but does not work for now
        - Disabling preview makes scan process faster than current version (on 64-bit OS at
          least)
        - Implemented post-view (display captured image) when preview is disabled (also has
          a speed cost, result is closer to current version)
30/08/2022: JRE, fixed segment fault
        - It was clearly related to the askyesno popup asking if the user wanted to retrieve
          previous session (commenting out the popup was avoiding thg segment fault)
          Moving the session recovery code to a dedicated function solved the issue (do not ask me why)
31/08/2022: JRE, UI changes
        - Use LabelFrame instead of Frame
        - Reorganize position of controls
01/09/2022: JRE Removed function to dynamically modify the perforation level threshold
        - Already used for it's purpose (find optimal value), remove it as it is confusing
        - Also with the new approach prioritizing the minimal number of steps, perforation
          detection is more a confirmation we are in next frame
04/09/2022: JRE - Port awb_gains to PiCamera2 (via libcamera controls AwbEnable, ColourGains)
                  Negative image can probably be achieved via ColourCorrectionMatrix
                  For now, if awb_gains values found in PiCamera legacy version are ported as they are
                  to th ePiCamera2 version, terrible colors result. For now code is left commented out
                - Optimization of 'postview' capture: Instead of retrieving the captured image from disk,
                  we reuse the one captured in  memory (slight speed improvement, 55 to 64 FPM)
                - Bug fix: We were writing session info to disk each capture loop, instead of each frame
                  Significant speed improvement (including also previous optimization):
                   - Without preview: 99 to 115 FPM
                   - Postview 1/1: 55 to 74 FPM
                   - Postview 1/10: 81 to 109
                   - QTGL Preview: 30 to 36 (still quite unusable)
                - Implement support for new Arduino message (12), indicating an error during the scan
                  process. This allows for clean termination and reset of the UI to default status.
                  This is useful mainly when the single step or scan buttons are clicked with no film
08/09/2022: JRE
                - Factorize code to hide/redisplay preview when using PiCamera legacy
                - Add new hidden UI section for experimental features. Can be enabled with command line parameter '-x'
                - Add UI controls to allow handling AWT (automatic white balance) in a similar way automatic exposure is handled
                - Add option to allow waiting for AWB adaptation during capture (same as what is already done for automatic exposure). Needs to be automati cas it slows down the process, and it is not that critical (IMHO)
09/09/2022: JRE
                - Preview modes consolidated in a single variable: 'PreviewMode'
                - Persisted PreviewMode in session data
                - Create enum of preview modes (to consolidate in a single var)
                - Move hole marker to experimental area. Add button to adjust position of marker
                - Fix display issues for CCM and AWB values in experimental area (although modification of CCM seems unsupported)
                - Move 'Open folder' button to experimental area

"""

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
import sys, getopt

try:
    import smbus
    try:
        from picamera2 import Picamera2, Preview
        from libcamera import Transform
        # Global variable to isolate camera specific code (Picamera vs PiCamera2)
        IsPiCamera2 = True
    except:
        # If PiCamera2 cannot be imported, it will default to PiCamera legacy, so no need to change this
        IsPiCamera2 = False
        import picamera

    # Global variable to allow basic UI testing on PC (where PiCamera imports should fail)
    SimulatedRun = False
except:
    SimulatedRun=True
    IsPiCamera2 = False

if SimulatedRun:
    print("Not running on Raspberry Pi, simulated run for UI debugging purposes only")
else:
    print("Running on Raspberry Pi")


#  ######### Global variable definition ##########
FocusState = True
lastFocus = True
FocusZoomActive = False
FreeWheelActive = False
BaseDir = '/home/juan/Vídeos/'  # dirplats in original code from Torulf
CurrentDir = BaseDir
CurrentFrame = 0  # bild in original code from Torulf
CurrentScanStartTime = datetime.now()
CurrentScanStartFrame = 0
CurrentExposure = 0
PreviousCurrentExposure = 0  # Used to spot changes in exposure, and cause a delay to allow camera to adapt
CurrentExposureStr = "Auto"
ExposureAdaptPause = False
NegativeCaptureActive = False
AdvanceMovieActive = False
RewindMovieActive = False  # SpolaState in original code from Torulf
RewindErrorOutstanding = False
FastForwardActive = False
FastForwardErrorOutstanding = False
OpenFolderActive = False
ScanOngoing = False  # PlayState in original code from Torulf (opposite meaning)
NewFrameAvailable = False  # To be set to true upon reception of Arduino event
ScanProcessError = False # To be set to true  upon reception of Arduino event
ScriptDir = os.path.dirname(
    sys.argv[0])  # Directory where python scrips run, to store the json file with persistent data
PersistedDataFilename = os.path.join(ScriptDir, "T-Scann8.json")
PersistedDataLoaded = False
ArduinoTrigger = 0
# Variables to track windows movement adn set preview accordingly
TopWinX = 0
TopWinY = 0
PreviewWinX = 90
PreviewWinY = 75
DeltaX = 0
DeltaY = 0
WinInitDone = False
FolderProcess = 0
PostviewModule = 1
PostviewModulePartial = 4  # defautl mode for preview partial mode
# Create enum to consolidate all pre/post view modes in a single variable
class PreviewType(Enum):
    NO_PREVIEW = 0
    CAMERA_PREVIEW = 1
    CAPTURE_ALL = 2
    CAPTURE_PARTIAL = 3
PreviewMode = PreviewType.CAMERA_PREVIEW
PostviewCounter = 0
FramesPerMinute = 0
PreviewAreaImage = ''
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
draw_capture_label = ''
simulated_images_in_list = 0
FilmHoleY=300

Experimental = False
CurrentAwbAuto = True
gain_red = 1 # 2.4
gain_blue = 1 # 2.8
AwbPause = False
PreviousGainRed = 1
PreviousGainBlue = 1

PreviewWarnAgain = True

# Persisted data
SessionData = {
    "CurrentDate": str(datetime.now()),
    "CurrentDir": CurrentDir,
    "CurrentFrame": str(CurrentFrame),
    "CurrentExposure": str(CurrentExposure),
    "FilmHoleY": str(FilmHoleY),
    "PreviewMode": PreviewMode.name,
    "NegativeCaptureActive": str(NegativeCaptureActive)
}

#  ######### Special Global variables defined inside functions  ##########
"""
global win
global AdvanceMovie_btn
global SingleStep_btn
global PosNeg_btn
global DisablePreview_btn
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
global exposure_frame_value_label
global film_type_S8_btn
global film_type_R8_btn
global preview_border_frame
global camera
global CurrentFrame
global i2c
global capture_config
global preview_config
"""

def exit_app():  # Exit Application
    global SimulatedRun
    global camera
    global win
    global PreviewMode

    # Uncomment next two lines when running on RPi
    if not SimulatedRun:
        if PreviewMode == PreviewType.CAMERA_PREVIEW:
            camera.stop_preview()
        camera.close()
    # Write session data upon exit
    with open(PersistedDataFilename, 'w') as f:
        json.dump(SessionData, f)

    win.destroy()

    # poweroff()  # shut down Raspberry PI (remove "#" before poweroff)


def set_free_mode():
    global FreeWheelActive
    global save_bg
    global save_fg
    global SimulatedRun
    global Free_btn

    if not FreeWheelActive:
        Free_btn.config(text='Lock Reels', bg='red', fg='white')
    else:
        Free_btn.config(text='Unlock Reels', bg=save_bg, fg=save_fg)

    if not SimulatedRun:
        i2c.write_byte_data(16, 20, 0)

    FreeWheelActive = not FreeWheelActive

    # Enable/Disable related buttons
    button_status_change_except(Free_btn, FreeWheelActive)


# Enable/Disable camera zoom to facilitate focus
def set_focus_zoom():
    global FocusZoomActive
    global save_bg
    global save_fg
    global SimulatedRun
    global ZoomSize
    global Focus_btn

    if not FocusZoomActive:
        Focus_btn.config(text='Focus Zoom OFF', bg='red', fg='white')
        if not SimulatedRun:
            if IsPiCamera2:
                camera.set_controls({"ScalerCrop": (int(0.35 * ZoomSize[0]), int(0.35 * ZoomSize[1])) +
                                                   (int(0.2 * ZoomSize[0]), int(0.2 * ZoomSize[1]))})
            else:
                camera.crop = (0.35, 0.35, 0.2, 0.2)  # Activate camera zoom
    else:
        Focus_btn.config(text='Focus Zoom ON', bg=save_bg, fg=save_fg)
        if not SimulatedRun:
            if IsPiCamera2:
                camera.set_controls({"ScalerCrop": (0, 0) + (ZoomSize[0], ZoomSize[1])})
            else:
                camera.crop = (0.0, 0.0, 835, 720)  # Remove camera zoom

    time.sleep(.2)
    FocusZoomActive = not FocusZoomActive

    # Enable/Disable related buttons
    button_status_change_except(Focus_btn, FocusZoomActive)


# A couple of helper funtcions to hide/display preview when needed (displaying popups with picamera legacy)
def hide_preview():
    global PreviewMode
    if PreviewMode == PreviewType.CAMERA_PREVIEW and not SimulatedRun and not IsPiCamera2:
        camera.stop_preview()
def display_preview():
    global PreviewMode
    if PreviewMode == PreviewType.CAMERA_PREVIEW and not SimulatedRun and not IsPiCamera2:
        camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))

def set_new_folder():
    global CurrentDir
    global CurrentFrame
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
    global CurrentDir
    global CurrentFrame
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
        if (current_frame_str==''):
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
    global CurrentExposure
    global CurrentExposureStr
    global SimulatedRun

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
    if not SimulatedRun:
        if IsPiCamera2:
            camera.controls.ExposureTime = CurrentExposure  # maybe will not work, check pag 26 of picamera2 specs
        else:
            camera.shutter_speed = CurrentExposure
    auto_exp_wait_checkbox.config(state=DISABLED)


def auto_exp():
    global CurrentExposure
    global CurrentExposureStr

    CurrentExposure = 0

    CurrentExposureStr = "Auto"

    SessionData["CurrentExposure"] = CurrentExposureStr

    exposure_frame_value_label.config(text=CurrentExposureStr)
    if not SimulatedRun:
        if IsPiCamera2:
            camera.controls.ExposureTime = CurrentExposure  # maybe will not work, check pag 26 of picamera2 specs
        else:
            camera.shutter_speed = CurrentExposure

    auto_exp_wait_checkbox.config(state=NORMAL)

def increase_exp():
    global CurrentExposure
    global CurrentExposureStr
    global SimulatedRun

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
    global gain_blue
    global gain_red
    gain_red += 0.1
    SessionData["gain_red"] = str(gain_red)
    colour_gains_red_value_label.config(text=str(round(gain_red,1)))
    if not SimulatedRun and not CurrentAwbAuto:
        if IsPiCamera2:
            #camera.set_controls({"AwbEnable": 0})
            camera.set_controls({"ColourGains": (gain_red, gain_blue)})
        else:
            #camera.awb_mode = 'off'
            camera.awb_gains = (gain_red, gain_blue)

def colour_gain_red_minus():
    global colour_gains_red_value_label
    global gain_blue
    global gain_red
    gain_red -= 0.1
    SessionData["gain_red"] = str(gain_red)
    colour_gains_red_value_label.config(text=str(round(gain_red,1)))
    if not SimulatedRun and not CurrentAwbAuto:
        if IsPiCamera2:
            #camera.set_controls({"AwbEnable": 0})
            camera.set_controls({"ColourGains": (gain_red, gain_blue)})
        else:
            #camera.awb_mode = 'off'
            camera.awb_gains = (gain_red, gain_blue)

def colour_gain_blue_plus():
    global colour_gains_blue_value_label
    global gain_blue
    global gain_red
    gain_blue += 0.1
    SessionData["gain_blue"] = str(gain_blue)
    colour_gains_blue_value_label.config(text=str(round(gain_blue,1)))
    if not SimulatedRun and not CurrentAwbAuto:
        if IsPiCamera2:
            #camera.set_controls({"AwbEnable": 0})
            camera.set_controls({"ColourGains": (gain_red, gain_blue)})
        else:
            #camera.awb_mode = 'off'
            camera.awb_gains = (gain_red, gain_blue)

def colour_gain_blue_minus():
    global colour_gains_blue_value_label
    global gain_blue
    global gain_red
    gain_blue -= 0.1
    SessionData["gain_blue"] = str(gain_blue)
    colour_gains_blue_value_label.config(text=str(round(gain_blue,1)))
    if not SimulatedRun and not CurrentAwbAuto:
        if IsPiCamera2:
            #camera.set_controls({"AwbEnable": 0})
            camera.set_controls({"ColourGains": (gain_red, gain_blue)})
        else:
            #camera.awb_mode = 'off'
            camera.awb_gains = (gain_red, gain_blue)

def ccm_update():
    global ccm_11,ccm_12,ccm_13,ccm_21,ccm_22,ccm_23,ccm_31,ccm_32,ccm_33
    if IsPiCamera2:
        camera.set_controls({"ColourCorrectionMatrix": (float(ccm_11.get()),
                                                        float(ccm_12.get()),
                                                        float(ccm_13.get()),
                                                        float(ccm_21.get()),
                                                        float(ccm_22.get()),
                                                        float(ccm_23.get()),
                                                        float(ccm_31.get()),
                                                        float(ccm_32.get()),
                                                        float(ccm_33.get()))})

def colour_gain_auto():
    global CurrentAwbAuto
    global gain_blue
    global gain_red
    global colour_gains_auto_btn, awb_frame
    global colour_gains_red_btn_plus
    global colour_gains_red_btn_minus
    global colour_gains_blue_btn_plus
    global colour_gains_blue_btn_minus
    global colour_gains_red_value_label
    global colour_gains_blue_value_label

    CurrentAwbAuto = not CurrentAwbAuto
    SessionData["CurrentAwbAuto"] = str(CurrentAwbAuto)

    if CurrentAwbAuto:
        awb_frame.config(text='Automatic White Balance ON')
        awb_wait_checkbox.config(state=NORMAL)
        colour_gains_auto_btn.config(text='AWB OFF')
        colour_gains_red_btn_plus.config(state=DISABLED)
        colour_gains_red_btn_minus.config(state=DISABLED)
        colour_gains_blue_btn_plus.config(state=DISABLED)
        colour_gains_blue_btn_minus.config(state=DISABLED)
        if not SimulatedRun:
            if IsPiCamera2:
                camera.set_controls({"AwbEnable": 1})
                colour_gains_red_value_label.config(text="Auto")
                colour_gains_blue_value_label.config(text="Auto")
            else:
                camera.awb_mode = 'auto'
                colour_gains_red_value_label.config(text="Auto")
                colour_gains_blue_value_label.config(text="Auto")
    else:
        awb_frame.config(text='Automatic White Balance OFF')
        awb_wait_checkbox.config(state=DISABLED)
        colour_gains_auto_btn.config(text='AWB ON')
        colour_gains_red_btn_plus.config(state=NORMAL)
        colour_gains_red_btn_minus.config(state=NORMAL)
        colour_gains_blue_btn_plus.config(state=NORMAL)
        colour_gains_blue_btn_minus.config(state=NORMAL)
        if not SimulatedRun:
            if IsPiCamera2:
                # Retrieve current gain values from Camera
                metadata = camera.capture_metadata()
                camera_colour_gains = metadata["ColourGains"]
                gain_red = camera_colour_gains[0]
                gain_blue = camera_colour_gains[1]
                colour_gains_red_value_label.config(text=str(round(gain_red,1)))
                colour_gains_blue_value_label.config(text=str(round(gain_blue,1)))
                camera.set_controls({"AwbEnable": 0})
            else:
                gain_red = camera.awb_gains[0]
                gain_blue = camera.awb_gains[1]
                colour_gains_red_value_label.config(text=str(round(gain_red,1)))
                colour_gains_blue_value_label.config(text=str(round(gain_blue,1)))
                camera.awb_mode = 'off'
                camera.awb_gains = (gain_red, gain_blue)
        else: # Add fake values for simulated run
            gain_red = 1
            gain_blue = 1


def button_status_change_except(except_button, active):
    global Free_btn
    global SingleStep_btn
    global AdvanceMovie_btn
    global Rewind_btn
    global FastForward_btn
    global Start_btn
    global PosNeg_btn
    global Focus_btn
    global Start_btn
    global Exit_btn
    global film_type_S8_btn
    global film_type_R8_btn

    if except_button != Free_btn:
        Free_btn.config(state=DISABLED if active else NORMAL)
    if except_button != SingleStep_btn:
        SingleStep_btn.config(state=DISABLED if active else NORMAL)
    if except_button != AdvanceMovie_btn:
        AdvanceMovie_btn.config(state=DISABLED if active else NORMAL)
    if except_button != Rewind_btn:
        Rewind_btn.config(state=DISABLED if active else NORMAL)
    if except_button != FastForward_btn:
        FastForward_btn.config(state=DISABLED if active else NORMAL)
    if except_button != Start_btn:
        Start_btn.config(state=DISABLED if active else NORMAL)
    if except_button != PosNeg_btn:
        PosNeg_btn.config(state=DISABLED if active else NORMAL)
    if except_button != Focus_btn:
        Focus_btn.config(state=DISABLED if active else NORMAL)
    if except_button != Start_btn:
        Start_btn.config(state=DISABLED if active else NORMAL)
    if except_button != Exit_btn:
        Exit_btn.config(state=DISABLED if active else NORMAL)
    if except_button != film_type_S8_btn:
        film_type_S8_btn.config(state=DISABLED if active else NORMAL)
    if except_button != film_type_R8_btn:
        film_type_R8_btn.config(state=DISABLED if active else NORMAL)


def advance_movie():
    global AdvanceMovieActive
    global save_bg
    global save_fg
    global SimulatedRun

    # Update button text
    if not AdvanceMovieActive:  # Advance movie is about to start...
        AdvanceMovie_btn.config(text='Stop movie', bg='red',
                                fg='white')  # ...so now we propose to stop it in the button test
    else:
        AdvanceMovie_btn.config(text='Movie forward', bg=save_bg,
                                fg=save_fg)  # Otherwise change to default text to start the action
    AdvanceMovieActive = not AdvanceMovieActive
    # Send instruction to Arduino
    if not SimulatedRun:
        i2c.write_byte_data(16, 30, 0)

    # Enable/Disable related buttons
    button_status_change_except(AdvanceMovie_btn, AdvanceMovieActive)


def rewind_movie():
    global RewindMovieActive
    global SimulatedRun
    global RewindErrorOutstanding
    global save_bg
    global save_fg

    # Before proceeding, get confirmation from user that fild is correctly routed
    if not RewindMovieActive:  # Ask only when rewind is not ongoing
        # Disable preview to make tkinter dialogs visible
        hide_preview()
        answer = tk.messagebox.askyesno(title='Security check ',
                                             message='Have you routed the film via the upper path?')
        display_preview()
        if not answer:
            return()
    else:
        if RewindErrorOutstanding:
            hide_preview()
            tk.messagebox.showerror(title='Error during rewind',
                                         message='It seems there is film loaded via filmgate. \
                                         Please route it via upper path.')
            display_preview()

    # Update button text
    if not RewindMovieActive:  # Rewind movie is about to start...
        Rewind_btn.config(text='Stop\n<<', bg='red', fg='white')  # ...so now we propose to stop it in the button test
    else:
        Rewind_btn.config(text='<<', bg=save_bg, fg=save_fg)  # Otherwise change to default text to start the action
    # Send instruction to Arduino
    RewindMovieActive = not RewindMovieActive

    # Enable/Disable related buttons
    button_status_change_except(Rewind_btn, RewindMovieActive)

    if RewindErrorOutstanding:
        RewindErrorOutstanding = False
    else:
        time.sleep(0.2)
        if not SimulatedRun:
            i2c.write_byte_data(16, 60, 0)

        # Invoke rewind_loop a first time shen rewind starts
        if RewindMovieActive:
            win.after(5, rewind_loop)


def rewind_loop():
    global RewindMovieActive
    global SimulatedRun
    global RewindErrorOutstanding

    if RewindMovieActive:
        # Invoke rewind_loop one more time, as long as rewind is ongoing
        if not RewindErrorOutstanding:
            win.after(5, rewind_loop)
        else:
            rewind_movie()


def fast_forward_movie():
    global FastForwardActive
    global SimulatedRun
    global FastForwardErrorOutstanding
    global save_bg
    global save_fg

    # Before proceeding, get confirmation from user that fild is correctly routed
    if not FastForwardActive:  # Ask only when rewind is not ongoing
        # Disable preview to make tkinter dialogs visible
        hide_preview()
        answer = tk.messagebox.askyesno(title='Security check ',
                                             message='Have you routed the film via the upper path?')
        display_preview()
        if not answer:
            return ()
    else:
        if FastForwardErrorOutstanding:
            hide_preview()
            tk.messagebox.showerror(title='Error during fast forward',
                                         message='It seems there is film loaded via filmgate. \
                                         Please route it via upper path.')
            display_preview()

    # Update button text
    if not FastForwardActive:  # Fast-forward movie is about to start...
        FastForward_btn.config(text='Stop\n>>', bg='red',
                               fg='white')  # ...so now we propose to stop it in the button test
    else:
        FastForward_btn.config(text='>>', bg=save_bg,
                               fg=save_fg)  # Otherwise change to default text to start the action
    FastForwardActive = not FastForwardActive

    # Enable/Disable related buttons
    button_status_change_except(FastForward_btn, FastForwardActive)

    if FastForwardErrorOutstanding:
        FastForwardErrorOutstanding = False
    else:
        # Send instruction to Arduino
        time.sleep(0.2)
        if not SimulatedRun:
            i2c.write_byte_data(16, 80, 0)
        # Invoke fast_forward_loop a first time shen fast-forward starts
        if FastForwardActive:
            win.after(5, fast_forward_loop)


def fast_forward_loop():
    global FastForwardActive
    global SimulatedRun
    global FastForwardErrorOutstanding

    if FastForwardActive:
        # Invoke fast_forward_loop one more time, as long as rewind is ongoing
        if not FastForwardErrorOutstanding:
            win.after(5, fast_forward_loop)
        else:
            fast_forward_movie()


def draw_preview_image(preview_image):
    global draw_capture_label
    global preview_border_frame
    global PreviewAreaImage

    preview_image = preview_image.resize((844, 634))
    PreviewAreaImage = ImageTk.PhotoImage(preview_image)
    # The Label widget is a standard Tkinter widget used to display a text or image on the screen.
    draw_capture_label = tk.Label(preview_border_frame, image=PreviewAreaImage)
    # The Pack geometry manager packs widgets in rows or columns.
    draw_capture_label.place(x=0, y=0)


def single_step_movie():
    global SimulatedRun
    global camera
    global PreviewMode

    if not SimulatedRun:
        i2c.write_byte_data(16, 40, 0)

        if PreviewMode == PreviewType.CAPTURE_ALL or PreviewMode == PreviewType.CAPTURE_PARTIAL:
            # If no preview, capture frame in memory and display it
            # Single step is not a critical operation, waiting 100ms for it to happen should be enough
            # No need to implement confirmation from Arduino, as we have for regular capture during scan
            time.sleep(0.1)
            single_step_image = camera.capture_image("main")
            draw_preview_image(single_step_image)


def emergency_stop():
    global SimulatedRun
    if not SimulatedRun:
        i2c.write_byte_data(16, 90, 0)


def update_rpi_temp():
    global SimulatedRun
    global RPiTemp
    if not SimulatedRun:
        file = open('/sys/class/thermal/thermal_zone0/temp', 'r')
        temp_str = file.readline()
        file.close()
        RPiTemp = int(int(temp_str) / 100) / 10


def negative_capture():
    global NegativeCaptureActive
    global SimulatedRun
    global PosNeg_btn

    NegativeCaptureActive = not NegativeCaptureActive
    SessionData["NegativeCaptureActive"] = str(NegativeCaptureActive)
    PosNeg_btn.config(text='Positive image' if NegativeCaptureActive else 'Negative image')

    if not SimulatedRun:
        if IsPiCamera2:
            # Terrible colors with these values, need to tune
            if NegativeCaptureActive:
                # camera.image_effect = 'negative'
                camera.set_controls({"ColourGains": (1.0, 1.0), "ColourCorrectionMatrix": (-1,0,0,0,-1,0,0,0,-1)})
            else:
                # camera.image_effect = 'none'
                camera.set_controls({"ColourGains": (1.0, 1.0), "ColourCorrectionMatrix": (1,0,0,0,1,0,0,0,1)})
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
    global save_bg
    global save_fg
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


def change_preview_status():
    global win
    global PreviewMode
    global PreviewStatus
    global PostviewModule
    global PostviewCounter
    global capture_config
    global preview_config

    choice = PreviewStatus.get()
    if choice == 1:
        PreviewMode = PreviewType.CAMERA_PREVIEW
        SessionData["PreviewMode"] = PreviewMode.name
    elif choice == 2:
        PreviewMode = PreviewType.NO_PREVIEW
        SessionData["PreviewMode"] = PreviewMode.name
    elif choice == 3:
        PreviewMode = PreviewType.CAPTURE_ALL
        PostviewModule = 1
        SessionData["PreviewMode"] = PreviewMode.name
    elif choice == 4:
        PreviewMode = PreviewType.CAPTURE_PARTIAL
        PostviewModule = PostviewModulePartial
        SessionData["PreviewMode"] = PreviewMode.name

    if not SimulatedRun:
        if PreviewMode == PreviewType.CAMERA_PREVIEW:
            if IsPiCamera2:
                camera.stop_preview()
                camera.start_preview(Preview.QTGL, x=PreviewWinX, y=PreviewWinY, width=840, height=720)
                time.sleep(0.1)
                camera.switch_mode(preview_config)
                #self.canvas.create_rectangle(90, 75, 840, 720, fill="RED")
            else:
                camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))
        else:
            if IsPiCamera2:
                camera.stop_preview()
                camera.start_preview(False)
                time.sleep(0.1)
                camera.switch_mode(capture_config)
            else:
                camera.stop_preview()



def set_s8():
    global SimulatedRun
    global film_type_R8_btn, film_type_S8_btn

    film_type_S8_btn.config(relief=SUNKEN)
    film_type_R8_btn.config(relief=RAISED)
    SessionData["FilmType"] = "S8"
    time.sleep(0.2)
    if not SimulatedRun:
        i2c.write_byte_data(16, 19, 0)


def set_r8():
    global SimulatedRun
    global film_type_R8_btn, film_type_S8_btn

    film_type_R8_btn.config(relief=SUNKEN)
    film_type_S8_btn.config(relief=RAISED)
    SessionData["FilmType"] = "R8"
    time.sleep(0.2)
    if not SimulatedRun:
        i2c.write_byte_data(16, 18, 0)

def film_hole_up():
    global film_hole_frame, FilmHoleY
    if FilmHoleY > 38:
        FilmHoleY -= 4
    film_hole_frame.place(x=4, y=FilmHoleY)
    SessionData["FilmHoleY"] = str(FilmHoleY)

def film_hole_down():
    global film_hole_frame, FilmHoleY
    if FilmHoleY < 758:
        FilmHoleY += 3 # Intentionally different from button up, to allow eventual fine tunning
    film_hole_frame.place(x=4, y=FilmHoleY)
    SessionData["FilmHoleY"] = str(FilmHoleY)

def capture():
    global CurrentDir
    global CurrentFrame
    global SessionData
    global CurrentExposure
    global PreviousCurrentExposure
    global SimulatedRun
    global raw_simulated_capture_image
    global simulated_capture_image
    global draw_capture_label
    global PostviewCounter
    global PostviewModule
    global ExposureAdaptPause
    global CurrentAwbAuto
    global AwbPause
    global PreviousGainRed
    global PreviousGainBlue
    global PreviewMode


    os.chdir(CurrentDir)

    # Wait for auto exposure to adapt only if allowed
    if CurrentExposure == 0 and ExposureAdaptPause:
        while True:  # In case of exposure change, give time for the camera to adapt
            if IsPiCamera2:
                metadata = camera.capture_metadata()
                aux_current_exposure = metadata["ExposureTime"]
            else:
                aux_current_exposure = camera.exposure_speed
            # With PiCamera2, exposure was changing too often, so level changed from 1000 to 2000, then to 4000
            if abs(aux_current_exposure - PreviousCurrentExposure) > 4000:
                curtime = time.ctime()
                aux_exposure_str = "Auto (" + str(round((aux_current_exposure - 20000) / 2000)) + ")"
                print(
                    f"{curtime} - Automatic exposure: Waiting for camera to adapt \
                    ({aux_current_exposure},{aux_exposure_str})")
                exposure_frame_value_label.config(text=aux_exposure_str)
                PreviousCurrentExposure = aux_current_exposure
                win.update()
                time.sleep(0.2)
            else:
                break

    # Wait for auto white balance to adapt only if allowed
    if CurrentAwbAuto and AwbPause:
        while True:  # In case of exposure change, give time for the camera to adapt
            if IsPiCamera2:
                metadata = camera.capture_metadata()
                camera_colour_gains = metadata["ColourGains"]
                aux_gain_red = camera_colour_gains[0]
                aux_gain_blue = camera_colour_gains[1]
            else:
                aux_gain_red = camera.awb_gains[0]
                aux_gain_blue = camera.awb_gains[1]

            if round(aux_gain_red,2) != round(PreviousGainRed,2) or round(aux_gain_blue,2) != round(PreviousGainBlue,2):
                curtime = time.ctime()
                aux_gains_str = "Auto (" + str(round(aux_gain_red,2)) + ", " + str(round(aux_gain_blue,2)) + ")"
                print(
                    f"{curtime} - Automatic Wait Balance: Waiting for camera to adapt {aux_gains_str})")
                colour_gains_red_value_label.config(text=str(round(aux_gain_red,1)))
                colour_gains_blue_value_label.config(text=str(round(aux_gain_blue,1)))
                PreviousGainRed = aux_gain_red
                PreviousGainBlue = aux_gain_blue
                win.update()
                time.sleep(0.2)
            else:
                break


    if not SimulatedRun:
        if IsPiCamera2:
            if PreviewMode == PreviewType.CAMERA_PREVIEW:
                camera.switch_mode_and_capture_file(capture_config, 'picture-%05d.jpg' % CurrentFrame)
            else:
                # Allow time to stabilize image, too fast with PiCamera2 when no preview.
                # Need to refine this (shorter time, Arduino specific slowdown?)
                time.sleep(0.1)  # 100 ms seems OK. Tried with 50 and some frames were blurry
                #camera.capture_file('picture-%05d.jpg' % CurrentFrame)
                captured_snapshot = camera.capture_image("main")
                captured_snapshot.save('picture-%05d.jpg' % CurrentFrame)

        else:
            camera.capture('picture-%05d.jpg' % CurrentFrame, quality=100)

        # Treatment for postview common for Picamera2 and legacy
        if PreviewMode == PreviewType.CAPTURE_ALL or PreviewMode == PreviewType.CAPTURE_PARTIAL:
            # Mitigation when preview is disabled to speed up things in PiCamera2
            # Warning: Displaying the image just captured also has a cost in speed terms
            PostviewCounter += 1
            PostviewCounter %= PostviewModule
            if PostviewCounter == 0:
                # Even if there's no gain using postview in PiCamera legacy, support is implemented
                # to allow comparing same modes with PiCamera2. So now, for the case of PiCamera legacy,
                # we need to get the captured image in memory, by reading it from disk (recapturing it 
                # in memory directly implies importing yet another library so, no thanks)
                if not IsPiCamera2:
                    captured_snapshot = Image.open('picture-%05d.jpg' % CurrentFrame)

                #raw_simulated_capture_image = Image.open('picture-%05d.jpg' % CurrentFrame)
                #draw_preview_image(raw_simulated_capture_image)
                draw_preview_image(captured_snapshot)

    SessionData["CurrentDate"] = str(datetime.now())
    SessionData["CurrentFrame"] = str(CurrentFrame)


def start_scan_simulated():
    global CurrentDir
    global CurrentFrame
    global ScanOngoing
    global CurrentScanStartFrame
    global CurrentScanStartTime
    global save_bg
    global save_fg
    global simulated_captured_frame_list
    global simulated_images_in_list

    if not ScanOngoing and BaseDir == CurrentDir:
        tk.messagebox.showerror("Error!",
                                     "Please specify a folder where to retrieve captured images for scan simulation.")
        return

    if not ScanOngoing:  # Scanner session to be started
        Start_btn.config(text="STOP Scan", bg='red', fg='white')
    else:
        Start_btn.config(text="START Scan", bg=save_bg, fg=save_fg)

    ScanOngoing = not ScanOngoing

    # Enable/Disable related buttons
    button_status_change_except(Start_btn, ScanOngoing)

    # Invoke capture_loop  a first time shen scan starts
    if ScanOngoing:
        # Get list of previously captured frames for scan simulation
        simulated_captured_frame_list = os.listdir(CurrentDir)
        simulated_captured_frame_list.sort()
        simulated_images_in_list = len(simulated_captured_frame_list)
        win.after(500, capture_loop_simulated)


def capture_loop_simulated():
    global CurrentDir
    global CurrentFrame
    global CurrentExposure
    global FramesPerMinute
    global NewFrameAvailable
    global ScanOngoing
    global preview_border_frame
    global raw_simulated_capture_image
    global simulated_capture_image
    global draw_capture_label
    global simulated_captured_frame_list
    global simulated_images_in_list

    if ScanOngoing:
        os.chdir(CurrentDir)
        curtime = time.ctime()
        frame_to_display = CurrentFrame % simulated_images_in_list
        filename, ext = os.path.splitext(simulated_captured_frame_list[frame_to_display])
        if ext == '.jpg':
            print(f"{curtime} - Simulated scan: ({CurrentFrame},{simulated_captured_frame_list[frame_to_display]})")
            raw_simulated_capture_image = Image.open(simulated_captured_frame_list[frame_to_display])
            draw_preview_image(raw_simulated_capture_image)

        CurrentFrame += 1
        SessionData["CurrentFrame"] = str(CurrentFrame)

        # Update number of captured frames
        Scanned_Images_number_label.config(text=str(CurrentFrame))
        # Update Frames per Minute
        scan_period_time = datetime.now() - CurrentScanStartTime
        scan_period_seconds = scan_period_time.total_seconds()
        scan_period_frames = CurrentFrame - CurrentScanStartFrame
        if scan_period_seconds < 10:
            Scanned_Images_fpm.config(text="??")
        else:
            FramesPerMinute = scan_period_frames * 60 / scan_period_seconds
            Scanned_Images_fpm.config(text=str(int(FramesPerMinute)))
        win.update()

        # Invoke capture_loop one more time, as long as scan is ongoing
        win.after(500, capture_loop_simulated)


def start_scan():
    global CurrentDir
    global CurrentFrame
    global SessionData
    global ScanOngoing
    global CurrentScanStartFrame
    global CurrentScanStartTime
    global save_bg
    global save_fg
    global SimulatedRun

    if not ScanOngoing and BaseDir == CurrentDir:
        hide_preview()
        tk.messagebox.showerror("Error!", "Please specify a folder where to store the captured images.")
        display_preview()
        return

    if not ScanOngoing:  # Scanner session to be started
        Start_btn.config(text="STOP Scan", bg='red', fg='white')
        SessionData["CurrentDate"] = str(datetime.now())
        SessionData["CurrentDir"] = CurrentDir
        SessionData["CurrentFrame"] = str(CurrentFrame)
        CurrentScanStartTime = datetime.now()
        CurrentScanStartFrame = CurrentFrame
    else:
        Start_btn.config(text="START Scan", bg=save_bg, fg=save_fg)
        CurrentScanStartFrame = CurrentFrame

    ScanOngoing = not ScanOngoing

    # Enable/Disable related buttons
    button_status_change_except(Start_btn, ScanOngoing)

    # Send command to Arduino to stop/start scan (as applicable, Arduino keeps its own status)
    if not SimulatedRun and ScanOngoing:
        i2c.write_byte_data(16, 10, 0)

    # Invoke capture_loop a first time shen scan starts
    if ScanOngoing:
        win.after(5, capture_loop)


def capture_loop():
    global CurrentDir
    global CurrentFrame
    global CurrentExposure
    global SessionData
    global FramesPerMinute
    global NewFrameAvailable
    global ScanProcessError
    global ScanOngoing
    global SimulatedRun

    if ScanOngoing:
        if NewFrameAvailable:
            CurrentFrame += 1
            capture()
            if not SimulatedRun:
                try:
                    # Set NewFrameAvailable to False here, to avoid overwriting new frame from arduino
                    NewFrameAvailable = False
                    i2c.write_byte_data(16, 12, 0)  # Tell Arduino to move to next frame
                except IOError:
                    CurrentFrame -= 1
                    NewFrameAvailable = True  # Set NewFrameAvailable to True to repeat next time
                    # Log error to console
                    curtime = time.ctime()
                    print(f"{curtime} - Error while telling Arduino to move to next Frame.")
                    print(f"    Frame {CurrentFrame} capture to be tried again.")
                    win.after(5, capture_loop)
                    return

            SessionData["CurrentDate"] = str(datetime.now())
            SessionData["CurrentDir"] = CurrentDir
            SessionData["CurrentFrame"] = str(CurrentFrame)
            if CurrentExposureStr == "Auto":
                SessionData["CurrentExposure"] = CurrentExposureStr
            else:
                SessionData["CurrentExposure"] = str(CurrentExposure)
            with open(PersistedDataFilename, 'w') as f:
                json.dump(SessionData, f)

            # Update number of captured frames
            Scanned_Images_number_label.config(text=str(CurrentFrame))
            # Update Frames per Minute
            scan_period_time = datetime.now() - CurrentScanStartTime
            scan_period_seconds = scan_period_time.total_seconds()
            scan_period_frames = CurrentFrame - CurrentScanStartFrame
            if scan_period_seconds < 10:
                Scanned_Images_fpm.config(text="??")
            else:
                FramesPerMinute = scan_period_frames * 60 / scan_period_seconds
                Scanned_Images_fpm.config(text=str(int(FramesPerMinute)))
            win.update()
        elif ScanProcessError:
            curtime = time.ctime()
            print(f"{curtime} - Error during scan process.")
            ScanProcessError = False
            if ScanOngoing:
                start_scan()  # If scan ongoing (not single step) call start_scan to get back to normal state
            return
        # Invoke capture_loop one more time, as long as scan is ongoing
        win.after(0, capture_loop)


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
            rounded_temp = round(RPiTemp*1.8+32,1)
            temp_str = str(rounded_temp) + 'ºF'
        else:
            temp_str = str(RPiTemp) + 'º'
        RPi_temp_value_label.config(text=str(temp_str))
        win.update()
        last_temp = RPiTemp
        LastTempInFahrenheit = TempInFahrenheit

    win.after(1000, temperature_loop)


def arduino_listen_loop():  # Waits for Arduino communicated events adn dispatches accordingly
    global NewFrameAvailable
    global RewindErrorOutstanding
    global FastForwardErrorOutstanding
    global ArduinoTrigger
    global SimulatedRun
    global ScanProcessError
    global ScanOngoing

    if not SimulatedRun:
        try:
            ArduinoTrigger = i2c.read_byte_data(16, 0)
        except IOError:
            # Log error to console
            curtime = time.ctime()
            print(f"{curtime} - Error while checking incoming event ({ArduinoTrigger}) from Arduino. Will check again.")

    if ArduinoTrigger == 11:  # New Frame available
        NewFrameAvailable = True
    elif ArduinoTrigger == 12:  # Error during scan
        print("Received scan error from Arduino")
        ScanProcessError = True
    elif ArduinoTrigger == 61:  # Error during Rewind
        RewindErrorOutstanding = True
        print("Received rewind error from Arduino")
    elif ArduinoTrigger == 81:  # Error during FastForward
        FastForwardErrorOutstanding = True
        print("Received fast forward error from Arduino")

    ArduinoTrigger = 0

    win.after(5, arduino_listen_loop)


def on_form_event(test):
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
            print('%s=%s' % (key, getattr(event, key)))
    print()
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

    warn_again_from_toplevel = tk.BooleanVar()
    preview_warning = Toplevel(win)
    preview_warning.title('*** PiCamera2 Preview warning ***')
    preview_warning.geometry('500x400')
    preview_warning.geometry('+250+250')  # setting the position of the window
    preview_label = Label(preview_warning,text='\rThe preview mode provided by PiCamera2 for use in '\
                                               'X-Window environment is not really usable for '\
                                               'T-Scann 8 during the film scanning process.\r\n'\
                                               'Compared to the preview provided by PiCamera legacy it is:\r'\
                                               '- Much slower (due to context switch between preview/capture)\r'\
                                               '- Very imprecise (preview does not match captured image)\r\n'\
                                               'PiCamera2 preview mode can and should still be used in some '\
                                               'cases (typically for the focus procedure), however for the '\
                                               'scanning process one of the other three provided modes is recommended:\r'\
                                               '- Capture 1/1: Displays each frame post-capture (legacy-like speed)\r'\
                                               '- Capture 1/4: Displays one of four frames post-capture (faster)\r'\
                                               '- None: No preview at all (fastest)\r\n', wraplength=450, justify=LEFT)
    preview_warn_again = tk.BooleanVar(value=PreviewWarnAgain)
    preview_btn = Button(preview_warning, text="OK", width=2, height=1, command=close_preview_warning)
    preview_checkbox = tk.Checkbutton(preview_warning, text='Do not show this warning again', height=1, variable=preview_warn_again, onvalue=False, offvalue=True, command=preview_do_not_warn_again_selection)

    preview_label.pack(side=TOP)
    preview_btn.pack(side=TOP, pady=10)
    preview_checkbox.pack(side=LEFT)

    preview_warning.mainloop()



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
    global PreviewMode
    global PostviewModule
    global preview_radio1, preview_radio2, preview_radio3, preview_radio4
    global PreviewWarnAgain
    global TempInFahrenheit
    global temp_in_fahrenheit_checkbox
    global PersistedDataLoaded

    if PersistedDataLoaded:
        print("SessionData loaded from disk:")
        if 'CurrentDate' in SessionData:
            print(SessionData["CurrentDate"])
        if 'FilmHoleY' in SessionData:
            print(SessionData["FilmHoleY"])
            FilmHoleY = int(SessionData["FilmHoleY"])
            film_hole_frame.place(x=4, y=FilmHoleY)
        if 'PreviewMode' in SessionData:
            print(SessionData["PreviewMode"])
            PreviewMode = PreviewType[SessionData["PreviewMode"]]
            if PreviewMode.name == "NO_PREVIEW":
                preview_radio1.select()
            elif PreviewMode.name == "CAMERA_PREVIEW":
                preview_radio2.select()
            elif PreviewMode.name == "CAPTURE_ALL":
                PostviewModule = 1
                preview_radio3.select()
            elif PreviewMode.name == "CAPTURE_PARTIAL":
                PostviewModule = PostviewModulePartial
                preview_radio4.select()
            if PreviewMode.name != "CAMERA_PREVIEW":    # This is the default, no action needed if this was selected before
                change_preview_status()
        if 'PreviewWarnAgain' in SessionData:
            print(SessionData["PreviewWarnAgain"])
            PreviewWarnAgain = eval(SessionData["PreviewWarnAgain"])
        if 'TempInFahrenheit' in SessionData:
            print(SessionData["TempInFahrenheit"])
            TempInFahrenheit = eval(SessionData["TempInFahrenheit"])
            if (TempInFahrenheit):
                temp_in_fahrenheit_checkbox.select()

def load_session_data():
    global SessionData
    global CurrentExposure, CurrentExposureStr, ExposureAdaptPause
    global CurrentDir
    global CurrentFrame
    global folder_frame_target_dir
    global NegativeCaptureActive, PosNeg_btn
    global CurrentAwbAuto, AwbPause, gain_red, gain_blue
    global awb_wait_checkbox
    global colour_gains_red_value_label, colour_gains_blue_value_label
    global film_type_R8_btn, film_type_S8_btn
    global PersistedDataLoaded

    if PersistedDataLoaded:
        hide_preview()
        confirm = tk.messagebox.askyesno(title='Persisted session data exist',
                                              message='It seems T-Scann 8 was interrupted during the last session.\
                                                        \r\nDo you want to continue from where it was stopped?')
        if confirm:
            print("SessionData loaded from disk:")
            if 'CurrentDate' in SessionData:
                print(SessionData["CurrentDate"])
            if 'CurrentDir' in SessionData:
                print(SessionData["CurrentDir"])
                CurrentDir = SessionData["CurrentDir"]
                folder_frame_target_dir.config(text=CurrentDir)
            if 'CurrentFrame' in SessionData:
                print(SessionData["CurrentFrame"])
                CurrentFrame = int(SessionData["CurrentFrame"])
                Scanned_Images_number_label.config(text=SessionData["CurrentFrame"])
            if 'FilmType' in SessionData:
                print(SessionData["FilmType"])
                if SessionData["FilmType"] == "R8":
                    if not SimulatedRun:
                        i2c.write_byte_data(16, 18, 0)
                    film_type_R8_btn.config(relief=SUNKEN)
                    film_type_S8_btn.config(relief=RAISED)
                elif SessionData["FilmType"] == "S8":
                    if not SimulatedRun:
                        i2c.write_byte_data(16, 19, 0)
                    film_type_R8_btn.config(relief=RAISED)
                    film_type_S8_btn.config(relief=SUNKEN)
            if 'NegativeCaptureActive' in SessionData:
                NegativeCaptureActive = eval(SessionData["NegativeCaptureActive"])
                PosNeg_btn.config(text='Positive image' if NegativeCaptureActive else 'Negative image')
            if 'CurrentExposure' in SessionData:
                print(SessionData["CurrentExposure"])
                CurrentExposureStr = SessionData["CurrentExposure"]
                if CurrentExposureStr == "Auto":
                    CurrentExposure = 0
                else:
                    CurrentExposure = int(CurrentExposureStr)
                    CurrentExposureStr = str(round((CurrentExposure - 20000) / 2000))
                exposure_frame_value_label.config(text=CurrentExposureStr)
            if 'ExposureAdaptPause' in SessionData:
                print(SessionData["ExposureAdaptPause"])
                ExposureAdaptPause = eval(SessionData["ExposureAdaptPause"])
                if (ExposureAdaptPause):
                    auto_exp_wait_checkbox.select()
            if 'CurrentAwbAuto' in SessionData:
                print(SessionData["CurrentAwbAuto"])
                CurrentAwbAuto = eval(SessionData["CurrentAwbAuto"])
                if not CurrentAwbAuto:  # AWB enabled by defautl, if not enabled, call button action to disable and perform associated actions
                    CurrentAwbAuto = True   # Set back to true, as button actino will invert the value
                    colour_gain_auto()
                awb_frame.config(text='Automatic White Balance ON' if CurrentAwbAuto else 'Automatic White Balance OFF')
            if 'AwbPause' in SessionData:
                print(SessionData["AwbPause"])
                AwbPause = eval(SessionData["AwbPause"])
                if AwbPause:
                    awb_wait_checkbox.select()
            if 'gain_red' in SessionData:
                print(SessionData["gain_red"])
                gain_red = float(SessionData["gain_red"])
                colour_gains_red_value_label.config(text=str(round(gain_red, 1)))
            if 'gain_blue' in SessionData:
                print(SessionData["gain_blue"])
                gain_blue = float(SessionData["gain_blue"])
                colour_gains_blue_value_label.config(text=str(round(gain_blue, 1)))
        display_preview()


def tscann8_init():
    global win
    global camera
    global CurrentExposure
    global CurrentExposureStr
    global TopWinX
    global TopWinY
    global preview_border_frame
    global i2c
    global WinInitDone
    global CurrentDir
    global CurrentFrame
    global ZoomSize
    global capture_config
    global preview_config
    global draw_capture_label
    global PreviewAreaImage
    global PreviewMode

    if not SimulatedRun:
        i2c = smbus.SMBus(1)

    win = Tk()  # creating the main window and storing the window object in 'win'
    win.title('T-Scann 8')  # setting title of the window
    win.geometry('1100x830')  # setting the size of the window
    win.geometry('+50+50')  # setting the position of the window
    # Prevent window resize
    win.minsize(1100, 830)
    win.maxsize(1100, 830)
    if (Experimental):
        win.geometry('1100x950')  # setting the size of the window
        win.minsize(1100, 950)
        win.maxsize(1100, 950)

    if SimulatedRun:
        win.wm_title(string='*** T-Scann 8 SIMULATED RUN * NOT OPERATIONAL ***')

    win.update_idletasks()

    # Get Top window coordinates
    TopWinX = win.winfo_x()
    TopWinY = win.winfo_y()

    WinInitDone = True

    # Create a frame to add a border to the preview
    preview_border_frame = Frame(win, width=844, height=634, bg='dark grey')
    preview_border_frame.pack()
    preview_border_frame.place(x=38, y=38)
    # Also a label to draw images when preview is not used
    draw_capture_label = tk.Label(preview_border_frame)

    if not SimulatedRun:
        if IsPiCamera2:
            camera = Picamera2()
            camera.start_preview(Preview.QTGL, x=PreviewWinX, y=PreviewWinY, width=840, height=720)
            capture_config = camera.create_still_configuration(main={"size": (2028, 1520)},
                                                               transform=Transform(hflip=True))
            preview_config = camera.create_preview_configuration({"size": (840, 720)}, transform=Transform(hflip=True))
            if PreviewMode == PreviewType.CAMERA_PREVIEW:
                camera.configure(preview_config)
            else:
                camera.configure(capture_config)
            camera.set_controls({"ExposureTime": CurrentExposure, "AnalogueGain": 1.0})
            camera.set_controls({"AwbEnable": 1})
            #camera.set_controls({"ColourGains": (2.4, 2.8)}) # Red 2.4, Blue 2.8 seem to be OK
            camera.start(show_preview=True)
            ZoomSize = camera.capture_metadata()['ScalerCrop'][2:]
        else:
            camera = picamera.PiCamera()
            camera.sensor_mode = 3
            # settings resolution higher for HQ camera 2028, 1520
            camera.resolution = (2028, 1520)  # not supported in picamera2
            camera.iso = 100  # not supported in picamera2
            camera.sharpness = 100
            camera.hflip = True
            camera.awb_mode = 'auto'
            #camera.awb_gains = (3.5, 1.0)
            camera.start_preview(fullscreen=False, window=(90, 75, 840, 720))
            camera.shutter_speed = CurrentExposure

# Enable events on windows movements, to allow preview to follow
    # lblText = tk.Label(win, text='')
    # lblText.pack()
    if not SimulatedRun and not IsPiCamera2:
        win.bind('<Configure>', on_form_event)


def build_ui():
    global win
    global Experimental
    global AdvanceMovie_btn
    global SingleStep_btn
    global PosNeg_btn
    global DisablePreview_btn
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
    global exposure_frame_value_label
    global film_type_S8_btn
    global film_type_R8_btn
    global save_bg, save_fg
    global PreviewStatus
    global auto_exposure_change_pause
    global auto_exp_wait_checkbox
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
    global ccm_11,ccm_12,ccm_13,ccm_21,ccm_22,ccm_23,ccm_31,ccm_32,ccm_33
    global OpenFolder_btn
    global film_hole_frame, FilmHoleY
    global preview_radio1, preview_radio2, preview_radio3, preview_radio4
    global temp_in_fahrenheit_checkbox

    # Create horizontal button row at bottom
    # Advance movie (slow forward through filmgate)
    AdvanceMovie_btn = Button(win, text="Movie Forward", width=8, height=3, command=advance_movie,
                              activebackground='green', activeforeground='white', wraplength=80)
    AdvanceMovie_btn.place(x=30, y=710)
    # Once first button created, get default colors, to revert when we change them
    save_bg = AdvanceMovie_btn['bg']
    save_fg = AdvanceMovie_btn['fg']

    # Advance one single frame
    SingleStep_btn = Button(win, text="Single Step", width=8, height=3, command=single_step_movie,
                            activebackground='green', activeforeground='white', wraplength=80)
    SingleStep_btn.place(x=130, y=710)

    # Rewind movie (via upper path, outside of film gate)
    Rewind_btn = Button(win, text="<<", font=("Arial", 16), width=2, height=2, command=rewind_movie,
                        activebackground='green', activeforeground='white', wraplength=80)
    Rewind_btn.place(x=230, y=710)
    # Fast Forward movie (via upper path, outside of film gate)
    FastForward_btn = Button(win, text=">>", font=("Arial", 16), width=2, height=2, command=fast_forward_movie,
                             activebackground='green', activeforeground='white', wraplength=80)
    FastForward_btn.place(x=290, y=710)

    # Unlock reels button (to load film, rewind, etc)
    Free_btn = Button(win, text="Unlock Reels", width=8, height=3, command=set_free_mode, activebackground='green',
                      activeforeground='white', wraplength=80)
    Free_btn.place(x=350, y=710)

    # Switch Positive/negative modes
    PosNeg_btn = Button(win, text="Negative image", width=8, height=3, command=negative_capture, activebackground='green',
                        activeforeground='white', wraplength=80)
    PosNeg_btn.place(x=450, y=710)

    # Activate focus zoom, to facilitate focusing the camera
    Focus_btn = Button(win, text="Focus Zoom ON", width=8, height=3, command=set_focus_zoom, activebackground='green',
                       activeforeground='white', wraplength=80)
    Focus_btn.place(x=550, y=710)

    # Pi Camera preview selection: Preview (by PiCamera), disabled, postview (display last captured frame))
    preview_frame = LabelFrame(win, text='Preview', width=8, height=3)
    preview_frame.pack(side=TOP, padx=1, pady=1)
    preview_frame.place(x=650, y=700)

    PreviewStatus=tk.IntVar()
    preview_radio1 = Radiobutton(preview_frame,text="None          ", variable=PreviewStatus, value=2, command=change_preview_status)
    preview_radio1.grid(row=0, column=1)
    preview_radio2 = Radiobutton(preview_frame,text="From camera", variable=PreviewStatus, value=1, command=change_preview_status)
    preview_radio2.grid(row=0, column=2)
    preview_radio2.select()
    preview_radio3 = Radiobutton(preview_frame,text="Capture 1/1", variable=PreviewStatus, value=3, command=change_preview_status)
    preview_radio3.grid(row=1, column=1)
    preview_radio4 = Radiobutton(preview_frame,text="Capture 1/4", variable=PreviewStatus, value=4, command=change_preview_status)
    preview_radio4.grid(row=1, column=2)
    PreviewStatus.set(1)

    # Application Exit button
    Exit_btn = Button(win, text="Exit", width=12, height=5, command=exit_app, activebackground='red',
                      activeforeground='white', wraplength=80)
    Exit_btn.place(x=925, y=700)

    # Create vertical button column at right
    # Start scan button
    if SimulatedRun:
        Start_btn = Button(win, text="START Scan", width=14, height=5, command=start_scan_simulated,
                           activebackground='green', activeforeground='white', wraplength=80)
    else:
        Start_btn = Button(win, text="START Scan", width=14, height=5, command=start_scan, activebackground='green',
                           activeforeground='white', wraplength=80)
    Start_btn.place(x=925, y=40)

    # Create frame to select target folder
    folder_frame = LabelFrame(win, text='Target Folder', width=16, height=8)
    folder_frame.pack()
    folder_frame.place(x=925, y=150)

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
    scanned_images_frame = LabelFrame(win, text='Scanned frames', width=16, height=4)
    scanned_images_frame.pack(side=TOP, padx=1, pady=1)
    scanned_images_frame.place(x=925, y=260)

    Scanned_Images_number_label = Label(scanned_images_frame, text=str(CurrentFrame), font=("Arial", 24), width=5,
                                        height=1)
    Scanned_Images_number_label.pack(side=TOP)

    scanned_images_fpm_frame = Frame(scanned_images_frame, width=16, height=2)
    scanned_images_fpm_frame.pack(side=TOP)
    scanned_images_fpm_label = Label(scanned_images_fpm_frame, text='Frames/Min:', font=("Arial", 8), width=12,
                                     height=1)
    scanned_images_fpm_label.pack(side=LEFT)
    Scanned_Images_fpm = Label(scanned_images_fpm_frame, text=str(FramesPerMinute), font=("Arial", 8), width=8,
                               height=1)
    Scanned_Images_fpm.pack(side=LEFT)

    # Create frame to select exposure value
    exposure_frame = LabelFrame(win, text='Exposure', width=16, height=2)
    exposure_frame.pack(side=TOP)
    exposure_frame.place(x=925, y=350)

    exposure_frame_value_label = Label(exposure_frame, text=CurrentExposureStr, width=8, height=1, font=("Arial", 16))
    exposure_frame_value_label.pack(side=TOP)

    exposure_frame_buttons = Frame(exposure_frame, width=8, height=1)
    exposure_frame_buttons.pack(side=TOP)
    decrease_exp_btn = Button(exposure_frame_buttons, text='-', width=1, height=1, font=("Arial", 16, 'bold'),
                              command=decrease_exp, activebackground='green', activeforeground='white')
    decrease_exp_btn.pack(side=LEFT)
    auto_exp_btn = Button(exposure_frame_buttons, text='A', width=2, height=1, font=("Arial", 16, 'bold'),
                          command=auto_exp, activebackground='green', activeforeground='white')
    auto_exp_btn.pack(side=LEFT)
    increase_exp_btn = Button(exposure_frame_buttons, text='+', width=1, height=1, font=("Arial", 16, 'bold'),
                              command=increase_exp, activebackground='green', activeforeground='white')
    increase_exp_btn.pack(side=LEFT)

    auto_exposure_change_pause = tk.BooleanVar(value=ExposureAdaptPause)
    auto_exp_wait_checkbox = tk.Checkbutton(exposure_frame, text='Adapt. wait', height=1, variable=auto_exposure_change_pause, onvalue=True, offvalue=False, command=auto_exposure_change_pause_selection)
    auto_exp_wait_checkbox.pack(side=TOP)

    # Create frame to select S8/R8 film
    film_type_frame = LabelFrame(win, text='Film type', width=16, height=1)
    film_type_frame.pack(side=TOP)
    film_type_frame.place(x=925, y=490)

    film_type_buttons = Frame(film_type_frame, width=16, height=1)
    film_type_buttons.pack(side=TOP)
    film_type_S8_btn = Button(film_type_buttons, text='S8', width=3, height=1, font=("Arial", 16, 'bold'),
                              command=set_s8, activebackground='green', activeforeground='white',
                              relief=SUNKEN)
    film_type_S8_btn.pack(side=LEFT)
    film_type_R8_btn = Button(film_type_buttons, text='R8', width=3, height=1, font=("Arial", 16, 'bold'),
                              command=set_r8, activebackground='green', activeforeground='white')
    film_type_R8_btn.pack(side=LEFT)

    # Create frame to display RPi temperature
    rpi_temp_frame = LabelFrame(win, text='RPi Temp.', width=8, height=1)
    rpi_temp_frame.pack(side=TOP)
    rpi_temp_frame.place(x=925, y=580)
    temp_str = str(RPiTemp)+'º'
    RPi_temp_value_label = Label(rpi_temp_frame, text=temp_str, font=("Arial", 18), width=1, height=1)
    RPi_temp_value_label.pack(side=TOP, fill='x')

    temp_in_fahrenheit = tk.BooleanVar(value=TempInFahrenheit)
    temp_in_fahrenheit_checkbox = tk.Checkbutton(rpi_temp_frame, text='Fahrenheit   ', height=1, variable=temp_in_fahrenheit, onvalue=True, offvalue=False, command=temp_in_fahrenheit_selection)
    temp_in_fahrenheit_checkbox.pack(side=TOP)

    # Create experimental frame to play with ColourGains
    if Experimental:
        experimental_frame = LabelFrame(win, text='Experimental', width=8, height=5, font=("Arial", 7))
        experimental_frame.pack(side=TOP)
        experimental_frame.place(x=30, y=790)

        awb_frame = LabelFrame(experimental_frame, text='Automatic White Balance ON', width=8, height=1, font=("Arial", 7))
        awb_frame.pack(side=LEFT, padx=5)

        colour_gains_auto_btn= Button(awb_frame,text="AWB OFF", width=6, height=1, command=colour_gain_auto, activebackground='green', activeforeground='white', font=("Arial", 7))
        colour_gains_auto_btn.grid(row=0, column=0)

        auto_white_balance_change_pause = tk.BooleanVar(value=AwbPause)
        awb_wait_checkbox = tk.Checkbutton(awb_frame, text='Adapt. wait', height=1, variable=auto_white_balance_change_pause, onvalue=True, offvalue=False, command=auto_white_balance_change_pause_selection, font=("Arial", 7))
        awb_wait_checkbox.grid(row=1, column=0)

        colour_gains_red_btn_plus = Button(awb_frame,text="Red-", command=colour_gain_red_minus, activebackground='green', activeforeground='white', font=("Arial", 7), state = DISABLED)
        colour_gains_red_btn_plus.grid(row=0, column=1)
        colour_gains_red_btn_minus = Button(awb_frame,text="Red+", command=colour_gain_red_plus, activebackground='green', activeforeground='white', font=("Arial", 7), state = DISABLED)
        colour_gains_red_btn_minus.grid(row=0, column=2)
        colour_gains_red_value_label = Label(awb_frame, text="Auto", width=8, height=1, font=("Arial", 7))
        colour_gains_red_value_label.grid(row=0, column=3)
        colour_gains_blue_btn_plus = Button(awb_frame,text="Blue-", command=colour_gain_blue_minus, activebackground='green', activeforeground='white', font=("Arial", 7), state = DISABLED)
        colour_gains_blue_btn_plus.grid(row=1, column=1)
        colour_gains_blue_btn_minus = Button(awb_frame,text="Blue+", command=colour_gain_blue_plus, activebackground='green', activeforeground='white', font=("Arial", 7), state = DISABLED)
        colour_gains_blue_btn_minus.grid(row=1, column=2)
        colour_gains_blue_value_label = Label(awb_frame, text="Auto", width=8, height=1, font=("Arial", 7))
        colour_gains_blue_value_label.grid(row=1, column=3)

        ccm_11 = StringVar()
        ccm_12 = StringVar()
        ccm_13 = StringVar()
        ccm_21 = StringVar()
        ccm_22 = StringVar()
        ccm_23 = StringVar()
        ccm_31 = StringVar()
        ccm_32 = StringVar()
        ccm_33 = StringVar()
        ccm_frame = LabelFrame(experimental_frame, text='CCM', width=1, height=4, font=("Arial", 7))
        ccm_frame.pack(side=LEFT, padx=5, pady=5)
        matrix_frame = Frame(ccm_frame, width=1, height=1)
        matrix_frame.pack(side=TOP, padx=5)

        ccm_entry_11 = Entry(matrix_frame, textvariable=ccm_11, font=("Arial", 7), width=5)
        ccm_entry_11.grid(row=0, column=0)
        ccm_entry_12 = Entry(matrix_frame, textvariable=ccm_12, font=("Arial", 7), width=5)
        ccm_entry_12.grid(row=0, column=1)
        ccm_entry_13 = Entry(matrix_frame, textvariable=ccm_13, font=("Arial", 7), width=5)
        ccm_entry_13.grid(row=0, column=2)
        ccm_entry_21 = Entry(matrix_frame, textvariable=ccm_21, font=("Arial", 7), width=5)
        ccm_entry_21.grid(row=1, column=0)
        ccm_entry_22 = Entry(matrix_frame, textvariable=ccm_22, font=("Arial", 7), width=5)
        ccm_entry_22.grid(row=1, column=1)
        ccm_entry_23 = Entry(matrix_frame, textvariable=ccm_23, font=("Arial", 7), width=5)
        ccm_entry_23.grid(row=1, column=2)
        ccm_entry_31 = Entry(matrix_frame, textvariable=ccm_31, font=("Arial", 7), width=5)
        ccm_entry_31.grid(row=2, column=0)
        ccm_entry_32 = Entry(matrix_frame, textvariable=ccm_32, font=("Arial", 7), width=5)
        ccm_entry_32.grid(row=2, column=1)
        ccm_entry_33 = Entry(matrix_frame, textvariable=ccm_33, font=("Arial", 7), width=5)
        ccm_entry_33.grid(row=2, column=2)
        ccm_go = Button(ccm_frame,text="Update CCM (KO)", command=ccm_update, activebackground='green', activeforeground='white', font=("Arial", 7), state = NORMAL)
        ccm_go.pack(side=TOP, pady=2)

        if not SimulatedRun:
            metadata = camera.capture_metadata()
            camera_ccm = metadata["ColourCorrectionMatrix"]
            ccm_11.set(round(camera_ccm[0],2))
            ccm_12.set(round(camera_ccm[1],2))
            ccm_13.set(round(camera_ccm[2],2))
            ccm_21.set(round(camera_ccm[3],2))
            ccm_22.set(round(camera_ccm[4],2))
            ccm_23.set(round(camera_ccm[5],2))
            ccm_31.set(round(camera_ccm[6],2))
            ccm_32.set(round(camera_ccm[7],2))
            ccm_33.set(round(camera_ccm[8],2))

        # Open target folder (to me this is useless. Also, gives problem with closure, not as easy at I imagined)
        # Leave it in the experimental area, disabled, just in case it is reused
        openfolder_frame = LabelFrame(experimental_frame, text='Open Folder', width=8, height=2, font=("Arial", 7))
        openfolder_frame.pack(side=LEFT, padx=5)
        OpenFolder_btn = Button(openfolder_frame, text="Open Folder", width=8, height=3, command=open_folder, activebackground='green', activeforeground='white', wraplength=80, state = DISABLED, font=("Arial", 7))
        OpenFolder_btn.pack(side=TOP, padx=5, pady=2)

        # Display marker for film hole
        film_hole_frame = Frame(win, width=1, height=11, bg='black')
        film_hole_frame.pack(side=TOP, padx=1, pady=1)
        film_hole_frame.place(x=4, y=FilmHoleY)
        film_hole_label = Label(film_hole_frame, justify=LEFT, font=("Arial", 8), width=5, height=11, bg='white', fg='white')
        film_hole_label.pack(side=TOP)
        # Up/Down buttons to move marker for film hole
        film_hole_control_frame = LabelFrame(experimental_frame, text="Film hole pos.", width=8, height=2, font=("Arial", 7))
        film_hole_control_frame.pack(side=LEFT, padx=5)
        film_hole_control_up = Button(film_hole_control_frame, text="⇑",width=1, height=1, command=film_hole_up,
                                  activebackground='green', activeforeground='white', font=("Arial", 7))
        film_hole_control_up.pack(side=TOP, padx=2, pady=2)
        film_hole_control_down = Button(film_hole_control_frame, text="⇓",width=1, height=1, command=film_hole_down,
                                  activebackground='green', activeforeground='white', font=("Arial", 7))
        film_hole_control_down.pack(side=TOP, padx=2, pady=2)



def main(argv):
    global SimulatedRun
    global Experimental

    opts, args = getopt.getopt(argv, "sx")

    for opt, arg in opts:
        if opt == '-s':
            SimulatedRun = True
        elif opt  == '-x':
            Experimental = True

    tscann8_init()

    build_ui()

    load_persisted_data_from_disk()

    load_config_data()

    display_preview_warning()

    load_session_data()

    if not SimulatedRun:
        temperature_loop()

    arduino_listen_loop()

    # Main Loop
    win.mainloop()  # running the loop that works as a trigger

    if not SimulatedRun:
        camera.close()


if __name__ == '__main__':
    main(sys.argv[1:])

