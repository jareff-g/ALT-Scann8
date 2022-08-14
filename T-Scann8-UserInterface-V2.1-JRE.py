
# 06/08/2022: 2.1.7: JRE: Add Button for EmergencyStop
# 10/08/2022: JRE: Comment emergency stop button
# 10/08/2022: JRE: After capturing image, if exposure has changed since previous capture wait one sec (to allow camera to adapt in automatic mode)
# 12/08/2022: JRE: Improve automatic exposure adaptation
# 13/08/2022: JRE Implemented detection of fild loaded via FilmGate, to prevent FF/Rewind
# 13/08/2022: JRE Move to 2.1.9
# 14/08/2022: JRE Implemented function to dynamically modify the perforation level threshold
IsRpi = False

if IsRpi:
    print("Running on Raspbery Pi")

import tkinter as tk
from tkinter import filedialog

import tkinter.messagebox
import tkinter.simpledialog
from tkinter import *

if IsRpi:
    import picamera
import os
import subprocess
import time
import json
if IsRpi:
    import smbus
from datetime import datetime
import sys

if IsRpi:
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

if IsRpi:
    camera = picamera.PiCamera()
    camera.sensor_mode = 3
    # settings resolution higher for HQ camera 2028, 1520
    camera.resolution = (2028, 1520)
    camera.iso = 100
    camera.sharpness = 100
    camera.hflip = True
    camera.awb_mode = 'off'
    camera.awb_gains = (3.5, 1.0)
    camera.start_preview(fullscreen = False, window= (90,75,840,720))
    camera.shutter_speed = CurrentExposure


def exit_app():  # Exit Application
    global ExitRequested
    # Uncomment next two lines when running on RPi
    if IsRpi:
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

    if not FreeWheelActive:
        Free_btn.config(text='Lock Reels',bg='red',fg='white')
    else:
        Free_btn.config(text='Unlock Reels',bg=save_bg,fg=save_fg)

    if IsRpi:
        i2c.write_byte_data(16, 20, 0)

    FreeWheelActive = not FreeWheelActive

    # Enable/Disable related buttons
    AdvanceMovie_btn.config(state=DISABLED if FreeWheelActive else NORMAL)
    SingleStep_btn.config(state = DISABLED if FreeWheelActive else NORMAL)
    Rewind_btn.config(state = DISABLED if FreeWheelActive else NORMAL)
    FastForward_btn.config(state = DISABLED if FreeWheelActive else NORMAL)
    Start_btn.config(state = DISABLED if FreeWheelActive else NORMAL)

# Enable/Disable camera zoom to facilitate focus
def set_focus_zoom():
    global FocusZoomActive
    global save_bg
    global save_fg

    if not FocusZoomActive:
        Focus_btn.config(text='Focus Zoom ON',bg=save_bg,fg=save_fg)
        if IsRpi:
            camera.crop = (0.35, 0.35, 0.2, 0.2)  # Activate camera zoon
        time.sleep(.2)
    else:
        Focus_btn.config(text='Focus Zoom OFF',bg='red',fg='white')
        if IsRpi:
            camera.crop = (0.0, 0.0, 835, 720)  # Remove camera zoom

    FocusZoomActive = not FocusZoomActive

    # Enable/Disable related buttons
    Start_btn.config(state = DISABLED if FocusZoomActive else NORMAL)


def set_new_folder():
    global GlobalDir
    global CurrentDir
    global CurrentFrame
    RequestedDir = ""

    # CurrentDir = tkinter.filedialog.askdirectory(initialdir=BaseDir, title="Select parent folder first")
    CurrentDir = BaseDir
    #folder_frame_folder_label.config(text=CurrentDir)
    # Disable preview to make tkinter dialogs visible
    if IsRpi:
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

    if IsRpi:
        camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))

    folder_frame_folder_label.config(text=CurrentDir)
    Scanned_Images_number_label.config(text=str(CurrentFrame))



def set_existing_folder():
    global CurrentDir
    global CurrentFrame

    # Disable preview to make tkinter dialogs visible
    if IsRpi and PreviewEnabled:
        camera.stop_preview()
    CurrentDir = tkinter.filedialog.askdirectory(initialdir=BaseDir, title="Select existing folder for capture")
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

    if IsRpi and PreviewEnabled:
        camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))

# In order to display a non-too-cryptic value for the exposure (what we keep in 'CurrentExposure')
# we will convert it to a higher level by using a similar algorythm as the one used by torulf in his original code:
# We take '20000' as the base reference of zero, with chunks of 2000's up and down moving the counter by one unit
# 'CurrentExposure' = zero wil always be displayed as 'Auto'

def decrease_exp():
    global CurrentExposure
    global CurrentExposureStr
    if IsRpi:
        if CurrentExposure == 0:  # If we are in auto exposure mode, retrieve current value to start from there
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
    if IsRpi:
        camera.shutter_speed = CurrentExposure



def auto_exp():
    global CurrentExposure
    global CurrentExposureStr

    CurrentExposure = 0

    CurrentExposureStr = "Auto"

    exposure_frame_value_label.config(text=CurrentExposureStr)
    if IsRpi:
        camera.shutter_speed = CurrentExposure


def increase_exp():
    global CurrentExposure
    global CurrentExposureStr
    if IsRpi:
        if CurrentExposure == 0:  # If we are in auto exposure mode, retrieve current value to start from there
            CurrentExposure = camera.exposure_speed
    CurrentExposure += 2000
    CurrentExposureStr = str(round((CurrentExposure-20000)/2000))

    exposure_frame_value_label.config(text=CurrentExposureStr)
    if IsRpi:
        camera.shutter_speed = CurrentExposure

def decrease_perforation_threshold():
    global PerforationThresholdLevel

    if IsRpi:
        i2c.write_byte_data(16, 91, 0)

    if (PerforationThresholdLevel > 30):
        PerforationThresholdLevel-=10

def increase_perforation_threshold():
    global PerforationThresholdLevel

    if IsRpi:
        i2c.write_byte_data(16, 90, 0)

    if (PerforationThresholdLevel < 360):
        PerforationThresholdLevel+=10


def advance_movie():
    global AdvanceMovieActive
    global save_bg
    global save_fg

    # Update button text
    if not AdvanceMovieActive:  # Advance movie is about to start...
        AdvanceMovie_btn.config(text='Stop movie',bg='red',fg='white')  # ...so now we propose to stop it in the button test
    else:
        AdvanceMovie_btn.config(text='Movie forward',bg=save_bg,fg=save_fg)  # Otherwise change to default text to start the action
    AdvanceMovieActive = not AdvanceMovieActive
    # Send instruction to Arduino
    if IsRpi:
        i2c.write_byte_data(16, 30, 0)

    # Enable/Disable related buttons
    Free_btn.config(state=DISABLED if AdvanceMovieActive else NORMAL)
    SingleStep_btn.config(state = DISABLED if AdvanceMovieActive else NORMAL)
    Rewind_btn.config(state = DISABLED if AdvanceMovieActive else NORMAL)
    FastForward_btn.config(state = DISABLED if AdvanceMovieActive else NORMAL)
    Start_btn.config(state = DISABLED if AdvanceMovieActive else NORMAL)


def rewind_movie():
    global RewindMovieActive
    global IsRpi
    global RewindErrorOutstanding
    global save_bg
    global save_fg

    # Before proceeding, get confirmation from user that fild is correctly routed
    if not RewindMovieActive:  # Ask only when rewind is not ongoing
        # Disable preview to make tkinter dialogs visible
        if IsRpi and PreviewEnabled:
            camera.stop_preview()
        answer = tkinter.messagebox.askyesno(title='Security check ',  message='Have you routed the film via the upper path?')
        if IsRpi and PreviewEnabled:
            camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))
        if not answer:
            return()
    else:
        if RewindErrorOutstanding:
            if IsRpi and PreviewEnabled:
                camera.stop_preview()
            tkinter.messagebox.showerror(title='Error during rewind',
                                                 message='It seems there is film loaded via filmgate. Please route it via upper path.')
            if IsRpi and PreviewEnabled:
                camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))

    # Update button text
    if not RewindMovieActive:  # Rewind movie is about to start...
        Rewind_btn.config(text='Stop\n<<',bg='red',fg='white')  # ...so now we propose to stop it in the button test
    else:
        Rewind_btn.config(text='<<',bg=save_bg,fg=save_fg)  # Otherwise change to default text to start the action
    # Send instruction to Arduino
    RewindMovieActive = not RewindMovieActive

    # Enable/Disable related buttons
    Free_btn.config(state=DISABLED if RewindMovieActive else NORMAL)
    SingleStep_btn.config(state = DISABLED if RewindMovieActive else NORMAL)
    AdvanceMovie_btn.config(state = DISABLED if RewindMovieActive else NORMAL)
    FastForward_btn.config(state = DISABLED if RewindMovieActive else NORMAL)
    Start_btn.config(state = DISABLED if RewindMovieActive else NORMAL)
    PosNeg_btn.config(state = DISABLED if RewindMovieActive else NORMAL)
    Focus_btn.config(state = DISABLED if RewindMovieActive else NORMAL)
    OpenFolder_btn.config(state = DISABLED if RewindMovieActive else NORMAL)

    if RewindErrorOutstanding:
        RewindErrorOutstanding = False
    else:
        time.sleep(0.2)
        if IsRpi:
            i2c.write_byte_data(16, 60, 0)

        #Invoke RewindLoop a first time shen rewind starts
        if RewindMovieActive :
            win.after(5,RewindLoop)

def RewindLoop():
    global RewindMovieActive
    global IsRpi
    global RewindErrorOutstanding

    if RewindMovieActive:
        # Invoke RewindLoop one more time, as long as rewind is ongoing
        if not RewindErrorOutstanding:
            win.after(5, RewindLoop)
        else:
            rewind_movie()


def fast_forward_movie():
    global FastForwardActive
    global IsRpi
    global FastForwardErrorOutstanding
    global save_bg
    global save_fg

    # Before proceeding, get confirmation from user that fild is correctly routed
    if not FastForwardActive:  # Ask only when rewind is not ongoing
        # Disable preview to make tkinter dialogs visible
        if IsRpi and PreviewEnabled:
            camera.stop_preview()
        answer = tkinter.messagebox.askyesno(title='Security check ',  message='Have you routed the film via the upper path?')
        if IsRpi and PreviewEnabled:
            camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))
        if not answer:
            return()
    else:
        if FastForwardErrorOutstanding:
            if IsRpi and PreviewEnabled:
                camera.stop_preview()
            tkinter.messagebox.showerror(title='Error during fast forward',
                                                 message='It seems there is film loaded via filmgate. Please route it via upper path.')
            if IsRpi and PreviewEnabled:
                camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))

   # Update button text
    if not FastForwardActive:  # Fast forward movie is about to start...
        FastForward_btn.config(text='Stop\n>>',bg='red',fg='white')  # ...so now we propose to stop it in the button test
    else:
        FastForward_btn.config(text='>>',bg=save_bg,fg=save_fg)  # Otherwise change to default text to start the action
    FastForwardActive = not FastForwardActive

    # Enable/Disable related buttons
    Free_btn.config(state=DISABLED if FastForwardActive else NORMAL)
    SingleStep_btn.config(state = DISABLED if FastForwardActive else NORMAL)
    AdvanceMovie_btn.config(state = DISABLED if FastForwardActive else NORMAL)
    Rewind_btn.config(state = DISABLED if FastForwardActive else NORMAL)
    Start_btn.config(state = DISABLED if FastForwardActive else NORMAL)
    PosNeg_btn.config(state = DISABLED if FastForwardActive else NORMAL)
    Focus_btn.config(state = DISABLED if FastForwardActive else NORMAL)
    OpenFolder_btn.config(state = DISABLED if FastForwardActive else NORMAL)

    if FastForwardErrorOutstanding:
        FastForwardErrorOutstanding = False
    else:
        # Send instruction to Arduino
        time.sleep(0.2)
        if IsRpi:
            i2c.write_byte_data(16, 80, 0)
        #Invoke FastForwardLoop a first time shen fast forward starts
        if FastForwardActive :
            win.after(5,FastForwardLoop)


def FastForwardLoop():
    global FastForwardActive
    global IsRpi
    global FastForwardErrorOutstanding

    if FastForwardActive:
        # Invoke RewindLoop one more time, as long as rewind is ongoing
        if not FastForwardErrorOutstanding:
            win.after(5, FastForwardLoop)
        else:
            fast_forward_movie()


def single_step_movie():
    if IsRpi:
        i2c.write_byte_data(16, 40, 0)

def emergency_stop():
    if IsRpi:
        i2c.write_byte_data(16, 90, 0)

def update_rpi_temp():
    global RPiTemp
    if (IsRpi):
        file = open('/sys/class/thermal/thermal_zone0/temp', 'r')
        temp_str = file.readline()
        file.close()
        RPiTemp = int(int(temp_str)/100)/10

def negative_capture():
    global NegativeCaptureStatus

    if NegativeCaptureStatus == False:
        if IsRpi:
            camera.image_effect = 'negative'
            camera.awb_gains = (1.7, 1.9)
    else:
        if IsRpi:
            camera.image_effect = 'none'
            camera.awb_gains = (3.5, 1.0)
    NegativeCaptureStatus = not NegativeCaptureStatus

def open_folder():
    global OpenFolderActive
    global FolderProcess
    global save_bg
    global save_fg

    if not OpenFolderActive :
        OpenFolder_btn.config(text="Close Folder",bg='red',fg='white')
        if IsRpi and PreviewEnabled:
            camera.stop_preview()
        FolderProcess = subprocess.Popen(["pcmanfm", BaseDir])
    else:
        OpenFolder_btn.config(text="Open Folder",bg=save_bg,fg=save_fg)
        FolderProcess.terminate()  # This does not work, neither do some other means found on the internet. To be done (not too critical)

        time.sleep(.5)
        if IsRpi and PreviewEnabled:
            camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))
        time.sleep(.5)

    OpenFolderActive = not OpenFolderActive

def disable_preview():
    global PreviewEnabled
    global save_bg
    global save_fg

    if IsRpi:
        if PreviewEnabled:
            camera.stop_preview();
        else:
            camera.start_preview(fullscreen=False, window=(PreviewWinX, PreviewWinY, 840, 720))

    PreviewEnabled = not PreviewEnabled

   # Update button text
    if PreviewEnabled:  # Preview is about to be enabled
        DisablePreview_btn.config(text='Disable Preview',bg=save_bg,fg=save_fg)
    else:
        DisablePreview_btn.config(text='Enable Preview',bg='red',fg='white')  # Otherwise change to default text to start the action


def capture():
    global CurrentDir
    global CurrentFrame
    global SessionData
    global PreviousCurrentExposure

    os.chdir(CurrentDir)

    if CurrentExposure == 0:
        while True:     # In case of exposure change, give time for the camera to adapt
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

    if IsRpi:
        camera.capture('picture-%05d.jpg' % CurrentFrame, quality=100)
    SessionData["CurrentDate"] = str(datetime.now())
    SessionData["CurrentFrame"] = str(CurrentFrame)


def StartScan():
    global CurrentDir
    global CurrentFrame
    global SessionData
    global ScanOngoing
    global CurrentScanStartFrame
    global CurrentScanStartTime
    global save_bg
    global save_fg

    if not ScanOngoing and BaseDir == CurrentDir:
        if IsRpi and PreviewEnabled:
            camera.stop_preview()
        tkinter.messagebox.showerror("Error!", "Please specify a folder where to store the captured images.")
        if IsRpi and PreviewEnabled:
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
    Free_btn.config(state=DISABLED if ScanOngoing else NORMAL)
    SingleStep_btn.config(state = DISABLED if ScanOngoing else NORMAL)
    AdvanceMovie_btn.config(state = DISABLED if ScanOngoing else NORMAL)
    Rewind_btn.config(state = DISABLED if ScanOngoing else NORMAL)
    FastForward_btn.config(state = DISABLED if ScanOngoing else NORMAL)
    Focus_btn.config(state = DISABLED if ScanOngoing else NORMAL)
    PosNeg_btn.config(state=DISABLED if ScanOngoing else NORMAL)
    new_folder_btn.config(state=DISABLED if ScanOngoing else NORMAL)
    existing_folder_btn.config(state=DISABLED if ScanOngoing else NORMAL)
    OpenFolder_btn.config(state=DISABLED if ScanOngoing else NORMAL)
    Exit_btn.config(state=DISABLED if ScanOngoing else NORMAL)


    #Send command to Arduino to stop/start scan (as applicable, Arduino keeps its own status)
    if IsRpi:
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

    if ScanOngoing:
        if NewFrameAvailable:
            CurrentFrame += 1
            capture()
            if IsRpi:
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

    if IsRpi:
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
    if IsRpi and PreviewEnabled:
        camera.start_preview(fullscreen = False, window= (PreviewWinX,PreviewWinY,840,720))
    """
    # Uncomment to have the details of each event
    for key in dir(event):
        if not key.startswith('_'):
            print('%s=%s' % (key, getattr(event, key)))
    print()
    """

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


# Application Exit button
Exit_btn = Button(win, text="Exit", width=12, height=5, command=exit_app, activebackground='red', activeforeground='white', wraplength=80)
Exit_btn.place(x=925, y=700)

# Create vertical button column at right
# Start scan button
Start_btn = Button(win, text="START Scan", width=14, height=5, command=StartScan, activebackground='green', activeforeground='white',  wraplength=80)
Start_btn.place(x=925, y=40)

# Create frame to select target folder
folder_border_frame = Frame(win, width=16, height=8, bg='black')
folder_border_frame.pack()
folder_border_frame.place(x=925, y=150)

folder_frame = Frame(folder_border_frame, width=16, height=8)
folder_frame.pack(side=TOP, padx=1, pady=1)

folder_frame_title = Frame(folder_frame, width=16, height=4)
folder_frame_title.pack()
folder_frame_title_label = Label(folder_frame_title, text='Target Folder', width=16, height=1)
folder_frame_title_label.pack(side=TOP)
folder_frame_folder_label = Label(folder_frame_title, text=CurrentDir, width=16, height=3, font=("Arial", 8), wraplength=60)
folder_frame_folder_label.pack(side=TOP)

folder_frame_buttons = Frame(folder_frame, width=16, height=4, bd=2)
folder_frame_buttons.pack()
new_folder_btn = Button(folder_frame_buttons, text='New', width=5, height=1, command=set_new_folder, activebackground='green', activeforeground='white', wraplength=80)
new_folder_btn.pack(side=TOP)
existing_folder_btn = Button(folder_frame_buttons, text='Existing', width=5, height=1, command=set_existing_folder, activebackground='green', activeforeground='white', wraplength=80)
existing_folder_btn.pack(side=TOP)

# Create frame to display number of scanned images, and frames per minute
Scanned_Images_border_frame = Frame(win, width=16, height=2, bg='black')
Scanned_Images_border_frame.pack()
Scanned_Images_border_frame.place(x=925, y=300)

Scanned_Images_frame = Frame(Scanned_Images_border_frame, width=16, height=4)
Scanned_Images_frame.pack(side=TOP, padx=1, pady=1)

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
exposure_border_frame = Frame(win, width=16, height=2, bg='black')
exposure_border_frame.pack()
exposure_border_frame.place(x=925, y=410)

exposure_frame = Frame(exposure_border_frame, width=16, height=2, bg='white')
exposure_frame.pack(side=TOP, padx=1, pady=1)

#exposure_frame_title = Frame(exposure_frame, width=8, height=1, bg='white')
#exposure_frame_title.pack()
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

# exposure_frame_aux = Frame(exposure_frame, width=8, height=1, bg='white') # Additional frame just to have some whitespace below buttons
# exposure_frame_aux.pack(side=TOP)
# exposure_frame_aux_label = Label(exposure_frame_aux, text='', width=14, height=1, bg='white')
# exposure_frame_aux_label.pack(side=TOP)

# Create frame to select perforation threshold dynamically (however scan mode needs to be stopped)
perforation_threshold_border_frame = Frame(win, width=16, height=2, bg='black')
perforation_threshold_border_frame.pack()
perforation_threshold_border_frame.place(x=925, y=510)

perforation_threshold_frame = Frame(perforation_threshold_border_frame, width=16, height=2, bg='white')
perforation_threshold_frame.pack(side=TOP, padx=1, pady=1)

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

# Create frame to display RPi temperature
RPi_temp_border_frame = Frame(win, width=8, height=2, bg='black')
RPi_temp_border_frame.pack()
RPi_temp_border_frame.place(x=945, y=620)

RPi_temp_frame = Frame(RPi_temp_border_frame, width=8, height=2)
RPi_temp_frame.pack(side=TOP, padx=1, pady=1)

RPi_temp_frame_label = Label(RPi_temp_frame, text='RPi Temp.', width=8, height=1, wraplength=120, bg='white')
RPi_temp_frame_label.pack(side=TOP)
RPi_temp_value_label = Label(RPi_temp_frame, text=str(RPiTemp), font=("Arial", 18), width=5, height=1, wraplength=120, bg='white')
RPi_temp_value_label.pack(side=TOP, fill='x')



# Check if existing session on script start

# Main Loop
while not ExitRequested:
    CaptureLoop()
    TempLoop()
    ArduinoListenLoop()
    if IsRpi:
        camera.shutter_speed = CurrentExposure

    # Enable events on windows movements, to allow preview to follow
    lblText = tk.Label(win, text='')
    lblText.pack()
    win.bind('<Configure>', onFormEvent)

    win.mainloop()  # running the loop that works as a trigger

if IsRpi:
    camera.close()

# win.mainloop()  # running the loop that works as a trigger
