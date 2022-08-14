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
                          - Converted main loop with variables to 2 switches, one for the state, another for the incoming command
                          - Some stuff works erratically, others do not work at all
      05 Aug 2022 - JRE - Moving to 1.61.5 before doign more changes
                          - Renaming of variables for easier understanding of the flow
      06 Aug 2022 - JRE - Moving to 1.61.6 before doing more changes
                          - Version mostly working, includign slow forward and Scan
                          - Main issue pending: Frame not detected corretly (too high)
                          - Moving to new version in case we need to roll back
      06 Aug 2022 - JRE - Moving to 1.61.7 before doing more changes
                          - Implemented differentiated commands fro start and end of each action, where needed
*/

#include <Wire.h>
#include <stdio.h>

const int PHOTODETECT = A0; // Analog pin 0 perf

boolean GlobalDebug = false;
int MaxDebugRepetitions = 3;

int Pulse = LOW;
int Ic; // Stores I2C command from Raspberry PI --- ScanFilm=10 / UnlockReels mode=20 / Slow Forward movie=30 / One step frame=40 / Rewind movie=60 / Fast Forward movie=80 / Emergency Stop=90

//------------ Stepper motors control ----------------
const int MotorA_Stepper = 2;   // Stepper motor film feed
const int MotorA_Neutral = 3;     // neutral position
const int MotorB_Stepper = 4; // Stepper motor capstan propulsion
const int MotorB_Neutral = 5;     // neutral position
const int MotorC_Stepper = 6;   // Stepper motor film winding
const int MotorC_Neutral = 7;     // neutral position
const int MotorA_Direction = 8;    // direction
const int MotorB_Direction = 9;  // direction
const int MotorC_Direction = 10;   // direction


const int TractionStopPin = 12; // Traction stop
// Command list
/*
int ScanFilm = false;   // Scan film
int UnlockReels = false;   // Unlock reels
int Rewind = false;  // Rewind fild (Spola in Torulf original module)
int FastForward = false;  // FastForward
int SlowForward = false;   // Advance film (move forward without scanning)
//int Frame = LOW;  // Unused
int SingleStep = false; // Single step
*/
boolean ReelsUnlocked = false;
enum ScanState{
  Sts_Idle,
  Sts_Scan,
  Sts_UnlockReels,
  Sts_Rewind,
  Sts_FastForward,
  Sts_SlowForward,
  Sts_SingleStep,
  Sts_EmergencyStop
}
ScanState=Sts_Idle;

boolean FrameDetected = false;  // Used for frame detection, in play ond single step modes
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

int UVLedBrightness = 250;      // Brightness UV led, may need to be changed depending on LED
int ScanSpeed = 1000 ;     // speed stepper scann Play
int InitialScanSpeed = 15000;    // Play Slow before trig
int RewindSpeed = 4000;    // speed Rewind movie
int PerforationThresholdLevel = 250; // detector pulse level
int PerforationMaxLevel = 500;    // detector pulse high level, clear film and low contrast film perforation
int PerforationMinLevel = 200;    // detector pulse low level, originalyl hardcoded
int MinFrameSteps = 160;     // Minimum number of steps, before new frame is exposed - JRE: Best value for me -> 176
int MaxFrameSteps = 281;    // JRE assumption: Maximum number of steps, before new frame is exposed (default setting before sensing Super 8 or Regular 8)

// -------------------------------------------------------

const int OriginalPerforationThresholdLevel = PerforationThresholdLevel; // stores value for resetting PerforationThresholdLevel
// int Paus = LOW; // JRE: Unused
int FrameStepsDone = 0;  // Count steps
int OriginalScanSpeed = ScanSpeed; // restoration original value
int OriginalMinFrameSteps = MinFrameSteps; // restoration original value
int FilmTypeFrameCount = 0;  // counts to 2 before S8 / R8 is determined
int LastFrameSteps = 0; // stores number of steps


boolean TractionStopActive = true;  //used to be "int inDraState = HIGH;" in original Torulf code
int TractionStopEventCount = 2;

unsigned long TractionStopWaitingTime = 2000;  // winding wheel C Start value, changed by program.
// unsigned long time; // Reference time. Will get number of microsecods since program started. Will cicle in 70 minutes. Redefined in 'scan', so useless here
unsigned long LastTime = 0;   // This is not modified anywhere. What is the purpose? Need to make some experiments
unsigned long TractionStopLastWaitEventTime = 0;

int Exp = 0;    // 11 is exposure I2C

int PT_SignalLevelRead;   // Level out signal phototransistor detection

// JRE - Support data variables
#define QUEUE_SIZE 20
volatile struct {
  int Data[QUEUE_SIZE];
  int in;
  int out;
} CommandQueue;

void setup() {

  Serial.begin(9600);  // Used to be 9600. Should work with 230400
  Wire.begin(16);  // join I2c bus with address #16
  Wire.onReceive(receiveEvent); // register event
  Wire.onRequest(sendexp);


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
    SerialPrintInt(PT_SignalLevelRead); // can be read in Arduino IDE - Serial plotter

    TractionStopActive = digitalRead(TractionStopPin);

    if (ScanState == Sts_Idle) {
      // Set default state and direction of motors B and C (disabled, clockwise)
      // In the original main loop this was done when the Ic commamnd was NOT Single Step (49). Why???
      if (Ic != 40){  // In case we need the exact behavior of original code
        digitalWrite(MotorB_Stepper, LOW); 
        digitalWrite(MotorC_Stepper, LOW); 
        digitalWrite(MotorC_Direction, HIGH); 
        digitalWrite(MotorB_Direction, HIGH);
      }
  
      // Next does not make much sense, but this is what the original code does.
      if (ReelsUnlocked) {
        digitalWrite(MotorB_Neutral, HIGH);  
        digitalWrite(MotorC_Neutral, HIGH); 
      }
      else {
        digitalWrite(MotorB_Neutral, LOW);  
        digitalWrite(MotorC_Neutral, LOW); 
      }
    }

    switch (ScanState) {
      case Sts_Idle:
        switch (Ic) {
          case 10:
            DebugPrint("Idle -> Scan"); 
            ScanState = Sts_Scan;
            delay(250); 
            MinFrameSteps = 5; 
            tone(A2, 2000, 50);
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
            MinFrameSteps = 100; 
            delay(50);
            break;
          case 60:
            DebugPrint("Idle -> Rewind"); 
            ScanState = Sts_Rewind;
            delay (500); 
            digitalWrite(MotorA_Neutral, LOW); 
            digitalWrite(MotorB_Neutral, HIGH);  
            digitalWrite(MotorC_Neutral, HIGH); 
            tone(A2, 2000, 200); 
            delay (300); 
            tone(A2, 2000, 200); 
            RewindSpeed = 4000;
            break;
          case 80:
            DebugPrint("Idle -> FastForward"); 
            ScanState = Sts_FastForward;
            delay (500); 
            digitalWrite(MotorA_Neutral, HIGH); 
            digitalWrite(MotorB_Neutral, HIGH);  
            digitalWrite(MotorC_Neutral, LOW); 
            tone(A2, 2000, 200); 
            delay (300); 
            tone(A2, 2000, 200); 
            RewindSpeed = 4000;
            break;
          case 90:
            DebugPrint("Idle -> EmergencyStop"); 
            ScanState = Sts_EmergencyStop;
            delay(50);
            break;
        }
        break;
      case Sts_Scan:
        if (Ic == 10) {
          DebugPrint("Exiting Scan state"); 
          ScanState = Sts_Idle; // Exit scan loop
        }
        else if (scan(Ic)) {
          if (!TractionStopActive) { // Wind outgoing film on reel C, if traction stop swicth not active
            delay (5); 
            digitalWrite(MotorC_Stepper, HIGH);
          }
          // Advance to next frame ? (to be checked)
          /* does not seem to be required (loop -> scan -> loop -> scan ...). Not sure how it works. Thanks to extensive use of global variables maybe
          digitalWrite(MotorB_Stepper, LOW); 
          delay(20); 
          digitalWrite(MotorB_Stepper, HIGH); 
          delay (20); 
          digitalWrite(MotorB_Stepper, LOW);
          */
          DebugPrint("Staying in Scan state"); 
        }
        else {
          DebugPrint("Exiting Scan state"); 
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
          DebugPrint("Staying in unlock reels state"); 
        }
        break;
      case Sts_Rewind:
        if (!RewindFilm(Ic)) {
          DebugPrint("Exiting rewind state"); 
          ScanState = Sts_Idle;
        }
        else
          DebugPrint("Staying in rewind state"); 
        break;
      case Sts_FastForward:
        if (!FastForwardFilm(Ic)) {
          DebugPrint("Exiting FastForward state"); 
          ScanState = Sts_Idle;
        }
        else
          DebugPrint("Staying in FastForward state"); 
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
          //DebugPrint("Staying in slow forward state"); 
        }
        break;
      case Sts_SingleStep:
        if (!scan(Ic)) {
          DebugPrint("Exiting single step state"); 
          ScanState = Sts_Idle;
        }
        break;
      case Sts_EmergencyStop:
        DebugPrint("Exiting EmergencyStop state"); 
        digitalWrite(MotorA_Stepper, LOW); 
        digitalWrite(MotorB_Stepper, LOW); 
        digitalWrite(MotorC_Stepper, LOW); 
        digitalWrite(MotorA_Neutral, HIGH);
        ScanState = Sts_Idle;
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
    if (RewindSpeed >= 250) {
      RewindSpeed = RewindSpeed - 2;
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
    analogWrite (A1, 255); // Light green led
    Exp = 11; 
    digitalWrite(13, HIGH);
  }
  else if (FilteredSignalLevel == 0 && Pulse == HIGH) {
    DebugPrint("check - Previous frame is now done"); 
    Pulse = LOW; 
    analogWrite(A1, 0); // Turn off green led
  }

  // -- One step frame --
  if (ScanState == Sts_SingleStep && FrameDetected) {
    DebugPrint("check - Single step mode, exit scan"); 
    Exp = 0; 
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

  if (FrameStepsDone >= MaxFrameSteps && FilmTypeFrameCount >= 2 ) {
    ScanSpeed = InitialScanSpeed;
  }

  // Detect whether Super 8 or Regular 8
  if (FilmTypeFrameCount >= 2 && LastFrameSteps > 280 && LastFrameSteps < 300 ) {
    DebugPrint("scan - R8 detected"); 
    MaxFrameSteps = 270; //R8
  }

  if (FilmTypeFrameCount >= 2 && LastFrameSteps > 300) {
    DebugPrint("scan - S8 detected"); 
    MaxFrameSteps = 290; //S8
  }

  // Push Phototransistor level unconditionally, we neccesarily are in Scan or SingleStep modes
  // JRE 4/8/22: SerialPrint used to inhibit regular writes to Serial while in debug mode
  SerialPrintInt(PT_SignalLevelRead);

  // --- Waiting for the green light from the Raspberry Pi, to move forward to the next frame-----
  /*
  if (Ic == 12) {
    DebugPrint("scan - RPi says GO for next frame"); 
    ScanSpeed = OriginalScanSpeed; 
    MinFrameSteps = OriginalMinFrameSteps; 
    FilmTypeFrameCount = FilmTypeFrameCount + 1;
  }
  */

  // ------------ Stretching film pickup wheel (C) ------
  TractionStopActive = digitalRead(TractionStopPin);

  if (!TractionStopActive && (CurrentTime - TractionStopLastWaitEventTime) >= TractionStopWaitingTime) {
    digitalWrite(MotorC_Stepper, LOW); 
    digitalWrite(MotorC_Stepper, HIGH); 
    TractionStopLastWaitEventTime = CurrentTime;
  }

  if (TractionStopActive) {
    TractionStopWaitingTime = TractionStopWaitingTime + 200;
  }

  if (TractionStopActive && TractionStopWaitingTime >= 12000) {
    TractionStopWaitingTime = 7000;
  }


  //-------------ScanFilm-----------
  if (Ic == 10) {   // UI Requesting to end current scan
    DebugPrint("scan - RPi asks to end scan"); 
    retvalue = false; 
    FrameDetected = false; 
    FilmTypeFrameCount = 0; 
    LastFrameSteps = 0; 
    MaxFrameSteps = 260; 
    TractionStopWaitingTime = 1000; 
    LastFrameSteps = 0;
  }
  else {
    check();
    if (!FrameDetected) {
      // ---- Speed on stepper motors  ------------------
      if ((CurrentTime - LastTime) >= ScanSpeed ) {  // Last time is set to zero, and never modified. What is the purpose? Somethign migth be mising
        for (int x = 0; x <= 0; x++) {    // Why only 4 times? Maybe because LastTime is not updated
          FrameStepsDone = FrameStepsDone + 1; 
          digitalWrite(MotorB_Stepper, LOW); 
          digitalWrite(MotorB_Stepper, HIGH); 
          check();
          if (FrameDetected) break;
        }
      }
    }
  }
  digitalWrite(MotorB_Stepper, LOW);

  if (FrameDetected) {
    FrameDetected = false;
    retvalue = false;
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
void sendexp() {

  Wire.write(Exp);
  Exp = 0;

}

boolean push(int IncomingIc) {
    boolean retvalue = false;
    if ((CommandQueue.in+1) % QUEUE_SIZE != CommandQueue.out) {
      CommandQueue.Data[CommandQueue.in++] = IncomingIc;
      CommandQueue.in %= QUEUE_SIZE;
      retvalue = true;
    }
    // else: Queue full: Should not happen. Not sure how this should be handled
    {
      static char debug[20];
      sprintf(debug,"In: %i",IncomingIc);
      DebugPrint(debug);
    }
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

void DebugPrint(const char * str) {
  static char PreviousDebug[128];
  static char AuxLine[128];
  static int CurrentRepetitions = 0;
  boolean GoPrint = true;
  
  if (!GlobalDebug) return;
  
  if (strcmp(str,PreviousDebug) == 0) {
    CurrentRepetitions++;
    if (CurrentRepetitions > MaxDebugRepetitions) GoPrint = false;
  }
  else {
    if (CurrentRepetitions > MaxDebugRepetitions) {
      sprintf(AuxLine,"Previous line repeated %u times",CurrentRepetitions-MaxDebugRepetitions);
      Serial.println(AuxLine);
    }
    CurrentRepetitions = 0;
  }
  strcpy(PreviousDebug, str);

  if (GoPrint) Serial.println(str);
}

void SerialPrintStr(const char * str) {
  if (!GlobalDebug) Serial.println(str);
}

void SerialPrintInt(int i) {
  if (!GlobalDebug) Serial.println(i);
}
