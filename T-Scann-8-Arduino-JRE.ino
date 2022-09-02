/*    T-Scann8 Super8/Regular8 Scanner ver 1.61
      -UV led version-
      © Torulf Holmström Sweden 2022
      project page
      tscann8.torulf.com

      01 Aug 2022 - JRE - Added fast forward function
      04 Aug 2022 - JRE - Renamed commands, initialized to 'false' instead of 'LOW' (easier understanding)
      04 Aug 2022 - JRE - Read and understoow the basic way Arduino code is supposed to work: Interrupts and main loop
      04 Aug 2022 - JRE - Restructuring main loop: Addig a queue for incoming commands, use a switch for command processing
                          Beware: 
                          - Not everything happening in the main loop is linked to a received command
                          - Main loop migth call functions that have their own loops
                          Possible new approach:
                          - Only one loop (main one)
                          - One main switch with current status (scan, rewind, etc)
                          - Secondary switch per state to handle command
      04 Aug 2022 - JRE - Moving to 1.61.4 before bug changes
      04 Aug 2022 - JRE - Reorganized overall structure
                          - Converted main loop with variables to 2 switches, one for the state, other for incoming command
                          - Some stuff works erratically, others do not work at all
      05 Aug 2022 - JRE - Moving to 1.61.5 before doign more changes
                          - Renaming of variables for easier understanding of the flow
      06 Aug 2022 - JRE - Moving to 1.61.6 before doing more changes
                          - Version mostly working, includign slow forward and Scan
                          - Main issue pending: Frame not detected corretly (too high)
                          - Moving to new version in case we need to roll back
      06 Aug 2022 - JRE - Moving to 1.61.7 before doing more changes
                          - Implemented differentiated commands fro start and end of each action, where needed
      08 Aug 2022 - JRE - Moving to 1.61.8 before doing more changes
                          - Chanhe the way Scan state terminates between frames
      10 Aug 2022 - JRE - 1.61.8 Working fine, move to version 1.61.9 to keep 1.61.8 as reference
      13 Aug 2022 - JRE - 1.61.9 Implemented detection of film loaded via filmgate, to prevent FF/RWND
                        - Move to 1.61.10
      23 Aug 2022 - JRE - (version in GIT) Improvement on outgoing film management durign scan. Collect all 
                          until traction switch triggers
      31 Aug 2022 - JRE - Nice and easy improvement in frame detection
                        - Increase MinFrameSteps (WstepV) from 176 to 270-275
                        - Logic behind: 
                          1/ There is no reason why, for a given build, the capstan will move LESS than n steps to get 
                             the next frame
                            1.1/ MORE than n steps might happen (if film slides over capstan), and should handled
                          2/ Number of steps n depends on stepper motor model and configuration, plus capstan radius
                          3/ Usign the standard components advised by Torulf, this number is around 270-275
                          4/ The minumum number of step considered in the Arduino program (as of 1.61) is 176 (WstepV)
                          5/ Because of this, it sometimes happen (due to factors like sub-optimal FT isolation) that 
                             the frame is detected before reaching 270 steps (this is typically when the lower part of 
                             the frame is off limits in the captured image)
      01 Sep 2022 - JRE - Remove interface to allow RPi to tell us to modify the perforation level threshold
                          This was mostly to analyze best value, can be removed now.
                          Also, with yesterday's change (increase of MinFrameSteps), hole detection is more of a confirmation
*/

#include <Wire.h>
#include <stdio.h>

const int PHOTODETECT = A0; // Analog pin 0 perf

boolean GlobalDebug = true;
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
// Command list
/*
int ScanFilm = false;       // Scan film
int UnlockReels = false;    // Unlock reels
int Rewind = false;         // Rewind film (Spola in Torulf original module)
int FastForward = false;    // FastForward
int SlowForward = false;    // Advance film (move forward without scanning)
//int Frame = LOW;          // Unused
int SingleStep = false;     // Single step
*/
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
// Last status for each command: I think this is useless, the base variable can be used instead
/*
int lastScanFilm = LOW;
int lastUnlockReels = LOW;
int lastRewind = LOW;
int lastFastForward = LOW;
int lastSlowForward = LOW;
int lastFrame = LOW;
int LastWstep = 0;  // Unused
*/
int FilteredSignalLevel = 0;
// int waveC = 0;  // Not used
// int waveCS = 0;  // Not used


// ----- Important setting, may need to be adjusted ------

int UVLedBrightness = 250;                    // Brightness UV led, may need to be changed depending on LED (Torulf: 250)
unsigned long ScanSpeed = 500 ;               // speed stepper scann Play (original 500)
unsigned long FetchFrameScanSpeed = 25000;    // Play Slow before trig (Original 15000)
int RewindSpeed = 4000;                       // speed Rewind movie
int PerforationThresholdLevel = 160;          // detector pulse level (Torulf: 250)
                                              // JRE: After increasing MinFramSteps, this one is not so critical any more
int PerforationMaxLevel = 500;      // detector pulse high level, clear film and low contrast film perforation
int PerforationMinLevel = 200;      // detector pulse low level, originalyl hardcoded
int MinFrameStepsR8 = 260;            // Minimum number of steps to allow frame detection (less than this cannot happen) - Torulf:200
int MinFrameStepsS8 = 280;            // Minimum number of steps to allow frame detection (less than this cannot happen) - Torulf:200
int MinFrameSteps = MinFrameStepsS8;            // Minimum number of steps to allow frame detection (less than this cannot happen) - Torulf:200
int DecreaseSpeedFrameStepsR8 = 260;          // JRE: Specific value for Regular 8 (Torulf: 270, JRE: ??)
int DecreaseSpeedFrameStepsS8 = 280;          // JRE: Specific value for Super 8 (Torulf: 290, JRE: ??)
int DecreaseSpeedFrameSteps = DecreaseSpeedFrameStepsS8;            // JRE: Number of steps at which we decrease motor speed, to allow precise frame detection (defaults to S8)


// -------------------------------------------------------

/*const */int OriginalPerforationThresholdLevel = PerforationThresholdLevel; // stores value for resetting PerforationThresholdLevel
// int Paus = LOW;                          // JRE: Unused
int FrameStepsDone = 0;                     // Count steps
int OriginalScanSpeed = ScanSpeed;          // restoration original value
int OriginalMinFrameSteps = MinFrameSteps;  // restoration original value
int FilmTypeFrameCount = 0;                 // counts to 2 before S8 / R8 is determined
int LastFrameSteps = 0;                     // stores number of steps


boolean TractionStopActive = true;  //used to be "int inDraState = HIGH;" in original Torulf code
int TractionStopEventCount = 2;

unsigned long TractionStopWaitingTime = 20000;  // winding wheel C Start value, changed by program. 2000 in Original code (JRE: 20000, after the change in the collecting film code in scan function)
// unsigned long time; // Reference time. Will get number of microsecods since program started. Will cicle in 70 minutes. Redefined in 'scan', so useless here
unsigned long LastTime = 0;   // This is not modified anywhere. What is the purpose? JRE: Corrected, updated when moving capstan to find next frame
unsigned long TractionStopLastWaitEventTime = 0;

unsigned long StartFrameTime = 0;   // Time at which we get RPi command to get next frame
unsigned long StartPictureSaveTime = 0;   // Time at which we tell RPi to save current frame

int EventForRPi = 0;    // 11-Frame ready for exposure, 61-Rewind error, 81-FF error

int PT_SignalLevelRead;   // Level out signal phototransistor detection

// JRE - Support data variables
#define QUEUE_SIZE 20
volatile struct {
  int Data[QUEUE_SIZE];
  int in;
  int out;
} CommandQueue;

void setup() {

  // Possible serial speeds: 1200, 2400, 4800, 9600, 19200, 38400, 57600,74880, 115200, 230400, 250000, 500000, 1000000, 2000000
  if (GlobalDebug)
    Serial.begin(115200);  // As fast as possible for debug, otherwise it slows down execution
  else
    Serial.begin(9600);  // 9600 for serial plotter (otyherwise it goes too fast)
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
    if (dataInQueue())
      Ic = pop();   // Get next command from queue if one exists
    else
      Ic = 0;

    // First do some common stuff (set port, push phototransistor level)
    Wire.begin(16);

    // Get phototransistor level in order to make it available via Arduino serial interface
    // JRE 4/8/22: Check first if we are in debug mode: If yes, serial i/f is dedicated for it
    int PT_SignalLevelRead = analogRead(PHOTODETECT);
    if (ScanState == Sts_Scan || ScanState == Sts_SingleStep)
      SerialPrintInt(PT_SignalLevelRead); // can be read in Arduino IDE - Serial plotter

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
        if (UVLedOn) {
            analogWrite(11, 0); // Turn off UV LED
            UVLedOn = false;
        }
        switch (Ic) {
          case 10:
            DebugPrint(">>>>>> Scan started by user"); 
            ScanState = Sts_Scan;
            //delay(250); 
            StartFrameTime = micros();
            MinFrameSteps = 5; 
            tone(A2, 2000, 50);
            break;
          case 12:  // Continue scan to next frame
            ScanState = Sts_Scan;
            MinFrameSteps = OriginalMinFrameSteps; 
            StartFrameTime = micros();
            ScanSpeed = OriginalScanSpeed; 
            DebugPrintAux("Last picture save time",StartFrameTime-StartPictureSaveTime);
            DebugPrint(">>>>>> Scan next frame");
            FilmTypeFrameCount = FilmTypeFrameCount + 1;
            break;
          case 18:  // Select R8 film
            DebugPrint("Idle -> Select R8"); 
            DecreaseSpeedFrameSteps = DecreaseSpeedFrameStepsR8;
            MinFrameSteps = MinFrameStepsR8;
            break;
          case 19:  // Select S8 film
            DebugPrint("Idle -> Select S8"); 
            DecreaseSpeedFrameSteps = DecreaseSpeedFrameStepsS8;
            MinFrameSteps = MinFrameStepsS8;
            break;
          case 20:
            DebugPrint("Idle -> UnlockReels"); 
            ScanState = Sts_UnlockReels;
            delay(50);
            break;
          case 30:
            DebugPrint("Idle -> SlowForward"); 
            ScanState = Sts_SlowForward;
            delay(50);
            break;
          case 40:
            DebugPrint("Idle -> SingleStep"); 
            ScanState = Sts_SingleStep;
            MinFrameSteps = 100; // Used to be 100
            delay(50);
            break;
          case 60:
            if (FilmInFilmgate()) { // JRE 13 Aug 22: Cannot rewind, there is film loaded
              DebugPrint("Rewind error"); 
              EventForRPi = 61; 
              digitalWrite(13, HIGH);
              tone(A2, 2000, 100); 
              delay (150); 
              tone(A2, 1000, 100); 
            }
            else {
              DebugPrint("Idle -> Rewind"); 
              ScanState = Sts_Rewind;
              delay (500); 
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
          case 80:
            if (FilmInFilmgate()) { // JRE 13 Aug 22: Cannot fast forward, there is film loaded
              DebugPrint("FF error"); 
              EventForRPi = 81; 
              digitalWrite(13, HIGH);
              tone(A2, 2000, 100); 
              delay (150); 
              tone(A2, 1000, 100); 
            }
            else {
              DebugPrint("Idle -> FastForward"); 
              ScanState = Sts_FastForward;
              delay (500); 
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
        }
        break;
      case Sts_Scan:
        if (!TractionStopActive) { // Wind outgoing film on reel C, if traction stop swicth not active
          delay (5); 
          digitalWrite(MotorC_Stepper, HIGH);
        }
        if (Ic == 10) {
          DebugPrint("Scan stopped by user command"); 
          ScanState = Sts_Idle; // Exit scan loop
        }
        else if (scan(Ic)) {
          // Advance to next frame ? (to be checked)
          /* does not seem to be required (loop -> scan -> loop -> scan ...). Not sure how it works. Thanks to extensive use of global variables maybe
          digitalWrite(MotorB_Stepper, LOW); 
          delay(20); 
          digitalWrite(MotorB_Stepper, HIGH); 
          delay (20); 
          digitalWrite(MotorB_Stepper, LOW);
          */
        }
        else {
          ScanState = Sts_Idle; // Exit scan loop
        }
        break;
      case Sts_SingleStep:
        if (!scan(Ic)) {
          DebugPrint("Exiting single step state"); 
          ScanState = Sts_Idle;
        }
        break;
      case Sts_UnlockReels:
        if (Ic == 20) { //request to lock reels again
          ReelsUnlocked = false;
          digitalWrite(MotorB_Neutral, LOW); 
          digitalWrite(MotorC_Neutral, LOW);
          ScanState = Sts_Idle;
          DebugPrint("Exiting Unlock Reels state"); 
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
          DebugPrint("Exiting rewind state"); 
          ScanState = Sts_Idle;
        }
        break;
      case Sts_FastForward:
        if (!FastForwardFilm(Ic)) {
          DebugPrint("Exiting FastForward state"); 
          ScanState = Sts_Idle;
        }
        break;
      case Sts_SlowForward:
        if (Ic == 30) { // Stop slow forward
          delay(50);
          ScanState = Sts_Idle;
          DebugPrint("Exiting slow forward"); 
        }
        else {
          if (!TractionStopActive) {
            TractionStopEventCount = TractionStopEventCount + 1; 
            delay(10); 
            digitalWrite(MotorC_Stepper, HIGH);
          }
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
  
  Wire.begin(16);

  if (Ic == 60) {
    retvalue = false;
    digitalWrite(MotorA_Neutral, HIGH);
    delay (100);
  }
  else {
    digitalWrite(MotorA_Stepper, HIGH); 
    delayMicroseconds(RewindSpeed); 
    digitalWrite(MotorA_Stepper, LOW);
    if (RewindSpeed >= 200) {
      RewindSpeed -= 2;
    }
  }
  return(retvalue);
}

// ------ fast forward the movie ------
boolean FastForwardFilm(int Ic) {
  boolean retvalue = true;

  Wire.begin(16);  // join I2c bus with address #16

  if (Ic == 80) {
    retvalue = false;
    digitalWrite(MotorC_Neutral, HIGH); 
    delay (100);
  }
  else {
    digitalWrite(MotorC_Stepper, HIGH); 
    delayMicroseconds(RewindSpeed); 
    digitalWrite(MotorC_Stepper, LOW);
  }
    if (RewindSpeed >= 250) {
      RewindSpeed = RewindSpeed - 2;
    }
  return(retvalue);
}

// ------------- Collect outgoing film
void CollectOutgoingFilm(void) {
  // --- New code by JRE (to put the new switch to good use)
  unsigned long CurrentTime = micros();

  if ((CurrentTime - TractionStopLastWaitEventTime) >= TractionStopWaitingTime) {
    do {
      TractionStopActive = digitalRead(TractionStopPin);
  
      if (!TractionStopActive) {
        digitalWrite(MotorC_Stepper, LOW); 
        delayMicroseconds(1000);
        digitalWrite(MotorC_Stepper, HIGH); 
        delayMicroseconds(1000);
        digitalWrite(MotorC_Stepper, LOW); 
      }
      else {
        TractionStopLastWaitEventTime = CurrentTime;
        TractionStopWaitingTime = TractionStopWaitingTime + 2000;
        if (TractionStopWaitingTime >= 120000)
          TractionStopWaitingTime = 70000;
        break;
      }
    } while (!TractionStopActive);
  } 
}

// ------------- is there film loaded in filmgate? ---------------
boolean FilmInFilmgate() {
  int SignalLevel,PreviousSignalLevel=0;
  boolean retvalue = false;

  analogWrite(11, UVLedBrightness); // Turn on UV LED
  UVLedOn = true;
  delay(100);  // Give time to FT to stabilize

  PreviousSignalLevel = analogRead(PHOTODETECT);
  //DebugPrintAux("Signal=", PreviousSignalLevel );

  // MinFrameSteps used here as a reference, just to skip two frames in worst case
  // Anyhow this funcion is used only for protection in rewind/ff, no film expected to be in filmgate
  for (int x = 0; x <= 2*MinFrameSteps; x++) {
    digitalWrite(MotorB_Stepper, LOW); 
    digitalWrite(MotorB_Stepper, HIGH); 
    SignalLevel = analogRead(PHOTODETECT);
    //DebugPrintAux("Signal=", SignalLevel );
    if (abs(SignalLevel - PreviousSignalLevel) > 50) {
      retvalue = true;
      break;
    }
    PreviousSignalLevel = SignalLevel;
  }
  digitalWrite(MotorB_Stepper, LOW); 
  analogWrite(11, 0); // Turn off UV LED
  UVLedOn = false;
  return(retvalue);
}


// ------------- is the film perforation in position to take picture? ---------------
// Returns false if status should change to idle
void check() {
  PT_SignalLevelRead = analogRead(PHOTODETECT);

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
  if (FilteredSignalLevel >= PerforationThresholdLevel && Pulse == LOW && FrameStepsDone >= MinFrameSteps ) {
    DebugPrint("check - Frame detected"); 
    Pulse = HIGH; 
    FrameDetected = true; 
    LastFrameSteps = FrameStepsDone; 
    FrameStepsDone = 0; 
    analogWrite(A1, 255); // Light green led
    StartPictureSaveTime = micros();
    EventForRPi = 11; 
    digitalWrite(13, HIGH);
  }
  else if (FilteredSignalLevel == 0 && Pulse == HIGH) {
    DebugPrint("check - Previous frame has now passed"); 
    Pulse = LOW; 
    analogWrite(A1, 0); // Turn off green led
  }

  // -- One step frame --
  if (ScanState == Sts_SingleStep && FrameDetected) {
    DebugPrint("check - Single step mode, exit scan"); 
    EventForRPi = 0; 
    // Leave FrameDetected as true, will be disable in 'scan' after we exit here
    tone(A2, 2000, 35); 
  }
}


// ----- This is the function to "ScanFilm" -----
// Returns false when done
boolean scan(int Ic) {
  boolean retvalue = true;
  
  Wire.begin(16);

  analogWrite(11, UVLedBrightness);
  UVLedOn = true;

  PT_SignalLevelRead = analogRead(PHOTODETECT);
  unsigned long CurrentTime = micros();

  TractionStopActive = digitalRead(TractionStopPin);

  if (PT_SignalLevelRead >= PerforationThresholdLevel) {
    FilteredSignalLevel = PT_SignalLevelRead;
  }

  if (PT_SignalLevelRead >= PerforationMaxLevel) {
    PerforationThresholdLevel = PerforationMaxLevel;
  }

  else if (PT_SignalLevelRead < PerforationMinLevel) {
    PerforationThresholdLevel = OriginalPerforationThresholdLevel;
  }

  if (PT_SignalLevelRead < PerforationThresholdLevel) {
    FilteredSignalLevel = 0;
  }

  if (FrameStepsDone >= DecreaseSpeedFrameSteps && FilmTypeFrameCount >= 2 ) {
    ScanSpeed = FetchFrameScanSpeed;
    DebugPrintAux("ScanSpeed",ScanSpeed);
  }

/*** Disable automatic detection
  // Detect whether Super 8 or Regular 8
  if (FilmTypeFrameCount >= 2 && LastFrameSteps > 280 && LastFrameSteps < 300 ) {
    DebugPrint("scan - R8 detected"); 
    DecreaseSpeedFrameSteps = DecreaseSpeedFrameStepsR8; //R8
  }

  if (FilmTypeFrameCount >= 2 && LastFrameSteps > 300) {
    DebugPrint("scan - S8 detected"); 
    DecreaseSpeedFrameSteps = DecreaseSpeedFrameStepsS8; //S8
  }
***/

  // Push Phototransistor level unconditionally, we neccesarily are in Scan or SingleStep modes
  // JRE 4/8/22: SerialPrint used to inhibit regular writes to Serial while in debug mode
  SerialPrintInt(PT_SignalLevelRead);

  // ------------ Stretching film pickup wheel (C) ------ 
  CollectOutgoingFilm();

  //-------------ScanFilm-----------
  if (Ic == 10) {   // UI Requesting to end current scan
    DebugPrint("scan - RPi asks to end scan"); 
    retvalue = false; 
    FrameDetected = false; 
    FilmTypeFrameCount = 0; 
    //DecreaseSpeedFrameSteps = 260; // JRE 20/08/2022 - Disabled, added option to set manually from UI
    TractionStopWaitingTime = 1000; 
    LastFrameSteps = 0;
  }
  else {
    check();
    if (!FrameDetected) {
      // ---- Speed on stepper motors  ------------------
      if ((CurrentTime - LastTime) >= ScanSpeed ) {  // Last time is set to zero, and never modified. What is the purpose? Somethign migth be mising
        //LastTime = CurrentTime; // JRE: Update LastTime here. Never updated in original code, meaning it was useless (previous condition always true)
        for (int x = 0; x <= 3; x++) {    // Originally from 0 to 3. Looping more than that required the collection code above to be optimized
          FrameStepsDone = FrameStepsDone + 1; 
          digitalWrite(MotorB_Stepper, LOW); 
          digitalWrite(MotorB_Stepper, HIGH); 
          check();
          if (FrameDetected) break;
        }
        digitalWrite(MotorB_Stepper, LOW);
      }
    }
  }

  if (FrameDetected) {
    FrameDetected = false;
    retvalue = false;
    DebugPrintAux("Last Frame Steps",LastFrameSteps);
    DebugPrintAux("Last Frame Detect Time",CurrentTime-StartFrameTime);
  }

  return (retvalue);
}

// ---- Receive I2C command from Raspberry PI, ScanFilm... and more ------------
// JRE 04/08/22: Theoretically thia might happen any time, thu Ic might change in the middle of the loop. Adding a queue...
void receiveEvent(int byteCount) {
  int IncomingIc;

  IncomingIc = Wire.read();

  push(IncomingIc); // No error treatment for now
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
  
  if (!GlobalDebug) return;

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
  if (!GlobalDebug) Serial.println(str);
}

void SerialPrintInt(int i) {
  if (!GlobalDebug) Serial.println(i);
}
