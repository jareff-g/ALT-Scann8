/*
ALT-Scann8 UI - Alternative software for T-Scann 8

This tool is a fork of the original user interface application of T-Scann 8

Some additional features of this version include:
- PiCamera 2 integration
- Use of Tkinter instead of Pygame
- Automatic exposure support
- Fast forward support

  Licensed under a MIT LICENSE.

More info in README.md file
*/

#define __author__      "Juan Remirez de Esparza"
#define __copyright__   "Copyright 2022-25, Juan Remirez de Esparza"
#define __credits__     "Juan Remirez de Esparza"
#define __license__     "MIT"
#define __version__     "1.1.8"
#define  __date__       "2025-02-27"
#define  __version_highlight__  "Save scan mode to global var to prevent sending capstan advance message to RPi in PFD mode"
#define __maintainer__  "Juan Remirez de Esparza"
#define __email__       "jremirez@hotmail.com"
#define __status__      "Development"

#include <Wire.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

const int PHOTODETECT = A0; // Analog pin 0 perf
int MaxPT = 0;
int MinPT = 200;
// These two vars are to keep max/min pt values for the recent past
// Since keeping a sliding window will be too memory heavy (too manu samples) for Arduino, instead the max/min values
// are decrease/increased each time a new sample is taken. Stored values are multiplied by 10, to have more resolution
// (avoid decreasing/increasing too fast).
// The idea is to see if we can make the PT level value automatically set by the software, so that it adapts to different 
// part of the film (clear/dark around the holes) dynamically.
unsigned int MaxPT_Dynamic = 0;
unsigned int MinPT_Dynamic = 10000;


enum {
    PlotterInfo,
    FrameSteps,
    DebugInfo,
    DebugInfoSingle,
    None
} DebugState = None;

int MaxDebugRepetitions = 3;
#define MAX_DEBUG_REPETITIONS_COUNT 30000

boolean GreenLedOn = false;  
int UI_Command; // Stores I2C command from Raspberry PI --- ScanFilm=10 / UnlockReels mode=20 / Slow Forward movie=30 / One step frame=40 / Rewind movie=60 / Fast Forward movie=61 / Set Perf Level=90
// I2C commands (RPi to Arduino): Constant definition
#define CMD_VERSION_ID 1
#define CMD_GET_CNT_STATUS 2
#define CMD_RESET_CONTROLLER 3
#define CMD_ADJUST_MIN_FRAME_STEPS 4
#define CMD_START_SCAN 10
#define CMD_TERMINATE 11
#define CMD_GET_NEXT_FRAME 12
#define CMD_STOP_SCAN 13
#define CMD_SET_REGULAR_8 18
#define CMD_SET_SUPER_8 19
#define CMD_SWITCH_REEL_LOCK_STATUS 20
#define CMD_MANUAL_UV_LED 22
#define CMD_FILM_FORWARD 30
#define CMD_FILM_BACKWARD 31
#define CMD_SINGLE_STEP 40
#define CMD_ADVANCE_FRAME 41
#define CMD_ADVANCE_FRAME_FRACTION 42
#define CMD_RUN_FILM_COLLECTION 43
#define CMD_SET_PT_LEVEL 50
#define CMD_SET_MIN_FRAME_STEPS 52
#define CMD_SET_FRAME_FINE_TUNE 54
#define CMD_SET_EXTRA_STEPS 56
#define CMD_SET_UV_LEVEL 58
#define CMD_REWIND 60
#define CMD_FAST_FORWARD 61
#define CMD_INCREASE_WIND_SPEED 62
#define CMD_DECREASE_WIND_SPEED 63
#define CMD_UNCONDITIONAL_REWIND 64
#define CMD_UNCONDITIONAL_FAST_FORWARD 65
#define CMD_SET_SCAN_SPEED 70
#define CMD_SET_STALL_TIME 72
#define CMD_SET_AUTO_STOP 74
#define CMD_REPORT_PLOTTER_INFO 87
// I2C responses (Arduino to RPi): Constant definition
#define RSP_VERSION_ID 1
#define RSP_FORCE_INIT 2
#define RSP_FRAME_AVAILABLE 80
#define RSP_SCAN_ERROR 81
#define RSP_REWIND_ERROR 82
#define RSP_FAST_FORWARD_ERROR 83
#define RSP_REWIND_ENDED 84
#define RSP_FAST_FORWARD_ENDED 85
#define RSP_REPORT_AUTO_LEVELS 86
#define RSP_REPORT_PLOTTER_INFO 87
#define RSP_SCAN_ENDED 88
#define RSP_FILM_FORWARD_ENDED 89
#define RSP_ADVANCE_FRAME_FRACTION 90


// Immutable values
#define S8_HEIGHT  4.01
#define R8_HEIGHT  3.3
#define NEMA_STEP_DEGREES  1.8
#define NEMA_MICROSTEPS_IN_STEP  16

//------------ Stepper motors control ----------------
const int MotorA_Stepper = 2;     // Stepper motor film feed
const int MotorA_Neutral = 3;     // neutral position
const int MotorB_Stepper = 4;     // Stepper motor capstan propulsion
const int MotorB_Neutral = 5;     // neutral position
const int MotorC_Stepper = 6;     // Stepper motor film winding
const int MotorC_Neutral = 7;     // neutral position
const int MotorA_Direction = 8;   // direction
const int MotorB_Direction = 9;   // direction
const int MotorC_Direction = 10;  // direction
const int TractionStopPin = 12; // Traction stop

enum ScanResult{SCAN_NO_FRAME_DETECTED, SCAN_FRAME_DETECTED, SCAN_FRAME_DETECTION_ERROR, SCAN_TERMINATION_REQUESTED};

enum ScanState{
    Sts_Idle,
    Sts_Scan,
    Sts_UnlockReels,
    Sts_Rewind,
    Sts_FastForward,
    Sts_SlowForward,
    Sts_SlowBackward,
    Sts_SingleStep,
    Sts_ManualUvLed
}
ScanState=Sts_Idle;

// ----- Scanner specific variables: Might need to be adjusted for each specific scanner ------
int UVLedBrightness = 255;                  // Brightness UV led, may need to be changed depending on LED type
int ScanSpeed = 10;                         // 10 - Nominal scan speed as displayed in the UI
unsigned long BaseScanSpeedDelay = 10;      // 25 - Base delay to calculate scan speed on which other are based
unsigned long StepScanSpeedDelay = 100;     // 250: Increment delays to reduce scan speed
unsigned long ScanSpeedDelay = BaseScanSpeedDelay;    // 500 - Delay in microseconds used to adjust speed of stepper motor during scan process
unsigned long DecreaseScanSpeedDelayStep = 50;   // 100 - Increment in microseconds of delay to slow down progressively scanning speed, to improve detection (set to zero to disable)
int RewindSpeed = 4000;                     // Initial delay in microseconds used to determine speed of rewind/FF movie
int TargetRewindSpeedLoop = 200;            // Final delay  in microseconds for rewind/SS speed (Originally hardcoded)
int PerforationMaxLevel = 550;              // Phototransistor reported value, max level
int PerforationMinLevel = 50;               // Phototransistor reported value, min level (originalyl hardcoded)
int PerforationThresholdLevelR8 = 180;      // Default value for R8
int PerforationThresholdLevelS8 = 90;       // Default value for S8
int PerforationThresholdLevel = PerforationThresholdLevelS8;    // Phototransistor value to decide if new frame is detected
int PerforationThresholdAutoLevelRatio = 40;  // Percentage between dynamic max/min PT level - Can be changed from 20 to 60
float CapstanDiameter = 14.3;         // Capstan diameter, to calculate actual number of steps per frame
int MinFrameStepsR8;                  // R8_HEIGHT/((PI*CapstanDiameter)/(360/(NEMA_STEP_DEGREES/NEMA_MICROSTEPS_IN_STEP)));  // Default value for R8 (236 aprox)
int MinFrameStepsS8;                  // S8_HEIGHT/((PI*CapstanDiameter)/(360/(NEMA_STEP_DEGREES/NEMA_MICROSTEPS_IN_STEP))); // Default value for S8 (286 aprox)
int MinFrameSteps = MinFrameStepsS8;        // Minimum number of steps to allow frame detection
int FrameExtraSteps = 0;              // Allow framing adjustment on the fly (manual, automatic would require using CV2 pattern matching, maybe to be checked)
int FrameDeductSteps = 0;               // Manually force reduction of MinFrameSteps when ExtraFrameSteps is negative
int DecreaseSpeedFrameStepsBefore = 3;  // 3 - Hardcoded, before Dec 2024 it was adjusted according to scan speed
int DecreaseSpeedFrameSteps = MinFrameSteps - DecreaseSpeedFrameStepsBefore;    // Steps at which the scanning speed starts to slow down to improve detection
// ------------------------------------------------------------------------------------------

boolean ReelsUnlocked = false;
boolean FrameDetected = false;  // Used for frame detection, in play ond single step modes
boolean UVLedOn = false;
int FilteredSignalLevel = 0;
int OriginalPerforationThresholdLevel = PerforationThresholdLevel; // stores value for resetting PerforationThresholdLevel
int OriginalPerforationThresholdAutoLevelRatio = PerforationThresholdAutoLevelRatio;
int FrameStepsDone = 0;                     // Count steps
// OriginalScanSpeedDelay keeps a safe value to revert to in case of need, should not be updated
// with dynamically calculated values
unsigned long OriginalScanSpeedDelay = ScanSpeedDelay;          // Keep to restore original value when needed
int OriginalMinFrameSteps = MinFrameSteps;  // Keep to restore original value when needed

int LastFrameSteps = 0;                     // Stores number of steps required to reach current frame (stats only)
int LastPTLevel = 0;                        // Stores last PT level (stats only)

boolean IsS8 = true;

boolean TractionSwitchActive = true;  // When traction micro-switch is closed

unsigned long StartFrameTime = 0;           // Time at which we get RPi command to get next frame (stats only)
unsigned long StartPictureSaveTime = 0;     // Time at which we tell RPi to save current frame (stats only)
unsigned long FilmDetectedTime = 0;         // Updated when film is present (relevant PT variation)
bool NoFilmDetected = false;
int MaxFilmStallTime = 6000;                // Maximum time film can be undetected to report end of reel

byte BufferForRPi[9];   // 9 byte array to send data to Raspberry Pi over I2C bus

int PT_SignalLevelRead;   // Raw signal level from phototransistor
boolean PT_Level_Auto = true;   // Automatic calculation of PT level threshold

boolean Frame_Steps_Auto = true;

boolean IntegratedPlotter = false;

boolean AutoStopEnabled = false;

boolean VFD_mode_active = false;

// Collect outgoing film frequency
int default_collect_timer = 1000;
int collect_timer = default_collect_timer;
int scan_collect_timer = collect_timer;
bool scan_process_ongoing = false;

// JRE - Support data variables
#define QUEUE_SIZE 20
typedef struct Queue {
    int Data[QUEUE_SIZE];
    int Param[QUEUE_SIZE];
    int Param2[QUEUE_SIZE];
    int in;
    int out;
};

volatile Queue CommandQueue;
volatile Queue ResponseQueue;

void SendToRPi(byte rsp, int param1, int param2)
{
    push_rsp(rsp, param1, param2);
}

void(* resetFunc) (void) = 0;//declare reset function at address 0

void setup() {
    // Possible serial speeds: 1200, 2400, 4800, 9600, 19200, 38400, 57600,74880, 115200, 230400, 250000, 500000, 1000000, 2000000
    Serial.begin(1000000);  // As fast as possible for debug, otherwise it slows down execution
  
    Wire.begin(16);  // join I2c bus with address #16
    Wire.setClock(400000);  // Set the I2C clock frequency to 400 kHz
    Wire.onReceive(receiveEvent); // register event
    Wire.onRequest(sendEvent);

    //--- set pinMode Stepper motors -----
    pinMode(MotorA_Stepper, OUTPUT);
    pinMode(MotorA_Direction, OUTPUT);
    pinMode(MotorB_Stepper, OUTPUT);
    pinMode(MotorB_Direction, OUTPUT);
    pinMode(MotorC_Stepper, OUTPUT);
    pinMode(MotorC_Direction, OUTPUT);
    pinMode(TractionStopPin, INPUT);
    pinMode(MotorA_Neutral, OUTPUT);
    pinMode(MotorB_Neutral, OUTPUT);
    pinMode(MotorC_Neutral, OUTPUT);
    //---------------------------
    pinMode(A1, OUTPUT); // Green LED
    pinMode(A2, OUTPUT); // beep
    pinMode(11, OUTPUT); // UV Led

    // neutral position
    digitalWrite(MotorA_Neutral, HIGH);

    // set direction on stepper motors
    digitalWrite(MotorA_Direction, LOW);     // Always counter-clockwise (rewind)
    digitalWrite(MotorB_Direction, HIGH);    // Normally clockwise (advance to next frame)
    digitalWrite(MotorC_Direction, HIGH);    // Always clockwise (collect + FF)

    digitalWrite(MotorA_Stepper, LOW);
    digitalWrite(MotorB_Stepper, LOW);
    digitalWrite(MotorC_Stepper, LOW);

    // JRE 04/08/2022
    CommandQueue.in = 0;
    CommandQueue.out = 0;
    ResponseQueue.in = 0;
    ResponseQueue.out = 0;

    // Unlock reels at start up, then lock on demand
    SetReelsAsNeutral(HIGH, HIGH, HIGH);

    // Adjust Min frame steps based on capstan diameter
    AdjustMinFrameStepsFromCapstanDiameter(CapstanDiameter);
}

void loop() {
    int param;
    int cnt_ver_1 = 0, cnt_ver_2 = 0, cnt_ver_3 = 0;
    char *pt;

    SendToRPi(RSP_FORCE_INIT, 0, 0);  // Request UI to resend init sequence, in case controller reloaded while UI active

    while (1) {
        if (dataInCmdQueue())
            UI_Command = pop_cmd(&param);   // Get next command from queue if one exists
        else
            UI_Command = 0;

        ReportPlotterInfo();    // Regular report of plotter info

        /*
        if (ScanState != Sts_Scan && ScanState != Sts_SingleStep) {
            // Set default state and direction of motors B and C (disabled, clockwise)
            // In the original main loop this was done when UI_Command was NOT Single Step (49). Why???
            // JRE 23-08-2022: Explanation: THis is done mainly for the slow forward function, so that
            //    setting to high both the motors B and C they will move one step forward
            if (UI_Command != CMD_SINGLE_STEP){  // In case we need the exact behavior of original code
                digitalWrite(MotorB_Stepper, LOW);
                digitalWrite(MotorC_Stepper, LOW);
            }
        }
        */

        switch (UI_Command) {   // Stateless commands
            case CMD_RESET_CONTROLLER:
                resetFunc();
                break;
            case CMD_ADJUST_MIN_FRAME_STEPS:
                DebugPrint(">Adjust MFS", param);
                if (param >= 80 && param <= 300) {   // Capsta diameter between 8-30mm
                    CapstanDiameter = param/10;
                    AdjustMinFrameStepsFromCapstanDiameter(CapstanDiameter);
                    if (IsS8)
                        MinFrameSteps = MinFrameStepsS8;
                    else
                        MinFrameSteps = MinFrameStepsR8;
                    OriginalMinFrameSteps = MinFrameSteps;
                }
                break;
            case CMD_SET_PT_LEVEL:
                DebugPrint(">PTLevel", param);
                if (param >= 0 && param <= 900) {
                    if (param == 0)
                        PT_Level_Auto = true;     // zero means we go in automatic mode
                    else {
                        PT_Level_Auto = false;
                        PerforationThresholdLevel = param;
                        OriginalPerforationThresholdLevel = param;
                    }
                    DebugPrint(">PTLevel",param);
                }
                break;
            case CMD_SET_UV_LEVEL:
                DebugPrint(">UVLevel", param);
                if (param >= 1 && param <= 255) {
                    UVLedBrightness = param;
                    if (UVLedOn) {
                        analogWrite(11, UVLedBrightness); // If UV LED on, set it to requested level
                    }
                }
                break;
            case CMD_SET_MIN_FRAME_STEPS:
                DebugPrint(">MinFSteps", param);
                if (param == 0 || param >= 100 && param <= 600) {
                    if (param == 0) {
                        Frame_Steps_Auto = true;     // zero means we go in automatic mode
                        if (IsS8)
                            MinFrameSteps = MinFrameStepsS8;
                        else
                            MinFrameSteps = MinFrameStepsR8;
                        OriginalMinFrameSteps = MinFrameSteps;
                    }
                    else {
                        Frame_Steps_Auto = false;
                        MinFrameSteps = param;
                        OriginalMinFrameSteps = MinFrameSteps;
                        /*
                        if (IsS8)
                            MinFrameStepsS8 = param;
                        else
                            MinFrameStepsR8 = param;
                        */
                        DecreaseSpeedFrameSteps = MinFrameSteps - DecreaseSpeedFrameStepsBefore;
                        DebugPrint(">MinSteps",param);
                    }
                }
                break;
            case CMD_SET_STALL_TIME:
                DebugPrint(">Stall", param);
                // Limit parameter to valid values (between 1 and 12 seconds)
                if (param < 1) param = 1;
                if (param > 12) param = 12;
                MaxFilmStallTime = param * 1000;
                break;
            case CMD_SET_FRAME_FINE_TUNE:       // Adjust PT threshold to % between min and max PT
                DebugPrint(">FineT", param);
                if (param >= 5 and param <= 95)   // Añllowed valued between 5 adn 95%
                    PerforationThresholdAutoLevelRatio = param;
                break;
            case CMD_SET_EXTRA_STEPS:
                DebugPrint(">BoostPT", param);
                if (param >= 1 && param <= 30)  // Also to move up we add extra steps
                    FrameExtraSteps = param;
                else if (param >= -30 && param <= -1)  // Manually force reduction of MinFrameSteps
                    FrameDeductSteps = param;
                break;
            case CMD_SET_SCAN_SPEED:
                DebugPrint(">Speed", param);
                if (param >= 1 and param <= 10) {   // Handle only if valid speed (I2C sometimes fails)
                    ScanSpeed = param;
                    ScanSpeedDelay = BaseScanSpeedDelay + (10-param) * StepScanSpeedDelay;
                    scan_collect_timer = collect_timer = default_collect_timer + (10-param) * 100;
                    OriginalScanSpeedDelay = ScanSpeedDelay;
                    DecreaseSpeedFrameStepsBefore = max(3, 53 - 5*param);
                    DecreaseSpeedFrameSteps = MinFrameSteps - DecreaseSpeedFrameStepsBefore;
                }
                break;
            case CMD_REPORT_PLOTTER_INFO:
                DebugPrint(">PlotterInfo", param);
                IntegratedPlotter = param;
                break;
            case CMD_STOP_SCAN:
                DebugPrintStr(">Scan stop");
                FrameDetected = false;
                LastFrameSteps = 0;
                if (UVLedOn) {
                    analogWrite(11, 0); // Turn off UV LED
                    UVLedOn = false;
                }
                scan_process_ongoing = false;
                SetReelsAsNeutral(HIGH, HIGH, HIGH);
                ScanState = Sts_Idle;
                break;
            case CMD_SET_AUTO_STOP:
                DebugPrint(">Auto stop", param);
                AutoStopEnabled = param;
                break;
        }

        if (scan_process_ongoing)
            CollectOutgoingFilm();

        switch (ScanState) {
            case Sts_Idle:
                switch (UI_Command) {
                    case CMD_VERSION_ID:
                        DebugPrintStr(">V_ID");
                        char *pt;
                        pt = strtok (__version__,".");
                        if (pt != NULL) {
                            cnt_ver_1 = atoi(pt);
                            pt = strtok (NULL, ".");
                            if (pt != NULL) {
                                cnt_ver_2 = atoi(pt);
                                pt = strtok (NULL, ".");
                                if (pt != NULL) {
                                    cnt_ver_3 = atoi(pt);
                                }
                                else
                                    cnt_ver_3 = 0;
                            }
                            else
                                cnt_ver_2 = 0;
                        }
                        else
                            cnt_ver_1 = 0;
                        SendToRPi(RSP_VERSION_ID, cnt_ver_1 * 256 + 1, cnt_ver_2 * 256 + cnt_ver_3);  // 1 - Arduino, 2 - RPi Pico
                        break;
                    case CMD_START_SCAN:
                        tone(A2, 2000, 50); // Beep to indicate start of scanning
                        delay(100);     // Delay to avoind beep interfering with uv led PWB (both use same timer)
                        SetReelsAsNeutral(HIGH, LOW, LOW);
                        DebugPrintStr(">Scan start");
                        digitalWrite(MotorB_Direction, HIGH);    // Set as clockwise, just in case
                        VFD_mode_active = param;
                        if (!VFD_mode_active) {   // Traditional mode with phototransistor detection, go to dedicated state
                            ScanState = Sts_Scan;
                            StartFrameTime = micros();
                            FilmDetectedTime = millis() + MaxFilmStallTime;
                            NoFilmDetected = false;
                            ScanSpeedDelay = OriginalScanSpeedDelay;
                        }
                        analogWrite(11, UVLedBrightness); // Turn on UV LED
                        UVLedOn = true;
                        scan_process_ongoing = true;
                        delay(50);     // Wait for PT to stabilize after switching UV led on
                        collect_timer = scan_collect_timer;
                        break;
                    case CMD_TERMINATE:  //Exit app
                        if (UVLedOn) {
                            analogWrite(11, 0); // Turn off UV LED
                            UVLedOn = false;
                        }
                        break;
                    case CMD_GET_NEXT_FRAME:  // Continue scan to next frame
                        ScanState = Sts_Scan;
                        StartFrameTime = micros();
                        ScanSpeedDelay = OriginalScanSpeedDelay;
                        DebugPrint("Save t.",StartFrameTime-StartPictureSaveTime);
                        DebugPrintStr(">Next fr.");
                        // Also send, if required, to RPi autocalculated threshold level every frame
                        // Alternate reports for each value, otherwise I2C has I/O errors
                        if (PT_Level_Auto || Frame_Steps_Auto)
                            SendToRPi(RSP_REPORT_AUTO_LEVELS, PerforationThresholdLevel, MinFrameSteps+FrameDeductSteps);
                        break;
                    case CMD_SET_REGULAR_8:  // Select R8 film
                        DebugPrintStr(">R8");
                        IsS8 = false;
                        MinFrameSteps = MinFrameStepsR8;
                        DecreaseSpeedFrameSteps = MinFrameSteps - DecreaseSpeedFrameStepsBefore;
                        OriginalMinFrameSteps = MinFrameSteps;
                        if (!PT_Level_Auto)
                            PerforationThresholdLevel = PerforationThresholdLevelR8;
                        OriginalPerforationThresholdLevel = PerforationThresholdLevelR8;
                        break;
                    case CMD_SET_SUPER_8:  // Select S8 film
                        DebugPrintStr(">S8");
                        IsS8 = true;
                        MinFrameSteps = MinFrameStepsS8;
                        DecreaseSpeedFrameSteps = MinFrameSteps - DecreaseSpeedFrameStepsBefore;
                        OriginalMinFrameSteps = MinFrameSteps;
                        if (!PT_Level_Auto)
                            PerforationThresholdLevel = PerforationThresholdLevelS8;
                        OriginalPerforationThresholdLevel = PerforationThresholdLevelS8;
                        break;
                    case CMD_SWITCH_REEL_LOCK_STATUS:
                        ScanState = Sts_UnlockReels;
                        delay(50);
                        break;
                    case CMD_MANUAL_UV_LED:
                        analogWrite(11, UVLedBrightness); // Switch UV LED on
                        UVLedOn = true;
                        ScanState = Sts_ManualUvLed;
                        break;
                    case CMD_FILM_FORWARD:
                        SetReelsAsNeutral(HIGH, LOW, LOW);
                        FilmDetectedTime = millis() + MaxFilmStallTime;
                        NoFilmDetected = false;
                        collect_timer = 500;
                        analogWrite(11, UVLedBrightness); // Turn on UV LED
                        UVLedOn = true;
                        ScanState = Sts_SlowForward;
                        digitalWrite(MotorB_Direction, HIGH);    // Set as clockwise, just in case
                        delay(50);
                        break;
                    case CMD_FILM_BACKWARD:
                        SetReelsAsNeutral(HIGH, LOW, HIGH);
                        digitalWrite(MotorB_Direction, LOW);    // Set as anti-clockwise, only for this function
                        collect_timer = 10;
                        ScanState = Sts_SlowBackward;
                        delay(50);
                        break;
                    case CMD_SINGLE_STEP:
                        SetReelsAsNeutral(HIGH, LOW, LOW);
                        DebugPrintStr(">SStep");
                        ScanState = Sts_SingleStep;
                        digitalWrite(MotorB_Direction, HIGH);    // Set as clockwise, just in case
                        delay(50);
                        break;
                    case CMD_REWIND: // Rewind
                    case CMD_UNCONDITIONAL_REWIND: // Rewind unconditional
                        if (FilmInFilmgate() and UI_Command == CMD_REWIND) { // JRE 13 Aug 22: Cannot rewind, there is film loaded
                            DebugPrintStr("Rwnd err");
                            SendToRPi(RSP_REWIND_ERROR, 0, 0);
                            tone(A2, 2000, 100);
                            delay (150);
                            tone(A2, 1000, 100);
                        }
                        else {
                            DebugPrintStr("Rwnd");
                            ScanState = Sts_Rewind;
                            delay (100);
                            SetReelsAsNeutral(LOW, HIGH, HIGH);
                            tone(A2, 2200, 100);
                            delay (150);
                            tone(A2, 2200, 100);
                            delay (150);
                            tone(A2, 2000, 200);
                            RewindSpeed = 4000;
                        }
                        delay(50);
                        break;
                    case CMD_FAST_FORWARD:  // Fast Forward
                    case CMD_UNCONDITIONAL_FAST_FORWARD:  // Fast Forward unconditional
                        if (FilmInFilmgate() and UI_Command == CMD_FAST_FORWARD) { // JRE 13 Aug 22: Cannot fast forward, there is film loaded
                            DebugPrintStr("FF err");
                            SendToRPi(RSP_FAST_FORWARD_ERROR, 0, 0);
                            tone(A2, 2000, 100);
                            delay (150);
                            tone(A2, 1000, 100);
                        }
                        else {
                            DebugPrintStr(">FF");
                            ScanState = Sts_FastForward;
                            delay (100);
                            SetReelsAsNeutral(HIGH, HIGH, LOW);
                            tone(A2, 2000, 100);
                            delay (150);
                            tone(A2, 2000, 100);
                            delay (150);
                            tone(A2, 2200, 200);
                            RewindSpeed = 4000;
                        }
                        break;
                    case CMD_INCREASE_WIND_SPEED:  // Tune Rewind/FF speed delay up, allowing to slow down the rewind/ff speed
                        if (TargetRewindSpeedLoop < 4000)
                            TargetRewindSpeedLoop += 20;
                        break;
                    case CMD_DECREASE_WIND_SPEED:  // Tune Rewind/FF speed delay down, allowing to speed up the rewind/ff speed
                        if (TargetRewindSpeedLoop > 200)
                          TargetRewindSpeedLoop -= 20;
                        break;
                    case CMD_ADVANCE_FRAME:
                        SetReelsAsNeutral(HIGH, LOW, LOW);
                        DebugPrint(">Advance frame", IsS8 ? MinFrameStepsS8 : MinFrameStepsR8);
                        if (IsS8)
                            capstan_advance(MinFrameStepsS8);
                        else
                            capstan_advance(MinFrameStepsR8);
                        break;
                    case CMD_ADVANCE_FRAME_FRACTION:
                        SetReelsAsNeutral(HIGH, LOW, LOW);
                        DebugPrint(">Advance frame", param);
                        // Parameter validation: Can be 5 or 20 for manual scan, allow 400 for VFD)
                        if (param >=1 and param <= 400)
                            capstan_advance(param);
                        break;
                    case CMD_RUN_FILM_COLLECTION:   // Used by manual scan
                        SetReelsAsNeutral(HIGH, LOW, LOW);
                        DebugPrint(">Collect film", param);
                        CollectOutgoingFilmNow();
                        break;
                }
                break;
            case Sts_Scan:
                switch (scan(UI_Command)) {
                    case SCAN_NO_FRAME_DETECTED:
                        break;
                    case SCAN_FRAME_DETECTED:
                        ScanState = Sts_Idle; // Exit scan loop
                        SendToRPi(RSP_FRAME_AVAILABLE, LastFrameSteps, LastPTLevel);
                        break;
                    case SCAN_TERMINATION_REQUESTED:
                    case SCAN_FRAME_DETECTION_ERROR:
                        ScanState = Sts_Idle; // Exit scan loop
                        break;
                }
                break;
            case Sts_SingleStep:
                if (scan(UI_Command) != SCAN_NO_FRAME_DETECTED) {
                    ScanState = Sts_Idle;
                    SetReelsAsNeutral(HIGH, HIGH, HIGH);
                }
                break;
            case Sts_UnlockReels:
                if (UI_Command == CMD_SWITCH_REEL_LOCK_STATUS) { //request to lock reels again
                    ReelsUnlocked = false;
                    digitalWrite(MotorB_Neutral, LOW);
                    digitalWrite(MotorC_Neutral, LOW);
                    ScanState = Sts_Idle;
                }
                else {
                    if (not ReelsUnlocked){
                        ReelsUnlocked = true;
                        digitalWrite(MotorB_Neutral, HIGH);
                        digitalWrite(MotorC_Neutral, HIGH);
                    }
                    GetLevelPT();   // No need to know PT level here, but used to update plotter data
                }
                break;
            case Sts_ManualUvLed:
                if (UI_Command == CMD_MANUAL_UV_LED) { //request to switch of uv led
                    UVLedOn = false;
                    analogWrite(11, 0);
                    ScanState = Sts_Idle;
                }
                else {
                    GetLevelPT();   // No need to know PT level here, but used to update plotter data
                }
                break;
            case Sts_Rewind:
                if (!RewindFilm(UI_Command)) {
                    DebugPrintStr("-rwnd");
                    ScanState = Sts_Idle;
                    SetReelsAsNeutral(HIGH, HIGH, HIGH);
                }
                break;
            case Sts_FastForward:
                if (!FastForwardFilm(UI_Command)) {
                    DebugPrintStr("-FF");
                    ScanState = Sts_Idle;
                    SetReelsAsNeutral(HIGH, HIGH, HIGH);
                }
                break;
            case Sts_SlowForward:
                if (UI_Command == CMD_FILM_FORWARD) { // Stop slow forward
                    delay(50);
                    analogWrite(11, 0); // Turn off UV LED
                    UVLedOn = false;
                    ScanState = Sts_Idle;
                    SetReelsAsNeutral(HIGH, HIGH, HIGH);
                }
                else {
                    if (!SlowForward()) {
                        analogWrite(11, 0); // Turn off UV LED
                        UVLedOn = false;
                        ScanState = Sts_Idle;
                        SetReelsAsNeutral(HIGH, HIGH, HIGH);
                    }
                }
                break;
            case Sts_SlowBackward:
                if (UI_Command == CMD_FILM_BACKWARD) { // Stop slow forward
                    digitalWrite(MotorB_Direction, HIGH);    // Slow backward finished, set as clockwise again
                    delay(50);
                    ScanState = Sts_Idle;
                    SetReelsAsNeutral(HIGH, HIGH, HIGH);
                }
                else {
                    SlowBackward();
                }
                break;
        }
    }
}

void AdjustMinFrameStepsFromCapstanDiameter(float diameter) {
    MinFrameStepsR8 = R8_HEIGHT/((PI*diameter)/(360/(NEMA_STEP_DEGREES/NEMA_MICROSTEPS_IN_STEP)));  // Default value for R8 (236 aprox)
    MinFrameStepsS8 = S8_HEIGHT/((PI*diameter)/(360/(NEMA_STEP_DEGREES/NEMA_MICROSTEPS_IN_STEP)));  // Default value for S8 (286 aprox)
}

void SetReelsAsNeutral(boolean ReelA, boolean ReelB, boolean ReelC) {
    digitalWrite(MotorA_Neutral, ReelA);  // No need to unlock reel A, it is always unlocked (except in Rewind)
    digitalWrite(MotorB_Neutral, ReelB);
    digitalWrite(MotorC_Neutral, ReelC);

}

// ------ rewind the movie ------
boolean RewindFilm(int UI_Command) {
    boolean retvalue = true;
    static boolean stopping = false;

    if (UI_Command == CMD_REWIND) {
        stopping = true;
    }
    else if (stopping) {
        if (RewindSpeed < 4000) {
            digitalWrite(MotorA_Stepper, HIGH);
            delayMicroseconds(RewindSpeed);
            digitalWrite(MotorA_Stepper, LOW);
            RewindSpeed += round(max(1,RewindSpeed/400));
        }
        else {
            retvalue = false;
            stopping = false;
            ///SetReelsAsNeutral(HIGH, LOW, LOW);
            delay (100);
            SendToRPi(RSP_REWIND_ENDED, 0, 0);
        }
    }
    else {
        digitalWrite(MotorA_Stepper, HIGH);
        delayMicroseconds(RewindSpeed);
        digitalWrite(MotorA_Stepper, LOW);
        if (RewindSpeed >= TargetRewindSpeedLoop) {
            RewindSpeed -= round(max(1,RewindSpeed/400));
        }
    }
    return(retvalue);
}

// ------ fast forward the movie ------
boolean FastForwardFilm(int UI_Command) {
    boolean retvalue = true;
    static boolean stopping = false;

    if (UI_Command == CMD_FAST_FORWARD) {
        stopping = true;
    }
    else if (stopping) {
        if (RewindSpeed < 4000) {
            digitalWrite(MotorC_Stepper, HIGH);
            delayMicroseconds(RewindSpeed);
            digitalWrite(MotorC_Stepper, LOW);
            RewindSpeed += round(max(1,RewindSpeed/400));
        }
        else {
            retvalue = false;
            stopping = false;
            ///SetReelsAsNeutral(HIGH, LOW, LOW);
            delay (100);
            SendToRPi(RSP_FAST_FORWARD_ENDED, 0, 0);
        }
    }
    else {
        digitalWrite(MotorC_Stepper, HIGH);
        delayMicroseconds(RewindSpeed);
        digitalWrite(MotorC_Stepper, LOW);
        if (RewindSpeed >= TargetRewindSpeedLoop) {
            RewindSpeed -= round(max(1,RewindSpeed/400));
        }
    }
    return(retvalue);
}

// ------------- Collect outgoing film
// Latest version, simpler, based on regular activation and motor activation frequency (to soften the pull)
// Still, pinch roller (https://www.thingiverse.com/thing:5583753) and microswitch
// (https://www.thingiverse.com/thing:5541340) are required. Without them (specially without pinch roller)
// tension might not be enough for the capstan to pull the film.
void CollectOutgoingFilm(void) {
    static unsigned long TimeToCollect = 0;
    unsigned long CurrentTime = millis();

    if (CurrentTime < TimeToCollect && TimeToCollect - CurrentTime < collect_timer) {
        return;
    }
    else {
        TractionSwitchActive = digitalRead(TractionStopPin);
        if (!TractionSwitchActive) {  //Motor allowed to turn
            digitalWrite(MotorC_Stepper, LOW);
            digitalWrite(MotorC_Stepper, HIGH);
            // digitalWrite(MotorC_Stepper, LOW);
            TractionSwitchActive = digitalRead(TractionStopPin);
        }
        if (TractionSwitchActive)
            TimeToCollect = CurrentTime + collect_timer;
        else
            TimeToCollect = CurrentTime + 3;
    }
}

// Function required to collect the film when usign manual scan
// Since there is no dedicated step, and we do not want to lock motor C, 
// we collect all pending film in a single loop, with a 3ms delay to mimick the standard collect
void CollectOutgoingFilmNow(void) {
    TractionSwitchActive = digitalRead(TractionStopPin);
    while (!TractionSwitchActive) {  //Motor allowed to turn
        digitalWrite(MotorC_Stepper, LOW);
        digitalWrite(MotorC_Stepper, HIGH);
        // digitalWrite(MotorC_Stepper, LOW);
        TractionSwitchActive = digitalRead(TractionStopPin);
        delay(10);
    }
}

// ------------- Detect when PT curve becomes flat ---------------
boolean film_detected(int pt_value)
{
    static int max_value, min_value;
    int instant_variance;
    static unsigned long time_to_renew_minmax = 0;
    unsigned long CurrentTime = millis();
    int minmax_validity_time = 2000;  // Renew min max values every two seconds

    if (CurrentTime > time_to_renew_minmax || time_to_renew_minmax - CurrentTime > minmax_validity_time) {
      time_to_renew_minmax = CurrentTime + minmax_validity_time;
      max_value = MinPT;
      min_value = MaxPT;
    }
    max_value = max(max_value, pt_value);
    min_value = min(min_value, pt_value);

    instant_variance = max_value - min_value;
    if (instant_variance > 30)
        return(true);
    else
        return(false);
}

// ------------- Centralized phototransistor level read ---------------
int GetLevelPT() {
    float ratio;
    int user_margin, fixed_margin, average_pt;
    unsigned long CurrentTime = millis();

    PT_SignalLevelRead = analogRead(PHOTODETECT);
    MaxPT = max(PT_SignalLevelRead, MaxPT);
    MinPT = min(PT_SignalLevelRead, MinPT);
    MaxPT_Dynamic = max(PT_SignalLevelRead*10, MaxPT_Dynamic);
    MinPT_Dynamic = min(PT_SignalLevelRead*10, MinPT_Dynamic);
    if (MaxPT_Dynamic > (MinPT_Dynamic+5)) MaxPT_Dynamic-=5;
    //if (MinPT_Dynamic < MaxPT_Dynamic) MinPT_Dynamic+=int((MaxPT_Dynamic-MinPT_Dynamic)/10);  // need to catch up quickly for overexposed frames (proportional to MaxPT to adapt to any scanner)
    if (MinPT_Dynamic < (MaxPT_Dynamic-15)) MinPT_Dynamic+=15;  // need to catch up quickly for overexposed frames (proportional to MaxPT to adapt to any scanner)
    if (PT_Level_Auto && FrameStepsDone >= int((MinFrameSteps+FrameDeductSteps)*0.9)) {
        ratio = (float)PerforationThresholdAutoLevelRatio/100;
        fixed_margin = int((MaxPT_Dynamic-MinPT_Dynamic) * 0.1);
        user_margin = int((MaxPT_Dynamic-MinPT_Dynamic) * 0.9 * ratio);
        PerforationThresholdLevel = int((MinPT_Dynamic + fixed_margin + user_margin)/10);
    }

    // If relevant diff between max/min dinamic it means we have film passing by
    if (CurrentTime > FilmDetectedTime) {
        NoFilmDetected = true;
    }
    else if (FilmDetectedTime - CurrentTime > MaxFilmStallTime) { // Overrun: Normalize value
        FilmDetectedTime = millis() + MaxFilmStallTime;
    }
    else if (film_detected(PT_SignalLevelRead)) {
        FilmDetectedTime = millis() + MaxFilmStallTime;
    }

    return(PT_SignalLevelRead);
}

// ------------ Reports info (PT level, steps/frame, etc) to Serial Plotter 10 times/sec ----------
void ReportPlotterInfo() {
    static unsigned long NextReport = 0;
    static int Previous_PT_Signal = 0, PreviousFrameSteps = 0;
    static char out[100];

    if (millis() > NextReport) {
        if (Previous_PT_Signal != PT_SignalLevelRead || PreviousFrameSteps != LastFrameSteps) {
            NextReport = millis() + 20;
            if (DebugState == PlotterInfo) {  // Plotter info to Arduino IDE
                sprintf(out,"PT:%i, Th:%i, FSD:%i, PTALR:%i, MinD:%i, MaxD:%i", PT_SignalLevelRead, PerforationThresholdLevel, FrameStepsDone, PerforationThresholdAutoLevelRatio, MinPT_Dynamic/10, MaxPT_Dynamic/10);
                SerialPrintStr(out);
            }
            Previous_PT_Signal = PT_SignalLevelRead;
            PreviousFrameSteps = LastFrameSteps;
            if (IntegratedPlotter)  // Plotter info to ALT-Scann 8 Integrated plotter
                SendToRPi(RSP_REPORT_PLOTTER_INFO, PT_SignalLevelRead, PerforationThresholdLevel);
        }
    }
}

boolean SlowForward(){
    static unsigned long LastMove = 0;
    unsigned long CurrentTime = micros();
    if (CurrentTime > LastMove || LastMove-CurrentTime > 400) { // If timer expired (or wrapped over) ...
        GetLevelPT();   // No need to know PT level here, but used to update plotter data
        CollectOutgoingFilm();
        digitalWrite(MotorB_Stepper, LOW);
        digitalWrite(MotorB_Stepper, HIGH);
        LastMove = CurrentTime + 400;
    }
    // Check if film still present (auto stop at end of reel)
    if (AutoStopEnabled && NoFilmDetected) {
        SendToRPi(RSP_FILM_FORWARD_ENDED, 0, 0);
        return(false);
    }
    else return(true);
}

void SlowBackward(){
    static unsigned long LastMove = 0;
    unsigned long CurrentTime = micros();
    if (CurrentTime > LastMove || LastMove-CurrentTime > 700) { // If timer expired (or wrapped over) ...
        GetLevelPT();   // No need to know PT level here, but used to update plotter data
        // We have no traction sensor on the A reel, so no way to safely implement collect film of that one
        // Film must be collected manually
        digitalWrite(MotorB_Stepper, LOW);
        digitalWrite(MotorB_Stepper, HIGH);
        LastMove = CurrentTime + 700;
    }
}

// ------------- is there film loaded in filmgate? ---------------
boolean FilmInFilmgate() {
    int SignalLevel;
    boolean retvalue = false;
    int mini=800, maxi=0;

    analogWrite(11, UVLedBrightness); // Turn on UV LED
    UVLedOn = true;
    delay(200);  // Give time to FT to stabilize

    SetReelsAsNeutral(HIGH, LOW, HIGH);   // Lock reel B

    // MinFrameSteps used here as a reference, just to skip two frames in worst case
    // Anyhow this funcion is used only for protection in rewind/ff, no film expected to be in filmgate
    for (int x = 0; x <= 300; x++) {
        digitalWrite(MotorB_Stepper, LOW);
        digitalWrite(MotorB_Stepper, HIGH);
        SignalLevel = GetLevelPT();
        if (SignalLevel > maxi) maxi = SignalLevel;
        if (SignalLevel < mini) mini = SignalLevel;
    }
    digitalWrite(MotorB_Stepper, LOW);
    SetReelsAsNeutral(HIGH, HIGH, HIGH);   // Return Reel B to neutral

    analogWrite(11, 0); // Turn off UV LED
    UVLedOn = false;

    if (abs(maxi-mini) > 0.33*(MaxPT-MinPT))   
        retvalue = true;

    return(retvalue);
}

void adjust_framesteps(int frame_steps) {
    static int steps_per_frame_list[32];
    static int idx = 0;
    static int items_in_list = 0;
    int total = 0;

    // Check if steps per frame are going beyond reasonable limits
    if (frame_steps > int(OriginalMinFrameSteps*1.05) || frame_steps < int(OriginalMinFrameSteps*0.95)) {   // Allow 5% deviation
        return; // Do not add invalid steps per frame to list
    }

    // We collect statistics even if not in auto mode
    steps_per_frame_list[idx] = frame_steps;
    idx = (idx + 1) % 32;
    if (items_in_list < 32)
        items_in_list++;

    if (Frame_Steps_Auto) {  // Update MinFrameSteps only if auto activated
        for (int i = 0; i < items_in_list; i++)
            total = total + steps_per_frame_list[i];
        MinFrameSteps = int(total / items_in_list) - 5;
        DecreaseSpeedFrameSteps = MinFrameSteps - DecreaseSpeedFrameStepsBefore;
    }
}


// ------------- is the film perforation in position to take picture? ---------------
// Returns false if status should change to idle
boolean IsHoleDetected() {
    boolean hole_detected = false;
    int PT_Level;
  
    PT_Level = GetLevelPT();

    // ------------- Frame detection ----
    // 14/Oct/2023: Until now, 'FrameStepsDone >= MinFrameSteps' was a precondition together with 'PT_Level >= PerforationThresholdLevel'
    // To consider a frame is detected. After changing the condition to allow 20% less in the number of steps, I can see a better precision
    // In the captured frames. So for the moment it stays like this. Also added a fuse to also give a frame as detected in case of reaching
    // 150% of the required steps, even of the PT level does no tmatch the required threshold. We'll see...
    if (PT_Level >= PerforationThresholdLevel && FrameStepsDone >= int(MinFrameSteps+FrameDeductSteps)) {
        LastPTLevel = PT_Level;
        hole_detected = true;
        GreenLedOn = true;
        analogWrite(A1, 255); // Light green led
    }

    return(hole_detected);
}

// 24/02/2025: Modify to do progressive acceleration deceleration when more than 20 steps or so
// For the moment we do it inside the function, but maybe should be spllit in slices in the main loop
void capstan_advance(int steps) {
    int middle, delay_factor;

    if (steps > 20) 
        middle = int(steps/2);
    for (int x = 0; x < steps; x++) {    // Advance steps five at a time, otherwise too slow
        digitalWrite(MotorB_Stepper, LOW);
        digitalWrite(MotorB_Stepper, HIGH);
        if (steps > 20) {
            delay_factor = (x < middle) ? int(middle - x) : (steps - x);
            delayMicroseconds(50 + min(500, delay_factor*10));
        }
        else if (steps >= 1)
            delayMicroseconds(100);        
    }
    digitalWrite(MotorB_Stepper, LOW);
    if (VFD_mode_active)
        SendToRPi(RSP_ADVANCE_FRAME_FRACTION, steps, 0);
}

// ----- This is the function to "ScanFilm" -----
// Returns false when done
ScanResult scan(int UI_Command) {
    ScanResult retvalue = SCAN_NO_FRAME_DETECTED;
    static unsigned long TimeToScan = 0;
    unsigned long CurrentTime = micros();
    int FrameStepsToDo = 1;

    if (CurrentTime < TimeToScan && TimeToScan - CurrentTime < ScanSpeedDelay) {
        return (retvalue);
    }
    else {
        TimeToScan = CurrentTime + ScanSpeedDelay;

        if (GreenLedOn) {  // If last time frame was detected ...
            GreenLedOn = false;
            analogWrite(A1, 0); // ... Turn off green led
        }

        TractionSwitchActive = digitalRead(TractionStopPin);

        if (FrameStepsDone > DecreaseSpeedFrameSteps)   // Progressively decrease speed before frame detection
            ScanSpeedDelay = OriginalScanSpeedDelay +
                min(20000, DecreaseScanSpeedDelayStep * (FrameStepsDone - DecreaseSpeedFrameSteps + 1));

        FrameDetected = false;

        // Check if film still present (auto stop at end of reel)
        if (AutoStopEnabled && NoFilmDetected) {
            SendToRPi(RSP_SCAN_ENDED, 0, 0);
            return(SCAN_TERMINATION_REQUESTED);
        }

        //-------------ScanFilm-----------
        FrameDetected = IsHoleDetected();
        if (!FrameDetected) {
            //FrameStepsToDo = min(1 + (ScanSpeed - 1) * 1, max(1,DecreaseSpeedFrameSteps-FrameStepsDone));
            FrameStepsToDo = 1;
            capstan_advance(FrameStepsToDo);
            FrameStepsDone+=FrameStepsToDo;
        }

        if (FrameDetected) {
            DebugPrintStr("Frame!");
            if (Frame_Steps_Auto and FrameExtraSteps > 0)  // If auto steps enabled, and extra steps positive, aditional steps after detection
                capstan_advance(FrameExtraSteps);
            LastFrameSteps = FrameStepsDone;
            adjust_framesteps(LastFrameSteps);
            FrameStepsDone = 0;
            TimeToScan = 0;
            StartPictureSaveTime = micros();
            // Tell UI (Raspberry PI) a new frame is available for processing
            if (ScanState == Sts_SingleStep) {  // Do not send event to RPi for single step
                tone(A2, 2000, 35);
                delay(100);     // Delay to avoid beep interfering with uv led PWB (both use same timer)
                analogWrite(11, UVLedBrightness); // Set UV LED to right brightness, as usign tone might have broken it (same timer used by both)
            }
            FrameDetected = false;
            retvalue = SCAN_FRAME_DETECTED;
            DebugPrint("FrmS",LastFrameSteps);
            DebugPrint("FrmT",CurrentTime-StartFrameTime);
            if (DebugState == FrameSteps)
                SerialPrintInt(LastFrameSteps);
        }
        else if (FrameStepsDone > 2*MinFrameSteps) {
            retvalue = SCAN_FRAME_DETECTION_ERROR;
            // Tell UI (Raspberry PI) an error happened during scanning
            SendToRPi(RSP_SCAN_ERROR, FrameStepsDone, 2*MinFrameSteps);
            FrameStepsDone = 0;
        }
        return (retvalue);
    }
}

// ---- Receive I2C command from Raspberry PI, ScanFilm... and more ------------
// JRE 13/09/22: Theoretically this might happen any time, thu UI_Command might change in the middle of the loop. Adding a queue...
void receiveEvent(int byteCount) {
    int IncomingIc, param = 0;

    if (Wire.available())
        IncomingIc = Wire.read();
    if (Wire.available())
        param =  Wire.read();
    if (Wire.available())
        param +=  256*Wire.read();
    while (Wire.available())
        Wire.read();

    if (IncomingIc > 0) {
        push_cmd(IncomingIc, param); // No error treatment for now
    }
}

// -- Sending I2C command to Raspberry PI, take picture now -------
void sendEvent() {
    int cmd, p1, p2;
    cmd = pop_rsp(&p1, &p2);
    if (cmd != -1) {
        BufferForRPi[0] = cmd;
        BufferForRPi[1] = p1/256;
        BufferForRPi[2] = p1%256;
        BufferForRPi[3] = p2/256;
        BufferForRPi[4] = p2%256;
        Wire.write(BufferForRPi,5);
    }
    else {
        BufferForRPi[0] = 0;
        BufferForRPi[1] = 0;
        BufferForRPi[2] = 0;
        BufferForRPi[3] = 0;
        BufferForRPi[4] = 0;
        Wire.write(BufferForRPi,5);
    }
}

boolean push(Queue * queue, int IncomingIc, int param, int param2) {
    boolean retvalue = false;
    if ((queue -> in+1) % QUEUE_SIZE != queue -> out) {
        queue -> Data[queue -> in] = IncomingIc;
        queue -> Param[queue -> in] = param;
        queue -> Param2[queue -> in] = param2;
        queue -> in++;
        queue -> in %= QUEUE_SIZE;
        retvalue = true;
    }
    // else: Queue full: Should not happen. Not sure how this should be handled
    return(retvalue);
}

int pop(Queue * queue, int * param, int * param2) {
    int retvalue = -1;  // default return value: -1 (error)
    if (queue -> out != queue -> in) {
        retvalue = queue -> Data[queue -> out];
        if (param != NULL)
            *param =  queue -> Param[queue -> out];
        if (param2 != NULL)
            *param2 =  queue -> Param2[queue -> out];
        queue -> out++;
        queue -> out %= QUEUE_SIZE;
    }
    // else: Queue empty: Nothing to do
    return(retvalue);
}

boolean push_cmd(int cmd, int param) {
    push(&CommandQueue, cmd, param, 0);
}
int pop_cmd(int * param) {
    return(pop(&CommandQueue, param, NULL));
}
boolean push_rsp(int rsp, int param, int param2) {
    push(&ResponseQueue, rsp, param, param2);
}
int pop_rsp(int * param, int * param2) {
    return(pop(&ResponseQueue, param, param2));
}

boolean dataInCmdQueue(void) {
    return (CommandQueue.out != CommandQueue.in);
}

boolean dataInRspQueue(void) {
    return (ResponseQueue.out != ResponseQueue.in);
}

void DebugPrintAux(const char * str, unsigned long i) {
    static char PreviousDebug[64];
    static char AuxLine[64];
    static char PrintLine[64];
    static int CurrentRepetitions = 0;
    boolean GoPrint = true;
  
    if (DebugState != DebugInfo && DebugState != DebugInfoSingle) return;

    if (strlen(str) >= 50) {
        Serial.println("Cannot print debug line, too long");
        return;
    }

    if (i != -1)
        sprintf(PrintLine,"%s=%u",str,i);
    else
        strcpy(PrintLine,str);
  
    if (strcmp(PrintLine,PreviousDebug) == 0) {
        if (CurrentRepetitions < MAX_DEBUG_REPETITIONS_COUNT)
            CurrentRepetitions++;
        if (CurrentRepetitions > MaxDebugRepetitions) GoPrint = false;
    }
    else {
        if (CurrentRepetitions > MaxDebugRepetitions) {
            if (CurrentRepetitions < MAX_DEBUG_REPETITIONS_COUNT)
                sprintf(AuxLine,"Previous line repeated %u times",CurrentRepetitions-MaxDebugRepetitions);
            else
                strcpy(AuxLine,"Previous line repeated more than 30,000 times");
            Serial.println(AuxLine);
        }
        CurrentRepetitions = 0;
    }
    strcpy(PreviousDebug, PrintLine);

    if (GoPrint) Serial.println(PrintLine);
}

void DebugPrintStr(const char * str) {
    if (DebugState != DebugInfo) return;
    DebugPrintAux(str,-1);
}

// Differentiated debug print function to debug specifics without printing all debug lines
void DebugPrint(const char * str, unsigned long i) {
    if (DebugState != DebugInfo) return;
    DebugPrintAux(str,i);
}


void SerialPrintStr(const char * str) {
    if (DebugState != DebugInfo) Serial.println(str);
}

void SerialPrintInt(int i) {
    if (DebugState != DebugInfo) Serial.println(i);
}

