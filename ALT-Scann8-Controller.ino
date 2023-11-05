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
#define __copyright__   "Copyright 2023, Juan Remirez de Esparza"
#define __credits__     "Juan Remirez de Esparza"
#define __license__     "MIT"
#define __version__     "1.0"
#define __maintainer__  "Juan Remirez de Esparza"
#define __email__       "jremirez@hotmail.com"
#define __status__      "Development"

#include <Wire.h>
#include <stdio.h>

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
} DebugState = PlotterInfo;

int MaxDebugRepetitions = 3;
#define MAX_DEBUG_REPETITIONS_COUNT 30000

boolean GreenLedOn = false;  
int UI_Command; // Stores I2C command from Raspberry PI --- ScanFilm=10 / UnlockReels mode=20 / Slow Forward movie=30 / One step frame=40 / Rewind movie=60 / Fast Forward movie=61 / Set Perf Level=90
// I2C commands (RPi to Arduino): Constant definition
#define CMD_VERSION_ID 1
#define CMD_GET_CNT_STATUS 2
#define CMD_START_SCAN 10
#define CMD_TERMINATE 11
#define CMD_GET_NEXT_FRAME 12
#define CMD_SET_REGULAR_8 18
#define CMD_SET_SUPER_8 19
#define CMD_SWITCH_REEL_LOCK_STATUS 20
#define CMD_FILM_FORWARD 30
#define CMD_SINGLE_STEP 40
#define CMD_ADVANCE_FRAME 41
#define CMD_ADVANCE_FRAME_FRACTION 42
#define CMD_SET_PT_LEVEL 50
#define CMD_SET_MIN_FRAME_STEPS 52
#define CMD_SET_FRAME_FINE_TUNE 54
#define CMD_BOOST_PT_THRESHOLD 56
#define CMD_REWIND 60
#define CMD_FAST_FORWARD 61
#define CMD_INCREASE_WIND_SPEED 62
#define CMD_DECREASE_WIND_SPEED 63
#define CMD_UNCONDITIONAL_REWIND 64
#define CMD_UNCONDITIONAL_FAST_FORWARD 65
#define CMD_SET_SCAN_SPEED 70
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
    Sts_SingleStep
}
ScanState=Sts_Idle;

// ----- Scanner specific variables: Might need to be adjusted for each specific scanner ------
int UVLedBrightness = 255;                  // Brightness UV led, may need to be changed depending on LED type
unsigned long BaseScanSpeed = 10;           // 25 - Base delay to calculate scan speed on which other are based
unsigned long StepScanSpeed = 100;          // 250: Increment delays to reduce scan speed
unsigned long ScanSpeed = BaseScanSpeed;    // 500 - Delay in microseconds used to adjust speed of stepper motor during scan process
unsigned long FetchFrameScanSpeed = 3*ScanSpeed;    // 500 - Delay (microsec also) for slower stepper motor speed once minimum number of steps reached
unsigned long DecreaseScanSpeedStep = 50;   // 100 - Increment in microseconds of delay to slow down progressively scanning speed, to improve detection (set to zero to disable)
int RewindSpeed = 4000;                     // Initial delay in microseconds used to determine speed of rewind/FF movie
int TargetRewindSpeedLoop = 200;            // Final delay  in microseconds for rewind/SS speed (Originally hardcoded)
int PerforationMaxLevel = 550;              // Phototransistor reported value, max level
int PerforationMinLevel = 50;               // Phototransistor reported value, min level (originalyl hardcoded)
int PerforationThresholdLevelR8 = 180;      // Default value for R8
int PerforationThresholdLevelS8 = 90;       // Default value for S8
int PerforationThresholdLevel = PerforationThresholdLevelS8;    // Phototransistor value to decide if new frame is detected
int PerforationThresholdAutoLevelRatio = 40;  // Percentage between dynamic max/min PT level - Can be changed from 20 to 60
float CapstanDiameter = 14.3;         // Capstan diameter, to calculate actual number of steps per frame
int MinFrameStepsR8 = R8_HEIGHT/((PI*CapstanDiameter)/(360/(NEMA_STEP_DEGREES/NEMA_MICROSTEPS_IN_STEP)));  // Default value for R8 (236 aprox)
int MinFrameStepsS8 = S8_HEIGHT/((PI*CapstanDiameter)/(360/(NEMA_STEP_DEGREES/NEMA_MICROSTEPS_IN_STEP)));; // Default value for S8 (286 aprox)
int MinFrameSteps = MinFrameStepsS8;        // Minimum number of steps to allow frame detection
int FrameFineTune = 0;              // Allow framing adjustment on the fly (manual, automatic would require using CV2 pattern matching, maybe to be checked)
int DecreaseSpeedFrameStepsBefore = 0;  // 20 - No need to anticipate slow down, the default MinFrameStep should be always less
int DecreaseSpeedFrameSteps = MinFrameSteps - DecreaseSpeedFrameStepsBefore;    // Steps at which the scanning speed starts to slow down to improve detection
// ------------------------------------------------------------------------------------------

boolean ReelsUnlocked = false;
boolean FrameDetected = false;  // Used for frame detection, in play ond single step modes
boolean UVLedOn = false;
int FilteredSignalLevel = 0;
int OriginalPerforationThresholdLevel = PerforationThresholdLevel; // stores value for resetting PerforationThresholdLevel
int OriginalPerforationThresholdAutoLevelRatio = PerforationThresholdAutoLevelRatio;
int FrameStepsDone = 0;                     // Count steps
// OriginalScanSpeed keeps a safe value to recent to in case of need, should no tbe updated
// with dynamically calculated values
unsigned long OriginalScanSpeed = ScanSpeed;          // Keep to restore original value when needed
int OriginalMinFrameSteps = MinFrameSteps;  // Keep to restore original value when needed

int LastFrameSteps = 0;                     // Stores number of steps required to reach current frame (stats only)

boolean IsS8 = true;

boolean TractionSwitchActive = true;  // When traction micro-switch is closed

unsigned long StartFrameTime = 0;           // Time at which we get RPi command to get next frame (stats only)
unsigned long StartPictureSaveTime = 0;     // Time at which we tell RPi to save current frame (stats only)

byte BufferForRPi[9];   // 9 byte array to send data to Raspberry Pi over I2C bus

int PT_SignalLevelRead;   // Raw signal level from phototransistor
boolean PT_Level_Auto = true;   // Automatic calculation of PT level threshold

boolean Frame_Steps_Auto = true;

// Collect outgoing film frequency
int collect_modulo = 10; 

// Forward definition
void CollectOutgoingFilm(bool);

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


void setup() {
    // Possible serial speeds: 1200, 2400, 4800, 9600, 19200, 38400, 57600,74880, 115200, 230400, 250000, 500000, 1000000, 2000000
    Serial.begin(1000000);  // As fast as possible for debug, otherwise it slows down execution
  
    Wire.begin(16);  // join I2c bus with address #16
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
    digitalWrite(MotorA_Direction, LOW);
    digitalWrite(MotorB_Direction, LOW);

    digitalWrite(MotorA_Stepper, LOW);
    digitalWrite(MotorB_Stepper, LOW);
    digitalWrite(MotorC_Stepper, LOW);

    // JRE 04/08/2022
    CommandQueue.in = 0;
    CommandQueue.out = 0;
    ResponseQueue.in = 0;
    ResponseQueue.out = 0;
}

void loop() {
    int param;

    SendToRPi(RSP_FORCE_INIT, 0, 0);  // Request UI to resend init sequence, in case controller reloaded while UI active

    while (1) {
        if (dataInCmdQueue())
            UI_Command = pop_cmd(&param);   // Get next command from queue if one exists
        else
            UI_Command = 0;

        Wire.begin(16);

        TractionSwitchActive = digitalRead(TractionStopPin);

        ReportPlotterInfo();    // Regular report of plotter info

        if (ScanState != Sts_Scan && ScanState != Sts_SingleStep) {
            // Set default state and direction of motors B and C (disabled, clockwise)
            // In the original main loop this was done when UI_Command was NOT Single Step (49). Why???
            // JRE 23-08-2022: Explanation: THis is done mainly for the slow forward function, so that
            //    setting to high both the motors B and C they will move one step forward
            if (UI_Command != CMD_SINGLE_STEP){  // In case we need the exact behavior of original code
                digitalWrite(MotorB_Stepper, LOW);
                digitalWrite(MotorC_Stepper, LOW);
                digitalWrite(MotorC_Direction, HIGH);
                digitalWrite(MotorB_Direction, HIGH);
            }
        }

        switch (UI_Command) {   // Stateless commands
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
            case CMD_SET_MIN_FRAME_STEPS:
                DebugPrint(">MinFSteps", param);
                if (param == 0 || param >= 100 && param <= 600) {
                    if (param == 0)
                        Frame_Steps_Auto = true;     // zero means we go in automatic mode
                    else {
                        Frame_Steps_Auto = false;
                        MinFrameSteps = param;
                        if (IsS8)
                            MinFrameStepsS8 = param;
                        else
                            MinFrameStepsR8 = param;
                        DecreaseSpeedFrameSteps = MinFrameSteps - DecreaseSpeedFrameStepsBefore;
                        DebugPrint(">MinSteps",param);
                    }
                }
                break;
            case CMD_SET_FRAME_FINE_TUNE:
                DebugPrint(">FineT", param);
                PerforationThresholdAutoLevelRatio = 40 + param;    // Change threshold ratio
                OriginalPerforationThresholdAutoLevelRatio = PerforationThresholdAutoLevelRatio;
                if (param > 0)  // Also to move up we add extra steps
                    FrameFineTune = param;
                break;
            case CMD_BOOST_PT_THRESHOLD:
                DebugPrint(">BoostPT", param);
                if (param > 0)  // Also to move up we add extra steps
                    PerforationThresholdAutoLevelRatio = 90;    // Change threshold ratio to maximum (for damaged film)
                else
                    PerforationThresholdAutoLevelRatio = OriginalPerforationThresholdAutoLevelRatio;
                break;
            case CMD_SET_SCAN_SPEED:
                DebugPrint(">Speed", param);
                ScanSpeed = BaseScanSpeed + (10-param) * StepScanSpeed;
                if (ScanSpeed < OriginalScanSpeed && collect_modulo > 1)  // Increase film collection frequency if increasing scan speed
                    collect_modulo--;
                OriginalScanSpeed = ScanSpeed;
                DecreaseSpeedFrameStepsBefore = max(0, 70 - 7*param); 
                DecreaseSpeedFrameSteps = MinFrameSteps - DecreaseSpeedFrameStepsBefore;
                break;
        }

        switch (ScanState) {
            case Sts_Idle:
                switch (UI_Command) {
                    case CMD_VERSION_ID:
                        DebugPrintStr(">V_ID");
                        SendToRPi(RSP_VERSION_ID, 1, 0);  // 1 - Arduino, 2 - RPi Pico
                        break;
                    case CMD_START_SCAN:
                        DebugPrintStr(">Scan");
                        ScanState = Sts_Scan;
                        analogWrite(11, UVLedBrightness); // Turn on UV LED
                        UVLedOn = true;
                        delay(500);     // Wait for PT to stabilize after switching UV led on
                        StartFrameTime = micros();
                        ScanSpeed = OriginalScanSpeed;
                        collect_modulo = 10;
                        tone(A2, 2000, 50);
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
                        ScanSpeed = OriginalScanSpeed;
                        DebugPrint("Save t.",StartFrameTime-StartPictureSaveTime);
                        DebugPrintStr(">Next fr.");
                        // Also send, if required, to RPi autocalculated threshold level every frame
                        // Alternate reports for each value, otherwise I2C has I/O errors
                        if (PT_Level_Auto || Frame_Steps_Auto)
                            SendToRPi(RSP_REPORT_AUTO_LEVELS, PerforationThresholdLevel, MinFrameSteps);
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
                    case CMD_FILM_FORWARD:
                        collect_modulo = 4;
                        ScanState = Sts_SlowForward;
                        delay(50);
                        break;
                    case CMD_SINGLE_STEP:
                        DebugPrintStr(">SStep");
                        ScanState = Sts_SingleStep;
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
                            digitalWrite(MotorA_Neutral, LOW);
                            digitalWrite(MotorB_Neutral, HIGH);
                            digitalWrite(MotorC_Neutral, HIGH);
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
                            digitalWrite(MotorA_Neutral, HIGH);
                            digitalWrite(MotorB_Neutral, HIGH);
                            digitalWrite(MotorC_Neutral, LOW);
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
                        DebugPrint(">Advance frame", IsS8 ? MinFrameStepsS8 : MinFrameStepsR8);
                        if (IsS8)
                            capstan_advance(MinFrameStepsS8);
                        else
                            capstan_advance(MinFrameStepsR8);
                        break;
                    case CMD_ADVANCE_FRAME_FRACTION:
                        DebugPrint(">Advance frame", param);
                        capstan_advance(param);
                        break;
                }
                break;
            case Sts_Scan:
                CollectOutgoingFilm(false);
                if (UI_Command == CMD_START_SCAN) {
                    DebugPrintStr("-Scan");
                    ScanState = Sts_Idle; // Exit scan loop
                }
                else if (scan(UI_Command) != SCAN_NO_FRAME_DETECTED) {
                    ScanState = Sts_Idle; // Exit scan loop
                }
                else {
                    // Advance to next frame ? (to be checked)
                    /* does not seem to be required (loop -> scan -> loop -> scan ...). Not sure how it works. Thanks to extensive use of global variables maybe
                    digitalWrite(MotorB_Stepper, LOW);
                    delay(20);
                    digitalWrite(MotorB_Stepper, HIGH);
                    delay (20);
                    digitalWrite(MotorB_Stepper, LOW);
                    */
                }
                break;
            case Sts_SingleStep:
                if (scan(UI_Command) != SCAN_NO_FRAME_DETECTED) {
                    ScanState = Sts_Idle;
                }
                break;
            case Sts_UnlockReels:
                if (UI_Command == CMD_SWITCH_REEL_LOCK_STATUS) { //request to lock reels again
                    ReelsUnlocked = false;
                    digitalWrite(MotorB_Neutral, LOW);
                    digitalWrite(MotorC_Neutral, LOW);
                    ScanState = Sts_Idle;
                    analogWrite(11, 0); // Turn off UV LED
                    UVLedOn = false;
                }
                else {
                    if (not ReelsUnlocked){
                        ReelsUnlocked = true;
                        digitalWrite(MotorB_Neutral, HIGH);
                        digitalWrite(MotorC_Neutral, HIGH);
                        analogWrite(11, UVLedBrightness); // Turn on UV LED
                        UVLedOn = true;
                    }
                    GetLevelPT();   // No need to know PT level here, but used to update plotter data
                }
                break;
            case Sts_Rewind:
                if (!RewindFilm(UI_Command)) {
                    DebugPrintStr("-rwnd");
                    ScanState = Sts_Idle;
                }
                break;
            case Sts_FastForward:
                if (!FastForwardFilm(UI_Command)) {
                    DebugPrintStr("-FF");
                    ScanState = Sts_Idle;
                }
                break;
            case Sts_SlowForward:
                if (UI_Command == CMD_FILM_FORWARD) { // Stop slow forward
                    delay(50);
                    ScanState = Sts_Idle;
                }
                else {
                    SlowForward();
                }
                break;
        }

        // ----- Speed on stepper motors ------------------ JRE: To be checked if needed, here or elsewhere
        delayMicroseconds(1);

        // org 5
    }
}


// ------ rewind the movie ------
boolean RewindFilm(int UI_Command) {
    boolean retvalue = true;
    static boolean stopping = false;

    Wire.begin(16);

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
            digitalWrite(MotorA_Neutral, HIGH);
            digitalWrite(MotorB_Neutral, LOW);
            digitalWrite(MotorC_Neutral, LOW);
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

    Wire.begin(16);  // join I2c bus with address #16

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
            digitalWrite(MotorA_Neutral, HIGH);
            digitalWrite(MotorB_Neutral, LOW);
            digitalWrite(MotorC_Neutral, LOW);
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
// New version, collection speed is throttled based on the frequency of microswitch activation.
// This new method provides a more regular mechanism, and it keeps minimum tension in the film.
// Because of this, a pinch roller (https://www.thingiverse.com/thing:5583753) and microswitch 
// (https://www.thingiverse.com/thing:5541340) are required. Without them (specially without pinch roller)
// tension might not be enough for the capstan to pull the film.
void CollectOutgoingFilm(bool force = false) {
    static int loop_counter = 0;
    static boolean CollectOngoing = true;

    static unsigned long LastSwitchActivationCheckTime = millis()+3000;
    unsigned long CurrentTime = millis();

    if (loop_counter % collect_modulo == 0) {
        TractionSwitchActive = digitalRead(TractionStopPin);
        if (!TractionSwitchActive) {  //Motor allowed to turn
            CollectOngoing = true;
            //delayMicroseconds(1000);
            digitalWrite(MotorC_Stepper, LOW);
            digitalWrite(MotorC_Stepper, HIGH);
            digitalWrite(MotorC_Stepper, LOW);
        }
        TractionSwitchActive = digitalRead(TractionStopPin);
        if (TractionSwitchActive) {
            if (CollectOngoing) {
                if (CurrentTime < LastSwitchActivationCheckTime){  // Collecting too often: Increase modulo
                    collect_modulo++;
                }
                DebugPrint("Collect Mod", collect_modulo);
                LastSwitchActivationCheckTime = CurrentTime + 3000;
            }
            CollectOngoing = false;
        }
        else if (collect_modulo > 2 && CurrentTime > LastSwitchActivationCheckTime) {  // Not collecting enough : Decrease modulo
            collect_modulo-=2;
            DebugPrint("Collect Mod", collect_modulo);
        }
    }
    loop_counter++;
}

// ------------- Centralized phototransistor level read ---------------
int GetLevelPT() {
  float ratio;
    PT_SignalLevelRead = analogRead(PHOTODETECT);
    MaxPT = max(PT_SignalLevelRead, MaxPT);
    MinPT = min(PT_SignalLevelRead, MinPT);
    MaxPT_Dynamic = max(PT_SignalLevelRead*10, MaxPT_Dynamic);
    MinPT_Dynamic = min(PT_SignalLevelRead*10, MinPT_Dynamic);
    if (MaxPT_Dynamic > MinPT_Dynamic) MaxPT_Dynamic-=2;
    //if (MinPT_Dynamic < MaxPT_Dynamic) MinPT_Dynamic+=int((MaxPT_Dynamic-MinPT_Dynamic)/10);  // need to catch up quickly for overexposed frames (proportional to MaxPT to adapt to any scanner)
    if (MinPT_Dynamic < MaxPT_Dynamic) MinPT_Dynamic+=2;  // need to catch up quickly for overexposed frames (proportional to MaxPT to adapt to any scanner)
    if (PT_Level_Auto) {
        ratio = (float)PerforationThresholdAutoLevelRatio/100;
        PerforationThresholdLevel = int(((MinPT_Dynamic + (MaxPT_Dynamic-MinPT_Dynamic) * (ratio)))/10);
    }

    return(PT_SignalLevelRead);
}

// ------------ Reports info (PT level, steps/frame, etc) to Serial Plotter 10 times/sec ----------
void ReportPlotterInfo() {
    static unsigned long NextReport = 0;
    static int Previous_PT_Signal = 0, PreviousFrameSteps = 0;
    static char out[100];

    if (DebugState == PlotterInfo && millis() > NextReport) {
        if (Previous_PT_Signal != PT_SignalLevelRead || PreviousFrameSteps != LastFrameSteps) {
            NextReport = millis() + 20;
            sprintf(out,"PT:%i, Th:%i, FSD:%i, PTALR:%i, MinD:%i, MaxD:%i", PT_SignalLevelRead, PerforationThresholdLevel, FrameStepsDone, PerforationThresholdAutoLevelRatio, MinPT_Dynamic/10, MaxPT_Dynamic/10);
            //sprintf(out,"PT:%i", PT_SignalLevelRead);
            SerialPrintStr(out);
            Previous_PT_Signal = PT_SignalLevelRead;
            PreviousFrameSteps = LastFrameSteps;
        }
    }
}

void SlowForward(){
    static unsigned long LastMove = 0;
    unsigned long CurrentTime = micros();
    if (CurrentTime > LastMove || LastMove-CurrentTime > 700) { // If timer expired (or wrapped over) ...
        GetLevelPT();   // No need to know PT level here, but used to update plotter data
        CollectOutgoingFilm(false);
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
    delay(500);  // Give time to FT to stabilize


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
    analogWrite(11, 0); // Turn off UV LED
    UVLedOn = false;

    if (abs(maxi-mini) > 0.5*(MaxPT-MinPT))
        retvalue = true;

    return(retvalue);
}

void adjust_framesteps(int frame_steps) {
    static int steps_per_frame_list[32];
    static int idx = 0;
    static int items_in_list = 0;
    int total;

    // Check if steps per frame are going beyond reasonable limits
    if (frame_steps > int(OriginalMinFrameSteps*1.05) || frame_steps < int(OriginalMinFrameSteps*0.95)) {   // Allow 5% deviation
        MinFrameSteps = OriginalMinFrameSteps;  // Revert to original value
        DecreaseSpeedFrameSteps = MinFrameSteps - DecreaseSpeedFrameStepsBefore;
        return; // Do not add invalid steps per frame to list
    }

    // We collect statistics even if not in auto mode
    steps_per_frame_list[idx] = frame_steps;
    idx = (idx + 1) % 32;
    if (items_in_list < 32)
        items_in_list++;

    if (Frame_Steps_Auto && items_in_list == 32) {  // Update MinFrameSpeed only if auto activated
        for (int i = 0; i < 32; i++)
            total = total + steps_per_frame_list[i];
        MinFrameSteps = int(total / 32) - 10;
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
    if (PT_Level >= PerforationThresholdLevel && FrameStepsDone >= int(MinFrameSteps*0.7) || FrameStepsDone > int(MinFrameSteps * 1.5)) {
        hole_detected = true;
        GreenLedOn = true;
        analogWrite(A1, 255); // Light green led
    }

    return(hole_detected);
}

void capstan_advance(int steps) {
    for (int x = 0; x < steps; x++) {    // Advance steps five at a time, otherwise too slow
        digitalWrite(MotorB_Stepper, LOW);
        digitalWrite(MotorB_Stepper, HIGH);
        if (steps > 1)
            delayMicroseconds(1000);
    }
    digitalWrite(MotorB_Stepper, LOW);
}

// ----- This is the function to "ScanFilm" -----
// Returns false when done
ScanResult scan(int UI_Command) {
    ScanResult retvalue = SCAN_NO_FRAME_DETECTED;
    static unsigned long TimeToScan = 0;
    unsigned long CurrentTime = micros();

    if (CurrentTime < TimeToScan && TimeToScan - CurrentTime < ScanSpeed) {
        return (retvalue);
    }
    else {
        TimeToScan = CurrentTime + ScanSpeed;

        Wire.begin(16);

        analogWrite(11, UVLedBrightness);
        UVLedOn = true;

        if (GreenLedOn) {  // If last time frame was detected ...
            GreenLedOn = false;
            analogWrite(A1, 0); // ... Turn off green led
        }

        TractionSwitchActive = digitalRead(TractionStopPin);

        if (FrameStepsDone > DecreaseSpeedFrameSteps)
            ScanSpeed = FetchFrameScanSpeed + min(20000, DecreaseScanSpeedStep * (FrameStepsDone - DecreaseSpeedFrameSteps + 1));

        FrameDetected = false;

        //-------------ScanFilm-----------
        if (UI_Command == CMD_START_SCAN) {   // UI Requesting to end current scan
            retvalue = SCAN_TERMINATION_REQUESTED;
            FrameDetected = false;
            //DecreaseSpeedFrameSteps = 260; // JRE 20/08/2022 - Disabled, added option to set manually from UI
            LastFrameSteps = 0;
            if (UVLedOn) {
                analogWrite(11, 0); // Turn off UV LED
                UVLedOn = false;
            }
        }
        else {
            FrameDetected = IsHoleDetected();
            if (!FrameDetected) {
                capstan_advance(1);
                FrameStepsDone++;
            }
        }

        if (FrameDetected) {
            DebugPrintStr("Frame!");
            if (FrameFineTune > 0)  // If positive, aditional steps after detection
                capstan_advance(FrameFineTune);
            LastFrameSteps = FrameStepsDone;
            adjust_framesteps(LastFrameSteps);
            FrameStepsDone = 0;
            StartPictureSaveTime = micros();
            // Tell UI (Raspberry PI) a new frame is available for processing
            if (ScanState == Sts_SingleStep) {  // Do not send event to RPi for single step
                tone(A2, 2000, 35);
            }
            else {
                SendToRPi(RSP_FRAME_AVAILABLE, 0, 0);
            }
      
            FrameDetected = false;
            retvalue = SCAN_FRAME_DETECTED;
            DebugPrint("FrmS",LastFrameSteps);
            DebugPrint("FrmT",CurrentTime-StartFrameTime);
            if (DebugState == FrameSteps)
                SerialPrintInt(LastFrameSteps);
        }
        else if (FrameStepsDone > 2*DecreaseSpeedFrameSteps) {
            retvalue = SCAN_FRAME_DETECTION_ERROR;
            // Tell UI (Raspberry PI) an error happened during scanning
            SendToRPi(RSP_SCAN_ERROR, FrameStepsDone, 2*DecreaseSpeedFrameSteps);
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

