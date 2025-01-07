



// _37c




// ATTENTION - NOTE:
// Works only on Arduino Nano EVERY (since all digital pins support Interrupts)
// or on an Arduino model with AT LEAST 6 (better at least 9)
// pins that can be enabled for External Interrupts
// (if you change the Arduino model, it will be necessary to reassign the Pins based on the board used)

// GENERAL NOTE: all buttons are with INTERNAL PULL-UP,
// then, their read HIGH/LOW logical states in the code, are reversed with a NOT in order to execute commands on their PRESS.


/*
NOTE
******************************************************
Tested and full 100% working without bug and with fast response on breadboard without Raspberry connected and without Alt-Scann running
Needs Intensive revision and Intensive test when connection with Raspberry and Alt-Scann8 will be available
*/


// Library Import
#include "Wire.h"            // Required for using I2C. (Already included in the Arduino IDE)
#include "NoiascaHt16k33.h"  // Noiasca HT16K33 library - download from http://werner.rothschopf.net/
#include "DFRobot_MCP23017.h"

// Set I2C bus to use: Wire, Wire1, etc.  // DELETE - no longer needed
// #define WIRE Wire                      // DELETE - no longer needed

// MCP23017 GPIO EXPANDER I2C Address
DFRobot_MCP23017 mcp_1(Wire, 0x20);  // (A0+A1+A2=GND)
DFRobot_MCP23017 mcp_2(Wire, 0x21);  // (A0=VDD A1+A2=GND)
DFRobot_MCP23017 mcp_3(Wire, 0x22);  // (A0=GND A1=VDD A2=GND)
DFRobot_MCP23017 mcp_4(Wire, 0x23);  // (A0+A1=VDD A2=GND)

// HT16K33 Address are in Void Setup at Begin
/*
  display1.begin(0x70);  // Display1 = Framecounter
  display2.begin(0x71);  // Display2 = Timecode
  display3.begin(0x72);  // Display3 = Blu + Framerate Speed
  display4.begin(0x73);  // Display4 = Exposure + Red
*/
Noiasca_ht16k33_hw_7 display1 = Noiasca_ht16k33_hw_7();  // Display FrameCounter object for 7 segments, 8 digits
Noiasca_ht16k33_hw_7 display2 = Noiasca_ht16k33_hw_7();  // Display Timecode object for 7 segments, 8 digits
Noiasca_ht16k33_hw_7 display3 = Noiasca_ht16k33_hw_7();  // Display Encoder Blu an Digitize Framerate object for 7 segments, 8 digits
Noiasca_ht16k33_hw_7 display4 = Noiasca_ht16k33_hw_7();  // Display Encoder Exposure and Red object for 7 segments, 8 digits

// Pins connected on Arduino EVERY Board
// Rotary Encoder INTERRUPT Pins on Arduino EVERY Board
const byte ENCblu_pinCLK = 2;   // BLU - CLK - Pin A
const byte ENCblu_pinDATA = 3;  // BLU - DATA - Pin B

const byte ENCred_pinCLK = 4;   // RED - CLK - Pin A
const byte ENCred_pinDATA = 5;  // RED - DATA - Pin B

const byte ENCexposure_pinCLK = 6;   // EXPOSURE - CLK - Pin A
const byte ENCexposure_pinDATA = 7;  // EXPOSURE - DATA - Pin B



// blinkInhibitFOCUSLed VARIABLES for Button inhibition
bool blinkFlagAA = false;
byte blinkLastButtonStateAA;
byte blinkCountAA;
unsigned long blinkMillisAA;
const long blinkTimeAA = 100;
// byte lastAAbuttonState = HIGH; // DO NOT DELETE - in use in void blinkInhibitFOCUSLed on disabled strings
// byte AAledState = LOW;         // DO NOT DELETE - in use in void blinkInhibitFOCUSLed on disabled strings
// byte AAbuttonLOCK = 0;         // DO NOT DELETE - in use in void blinkInhibitFOCUSLed on disabled strings

// blinkInhibitREADYLed VARIABLES for Button inhibition
bool blinkFlagBB = false;
byte blinkLastButtonStateBB;
byte blinkCountBB;
unsigned long blinkMillisBB;
const long blinkTimeBB = 100;
// byte lastBBbuttonState = HIGH; // DO NOT DELETE - in use in void blinkInhibitREADYLed on disabled strings
// byte BBledState = LOW;         // DO NOT DELETE - in use in void blinkInhibitREADYLed on disabled strings
// byte BBbuttonLOCK = 0;         // DO NOT DELETE - in use in void blinkInhibitREADYLed on disabled strings


// BUTTONs and LEDs Pins
byte LED_AUTOwhiteStato = LOW;
byte BUTTON_AUTOwhiteStato = LOW;
const int BUTTON_AUTOwhiteDebounceTime = 50;
unsigned long BUTTON_AUTOwhiteLastDebounceTime = 0;
byte BUTTON_AUTOwhiteUltimaLettura = LOW;

byte LED_AUTOexposureStato = LOW;
byte BUTTON_AUTOexposureStato = LOW;
const int BUTTON_AUTOexposureDebounceTime = 50;
unsigned long BUTTON_AUTOexposureLastDebounceTime = 0;
byte BUTTON_AUTOexposureUltimaLettura = LOW;

// ENCODERs values
byte BLU_unit;
byte BLU_tens;
byte BLU_cent;

byte RED_unit;
byte RED_tens;
byte RED_cent;

byte EXPOSURE_unit;
byte EXPOSURE_tens;
byte EXPOSURE_cent;

unsigned int BLU_Valore = 22;      // Display BLU Default = 22 at Start
unsigned int RED_Valore = 22;      // Display RED Default = 22 at Start
unsigned int EXPOSURE_Valore = 0;  // Display EXPOSURE Default = 0 at Start
unsigned long ENCtime = 0;         // ENCtime
unsigned long DELAYtime = 0;       // Used at Turn ON before clear the Displays


/*pinMode MCP23017 parameter:
  
eGPA0  eGPA1  eGPA2  eGPA3  eGPA4  eGPA5  eGPA6  eGPA7  eGPA
  0      1      2      3      4      5      6      7
eGPB0  eGPB1  eGPB2  eGPB3  eGPB4  eGPB5  eGPB6  eGPB7  eGPB
  8      9      10     11     12     13     14     15
*/

// -----------ASSEGNAZIONE PROVVISORIA PER TEST SU BREADBOARD-----------
// -----------Riassegnare TUTTO dopo il routing del PCB in base all'instradamento delle tracce

// MCP23017 - Pin assignment
// mcp_1 GP_A (0 to 7) - MCP23017 0x20
const byte LED_STOP = 3;      // STOP Led
const byte LED_START = 4;     // START Led
const byte LED_FORWARD = 2;   // FORWARD Led
const byte LED_BACKWARD = 5;  // BACKWARD Led
const byte LED_FF = 6;        // FAST-FORWARD Led
const byte LED_RW = 7;        // REWIND Led
// const byte ;
// const byte ;

// mcp_1 GP_B (08 to 15) - MCP23017 0x20
const byte RPI_PinchRollerDetect = 8;   // Detection from RPI
const byte RPI_AltScannDetect = 9;      // Detection from RPI
const byte RPI_ExternalHddDetect = 10;  // Detection from RPI
const byte LED_RPI_PinchRollerDetect = 11;
const byte LED_RPI_AltScannDetect = 12;
const byte LED_RPI_ExternalHddDetect = 13;
const byte BUTTON_FF = 14;  // FAST_FORWARD Button
const byte BUTTON_RW = 15;  // REWIND Button

// mcp_2 GP_A (0 to 7)- MCP23017 0x21
const byte ENCexposure_pinSW = 7;  // EXPOSURE - SWITCH to Default value
const byte LED_AUTOexposure = 6;
const byte BUTTON_AUTOexposure = 5;
const byte ENCred_pinSW = 4;  // RED - SWITCH to Default value
const byte LED_AUTOwhite = 3;
const byte BUTTON_AUTOwhite = 2;
const byte ENCblu_pinSW = 1;  // BLU - SWITCH to Default value
// const byte ;

// mcp_2 GP_B (8 to 15) - MCP23017 0x21
const byte BUTTON_STOP = 10;      // STOP Button
const byte BUTTON_START = 12;     // START Button
const byte BUTTON_FORWARD = 11;   // FORWARD Button
const byte BUTTON_BACKWARD = 13;  // BACKWARD Button
// const byte ;
// const byte ;
// const byte ;
// const byte ;

// mcp_3 GP_A (0 to 7)- MCP23017 0x22
const byte LED_16fps = 7;  //Indica conteggio visualizzato a 16 fps
const byte LED_18fps = 6;  //Indica conteggio visualizzato a 18 fps
const byte LED_24fps = 5;  //Indica conteggio visualizzato a 24 fps
const byte LED_25fps = 4;  //Indica conteggio visualizzato a 25 fps
// const byte ;
// const byte ;
// const byte ;
// const byte ;

// mcp_3 GP_B (8 to 15) - MCP23017 0x22
const byte LED_Super8Format = 8;       // Super8 Select LED
const byte LED_Normal8Format = 9;      // Normal8 Select LED
const byte Button_Super8Format = 10;   // Super8 Select Button
const byte Button_Normal8Format = 11;  // Normal8 Select Button
const byte Button_FocusON = 12;        // Focus ON-OFF Button
const byte LED_FocusON = 13;           // Focus ON-OFF LED indicator
const byte LED_ReadyRed = 14;          // LED Ready Red Blinks or stay Fixed ON when something is inhibited or some requirements are missing to Start Digitizing
const byte LED_ReadyGreen = 15;        // LED Ready Green stays ON when all requirements to Start Digitizing are OK
// const byte ;


// mcp_4 GP_A (0 to 7) - MCP23017 0x23
// const byte ;
// const byte ;
// const byte ;
// const byte ;
// const byte ;
// const byte ;
// const byte ;
// const byte ;

// mcp_4 GP_B (8 to 15) - MCP23017 0x23
const byte ButtonFpsSelect = 8;     // INPUT - Select Button per impostare fps da visualizare
const byte ButtonCounterReset = 9;  // INPUT - Pulsante per Resettare il Counter a 0:00:00:00
const byte DownInputPin = 10;       // INPUT Pin su Fronte Alto INVERTITO conta all'Indietro - Se si utlizza un pulsante durante i test, PREMUTO conta all'Indietro. - leggi sotto. NON NECESSARIO in ALT-Scann8, ma predisposto...
const byte UpInputPin = 11;         // INPUT Pin su Fronte Alto conta in Avanti - Se si utlizza un pulsante durante i test, PREMUTO conta in Avanti. - leggi sotto
// const byte ;
// const byte ;
// const byte ;
// const byte ;

// MOTOR CONTROL related
byte StopLOCK = 0;   // se ==1, impossibile attivare altri pulsanti DIVERSI da STOP...
                     // ....mentre è già attiva un altra funzione
byte StartLOCK = 0;  // Se ==0 la macchina NON è in Start, se ==1 la macchina è in Start (Digitizing)

// COUNTER related
byte eventLastStateUP;    //  Mantiene conservato l'ultimo stato del Fronte del segnale sul Pin UpInputPin (Rising o Falling) per consentire la condizione che determina l'AVANTI del counter SOLO al cambio di evento (Fronte da Basso ad Alto)
byte eventLastStateDOWN;  //  Mantiene conservato l'ultimo stato del Fronte del segnale sul Pin DownInputPin (Rising o Falling) per consentire la condizione che determina l'INDIETRO del counter SOLO al cambio di evento (Fronte da Alto a Basso)

// LED Counter ARRAY
const byte LED_fpsTOTALI = 4;  // numero dei LED coinvolti - necessario per lo Switch Fps
const byte LEDfpsPinArray[LED_fpsTOTALI] = {
  LED_16fps,
  LED_18fps,
  LED_24fps,
  LED_25fps
};

const int SwitchFpsDurataDebounche = 50;           // millisecondi (minimale antirimbalzo Software) su Pulsante Switch dei LED
const int SwitchFpsDurataMostra = 300;             // durata in millisecondi della modalità selezionata mostrata sul Display allo Switch del conteggio
unsigned long SwitchFpsUltimoTimeCambioStato = 0;  // usata per lo Switch dei LED (e quindi del Counter)

byte SwitchFpsUltimoStatoButton = HIGH;
byte SwitchFpsStatoMostra = 0;
// ...byte SwitchFpsStatoMostra: questa variabile...
// ...diventa ==1 quando il Display dalla visualizzazione della Modalità selezionata...
// ...passa alla visualizzazione del Conteggio.
// ...viene reimpostata ==0 quando si preme nuovamente il Pulsante ButtonFpsSelect

byte LEDfpsIndex = 2;  // Accende per Default il LED_24 all'avvio


// VARIABILI PER IL COUNTER
long frameNumber = 0;  // Conteggio di TUTTI i Frame - I frame saranno convertiti in Timecode
// assolve la funzione di "Clock" di riferimento per tenere in sync fra di loro tutti i contatori
// 6479982 = 99h:59m:59s:00f (per test)

byte framerate;  // framerate impostabili = 16, 18, 24, 25

long frameUnit;
long frameDec;
long secondiUnit;
long secondiDec;
long minutiUnit;
long minutiDec;
long oreUnit;
long oreDec;

long timecodeNumber;


// VARIABILI per Super8 - Normal8 Selector Switch
byte FormatSelectLOCK = 0;        // 0==Blink at Start; 1==Super8 or Normal8 selected
byte BlinkFormatLedState = HIGH;  // Alternate HIGH LOW for Blinking LED Format at Start - HIGH At Start

const int Format_Bink_Interval = 700;         // Blink LED Format interval if NO Format is selected
unsigned long FormatBlinkPreviousMillis = 0;  // will store last time LED Format was updated. Used at Start when NO Format is selected


// FocusON VARIABILI
byte LED_FocusStato = LOW;
byte Button_FocusStato = LOW;
byte FocusLOCK = 0;

int Button_FocusStatoDebounceTime = 50;
unsigned long Button_FocusONLastDebounceTime = 0;
byte Button_FocusStatoUltimaFocusONLettura = LOW;


// READY, BUSY, RPI Detect Staus and LED_Ready behavior VARIABLEs
unsigned long previousBlinkTimeLED_RPI_PinchRollerDetect = 0;  // last time Blink LED was updated
unsigned long previousBlinkTimeLED_RPI_AltScannDetect = 0;
unsigned long previousBlinkTimeLED_RPI_ExternalHddDetect = 0;
unsigned long previousBlinkTimeLED_ReadyRed = 0;
unsigned long previousBlinkTimeLED_START = 0;
const long BlinkTimeLED_RPI_Detect = 350;  // milliseconds Blink duration
byte LED_RPI_PinchRollerDetectState = LOW;
byte LED_RPI_AltScannDetectState = LOW;
byte LED_RPI_ExternalHddDetectState = LOW;
byte LED_ReadyRedState = LOW;
byte LED_STARTState = LOW;
byte Ready_LOCK = 0;  // Ready staus
byte Busy_LOCK = 0;   // Busy staus
byte RPI_LOCK = 0;    // RPI requirements staus



//###################################################################
//
//	Void_Setup - BEGIN
//
//###################################################################

void setup() {

  // delay (2000);  // Panel wait for 2 seconds before full Light ON

  // Serial.begin(115200);  // Only for some test

  //*******************************************************************
  //	Void_Setup - MCP23017 Expander
  //*******************************************************************

  // MCP23017 - Pin Parameter
  // Parameter mode can be: INPUT, OUTPUT, INPUT_PULLUP
  // mcp_1
  mcp_1.pinMode(LED_STOP, OUTPUT);
  mcp_1.pinMode(LED_START, OUTPUT);
  mcp_1.pinMode(LED_FORWARD, OUTPUT);
  mcp_1.pinMode(LED_BACKWARD, OUTPUT);
  mcp_1.pinMode(LED_FF, OUTPUT);
  mcp_1.pinMode(LED_RW, OUTPUT);

  mcp_1.pinMode(BUTTON_FF, INPUT_PULLUP);
  mcp_1.pinMode(BUTTON_RW, INPUT_PULLUP);

  mcp_2.pinMode(BUTTON_STOP, INPUT_PULLUP);
  mcp_2.pinMode(BUTTON_START, INPUT_PULLUP);
  mcp_2.pinMode(BUTTON_FORWARD, INPUT_PULLUP);
  mcp_2.pinMode(BUTTON_BACKWARD, INPUT_PULLUP);

}  // CHIUDE il void Setup


//###################################################################
//
//	Void_LOOP - BEGIN
//
//###################################################################

void loop() {

  //###################################################################
  //
  //	Void_LOOP - MCP23017 Expander
  //
  //###################################################################

  // Note: MCP23017 has internal Pull-Up,
  // Using Pull-Up and inverting the button reading logic with a "not",
  // action is executed at the PRESS of the button as using Pull-Down
  // all these conditions are necessary to prevent nothing unwanted from happening if you press multiple buttons at the same time
  if (!mcp_2.digitalRead(BUTTON_STOP) == 1 && mcp_2.digitalRead(BUTTON_START) == 1 && mcp_2.digitalRead(BUTTON_FORWARD) == 1 && mcp_2.digitalRead(BUTTON_BACKWARD) == 1 && mcp_1.digitalRead(BUTTON_FF) == 1 && mcp_1.digitalRead(BUTTON_RW) == 1) {  // INVERTED logic as using Pull-Down
    mcp_1.digitalWrite(LED_STOP, 1);
    mcp_1.digitalWrite(LED_START, 0);
    mcp_1.digitalWrite(LED_FORWARD, 0);
    mcp_1.digitalWrite(LED_BACKWARD, 0);
    mcp_1.digitalWrite(LED_FF, 0);
    mcp_1.digitalWrite(LED_RW, 0);
    // ATTENZIONE QUESTO DELAY ANDREBBE SOSTITUITO CON millis se si desidera usarlo
    // StopLOCK = 1;  // momentaneamente resta bloccata la condizione di premere un altro pulsante
    // delay(500);    // impedisce di attivare immediatamente un altro Pulsante relativo al Motore
    StopLOCK = 0;
    StartLOCK = 0;
  }

  // Start Button
  if (!mcp_2.digitalRead(BUTTON_START) == 1 && FormatSelectLOCK == 1 && StopLOCK == 0 && mcp_2.digitalRead(BUTTON_STOP) == 1) {  // INVERTED logic as using Pull-Down
    StopLOCK = 1;
    StartLOCK = 1;
    mcp_1.digitalWrite(LED_STOP, 0);
    mcp_1.digitalWrite(LED_START, 1);
  }


  // Forward Button
  if (!mcp_2.digitalRead(BUTTON_FORWARD) == 1 && StopLOCK == 0 && mcp_2.digitalRead(BUTTON_STOP) == 1) {  // INVERTED logic as using Pull-Down
    StopLOCK = 1;
    mcp_1.digitalWrite(LED_STOP, 0);
    mcp_1.digitalWrite(LED_FORWARD, 1);
  }


  // Backward Button
  if (!mcp_2.digitalRead(BUTTON_BACKWARD) == 1 && StopLOCK == 0 && mcp_2.digitalRead(BUTTON_STOP) == 1) {  // INVERTED logic as using Pull-Down
    StopLOCK = 1;
    mcp_1.digitalWrite(LED_STOP, 0);
    mcp_1.digitalWrite(LED_BACKWARD, 1);
  }

  // FF Fast Forward Button
  if (!mcp_1.digitalRead(BUTTON_FF) == 1 && StopLOCK == 0 && mcp_2.digitalRead(BUTTON_STOP) == 1) {  // INVERTED logic as using Pull-Down
    StopLOCK = 1;
    mcp_1.digitalWrite(LED_STOP, 0);
    mcp_1.digitalWrite(LED_FF, 1);
  }  // LED_RPI_PinchRollerDetect will Blink briefly to remember that FF and RW are not allowed if Pinch-Roller is Inserted

  // RW Rewind Button
  if (!mcp_1.digitalRead(BUTTON_RW) == 1 && StopLOCK == 0 && mcp_2.digitalRead(BUTTON_STOP) == 1) {  // INVERTED logic as using Pull-Down
    StopLOCK = 1;
    mcp_1.digitalWrite(LED_STOP, 0);
    mcp_1.digitalWrite(LED_RW, 1);
  }  // LED_RPI_PinchRollerDetect will Blink briefly to remember that FF and RW are not allowed if Pinch-Roller is Inserted

}  // CHIUDE il Void Loop





//************************************************
// MDS 18/07/2020 - Timecode and Counter
//************************************************

//************************************************
// MDS 12/02/2024 - Encoders
//************************************************

//************************************************
// MDS 30/05/2024 - Buttons and Logic
//************************************************

//***
