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
*/

#include <Wire.h>
#include <stdio.h>

const int PHOTODETECT = A0; // Analog pin 0 perf

int Pulse = LOW;
int Ic; // Stores I2C command from Raspberry PI --- ScanFilm=10 / UnlockReels mode=20 / Slow Forward movie=30 / One step frame=40 / Rewind movie=60 / Fast Forward movie=80

//------------ Stepper motors control ----------------
const int stepSpoleA = 2;   // Stepper motor film feed
const int neutralA = 3;     // neutral position
const int stepKapstanB = 4; // Stepper motor capstan propulsion
const int neutralB = 5;     // neutral position
const int stepSpoleC = 6;   // Stepper motor film winding
const int neutralC = 7;     // neutral position
const int dirSpoleA = 8;    // direction
const int dirKapstanB = 9;  // direction
const int dirSpoleC = 10;   // direction


const int inDra = 12; // Traction stop
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
  Sts_SingleStep
}
ScanState=Sts_Idle;

int okFrame = LOW;  // Used for frame detection, in play ond single step modes
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

int wave = 0;
int waveC = 0;
int waveCS = 0;


// ----- Important setting, may need to be adjusted ------

int Wled = 250;      // Brightness UV led, may need to be changed depending on LED
int sped = 1000 ;     // speed stepper scann Play
int spedS = 15000;    // Play Slow before trig
int Ssped = 4000;    // sped Rewind movie
int perfLevel = 250; // detector pulse level
int Hlevel = 500;    // detector pulse high level, clear film and low contrast film perforation
int WstepV = 176;     // Minimum number of steps, before new frame is exposed
int WstepS = 281;    // default setting before sensing Super 8 or Regular 8

// -------------------------------------------------------

const int perfLevelOrg = perfLevel; // stores value for resetting perfLevel
int Paus = LOW;
int Wstep = 0;  // Cunt steps
int spedV = sped; // restoration original value
int WstepVR = WstepV; // restoration original value
int typeF = 0;  // counts to 2 before S8 / R8 is determined
int WstepLast = 0; // stores number of steps

int inDraState = HIGH;
int inDraCount = 2;

unsigned long inDraTime = 2000;  // winding wheel C Start value, changed by program.
unsigned long time;
unsigned long LastTime = 0;
unsigned long LastTimeDra = 0;

int Exp = 0;    // 11 is exposure I2C

int measureP;   // Level out signal phototransistor detection

// JRE - Support data variables
#define QUEUE_SIZE 20
volatile struct {
  int Data[QUEUE_SIZE];
  int in;
  int out;
} CommandQueue;
boolean GlobalDebug = true;
int MaxDebugRepetitions = 3;

void setup() {

  Serial.begin(9600);  // Used to be 9600
  Wire.begin(16);  // join I2c bus with address #16
  Wire.onReceive(receiveEvent); // register event
  Wire.onRequest(sendexp);


  //--- set pinMode Stepper motors -----
  pinMode(stepSpoleA, OUTPUT);
  pinMode(dirSpoleA, OUTPUT);
  pinMode(stepKapstanB, OUTPUT);
  pinMode(dirKapstanB, OUTPUT);
  pinMode(stepSpoleC, OUTPUT);
  pinMode(dirSpoleC, OUTPUT);
  pinMode(inDra, INPUT);
  pinMode(neutralA, OUTPUT);
  pinMode(neutralB, OUTPUT);
  pinMode(neutralC, OUTPUT);
  //---------------------------
  pinMode(A1, OUTPUT); // Green LED
  pinMode(A2, OUTPUT); // beep
  pinMode(11, OUTPUT); // UV Led


  // neutral position
  digitalWrite(neutralA, HIGH);


  // set direction on stepper motors
  digitalWrite(dirSpoleA, LOW);
  digitalWrite(dirKapstanB, LOW);


  analogWrite(11, Wled); // Turn on UV LED


  digitalWrite(stepSpoleA, LOW);
  digitalWrite(stepKapstanB, LOW);
  digitalWrite(stepSpoleC, LOW);

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
    if (!GlobalDebug) {
      int measureP = analogRead(PHOTODETECT);
      Serial.println(measureP); // can be read in Arduino IDE - Serial plotter
    }

    if (ScanState == Sts_Idle) {
      // Set default state and direction of motors B and C (disabled, clockwise)
      // In the original main loop this was done when the Ic commamnd was NOT Single Step (49). Why???
      if (Ic != 40){  // In case we need the exact behavior of original code
        digitalWrite(stepKapstanB, LOW); 
        digitalWrite(stepSpoleC, LOW); 
        digitalWrite(dirSpoleC, HIGH); 
        digitalWrite(dirKapstanB, HIGH);
      }
  
      // Next does not make much sense, but this is what the original code does.
      if (ReelsUnlocked) {
        digitalWrite(neutralB, HIGH);  
        digitalWrite(neutralC, HIGH); 
      }
      else {
        digitalWrite(neutralB, LOW);  
        digitalWrite(neutralC, LOW); 
      }
    }
        
    switch (ScanState) {
      case Sts_Idle:
        switch (Ic) {
          case 10:
            DebugPrint("Idle -> Scan"); 
            ScanState = Sts_Scan;
            delay(250); 
            WstepV = 5; 
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
            WstepV = 100; 
            delay(50);
            break;
          case 60:
            DebugPrint("Idle -> Rewind"); 
            ScanState = Sts_Rewind;
            delay (500); 
            digitalWrite(neutralA, LOW); 
            digitalWrite(neutralB, HIGH);  
            digitalWrite(neutralC, HIGH); 
            tone(A2, 2000, 200); 
            delay (300); 
            tone(A2, 2000, 200); 
            Ssped = 4000;
            break;
          case 80:
            DebugPrint("Idle -> FastForward"); 
            ScanState = Sts_FastForward;
            delay (500); 
            digitalWrite(neutralA, HIGH); 
            digitalWrite(neutralB, HIGH);  
            digitalWrite(neutralC, LOW); 
            tone(A2, 2000, 200); 
            delay (300); 
            tone(A2, 2000, 200); 
            Ssped = 4000;
            break;
        }
        break;
      case Sts_Scan:
        if (scan(Ic)) {
          if (inDraState == LOW) { // Wind outgoing film on reel C
            delay (5); 
            digitalWrite(stepSpoleC, HIGH);
          }
          // Advance to next frame ? (to be checked)
          /* does not seem to be required (loop -> scan -> loop -> scan ...). Not sure how it works. Thanks to extensive use of global variables maybe
          digitalWrite(stepKapstanB, LOW); 
          delay(20); 
          digitalWrite(stepKapstanB, HIGH); 
          delay (20); 
          digitalWrite(stepKapstanB, LOW);
          */
          DebugPrint("Staying in Scan state"); 
        }
        else {
          DebugPrint("Exiting Scan state"); 
          inDraState = digitalRead(inDra);  // Get status of traction stop switch on exiting scan state
          ScanState = Sts_Idle; // Exit scan loop
        }
        break;
      case Sts_UnlockReels:
        if (Ic == 20) { //request to lock reels again
          ReelsUnlocked = false;
          digitalWrite(neutralB, LOW); 
          digitalWrite(neutralC, LOW);
          ScanState = Sts_Idle;
          DebugPrint("Exiting Unlock Reels state"); 
        }
        else if (not ReelsUnlocked){
          ReelsUnlocked = true;
          digitalWrite(neutralB, HIGH); 
          digitalWrite(neutralC, HIGH);
        }
        DebugPrint("Staying in unlock reels state"); 
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
          if (inDraState == LOW) {
            inDraCount = inDraCount + 1; 
            delay(10); 
            digitalWrite(stepSpoleC, HIGH);
          }
          digitalWrite(stepKapstanB, HIGH);
          DebugPrint("Staying in slow forward state"); 
        }
        break;
      case Sts_SingleStep:
        if (!scan(Ic)) {
          DebugPrint("Exiting single step state"); 
          ScanState = Sts_Idle;
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
    digitalWrite(neutralA, HIGH);
    delay (100);
  }
  else {
    digitalWrite(stepSpoleA, HIGH); 
    delayMicroseconds(Ssped); 
    digitalWrite(stepSpoleA, LOW);
    if (Ssped >= 250) {
      Ssped = Ssped - 2;
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
    digitalWrite(neutralC, HIGH); 
    delay (100);
  }
  else {
    digitalWrite(stepSpoleC, HIGH); 
    delayMicroseconds(Ssped); 
    digitalWrite(stepSpoleC, LOW);
  }
    if (Ssped >= 250) {
      Ssped = Ssped - 2;
    }
  return(retvalue);
}


// ------------- is the film perforation in position to take picture? ---------------
// Returns false if status should change to idle
boolean check() {
  boolean retvalue = true;

  measureP = analogRead(PHOTODETECT);

  DebugPrint("check 0"); 
  if (measureP >= perfLevel) {  // perfLevel - Minimum level at which we can think a perforation is detected
    wave = measureP;
  }

  if (measureP >= Hlevel) {   // Adjust perforation levels based on readings - TBC
    perfLevel = Hlevel;
  }
  else if (measureP < 200) {
    perfLevel = perfLevelOrg;
  }

  if (measureP < perfLevel) {
    wave = 0;
  }

  // ------------- Frame detection ----
  if (wave >= perfLevel && Pulse == LOW && Wstep >= WstepV ) {
    DebugPrint("check 1"); 
    retvalue = false;
    Pulse = HIGH; 
    okFrame = HIGH; 
    WstepLast = Wstep; 
    Wstep = 0; 
    analogWrite (A1, 255); 
    Exp = 11; 
    digitalWrite(13, HIGH);
  }
  else if (wave == 0 && Pulse == HIGH) {
    DebugPrint("check 2"); 
    Pulse = LOW; 
    analogWrite(A1, 0); 
    Ic = 0;
  }

  // -- One step frame --
  if (ScanState == Sts_SingleStep && okFrame == HIGH ) {
    DebugPrint("check 3"); 
    retvalue = false;
    Exp = 0; 
    okFrame = LOW; 
    tone(A2, 2000, 35); 
  }
  return(retvalue);
}


// ----- This is the function to "ScanFilm" -----
// Returns false when done
boolean scan(int Ic) {
  boolean retvalue = true;
  
  DebugPrint("scan 1"); 
  
  Wire.begin(16);

  analogWrite(11, Wled);

  measureP = analogRead(PHOTODETECT);
  unsigned long time = micros();

  inDraState = digitalRead(inDra);

  if (measureP >= perfLevel) {
    wave = measureP;
  }

  if (measureP >= Hlevel) {
    perfLevel = Hlevel;
  }

  else if (measureP < 200) {
    perfLevel = perfLevelOrg;
  }

  if (measureP < perfLevel) {
    wave = 0;
  }

  if (Wstep >= WstepS && typeF >= 2 ) {
    sped = spedS;
  }

  // Detect whether Super 8 or Regular 8
  if (typeF >= 2 && WstepLast > 280 && WstepLast < 300 ) {
    WstepS = 270; //R8
  }

  if (typeF >= 2 && WstepLast > 300) {
    WstepS = 290; //S8
  }
  DebugPrint("scan 2"); 

  // Push Phototransistor level unconditionally, we neccesarily are in Scan or SingleStep modes
  // JRE 4/8/22: Check first if we are in debug mode: If yes, serial i/f is dedicated for it
  if (!GlobalDebug) Serial.println(measureP);

  // --- Waiting for the green light from the Raspberry Pi, to pull forward to the next frame-----
  if (Ic == 12) {
    DebugPrint("scan Ic 12"); 
    sped = spedV; 
    WstepV = WstepVR; 
    typeF = typeF + 1;
  }
  DebugPrint("scan 3"); 

  // ------------ Stretching film pickup wheel (C) ------
  inDraState = digitalRead(inDra);

  if (inDraState == LOW && (time - LastTimeDra) >= inDraTime) {
    DebugPrint("scan reel C move"); 
    digitalWrite(stepSpoleC, LOW); 
    digitalWrite(stepSpoleC, HIGH); 
    LastTimeDra = time;
  }

  if (inDraState == HIGH) {
    inDraTime = inDraTime + 200;
  }

  if (inDraState == HIGH && inDraTime >= 12000) {
    inDraTime = 7000;
  }

  DebugPrint("scan 4"); 

  //-------------ScanFilm-----------
  if (Ic == 10) {   // UI Requesting to end current scan
    DebugPrint("scan 5 - exiting"); 
    retvalue = false; 
    okFrame = LOW; 
    typeF = 0; 
    WstepLast = 0; 
    WstepS = 260; 
    inDraTime = 1000; 
    WstepLast = 0;
  }
  else {
    DebugPrint("scan 6"); 
    if (retvalue) retvalue = check();
    DebugPrint("scan 7"); 
    
    // ---- Speed on stepper motors  ------------------
    if ((time - LastTime) >= sped ) {
      DebugPrint("scan move capstan"); 
      for (int x = 0; x <= 3; x++) {
        Wstep = Wstep + 1; 
        digitalWrite(stepKapstanB, LOW); 
        digitalWrite(stepKapstanB, HIGH); 
        if (retvalue) {
          retvalue = check();
          if (!retvalue) break;
        }
      }
    }
    DebugPrint("scan 8 - exiting"); 
  
    if (!retvalue) digitalWrite(stepKapstanB, LOW);
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
