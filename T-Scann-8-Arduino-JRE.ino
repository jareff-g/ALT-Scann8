/*    T-Scann8 Super8/Regular8 Scanner ver 1.61
      -UV led version-
      © Torulf Holmström Sweden 2022
      project page
      tscann8.torulf.com

      1 Aug 2022 - JRE - Added fast forward function
*/

#include <Wire.h>


const int PHOTODETECT = A0; // Analog pin 0 perf

int Pulse = LOW;
int Ic; // Stores I2C command from Raspberry PI --- Play=10 / Free mode=20 / Rewind movie=60 / Fast Forward movie=80 / One step frame=40 / Forward movie=30

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
int Play = LOW;
int Free = LOW;
int Spola = LOW;
int Fram = LOW;
int Frame = LOW;

int oneFrame = LOW;
int okFrame = LOW;
int lastPlay = LOW;
int lastFree = LOW;
int lastSpola = LOW;
int lastFram = LOW;
int lastFrame = LOW;
int LastWstep = 0;

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



void setup() {

  Serial.begin(9600);
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


}
void loop() {
  while (1) {
    Wire.begin(16);



    int measureP = analogRead(PHOTODETECT);

    // can be read in Arduino IDE - Serial plotter
    Serial.println(measureP);


    lastPlay = Play;

    //-------------PLAY-----------
    if (Ic == 10 && lastPlay == LOW) {
      Play = HIGH; delay(250); WstepV = 5; tone(A2, 2000, 50); Ic = 0; scan();
    }


    inDraState = digitalRead(inDra);

    //---------- step one frame ---------
    if (Ic == 40) {
      Play = HIGH; oneFrame = HIGH; Ic = 0; WstepV = 100; delay(50); scan();

    }


    else
    {
      digitalWrite(stepKapstanB, LOW); digitalWrite(stepSpoleC, LOW); digitalWrite(dirSpoleC, HIGH); digitalWrite(dirKapstanB, HIGH);
    }



    //-------------RUN forward film-----------

    lastFram = Fram;

    if (Ic == 30 && lastFram == LOW) {
      Fram = HIGH; delay(50); Ic = 0;
    }

    if (Ic == 30 && lastFram == HIGH) {
      Fram = LOW; delay(50); Ic = 0;
    }

    if (Fram == HIGH && inDraState == LOW) {
      inDraCount = inDraCount + 1; delay(10); digitalWrite(stepSpoleC, HIGH);
    }

    if (Fram == HIGH) {
      digitalWrite(stepKapstanB, HIGH);
    }


    if (Ic == 30 && lastFram == HIGH) {
      Fram = LOW; delay(50); Ic = 0;
    }



    //------------- Free mode -----------

    lastFree = Free;

    if (Ic == 20 && lastFree == LOW) {
      Free = HIGH; delay(50); Ic = 0;
    }

    if (Ic == 20 && lastFree == HIGH) {
      Free = LOW; delay(50); Ic = 0;
    }

    if (Free == HIGH) {
      digitalWrite(neutralB, HIGH); digitalWrite(neutralC, HIGH);

    }



    if (Free == LOW) {
      digitalWrite(neutralB, LOW); digitalWrite(neutralC, LOW);


    }


    //-------------rewind the movie -----------

    lastSpola = Spola;

    if (Ic == 60 && lastSpola == LOW && lastPlay == LOW && lastPlay == LOW && lastFram == LOW ) {
      Spola = HIGH; delay (500); digitalWrite(neutralA, LOW); digitalWrite(neutralB, HIGH);  digitalWrite(neutralC, HIGH); tone(A2, 2000, 200); delay (300); tone(A2, 2000, 200); Ssped = 4000; Ic = 0;  backfilm();
    }

    //-------------fast forward the movie -----------

    lastSpola = Spola;

    if (Ic == 80 && lastSpola == LOW && lastPlay == LOW && lastPlay == LOW && lastFram == LOW ) {
      Spola = HIGH; delay (500); digitalWrite(neutralA, HIGH); digitalWrite(neutralB, HIGH);  digitalWrite(neutralC, LOW); tone(A2, 2000, 200); delay (300); tone(A2, 2000, 200); Ssped = 4000; Ic = 0;  fastforwardfilm();
    }



    // ------------ Stretching film pickup wheel (C)-------

    if (Play == HIGH && inDraState == LOW) {
      delay (5); digitalWrite(stepSpoleC, HIGH);
    }




    // ----- Speed on stepper motors ------------------

    delayMicroseconds(1);

    // org 5

    if (Play == HIGH) {
      digitalWrite(stepKapstanB, LOW); delay(20); digitalWrite(stepKapstanB, HIGH); delay (20); digitalWrite(stepKapstanB, LOW);
    }


  }
}



// ------ rewind the movie ------
void backfilm() {
  Wire.begin(16);


  lastSpola = Spola;
  if (Ic == 60 && lastSpola == HIGH) {
    Spola = LOW; Ic = 0;
  }

  lastSpola = Spola;
  if (Ic == 60 && lastSpola == LOW) {
    Spola = LOW; digitalWrite(neutralA, HIGH); Ic = 0; delay (100); return;
  }



  digitalWrite(stepSpoleA, HIGH); delayMicroseconds(Ssped); digitalWrite(stepSpoleA, LOW);


  if (Ssped >= 250) {
    Ssped = Ssped - 2;
  }



  backfilm();
}

// ------ fast forward the movie ------
void fastforwardfilm() {
  Wire.begin(16);  // join I2c bus with address #16


  lastSpola = Spola;
  if (Ic == 80 && lastSpola == HIGH) {
    Spola = LOW; Ic = 0;
  }

  lastSpola = Spola;
  if (Ic == 80 && lastSpola == LOW) {
    Spola = LOW; digitalWrite(neutralC, HIGH); Ic = 0; delay (100); return;
  }



  digitalWrite(stepSpoleC, HIGH); delayMicroseconds(Ssped); digitalWrite(stepSpoleC, LOW);


  if (Ssped >= 250) {
    Ssped = Ssped - 2;
  }



  fastforwardfilm();
}



// ------------- is the film perforation in position to take picture? ---------------
void check() {

  measureP = analogRead(PHOTODETECT);

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

  // ------------- Frame detection ----
  if (wave >= perfLevel && Play == HIGH && Pulse == LOW && Wstep >= WstepV ) {
    Pulse = HIGH; okFrame = HIGH; WstepLast = Wstep; Wstep = 0; Play = LOW; analogWrite (A1, 255); Ic = 0;  Exp = 11; digitalWrite(13, HIGH);
  }

  else if (wave == 0 && Pulse == HIGH && Play == HIGH) {
    Pulse = LOW; analogWrite(A1, 0); Ic = 0;
  }

  // -- One step frame --
  if (ScanState == Sts_SingleStep && okFrame == HIGH ) {
    Exp = 0; 
    okFrame = LOW; 
    tone(A2, 2000, 35);
  }
  return;
}


// ----- This is the function to "PLAY / SCAN" -----
void scan() {

  while (1) {


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


    if (Play == HIGH) {
      Serial.println(measureP);
    }




    // --- Waiting for the green light from the Raspberry Pi, to pull forward to the next frame-----
    if (Ic == 12) {
      sped = spedV; Play = HIGH; WstepV = WstepVR; typeF = typeF + 1;
    }


    // ------------ Stretching film pickup wheel (C) ------

    inDraState = digitalRead(inDra);



    if (Play == HIGH && inDraState == LOW && (time - LastTimeDra) >= inDraTime) {
      digitalWrite(stepSpoleC, LOW); digitalWrite(stepSpoleC, HIGH); LastTimeDra = time;
    }

    if (Play == HIGH && inDraState == HIGH) {
      inDraTime = inDraTime + 200;
    }

    if (Play == HIGH && inDraState == HIGH && inDraTime >= 12000) {
      inDraTime = 7000;
    }



    lastPlay = Play;

    //-------------PLAY-----------
    if (Ic == 10 && lastPlay == HIGH) {
      Play = LOW; okFrame = LOW; Ic = 0; typeF = 0; WstepLast = 0; WstepS = 260; inDraTime = 1000; WstepLast = 0; loop();
    }


    check();
    // ---- Speed on stepper motors  ------------------

    if (Play == HIGH && (time - LastTime) >= sped ) {

      for (int x = 0; x <= 3; x++) {
        Wstep = Wstep + 1; digitalWrite(stepKapstanB, LOW); digitalWrite(stepKapstanB, HIGH); check();
      }
    }

    digitalWrite(stepKapstanB, LOW);
  }
}

// ---- Receive I2C command from Raspberry PI, play... and more ------------
void receiveEvent() {

  Ic = Wire.read();


  return Ic;
}

// -- Sending I2C command to Raspberry PI, take picture now -------
void sendexp() {

  Wire.write(Exp);
  Exp = 0;

}
