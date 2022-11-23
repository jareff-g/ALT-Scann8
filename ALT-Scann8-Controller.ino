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
#define __copyright__   "Copyright 2022, Juan Remirez de Esparza"
#define __credits__     "Juan Remirez de Esparza"
#define __license__     "MIT"
#define __version__     "0.9beta"
#define __maintainer__  "Juan Remirez de Esparza"
#define __email__       "jremirez@hotmail.com"
#define __status__      "Development"

#include <Wire.h>
#include <stdio.h>

const int PHOTODETECT = A0; // Analog pin 0 perf
int MaxPT = 0;
int MinPT = 5000;


enum {
  PT_Level,
  FrameSteps,
  DebugInfo,
  None
} DebugState = None;

int MaxDebugRepetitions = 3;
#define MAX_DEBUG_REPETITIONS_COUNT 30000

int Pulse = LOW;
int Ic; // Stores I2C command from Raspberry PI --- ScanFilm=10 / UnlockReels mode=20 / Slow Forward movie=30 / One step frame=40 / Rewind movie=60 / Fast Forward movie=80 / Set Perf Level=90

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

boolean ReelsUnlocked = false;
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

boolean FrameDetected = false;  // Used for frame detection, in play ond single step modes

boolean UVLedOn = false;
int FilteredSignalLevel = 0;
// int waveC = 0;  // Not used
// int waveCS = 0;  // Not used


// ----- Scanner specific variables: Might need to be adjusted for each specific scanner ------
int UVLedBrightness = 250;                    // Brightness UV led, may need to be changed depending on LED (Torulf: 250)
unsigned long ScanSpeed = 500 ;               // speed stepper scann Play (original 500)
unsigned long FetchFrameScanSpeed = 5000;    // Play Slow before trig (Original 15000)
unsigned long DecreaseScanSpeedStep = 3000;    // Attempt to have a progressively decreasing scan speed before stopping for a frame
int RewindSpeed = 4000;                       // speed Rewind movie (delay in rewind loop, progressibly reduced down to 200)
int TargetRewindSpeedLoop = 200;               // Originalyl hardcoded, not in a variable to allow modification from UI
int PerforationMaxLevel = 550;      // detector pulse high level, clear film and low contrast film perforation (Torulf: 250)
int PerforationMinLevel = 50;      // detector pulse low level, originally hardcoded
int PerforationThresholdLevelR8 = 210;          // detector pulse level: Specific for R8
int PerforationThresholdLevelS8 = 210;          // detector pulse level: Specific for S8
int PerforationThresholdLevel = PerforationThresholdLevelS8;          // detector pulse level (Torulf: 250, JRE:160, going down, detect earlier)
int MinFrameStepsR8 = 263;            // Minimum number of steps to allow frame detection (less than this cannot happen) - Torulf:200
int MinFrameStepsS8 = 275;            // Minimum number of steps to allow frame detection (less than this cannot happen) - Torulf:200, JRE: 280 (285 definitively too much)
int MinFrameSteps = MinFrameStepsS8;            // Minimum number of steps to allow frame detection (less than this cannot happen) - Torulf:200
int DecreaseSpeedFrameStepsR8 = 253;          // JRE: Specific value for Regular 8 (Torulf: 270, JRE: 280)
int DecreaseSpeedFrameStepsS8 = 265;          // JRE: Specific value for Super 8 (Torulf: 290, JRE: 280)
int DecreaseSpeedFrameSteps = DecreaseSpeedFrameStepsS8;            // JRE: Number of steps at which we decrease motor speed, to allow precise frame detection (defaults to S8)
// ------------------------------------------------------------------------------------------

int OriginalPerforationThresholdLevel = PerforationThresholdLevel; // stores value for resetting PerforationThresholdLevel
// int Paus = LOW;                          // JRE: Unused
int FrameStepsDone = 0;                     // Count steps
int OriginalScanSpeed = ScanSpeed;          // restoration original value
int OriginalMinFrameSteps = MinFrameSteps;  // restoration original value

int LastFrameSteps = 0;                     // stores number of steps


boolean TractionStopActive = true;  //used to be "int inDraState = HIGH;" in original Torulf code
int TractionStopEventCount = 2;

unsigned long TractionStopWaitingTime = 50000;  // winding wheel C Start value, changed by program. 2000 in Original code (JRE: 20000, after the change in the collecting film code in scan function. Later changed to 100000 (100 ms) to simplify)
// unsigned long time; // Reference time. Will get number of microsecods since program started. Will cicle in 70 minutes. Redefined in 'scan', so useless here
unsigned long LastTime = 0;   // This is not modified anywhere. What is the purpose? JRE: Corrected, updated when moving capstan to find next frame
unsigned long TractionStopLastWaitEventTime = 0;

unsigned long StartFrameTime = 0;   // Time at which we get RPi command to get next frame
unsigned long StartPictureSaveTime = 0;   // Time at which we tell RPi to save current frame

int EventForRPi = 0;    // 11-Frame ready for exposure, 12-Error during scan, 60-Rewind end, 61-FF end, 64-Rewind error, 65-FF error

int PT_SignalLevelRead;   // Level out signal phototransistor detection

// Flag to detect ALT UI version
// Need to prevent operation with main version since compatibility cannot be maintained
boolean ALT_Scann8_UI_detected = false;

// JRE - Support data variables
#define QUEUE_SIZE 20
volatile struct {
  int Data[QUEUE_SIZE];
  int in;
  int out;
} CommandQueue;

void setup() {

  // Possible serial speeds: 1200, 2400, 4800, 9600, 19200, 38400, 57600,74880, 115200, 230400, 250000, 500000, 1000000, 2000000
  Serial.begin(115200);  // As fast as possible for debug, otherwise it slows down execution
  
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


  analogWrite(11, UVLedBrightness); // Turn on UV LED
  UVLedOn = true;


  digitalWrite(MotorA_Stepper, LOW);
  digitalWrite(MotorB_Stepper, LOW);
  digitalWrite(MotorC_Stepper, LOW);

  // JRE 04/08/2022
  CommandQueue.in = 0;
  CommandQueue.out = 0;
}
void loop() {
  while (1) {
    if (dataInQueue()) {
      Ic = pop();   // Get next command from queue if one exists
      if (!ALT_Scann8_UI_detected && Ic != 1) {
        Ic = 0; // Drop dequeued commend until ALT UI version detected
        DebugPrint("UI req no id"); 
        EventForRPi = 3;  // Tell ALT UI to identify itself
        digitalWrite(13, HIGH);
      }
    }
    else
      Ic = 0;

    // First do some common stuff (set port, push phototransistor level)
    Wire.begin(16);

    TractionStopActive = digitalRead(TractionStopPin);

    if (ScanState != Sts_Scan && ScanState != Sts_SingleStep) {
      // Set default state and direction of motors B and C (disabled, clockwise)
      // In the original main loop this was done when the Ic commamnd was NOT Single Step (49). Why???
      // JRE 23-08-2022: Explanation: THis is done mainly for the slow forward function, so that
      //    setting to high both the motors B and C they will move one step forward
      if (Ic != 40){  // In case we need the exact behavior of original code
        digitalWrite(MotorB_Stepper, LOW); 
        digitalWrite(MotorC_Stepper, LOW); 
        digitalWrite(MotorC_Direction, HIGH); 
        digitalWrite(MotorB_Direction, HIGH);
      }
    }

    switch (ScanState) {
      case Sts_Idle:
        switch (Ic) {
          case 1:
            ALT_Scann8_UI_detected = true;
            DebugPrint("ALT UI Identified"); 
            EventForRPi = 2;  // Tell ALT UI that ALT controller is present too
            digitalWrite(13, HIGH);
            break;
          case 10:
            DebugPrint(">Scan"); 
            ScanState = Sts_Scan;
            //delay(250); 
            StartFrameTime = micros();
            ScanSpeed = OriginalScanSpeed; 
            //MinFrameSteps = 5; 
            MinFrameSteps = 100; 
            tone(A2, 2000, 50);
            break;
          case 11:
            if (UVLedOn) {
                analogWrite(11, 0); // Turn off UV LED
                UVLedOn = false;
            }
            break;
          case 12:  // Continue scan to next frame
            ScanState = Sts_Scan;
            MinFrameSteps = OriginalMinFrameSteps; 
            StartFrameTime = micros();
            ScanSpeed = OriginalScanSpeed; 
            DebugPrintAux("Save t.",StartFrameTime-StartPictureSaveTime);
            DebugPrint(">Next fr.");
            break;
          case 18:  // Select R8 film
            DecreaseSpeedFrameSteps = DecreaseSpeedFrameStepsR8;
            MinFrameSteps = MinFrameStepsR8;
            PerforationThresholdLevel = PerforationThresholdLevelR8;
            OriginalMinFrameSteps = MinFrameSteps;
            OriginalPerforationThresholdLevel = PerforationThresholdLevel;
            break;
          case 19:  // Select S8 film
            DecreaseSpeedFrameSteps = DecreaseSpeedFrameStepsS8;
            MinFrameSteps = MinFrameStepsS8;
            PerforationThresholdLevel = PerforationThresholdLevelS8;
            OriginalMinFrameSteps = MinFrameSteps;
            OriginalPerforationThresholdLevel = PerforationThresholdLevel;
            break;
          case 20:
            ScanState = Sts_UnlockReels;
            delay(50);
            break;
          case 30:
            ScanState = Sts_SlowForward;
            delay(50);
            break;
          case 40:
            DebugPrint(">SStep"); 
            ScanState = Sts_SingleStep;
            MinFrameSteps = 100; // Used to be 100
            delay(50);
            break;
          case 50:
            if (PerforationThresholdLevel < 250)
              PerforationThresholdLevel++;
              OriginalPerforationThresholdLevel = PerforationThresholdLevel;
            break;
          case 51:
            if (PerforationThresholdLevel > 50)
              PerforationThresholdLevel--;
              OriginalPerforationThresholdLevel = PerforationThresholdLevel;
            break;
          case 52:
            if (MinFrameSteps < 300)
              MinFrameSteps++;
              OriginalMinFrameSteps = MinFrameSteps;
            break;
          case 53:
            if (MinFrameSteps > 100)
              MinFrameSteps--;
              OriginalMinFrameSteps = MinFrameSteps;
            break;
          case 60: // Rewind
            if (FilmInFilmgate()) { // JRE 13 Aug 22: Cannot rewind, there is film loaded
              DebugPrint("Rwnd err"); 
              EventForRPi = 64;
              digitalWrite(13, HIGH);
              tone(A2, 2000, 100); 
              delay (150); 
              tone(A2, 1000, 100); 
            }
            else {
              DebugPrint("Rwnd"); 
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
          case 61:  // Fast Forward
            if (FilmInFilmgate()) { // JRE 13 Aug 22: Cannot fast forward, there is film loaded
              DebugPrint("FF err"); 
              EventForRPi = 65; 
              digitalWrite(13, HIGH);
              tone(A2, 2000, 100); 
              delay (150); 
              tone(A2, 1000, 100); 
            }
            else {
              DebugPrint(">FF"); 
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
          case 62:  // Tune Rewind/FF speed delay up, allowing to slow down the rewind/ff speed
            if (TargetRewindSpeedLoop < 4000)
              TargetRewindSpeedLoop += 20;
            break;
          case 63:  // Tune Rewind/FF speed delay down, allowing to speed up the rewind/ff speed
            if (TargetRewindSpeedLoop > 200)
              TargetRewindSpeedLoop -= 20;
            break;
        }
        break;
      case Sts_Scan:
        if (!TractionStopActive) { // Wind outgoing film on reel C, if traction stop swicth not active
          delay (5); 
          digitalWrite(MotorC_Stepper, HIGH);
        }
        if (Ic == 10) {
          DebugPrint("-Scan"); 
          ScanState = Sts_Idle; // Exit scan loop
        }
        else if (scan(Ic) != SCAN_NO_FRAME_DETECTED) {
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
        if (scan(Ic) != SCAN_NO_FRAME_DETECTED) {
          ScanState = Sts_Idle;
        }
        break;
      case Sts_UnlockReels:
        if (Ic == 20) { //request to lock reels again
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
        }
        break;
      case Sts_Rewind:
        if (!RewindFilm(Ic)) {
          DebugPrint("-rwnd"); 
          ScanState = Sts_Idle;
        }
        break;
      case Sts_FastForward:
        if (!FastForwardFilm(Ic)) {
          DebugPrint("-FF"); 
          ScanState = Sts_Idle;
        }
        break;
      case Sts_SlowForward:
        if (Ic == 30) { // Stop slow forward
          delay(50);
          ScanState = Sts_Idle;
        }
        else {
          CollectOutgoingFilm();
          delay(1); 

          GetLevelPT(); // Just to collect stats (MaxPT, MinPT)
          digitalWrite(MotorB_Stepper, HIGH);
        }
        break;
    }

    // ----- Speed on stepper motors ------------------ JRE: To be checked if needed, here or elsewhere
    delayMicroseconds(1);

    // org 5
  }
}


// ------ rewind the movie ------
boolean RewindFilm(int Ic) {
  boolean retvalue = true;
  static boolean stopping = false;
  
  Wire.begin(16);

  if (Ic == 60) {
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
      EventForRPi = 60; 
      digitalWrite(13, HIGH);
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
boolean FastForwardFilm(int Ic) {
  boolean retvalue = true;
  static boolean stopping = false;

  Wire.begin(16);  // join I2c bus with address #16

  if (Ic == 61) {
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
      digitalWrite(MotorC_Neutral, HIGH); 
      digitalWrite(MotorB_Neutral, LOW);
      digitalWrite(MotorC_Neutral, LOW); 
      delay (100);
      EventForRPi = 61; 
      digitalWrite(13, HIGH);
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
void CollectOutgoingFilm(void) {
  // --- New code by JRE (to put the new switch to good use)
  unsigned long CurrentTime = micros();
  int StepCount=0;

  if ((CurrentTime - TractionStopLastWaitEventTime) >= TractionStopWaitingTime) {
    do {
      TractionStopActive = digitalRead(TractionStopPin);
  
      if (!TractionStopActive) {
        digitalWrite(MotorC_Stepper, LOW); 
        delayMicroseconds(1000);
        digitalWrite(MotorC_Stepper, HIGH); 
        delayMicroseconds(1000);
        digitalWrite(MotorC_Stepper, LOW); 
        StepCount++;
      }
      else {
        TractionStopLastWaitEventTime = CurrentTime;
        /* This algorythm ois a bit complicated, and not sure it is that useful. Better to have a fixed time to avoid checking too often for traction  stop
        TractionStopWaitingTime = TractionStopWaitingTime + 2000;
        if (TractionStopWaitingTime >= 120000)
          TractionStopWaitingTime = 70000;
        break;
        */
      }
    } while (!TractionStopActive && StepCount < 10); // 10 should be enough. This function is called only from scan, and each pass it performs a max of 4 steps
  } 
}

// ------------- Centralized phototransistor level read ---------------
int GetLevelPT() {
  static int count = 0;
  int SignalLevel = analogRead(PHOTODETECT);
  MaxPT = max(SignalLevel, MaxPT);
  MinPT = min(SignalLevel, MinPT);
  if (DebugState == PT_Level)
    count = (count+1) % 20;  // Report only one in twenty
    if (count == 0)
      SerialPrintInt(SignalLevel);

  return(SignalLevel);
}
// ------------- is there film loaded in filmgate? ---------------
boolean FilmInFilmgate() {
  int SignalLevel;
  boolean retvalue = false;
  int min=300, max=0;

  analogWrite(11, UVLedBrightness); // Turn on UV LED
  UVLedOn = true;
  delay(200);  // Give time to FT to stabilize


  // MinFrameSteps used here as a reference, just to skip two frames in worst case
  // Anyhow this funcion is used only for protection in rewind/ff, no film expected to be in filmgate
  for (int x = 0; x <= 300; x++) {
    digitalWrite(MotorB_Stepper, LOW); 
    digitalWrite(MotorB_Stepper, HIGH); 
    SignalLevel = GetLevelPT();
    if (SignalLevel > max) max = SignalLevel;
    if (SignalLevel < min) min = SignalLevel;
  }
  digitalWrite(MotorB_Stepper, LOW); 
  analogWrite(11, 0); // Turn off UV LED
  UVLedOn = false;


  if (abs(max-min) > 0.7*(MaxPT-MinPT))
    retvalue = true;

  return(retvalue);
}


// ------------- is the film perforation in position to take picture? ---------------
// Returns false if status should change to idle
boolean IsHoleDetected() {
  boolean hole_detected = false;
  
  PT_SignalLevelRead = GetLevelPT();
  if (PT_SignalLevelRead >= PerforationThresholdLevel) {  // PerforationThresholdLevel - Minimum level at which we can think a perforation is detected
    FilteredSignalLevel = PT_SignalLevelRead;
  }

  if (PT_SignalLevelRead >= PerforationMaxLevel) {   // Adjust perforation levels based on readings - TBC
    PerforationThresholdLevel = PerforationMaxLevel;
  }
  else if (PT_SignalLevelRead < PerforationMinLevel) {
    PerforationThresholdLevel = OriginalPerforationThresholdLevel;
  }

  if (PT_SignalLevelRead < PerforationThresholdLevel) {
    FilteredSignalLevel = 0;
  }

  // ------------- Frame detection ----
  if (FrameStepsDone >= MinFrameSteps && FilteredSignalLevel >= PerforationThresholdLevel && Pulse == LOW) {
    hole_detected = true;
    Pulse = HIGH; 
    analogWrite(A1, 255); // Light green led
  }
  else if (FilteredSignalLevel == 0 && Pulse == HIGH) {
    Pulse = LOW; 
    analogWrite(A1, 0); // Turn off green led
  }

  return(hole_detected);
}


// ----- This is the function to "ScanFilm" -----
// Returns false when done
ScanResult scan(int Ic) {
  ScanResult retvalue = SCAN_NO_FRAME_DETECTED;
  
  Wire.begin(16);

  analogWrite(11, UVLedBrightness);
  UVLedOn = true;

  PT_SignalLevelRead = GetLevelPT();
  
  unsigned long CurrentTime = micros();

  TractionStopActive = digitalRead(TractionStopPin);

  if (FrameStepsDone >= DecreaseSpeedFrameSteps /*&& ScanSpeed != FetchFrameScanSpeed*/) {
    //ScanSpeed = FetchFrameScanSpeed;
    ScanSpeed = 5000 + min(20000, DecreaseScanSpeedStep * (FrameStepsDone - DecreaseSpeedFrameSteps + 1));
    //DebugPrintAux("SSpeed",ScanSpeed);
  }

  // ------------ Stretching film pickup wheel (C) ------ 
  CollectOutgoingFilm();

  //-------------ScanFilm-----------
  if (Ic == 10) {   // UI Requesting to end current scan
    retvalue = SCAN_TERMINATION_REQUESTED; 
    FrameDetected = false; 
    //DecreaseSpeedFrameSteps = 260; // JRE 20/08/2022 - Disabled, added option to set manually from UI
    TractionStopWaitingTime = 100000; 
    LastFrameSteps = 0;
    if (UVLedOn) {
        analogWrite(11, 0); // Turn off UV LED
        UVLedOn = false;
    }
  }
  else {
    FrameDetected = IsHoleDetected();
    if (!FrameDetected) {
      // ---- Speed on stepper motors  ------------------
      if ((CurrentTime - LastTime) >= ScanSpeed ) {  // Last time is set to zero, and never modified. What is the purpose? Somethign migth be mising
        LastTime = CurrentTime; // JRE: Update LastTime here. Never updated in original code, meaning it was useless (previous condition always true)
        for (int x = 0; x <= 3; x++) {    // Originally from 0 to 3. Looping more than that required the collection code above to be optimized
          FrameStepsDone = FrameStepsDone + 1; 
          digitalWrite(MotorB_Stepper, LOW); 
          digitalWrite(MotorB_Stepper, HIGH); 
          FrameDetected = IsHoleDetected();
          if (FrameDetected || FrameStepsDone > 3*DecreaseSpeedFrameSteps) break;
          else delayMicroseconds(100);  
          // Explanation of delay in previous line:
          // Info sent on serial port, specially at low speeds (9600) introduces a delay 
          // that affects ATL-Scann 8 behaviour. So, when debug is disabled, scanning 
          // process go a bit out of control. 
          // That needs to be investigated, in the meantime this delay (0.1 ms) seems to keep 
          // things under control
        }
        digitalWrite(MotorB_Stepper, LOW);
      }
    }
  }

  if (FrameDetected) {
    DebugPrint("Frame!"); 
    LastFrameSteps = FrameStepsDone; 
    FrameStepsDone = 0; 
    StartPictureSaveTime = micros();
    // Tell UI (Raspberry PI) a new frame is available for processing
    if (ScanState == Sts_SingleStep) {  // Do not send event to RPi for single step
      tone(A2, 2000, 35); 
    }
    else {
      EventForRPi = 11; 
      digitalWrite(13, HIGH);
    }
    
    FrameDetected = false;
    retvalue = SCAN_FRAME_DETECTED;
    DebugPrintAux("FrmS",LastFrameSteps);
    DebugPrintAux("FrmT",CurrentTime-StartFrameTime);
    if (DebugState == FrameSteps)
      SerialPrintInt(LastFrameSteps);
  }
  else if (FrameStepsDone > 3*DecreaseSpeedFrameSteps) {
    retvalue = SCAN_FRAME_DETECTION_ERROR;    
    FrameStepsDone = 0;
    DebugPrint("Err/scan");
    // Tell UI (Raspberry PI) an error happened during scanning
    EventForRPi = 12; 
    digitalWrite(13, HIGH);
  }

  return (retvalue);
}

// ---- Receive I2C command from Raspberry PI, ScanFilm... and more ------------
// JRE 13/09/22: Theoretically this might happen any time, thu Ic might change in the middle of the loop. Adding a queue...
void receiveEvent(int byteCount) {
  int IncomingIc;

  IncomingIc = Wire.read();

  if (IncomingIc > 0) {
    push(IncomingIc); // No error treatment for now
  }
}

// -- Sending I2C command to Raspberry PI, take picture now -------
void sendEvent() {

  Wire.write(EventForRPi);
  EventForRPi = 0;
}

boolean push(int IncomingIc) {
    boolean retvalue = false;
    if ((CommandQueue.in+1) % QUEUE_SIZE != CommandQueue.out) {
      CommandQueue.Data[CommandQueue.in++] = IncomingIc;
      CommandQueue.in %= QUEUE_SIZE;
      retvalue = true;
    }
    // else: Queue full: Should not happen. Not sure how this should be handled
    return(retvalue);
}

int pop(void) {
    int retvalue = -1;  // default return value: -1 (error)
    if (CommandQueue.out != CommandQueue.in) {
      retvalue = CommandQueue.Data[CommandQueue.out++];
      CommandQueue.out %= QUEUE_SIZE;
    }
    // else: Queue empty: Nothing to do
    return(retvalue);
}

boolean dataInQueue(void) {
  return (CommandQueue.out != CommandQueue.in);
}

void DebugPrintAux(const char * str, unsigned long i) {
  static char PreviousDebug[64];
  static char AuxLine[64];
  static char PrintLine[64];
  static int CurrentRepetitions = 0;
  boolean GoPrint = true;
  
  if (DebugState != DebugInfo) return;

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

void DebugPrint(const char * str) {
  DebugPrintAux(str,-1);
}


void SerialPrintStr(const char * str) {
  if (DebugState != DebugInfo) Serial.println(str);
}

void SerialPrintInt(int i) {
  if (DebugState != DebugInfo) Serial.println(i);
}
