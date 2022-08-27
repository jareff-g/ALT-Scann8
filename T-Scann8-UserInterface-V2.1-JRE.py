
# 06/08/2022: 2.1.7: JRE: Add Button for EmergencyStop
# 10/08/2022: JRE: Comment emergency stop button
# 10/08/2022: JRE: After capturing image, if exposure has changed since previous capture wait one sec (to allow camera to adapt in automatic mode)
# 12/08/2022: JRE: Improve automatic exposure adaptation
# 13/08/2022: JRE Implemented detection of fild loaded via FilmGate, to prevent FF/Rewind
# 13/08/2022: JRE Move to 2.1.9
# 14/08/2022: JRE Implemented function to dynamically modify the perforation level threshold
# 27/08/2022: JRE, first attempt at migrating to picamera2
#             - Highlights: Most functionality works fine, but slower (factors to check: SD card, preview mode, save to PNG?)
#		  - Advance Film: OK (not camera related)
#		  - Rewind: OK (not camera related)
#		  - Free wheels: OK (not camera related)
#		  - Negative film: KO, maybe can be done with overlays?
#		  - Focus zoom: OK
#		  - Automatic exposure: OK
#		  - Scan: OK, but slower

# Global variable to isolate Raspberry Pi specific code, to allow basic UI testing on PC
SimulatedRun = False

# Global variable to isolate camera specific code (Picamera vs PiCamera2)
IsPiCamera2 = True

if SimulatedRun:
    print("Not running on Raspbery Pi, simulated run for UI debugging purposes only")
else:
    print("Running on Raspbery Pi")

import tkinter as tk
from tkinter import filedialog

import tkinter.messagebox
import tkinter.simpledialog
from tkinter import *

if SimulatedRun:
    from PIL import ImageTk, Image
else:
    if IsPiCamera2:
        from picamera2 import Picamera2, Preview
        from libcamera import Transform
    else:
        import picamera

import os
import subprocess
import time
import json
if not SimulatedRun:
    import smbus
from datetime import datetime
import sys

if not SimulatedRun:
    i2c = smbus.SMBus(1)

# Global variables
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
NegativeCaptureStatus = False
AdvanceMovieActive = False
RewindMovieActive = False  # SpolaState in original code from Torulf
RewindErrorOutstanding = False
FastForwardActive = False
FastForwardErrorOutstanding = False
OpenFolderActive = False
ScanOngoing = False  # PlayState in original code from Torulf (opposite meaning)
NewFrameAvailable = False   # To be set to true upon reception of Arduino event
ScriptDir = os.path.dirname(sys.argv[0])  # Directory where python scrips run, to store the json file with persistent data
PersistedSessionFilename = os.path.join(ScriptDir,"T-Scann8.json")
ArduinoTrigger = 0
ExitRequested = False
LoopDelay = 0
# Variables to track windows movement adn set preview accordingly
TopWinX = 0
TopWinY = 0
PreviewWinX = 90
PreviewWinY = 75
DeltaX = 0
DeltaY = 0
WinInitDone=False
FolderProcess = 0
PreviewEnabled = True
FramesPerMinute = 0
RPiTemp = 0
last_temp = 1  # Needs to be different from RPiTemp the first time
PerforationThresholdLevel = 120 # To be synchronized with Arduino
save_bg = 'gray'
save_fg = 'black'
is_s8 = True
ZoomSize = 0
simulated_captured_frame_list=[None]*1000
raw_simulated_capture_image = ''
simulated_capture_image = ''
simulated_capture_label = ''
simulated_images_in_list = 0

# Persisted data
SessionData = {
    "IsActive": False,
    "CurrentDate": str(datetime.now()),
    "TargetFolder": CurrentDir,
    "CurrentFrame": str(CurrentFrame),
    "CurrentExposure": str(CurrentExposure)
}
# Some initialization
win = Tk()  # creating the main window and storing the window object in 'win'
win.title('T-Scann 8')  # setting title of the window
win.geometry('1100x850')  # setting the size of the window
win.geometry('+50+50')  # setting the position of the window
# Prevent window resize
win.minsize(1100,850)
win.maxsize(1100,850)

win.update_idletasks()

# Get Top window coordinates
TopWinX = win.winfo_x()
TopWinY = win.winfo_y()

WinInitDone = True

# Check if persisted data file exist: If it does, load it
if os.path.isfile(PersistedSessionFilename):
    # Preview not yet displayed, no need to disable to make this popup visible
    Confirm = tkinter.messagebox.askyesno(title='Persisted session data exist',
                                         message='It seems T-Scann 8 was interrupted during the last session.\nDo you want to continue from where it was stopped?')
    if Confirm:
        PersistedDateFile = open(PersistedSessionFilename)
        SessionData = json.load(PersistedDateFile)
        print("SessionData loaded from disk:")
        print(SessionData["IsActive"])
        print(SessionData["CurrentDate"])
        print(SessionData["TargetFolder"])
        print(SessionData["CurrentFrame"])
        print(SessionData["CurrentExposure"])
        CurrentDir = SessionData["TargetFolder"]
        CurrentFrame = int(SessionData["CurrentFrame"])
        CurrentExposureStr = SessionData["CurrentExposure"]
        if CurrentExposureStr == "Auto":
            CurrentExposure = 0
        else:
            CurrentExposure = int(CurrentExposureStr)
            CurrentExposureStr = str(round((CurrentExposure-20000)/2000))
        # when finished, close the file
        PersistedDateFile.close()
    else:
        if os.path.isfile(PersistedSessionFilename):
            os.remove(PersistedSessionFilename)


# Create a frame to add a border to the preview
preview_border_frame = Frame(win, width=844, height=634, bg='dark grey')
preview_border_frame.pack()
preview_border_frame.place(x=38, y=38)

if not SimulatedRun:
    if IsPiCamera2:
        camera = Picamera2()
        camera.start_preview(Preview.QTGL, x=PreviewWinX, y=PreviewWinY, width=840, height=720)
        capture_config = camera.create_still_configuration(main={"size": (2028, 1520)}, transform=Transform(hflip=True))
        camera.configure(camera.create_preview_configuration(transform=Transform(hflip=True)))
        camera.set_controls({"ExposureTime": CurrentExposure, "AnalogueGain": 1.0})
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
        camera.awb_mode = 'off'
        camera.awb_gains = (3.5, 1.0)
        camera.start_preview(fullscreen = False, window= (90,75,840,720))
        camera.shutter_speed = CurrentExposure

def exit_app():  # Exit Application
    global ExitRequested
    global SimulatedRun
    # Uncomment next two lines when running on RPi
    if not SimulatedRun:
        camera.close()
    # Exiting normally: Delete session info
    #if os.path.isfile(PersistedSessionFilename):
    #    os.remove(PersistedSessionFilename)

    ExitRequested = True
    win.destroy()

    # poweroff()  # shut down Raspberry PI (remove "#" before poweroff)


def set_free_mode():
    global FreeWheelActive
    global save_bg
    global save_fg
    global SimulatedRun

    if not FreeWheelActive:
        Free_btn.config(text='Lock Reels',bg='red',fg='white')
    else:
        Free_btn.config(text='Unlock Reels',bg=save_bg,fg=save_fg)

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

    if not FocusZoomActive:
        Focus_btn.config(text='Focus Zoom OFF',bg='red',fg='white')
        if not SimulatedRun:
            if IsPiCamera2:
                camera.set_controls({"ScalerCrop": (int(0.35*ZoomSize[0]),int(0.35*ZoomSize[1])) + (int(0.2*ZoomSize[0]),int(0.2*ZoomSize[1]))})
            else:
                camera.crop = (0.35, 0.35, 0.2, 0.2)  # Activate camera zoom
    else:
        Focus_btn.config(text='Focus Zoom ON',bg=save_bg,fg=save_fg)
        if not SimulatedRun:
            if IsPiCamera2:
                camera.set_controls({"ScalerCrop": (0,0) + (ZoomSize[0],ZoomSize[1])})
            else:
                camera.crop = (0.0, 0.0, 835, 720)  # Remove camera zoom

    time.sleep(.2)
    FocusZoomActive = not FocusZoomActive

    # Enable/Disable related buttons
    button_status_change_except(Focus_btn, FocusZoomActive)


def set_new_folder():
    global GlobalDir
    global CurrentDir
    global CurrentFrame
    global SimulatedRun

    RequestedDir = ""

    # CurrentDir = tkinter.filedialog.askdirectory(initialdir=BaseDir, title="Select parent folder first")
    CurrentDir = BaseDir
    #folder_frame_folder_label.config(text=CurrentDir)
    # Disable preview to make tkinter dialogs visible
    if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
        camera.stop_preview()
    while RequestedDir == "" or RequestedDir is None:
        RequestedDir = tkinter.simpledialog.askstring(title="Enter new folder name", prompt="New folder name?")
        if RequestedDir is None:
            return
        if RequestedDir == "":
            tkinter.messagebox.showerror("Error!", "Please specify a name for the folder to be created.")

    NewlyCreatedDir = os.path.join(CurrentDir, RequestedDir)

    if not os.path.isdir(NewlyCreatedDir):
        os.mkdir(NewlyCreatedDir)
        CurrentFrame = 0
        CurrentDir = NewlyCreatedDir
    else:
        tkinter.messagebox.showerror("Error!", "Folder " + RequestedDir + " already exists!")

    if not SimulatedRun:
        if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
            camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))

    folder_frame_folder_label.config(text=CurrentDir)
    Scanned_Images_number_label.config(text=str(CurrentFrame))



def set_existing_folder():
    global CurrentDir
    global CurrentFrame
    global SimulatedRun

    # Disable preview to make tkinter dialogs visible
    if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
        camera.stop_preview()
    if not SimulatedRun:
        CurrentDir = tkinter.filedialog.askdirectory(initialdir=BaseDir, title="Select existing folder for capture")
    else:
        CurrentDir = tkinter.filedialog.askdirectory(initialdir=BaseDir, title="Select existing folder with snapshots for simulated run")
    if not CurrentDir:
        return
    else:
        folder_frame_folder_label.config(text=CurrentDir)

    current_frame_str = tkinter.simpledialog.askstring(title="Enter number of last captured frame", prompt="Last frame captured?")
    if current_frame_str is None:
        return
    else:
        CurrentFrame = int(current_frame_str)
        Scanned_Images_number_label.config(text=current_frame_str)

    if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
        camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))

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
        CurrentExposureStr = str(round((CurrentExposure-20000)/2000))

    exposure_frame_value_label.config(text=CurrentExposureStr)
    if not SimulatedRun:
        if IsPiCamera2:
            camera.controls.ExposureTime = CurrentExposure  # maybe will not work, check pag 26 of picamera2 specs
        else:
            camera.shutter_speed = CurrentExposure



def auto_exp():
    global CurrentExposure
    global CurrentExposureStr

    CurrentExposure = 0

    CurrentExposureStr = "Auto"

    exposure_frame_value_label.config(text=CurrentExposureStr)
    if not SimulatedRun:
        if IsPiCamera2:
            camera.controls.ExposureTime = CurrentExposure  # maybe will not work, check pag 26 of picamera2 specs
        else:
            camera.shutter_speed = CurrentExposure


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
    CurrentExposureStr = str(round((CurrentExposure-20000)/2000))

    exposure_frame_value_label.config(text=CurrentExposureStr)
    if not SimulatedRun:
        if IsPiCamera2:
            camera.controls.ExposureTime = CurrentExposure
        else:
            camera.shutter_speed = CurrentExposure

def decrease_perforation_threshold():
    global PerforationThresholdLevel
    global SimulatedRun

    if not SimulatedRun:
        i2c.write_byte_data(16, 91, 0)

    if (PerforationThresholdLevel > 30):
        PerforationThresholdLevel-=10

def increase_perforation_threshold():
    global PerforationThresholdLevel
    global SimulatedRun

    if not SimulatedRun:
        i2c.write_byte_data(16, 90, 0)

    if (PerforationThresholdLevel < 360):
        PerforationThresholdLevel+=10

def button_status_change_except(except_button, active):
    if (except_button != Free_btn):
        Free_btn.config(state=DISABLED if active else NORMAL)
    if (except_button != SingleStep_btn):
        SingleStep_btn.config(state = DISABLED if active else NORMAL)
    if (except_button != AdvanceMovie_btn):
        AdvanceMovie_btn.config(state = DISABLED if active else NORMAL)
    if (except_button != Rewind_btn):
        Rewind_btn.config(state = DISABLED if active else NORMAL)
    if (except_button != FastForward_btn):
        FastForward_btn.config(state = DISABLED if active else NORMAL)
    if (except_button != Start_btn):
        Start_btn.config(state = DISABLED if active else NORMAL)
    if (except_button != PosNeg_btn):
        PosNeg_btn.config(state = DISABLED if active else NORMAL)
    if (except_button != Focus_btn):
        Focus_btn.config(state = DISABLED if active else NORMAL)
    if (except_button != Start_btn):
        Start_btn.config(state=DISABLED if active else NORMAL)
    if (except_button != Exit_btn):
        Exit_btn.config(state=DISABLED if active else NORMAL)
    if (except_button != DisablePreview_btn):
        DisablePreview_btn.config(state=DISABLED if active else NORMAL)
    if (except_button != film_type_S8_btn):
        film_type_S8_btn.config(state=DISABLED if active else NORMAL)
    if (except_button != film_type_R8_btn):
        film_type_R8_btn.config(state=DISABLED if active else NORMAL)

def advance_movie():
    global AdvanceMovieActive
    global save_bg
    global save_fg
    global SimulatedRun

    # Update button text
    if not AdvanceMovieActive:  # Advance movie is about to start...
        AdvanceMovie_btn.config(text='Stop movie',bg='red',fg='white')  # ...so now we propose to stop it in the button test
    else:
        AdvanceMovie_btn.config(text='Movie forward',bg=save_bg,fg=save_fg)  # Otherwise change to default text to start the action
    AdvanceMovieActive = not AdvanceMovieActive
    # Send instruction to Arduino
    if not SimulatedRun:
        i2c.write_byte_data(16, 30, 0)

    # Enable/Disable related buttons
    button_status_change_except(AdvanceMovie_btn,AdvanceMovieActive)


def rewind_movie():
    global RewindMovieActive
    global SimulatedRun
    global RewindErrorOutstanding
    global save_bg
    global save_fg

    # Before proceeding, get confirmation from user that fild is correctly routed
    if not RewindMovieActive:  # Ask only when rewind is not ongoing
        # Disable preview to make tkinter dialogs visible
        if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
            camera.stop_preview()
        answer = tkinter.messagebox.askyesno(title='Security check ',  message='Have you routed the film via the upper path?')
        if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
                camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))
        if not answer:
            return()
    else:
        if RewindErrorOutstanding:
            if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
                camera.stop_preview()
            tkinter.messagebox.showerror(title='Error during rewind',
                                                 message='It seems there is film loaded via filmgate. Please route it via upper path.')
            if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
                camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))

    # Update button text
    if not RewindMovieActive:  # Rewind movie is about to start...
        Rewind_btn.config(text='Stop\n<<',bg='red',fg='white')  # ...so now we propose to stop it in the button test
    else:
        Rewind_btn.config(text='<<',bg=save_bg,fg=save_fg)  # Otherwise change to default text to start the action
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

        #Invoke RewindLoop a first time shen rewind starts
        if RewindMovieActive :
            win.after(5,RewindLoop)

def RewindLoop():
    global RewindMovieActive
    global SimulatedRun
    global RewindErrorOutstanding

    if RewindMovieActive:
        # Invoke RewindLoop one more time, as long as rewind is ongoing
        if not RewindErrorOutstanding:
            win.after(5, RewindLoop)
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
        if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
            camera.stop_preview()
        answer = tkinter.messagebox.askyesno(title='Security check ',  message='Have you routed the film via the upper path?')
        if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
                camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))
        if not answer:
            return()
    else:
        if FastForwardErrorOutstanding:
            if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
                camera.stop_preview()
            tkinter.messagebox.showerror(title='Error during fast forward',
                                                 message='It seems there is film loaded via filmgate. Please route it via upper path.')
            if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
                camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))

    # Update button text
    if not FastForwardActive:  # Fast forward movie is about to start...
        FastForward_btn.config(text='Stop\n>>',bg='red',fg='white')  # ...so now we propose to stop it in the button test
    else:
        FastForward_btn.config(text='>>',bg=save_bg,fg=save_fg)  # Otherwise change to default text to start the action
    FastForwardActive = not FastForwardActive

    # Enable/Disable related buttons
    button_status_change_except(FastForward_btn,FastForwardActive)

    if FastForwardErrorOutstanding:
        FastForwardErrorOutstanding = False
    else:
        # Send instruction to Arduino
        time.sleep(0.2)
        if not SimulatedRun:
            i2c.write_byte_data(16, 80, 0)
        #Invoke FastForwardLoop a first time shen fast forward starts
        if FastForwardActive :
            win.after(5,FastForwardLoop)


def FastForwardLoop():
    global FastForwardActive
    global SimulatedRun
    global FastForwardErrorOutstanding

    if FastForwardActive:
        # Invoke RewindLoop one more time, as long as rewind is ongoing
        if not FastForwardErrorOutstanding:
            win.after(5, FastForwardLoop)
        else:
            fast_forward_movie()


def single_step_movie():
    global SimulatedRun
    if not SimulatedRun:
        i2c.write_byte_data(16, 40, 0)

def emergency_stop():
    global SimulatedRun
    if not SimulatedRun:
        i2c.write_byte_data(16, 90, 0)

def update_rpi_temp():
    global SimulatedRun
    global RPiTemp
    if (not SimulatedRun):
        file = open('/sys/class/thermal/thermal_zone0/temp', 'r')
        temp_str = file.readline()
        file.close()
        RPiTemp = int(int(temp_str)/100)/10

def negative_capture():
    global NegativeCaptureStatus
    global SimulatedRun

    if not SimulatedRun:
        if not IsPiCamera2:
            if NegativeCaptureStatus == False:
                camera.image_effect = 'negative'
                camera.awb_gains = (1.7, 1.9)
            else:
                camera.image_effect = 'none'
                camera.awb_gains = (3.5, 1.0)

    NegativeCaptureStatus = not NegativeCaptureStatus

def open_folder():
    global OpenFolderActive
    global FolderProcess
    global save_bg
    global save_fg
    global SimulatedRun

    if not OpenFolderActive :
        OpenFolder_btn.config(text="Close Folder",bg='red',fg='white')
        if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
            camera.stop_preview()
        FolderProcess = subprocess.Popen(["pcmanfm", BaseDir])
    else:
        OpenFolder_btn.config(text="Open Folder",bg=save_bg,fg=save_fg)
        FolderProcess.terminate()  # This does not work, neither do some other means found on the internet. To be done (not too critical)

        time.sleep(.5)
        if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
            camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))
        time.sleep(.5)

    OpenFolderActive = not OpenFolderActive

def disable_preview():
    global PreviewEnabled
    global save_bg
    global save_fg
    global SimulatedRun

    if not SimulatedRun:
        if PreviewEnabled:
            camera.stop_preview();
        else:
            if IsPiCamera2:
                camera.start_preview(True)
            else:
                camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))

    PreviewEnabled = not PreviewEnabled

   # Update button text
    if PreviewEnabled:  # Preview is about to be enabled
        DisablePreview_btn.config(text='Disable Preview',bg=save_bg,fg=save_fg)
    else:
        DisablePreview_btn.config(text='Enable Preview',bg='red',fg='white')  # Otherwise change to default text to start the action

def set_S8():
    global SimulatedRun

    film_type_S8_btn.config(relief=SUNKEN)
    film_type_R8_btn.config(relief=RAISED)
    is_s8 = True
    time.sleep(0.2)
    if not SimulatedRun:
        i2c.write_byte_data(16, 19, 0)


def set_R8():
    global SimulatedRun

    film_type_R8_btn.config(relief=SUNKEN)
    film_type_S8_btn.config(relief=RAISED)
    is_s8 = False
    time.sleep(0.2)
    if not SimulatedRun:
        i2c.write_byte_data(16, 18, 0)


def capture():
    global CurrentDir
    global CurrentFrame
    global SessionData
    global PreviousCurrentExposure
    global SimulatedRun

    os.chdir(CurrentDir)

    if CurrentExposure == 0:
        while True:     # In case of exposure change, give time for the camera to adapt
            if IsPiCamera2:
                metadata = camera.capture_metadata()
                AuxCurrentExposure = metadata["ExposureTime"]
                # AuxCurrentExposure = camera.controls.ExposureTime # Does not work, need to get all metadata
            else:
                AuxCurrentExposure = camera.exposure_speed
            if abs(AuxCurrentExposure - PreviousCurrentExposure) > 1000:
                curtime = time.ctime()
                aux_exposure_str = "Auto (" + str(round((AuxCurrentExposure-20000)/2000)) + ")"
                print(f"{curtime} - Automatic exposure: Waiting for camera to adapt ({AuxCurrentExposure},{aux_exposure_str})")
                exposure_frame_value_label.config(text=aux_exposure_str)
                PreviousCurrentExposure = AuxCurrentExposure
                win.update()
                time.sleep(0.5)
            else:
                break

    if not SimulatedRun:
        if IsPiCamera2:
            camera.switch_mode_and_capture_file(capture_config,'picture-%05d.jpg' % CurrentFrame)
        else:
            camera.capture('picture-%05d.jpg' % CurrentFrame, quality=100)
    SessionData["CurrentDate"] = str(datetime.now())
    SessionData["CurrentFrame"] = str(CurrentFrame)

def StartScanSimulated():
    global CurrentDir
    global CurrentFrame
    global SessionData
    global ScanOngoing
    global CurrentScanStartFrame
    global CurrentScanStartTime
    global save_bg
    global save_fg
    global simulated_captured_frame_list
    global simulated_images_in_list

    if not ScanOngoing and BaseDir == CurrentDir:
        tkinter.messagebox.showerror("Error!", "Please specify a folder where to retrieve captured images for scan simulation.")
        return

    if not ScanOngoing : # Scanner session to be started
        Start_btn.config(text="STOP Scan",bg='red',fg='white')
    else:
        Start_btn.config(text="START Scan",bg=save_bg,fg=save_fg)

    ScanOngoing = not ScanOngoing

    # Enable/Disable related buttons
    button_status_change_except(Start_btn, ScanOngoing)

    #Invoke CaptureLoop a first time shen scan starts
    if ScanOngoing :
        # Get list of previously captured frames for scan simulation
        simulated_captured_frame_list = os.listdir(CurrentDir)
        simulated_captured_frame_list.sort()
        simulated_images_in_list = len(simulated_captured_frame_list)
        win.after(500,CaptureLoopSimulated)


def CaptureLoopSimulated():
    global CurrentDir
    global CurrentFrame
    global CurrentExposure
    global SessionData
    global FramesPerMinute
    global NewFrameAvailable
    global ScanOngoing
    global preview_border_frame
    global raw_simulated_capture_image
    global simulated_capture_image
    global simulated_capture_label
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
            raw_simulated_capture_image = raw_simulated_capture_image.resize((844, 634))
            simulated_capture_image = ImageTk.PhotoImage(raw_simulated_capture_image)
            # The Label widget is a standard Tkinter widget used to display a text or image on the screen.
            simulated_capture_label = tk.Label(preview_border_frame, image=simulated_capture_image)
            # The Pack geometry manager packs widgets in rows or columns.
            simulated_capture_label.place(x=0, y=0)
            #simulated_capture_label.pack(side="top", fill="both")
            #simulated_capture_label.pack()
        CurrentFrame += 1

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

        # Invoke CaptureLoop one more time, as long as scan is ongoing
        win.after(500, CaptureLoopSimulated)
def StartScan():
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
        if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
            camera.stop_preview()
        tkinter.messagebox.showerror("Error!", "Please specify a folder where to store the captured images.")
        if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
            camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))
        return

    if not ScanOngoing : # Scanner session to be started
        Start_btn.config(text="STOP Scan",bg='red',fg='white')
        LoopDelay = 0.05
        SessionData["IsActive"] = True
        SessionData["CurrentDate"] = str(datetime.now())
        SessionData["TargetFolder"] = CurrentDir
        SessionData["CurrentFrame"] = str(CurrentFrame)
        CurrentScanStartTime = datetime.now()
        CurrentScanStartFrame = CurrentFrame
    else:
        Start_btn.config(text="START Scan",bg=save_bg,fg=save_fg)
        CurrentScanStartTime = 0
        CurrentScanStartFrame = CurrentFrame;
        LoopDelay = 0

    ScanOngoing = not ScanOngoing

    # Enable/Disable related buttons
    button_status_change_except(Start_btn, ScanOngoing)


    #Send command to Arduino to stop/start scan (as applicable, Arduino keeps its own status)
    if not SimulatedRun:
        i2c.write_byte_data(16, 10, 0)

    #Invoke CaptureLoop a first time shen scan starts
    if ScanOngoing :
        win.after(5,CaptureLoop)


def CaptureLoop():
    global CurrentDir
    global CurrentFrame
    global CurrentExposure
    global SessionData
    global FramesPerMinute
    global NewFrameAvailable
    global ScanOngoing
    global SimulatedRun


    if ScanOngoing:
        if NewFrameAvailable:
            CurrentFrame += 1
            capture()
            if not SimulatedRun:
                try:
                    NewFrameAvailable = False  # Set NewFrameAvailable to False here, to avoid overwriting new frame rom arduino
                    i2c.write_byte_data(16, 12, 0)  # Tell Arduino to move to next frame
                except:
                    CurrentFrame -= 1
                    NewFrameAvailable = True  # Set NewFrameAvailable to True to repeat next time
                    # Log error to console
                    curtime = time.ctime()
                    print(curtime + " - Error while telling Arduino to move to next Frame.")
                    print(f"    Frame {CurrentFrame} capture to be tried again.")
                    win.after(5, CaptureLoop)
                    return

        SessionData["CurrentDate"] = str(datetime.now())
        SessionData["TargetFolder"] = CurrentDir
        SessionData["CurrentFrame"] = str(CurrentFrame)
        if CurrentExposureStr == "Auto":
            SessionData["CurrentExposure"] = CurrentExposureStr
        else:
            SessionData["CurrentExposure"] = str(CurrentExposure)
        with open(PersistedSessionFilename, 'w') as f:
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

        # Invoke CaptureLoop one more time, as long as scan is ongoing
        win.after(0, CaptureLoop)

def TempLoop():    # Update RPi temperature every 10 seconds
    global last_temp
    update_rpi_temp()
    if last_temp != RPiTemp:
        RPi_temp_value_label.config(text=str(RPiTemp))
        win.update()
        last_temp = RPiTemp

    win.after(10000, TempLoop)

def ArduinoListenLoop():    # Waits for Arduino communicated events adn dispatches accordingly
    global NewFrameAvailable
    global RewindErrorOutstanding
    global FastForwardErrorOutstanding
    global ArduinoTrigger
    global PerforationThresholdLevel
    global SimulatedRun

    if not SimulatedRun:
        try:
            ArduinoTrigger = i2c.read_byte_data(16, 0)
        except:
            # Log error to console
            curtime = time.ctime()
            print(curtime + " - Error while checking incoming event from Arduino. Will check again.")
    if ArduinoTrigger == 11:    # New Frame available
        NewFrameAvailable = True
    elif ArduinoTrigger == 92:    # PerforationThresholdLevel value, next byte contains Arduino value
        #PerforationThresholdLevel = i2c.read_byte_data(16, 0)
        print("Received perforation threshold level event from Arduino")
        perforation_threshold_value_label.config(text=str(PerforationThresholdLevel))
        win.update()
    elif ArduinoTrigger == 61:    # Error during Rewind
        RewindErrorOutstanding = True
        print("Received rewind error from Arduino")
    elif ArduinoTrigger == 81:    # Error during FastForward
        FastForwardErrorOutstanding = True
        print("Received fast forward error from Arduino")

    ArduinoTrigger = 0

    win.after(5, ArduinoListenLoop)


def onFormEvent(event):
    global TopWinX
    global TopWinY
    global NewWinX
    global NewWinY
    global DeltaX
    global DeltaY
    global PreviewWinX
    global PreviewWinY
    global SimulatedRun

    if not WinInitDone:
        return

    NewWinX = win.winfo_x()
    NewWinY = win.winfo_y()
    DeltaX = NewWinX - TopWinX
    DeltaY = NewWinY - TopWinY
    TopWinX = NewWinX
    TopWinY = NewWinY
    PreviewWinX = PreviewWinX + DeltaX
    PreviewWinY = PreviewWinY + DeltaY
    if PreviewEnabled and not SimulatedRun and not IsPiCamera2:  # Preview hidden only when using picamera legacy
        camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))

    """
    # Uncomment to have the details of each event
    for key in dir(event):
        if not key.startswith('_'):
            print('%s=%s' % (key, getattr(event, key)))
    print()
    """

# SimulatedRun
# Create marker for film hole
# if SimulatedRun:
    film_hole = Frame(win, width=1, height=11, bg='black')
    film_hole.pack(side=TOP, padx=1, pady=1)
    film_hole.place(x=4, y=300)

    # film_hole_label = Label(film_hole, justify=LEFT, font=("Arial", 8), text="S\rP\rR  H\rO  O\rC  L\rK  E\rE\rT", width=5, height=11, bg='red' , fg='white')
    film_hole_label = Label(film_hole, justify=LEFT, font=("Arial", 8), width=5, height=11, bg='red' , fg='white')
    film_hole_label.pack(side=TOP)

# Create horizontal button row at bottom
# Advance movie (through filmgate)
AdvanceMovie_btn = Button(win, text="Movie Forward", width=8, height=3, command=advance_movie, activebackground='green', activeforeground='white', wraplength=80)
AdvanceMovie_btn.place(x=30, y=710)
# Once first button created, get default colors, to revert when we change them
save_bg = AdvanceMovie_btn['bg']
save_fg = AdvanceMovie_btn['fg']
# Advance one single frame
SingleStep_btn = Button(win, text="Single Step", width=8, height=3, command=single_step_movie, activebackground='green', activeforeground='white', wraplength=80)
SingleStep_btn.place(x=130, y=710)
# Switch Positive/negative modes
PosNeg_btn = Button(win, text="Pos/Neg", width=8, height=3, command=negative_capture, activebackground='green', activeforeground='white', wraplength=80)
PosNeg_btn.place(x=230, y=710)
# Disable Pi Camera preview (might hide some stuff)
DisablePreview_btn = Button(win, text="Disable Preview", width=8, height=3, command=disable_preview, activebackground='red', activeforeground='white', wraplength=80)
DisablePreview_btn.place(x=330, y=710)
# Rewind movie (via upper path, outside of film gate)
Rewind_btn = Button(win, text="<<", font=("Arial", 16), width=5, height=2, command=rewind_movie, activebackground='green', activeforeground='white', wraplength=80)
Rewind_btn.place(x=430, y=710)
# Fast Forward movie (via upper path, outside of film gate)
FastForward_btn = Button(win, text=">>", font=("Arial", 16), width=5, height=2, command=fast_forward_movie, activebackground='green', activeforeground='white', wraplength=80)
FastForward_btn.place(x=530, y=710)
# Open target folder (to me this is useless. Also, gives problem with closure, not as easy at I imegined)
# So, disabled to gain some space
# OpenFolder_btn = Button(win, text="Open Folder", width=8, height=3, command=open_folder, activebackground='green', activeforeground='white', wraplength=80)
# OpenFolder_btn.place(x=630, y=710)
# Unlock reels button (to load film, rewind, etc)
Free_btn = Button(win, text="Unlock Reels", width=8, height=3, command=set_free_mode, activebackground='green', activeforeground='white', wraplength=80)
Free_btn.place(x=630, y=710)
# Activate focus zoom, to facilitate focusing the camera
Focus_btn = Button(win, text="Focus Zoom ON", width=8, height=3, command=set_focus_zoom, activebackground='green', activeforeground='white', wraplength=80)
Focus_btn.place(x=730, y=710)

# Create frame to display RPi temperature
RPi_temp_frame = Frame(win, width=8, height=2, highlightbackground="black", highlightthickness=1)
RPi_temp_frame.pack(side=TOP, padx=1, pady=1)
RPi_temp_frame.place(x=840, y=715)

RPi_temp_frame_label = Label(RPi_temp_frame, text='RPi Temp.', width=8, height=1, wraplength=120, bg='white')
RPi_temp_frame_label.pack(side=TOP)
RPi_temp_value_label = Label(RPi_temp_frame, text=str(RPiTemp), font=("Arial", 18), width=5, height=1, wraplength=120, bg='white')
RPi_temp_value_label.pack(side=TOP, fill='x')


# Application Exit button
Exit_btn = Button(win, text="Exit", width=12, height=5, command=exit_app, activebackground='red', activeforeground='white', wraplength=80)
Exit_btn.place(x=925, y=700)

# Create vertical button column at right
# Start scan button
if SimulatedRun:
    Start_btn = Button(win, text="START Scan", width=14, height=5, command=StartScanSimulated, activebackground='green', activeforeground='white', wraplength=80)
else:
    Start_btn = Button(win, text="START Scan", width=14, height=5, command=StartScan, activebackground='green', activeforeground='white', wraplength=80)
Start_btn.place(x=925, y=40)

# Create frame to select target folder
folder_frame = Frame(win, width=16, height=8, highlightbackground="black", highlightthickness=1)
folder_frame.pack()
folder_frame.place(x=925, y=150)

folder_frame_title = Frame(folder_frame, width=16, height=4)
folder_frame_title.pack()
folder_frame_title_label = Label(folder_frame_title, text='Target Folder', width=16, height=1)
folder_frame_title_label.pack(side=TOP)
folder_frame_folder_label = Label(folder_frame_title, text=CurrentDir, width=16, height=3, font=("Arial", 8), wraplength=140)
folder_frame_folder_label.pack(side=TOP)

folder_frame_buttons = Frame(folder_frame, width=16, height=4, bd=2)
folder_frame_buttons.pack()
new_folder_btn = Button(folder_frame_buttons, text='New', width=5, height=1, command=set_new_folder, activebackground='green', activeforeground='white', wraplength=80, font=("Arial", 10))
new_folder_btn.pack(side=LEFT)
existing_folder_btn = Button(folder_frame_buttons, text='Existing', width=5, height=1, command=set_existing_folder, activebackground='green', activeforeground='white', wraplength=80, font=("Arial", 10))
existing_folder_btn.pack(side=LEFT)

# Create frame to display number of scanned images, and frames per minute
Scanned_Images_frame = Frame(win, width=16, height=4, highlightbackground="black", highlightthickness=1)
Scanned_Images_frame.pack(side=TOP, padx=1, pady=1)
Scanned_Images_frame.place(x=925, y=270)

Scanned_Images_label = Label(Scanned_Images_frame, text='Number of scanned Images', width=16, height=2, wraplength=120, bg='white')
Scanned_Images_label.pack(side=TOP)
Scanned_Images_number_label = Label(Scanned_Images_frame, text=str(CurrentFrame), font=("Arial", 24), width=5, height=1, wraplength=120, bg='white')
Scanned_Images_number_label.pack(side=TOP, fill='x')

Scanned_Images_fpm_frame = Frame(Scanned_Images_frame, width=16, height=2)
Scanned_Images_fpm_frame.pack(side=TOP, padx=1, pady=1)
Scanned_Images_fpm_label = Label(Scanned_Images_fpm_frame, text='Frames/Min:', font=("Arial", 8), width=12, height=1, wraplength=120, bg='white')
Scanned_Images_fpm_label.pack(side=LEFT)
Scanned_Images_fpm = Label(Scanned_Images_fpm_frame, text=str(FramesPerMinute), font=("Arial", 8), width=8, height=1, wraplength=120, bg='white')
Scanned_Images_fpm.pack(side=LEFT)

# Create frame to select exposure value
exposure_frame = Frame(win, width=16, height=2, bg='white', highlightbackground="black", highlightthickness=1)
exposure_frame.pack(side=TOP, padx=1, pady=1)
exposure_frame.place(x=925, y=390)

exposure_frame_title_label = Label(exposure_frame, text='Camera Exposure', width=16, height=1, bg='white')
exposure_frame_title_label.pack(side=TOP)
exposure_frame_value_label = Label(exposure_frame, text=CurrentExposureStr, width=8, height=1, font=("Arial", 16), wraplength=110, bg='white')
exposure_frame_value_label.pack(side=TOP)

exposure_frame_buttons = Frame(exposure_frame, width=8, height=1, bg='white')
exposure_frame_buttons.pack(side=TOP)
decrease_exp_btn = Button(exposure_frame_buttons, text='-', width=1, height=1, font=("Arial", 16, 'bold'), command=decrease_exp, activebackground='green', activeforeground='white', wraplength=80)
decrease_exp_btn.pack(side=LEFT)
auto_exp_btn = Button(exposure_frame_buttons, text='A', width=1, height=1, font=("Arial", 16, 'bold'), command=auto_exp, activebackground='green', activeforeground='white', wraplength=80)
auto_exp_btn.pack(side=LEFT)
increase_exp_btn = Button(exposure_frame_buttons, text='+', width=1, height=1, font=("Arial", 16, 'bold'), command=increase_exp, activebackground='green', activeforeground='white', wraplength=80)
increase_exp_btn.pack(side=LEFT)

# Create frame to select S8/R8 film
film_type_frame = Frame(win, width=16, height=2, bg='white', highlightbackground="black", highlightthickness=1)
film_type_frame.pack(side=TOP, padx=1, pady=1)
film_type_frame.place(x=925, y=500)

film_type_title_label = Label(film_type_frame, text='Film Type', width=16, height=1, bg='white')
film_type_title_label.pack(side=TOP)

film_type_buttons = Frame(film_type_frame, width=8, height=1, bg='white')
film_type_buttons.pack(side=TOP)
film_type_S8_btn = Button(film_type_buttons, text='S8', width=1, height=1, font=("Arial", 16, 'bold'), command=set_S8, activebackground='green', activeforeground='white', wraplength=80, relief=SUNKEN)
film_type_S8_btn.pack(side=LEFT)
film_type_R8_btn = Button(film_type_buttons, text='R8', width=1, height=1, font=("Arial", 16, 'bold'), command=set_R8, activebackground='green', activeforeground='white', wraplength=80)
film_type_R8_btn.pack(side=LEFT)


# Create frame to select perforation threshold dynamically (however scan mode needs to be stopped)
perforation_threshold_frame = Frame(win, width=16, height=2, bg='white', highlightbackground="black", highlightthickness=1)
perforation_threshold_frame.pack(side=TOP, padx=1, pady=1)
perforation_threshold_frame.place(x=925, y=580)

perforation_threshold_title_label = Label(perforation_threshold_frame, text='Perf. Threshold', width=16, height=1, bg='white')
perforation_threshold_title_label.pack(side=TOP)
perforation_threshold_value_label = Label(perforation_threshold_frame, text=str(PerforationThresholdLevel), width=8, height=1, font=("Arial", 16), wraplength=110, bg='white')
perforation_threshold_value_label.pack(side=TOP)

perforation_threshold_buttons = Frame(perforation_threshold_frame, width=8, height=1, bg='white')
perforation_threshold_buttons.pack(side=TOP)
decrease_perforation_threshold_btn = Button(perforation_threshold_buttons, text='-', width=1, height=1, font=("Arial", 16, 'bold'), command=decrease_perforation_threshold, activebackground='green', activeforeground='white', wraplength=80)
decrease_perforation_threshold_btn.pack(side=LEFT)
increase_perforation_threshold_btn = Button(perforation_threshold_buttons, text='+', width=1, height=1, font=("Arial", 16, 'bold'), command=increase_perforation_threshold, activebackground='green', activeforeground='white', wraplength=80)
increase_perforation_threshold_btn.pack(side=LEFT)


# Check if existing session on script start

# Main Loop
while not ExitRequested:
    # CaptureLoop()
    TempLoop()
    ArduinoListenLoop()
    if not SimulatedRun:
        if IsPiCamera2:
            camera.controls.ExposureTime = CurrentExposure
        else:
            camera.shutter_speed = CurrentExposure

    # Enable events on windows movements, to allow preview to follow
    lblText = tk.Label(win, text='')
    lblText.pack()
    if not IsPiCamera2:
    	win.bind('<Configure>', onFormEvent)

    win.mainloop()  # running the loop that works as a trigger

if not SimulatedRun:
    camera.close()

# win.mainloop()  # running the loop that works as a trigger
