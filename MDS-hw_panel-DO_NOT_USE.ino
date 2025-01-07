



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

// ******************************************
// Code copied from ALT-Scann8-Controller.ino
// ******************************************
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

byte BufferForRPi[9];  // 9 byte array to send data to Raspberry Pi over I2C bus

// ******************************************
// End of ALT-Scann8 copied code
// ******************************************

// ******************************************
// New code to support hw panel in ALT-Scann8
// ******************************************
#define RPI_I2C_ADD 17  // I2B bus address to communicate with RPi
#define ALT_SCAN_8_START 1
#define ALT_SCAN_8_STOP 2
#define ALT_SCAN_8_FORWARD 3
#define ALT_SCAN_8_BACKWARD 4
#define ALT_SCAN_8_FF 5
#define ALT_SCAN_8_RW 6

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


// ******************************************
// End of new code to support hw panel in ALT-Scann8
// ******************************************

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

  //*******************************************************************
  // 2024/12/29 - Code copied from ALT-Scann8-Controller.ino
  // Initialize I2C bus, using different address in case commo bus on
  // Raspberry Pi is reused
  //*******************************************************************
  // Possible serial speeds: 1200, 2400, 4800, 9600, 19200, 38400, 57600,74880, 115200, 230400, 250000, 500000, 1000000, 2000000
  Serial.begin(1000000);  // As fast as possible for debug, otherwise it slows down execution

  Wire.begin();                  // start the I2C interface
  Wire.begin(RPI_I2C_ADD);       // join I2c bus with address #17
  Wire.setClock(400000);         // Set the I2C clock frequency to 400 kHz
  Wire.onReceive(receiveEvent);  // register event
  Wire.onRequest(sendEvent);

  // JRE 04/08/2022
  CommandQueue.in = 0;
  CommandQueue.out = 0;
  ResponseQueue.in = 0;
  ResponseQueue.out = 0;


  //*******************************************************************
  // End of initialization code copied from ALT-Scann8-Controller.ino
  //*******************************************************************

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


  // ---Orginal Block at Row 837
  // LED Motor control at Start (STOP is Default)
  mcp_1.digitalWrite(LED_STOP, HIGH);
  mcp_1.digitalWrite(LED_START, LOW);
  mcp_1.digitalWrite(LED_FORWARD, LOW);
  mcp_1.digitalWrite(LED_BACKWARD, LOW);
  mcp_1.digitalWrite(LED_FF, LOW);
  mcp_1.digitalWrite(LED_RW, LOW);
  //

}  // CHIUDE il void Setup


//###################################################################
//
//	Void_LOOP - BEGIN
//
//###################################################################

void loop() {
  int param;       // Retrieves possible parameter in command from RPi
  int UI_Command;  // Stores I2C command from RPI

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
  FormatSelectLOCK = 1;  // FORCED - For initial Test only - to DELETE

  if (!mcp_2.digitalRead(BUTTON_START) == 1 && FormatSelectLOCK == 1 && StopLOCK == 0 && mcp_2.digitalRead(BUTTON_STOP) == 1) {  // INVERTED logic as using Pull-Down
    StopLOCK = 1;
    StartLOCK = 1;
    mcp_1.digitalWrite(LED_STOP, 0);
    mcp_1.digitalWrite(LED_START, 1);
    // New code to tell ALT_SCANN_8 to start
    SendToRPi(ALT_SCAN_8_START, 0, 0);  // Request RPi to start scanning
  }


  // Forward Button
  if (!mcp_2.digitalRead(BUTTON_FORWARD) == 1 && StopLOCK == 0 && mcp_2.digitalRead(BUTTON_STOP) == 1) {  // INVERTED logic as using Pull-Down
    StopLOCK = 1;
    mcp_1.digitalWrite(LED_STOP, 0);
    mcp_1.digitalWrite(LED_FORWARD, 1);
    // New code to tell ALT_SCANN_8 to move film forward
    SendToRPi(ALT_SCAN_8_FORWARD, 0, 0);  // Request RPi to move film forward
  }


  // Backward Button
  if (!mcp_2.digitalRead(BUTTON_BACKWARD) == 1 && StopLOCK == 0 && mcp_2.digitalRead(BUTTON_STOP) == 1) {  // INVERTED logic as using Pull-Down
    StopLOCK = 1;
    mcp_1.digitalWrite(LED_STOP, 0);
    mcp_1.digitalWrite(LED_BACKWARD, 1);
    // New code to tell ALT_SCANN_8 to move film backward
    SendToRPi(ALT_SCAN_8_BACKWARD, 0, 0);  // Request RPi to move film backward
  }

  // FF Fast Forward Button
  if (!mcp_1.digitalRead(BUTTON_FF) == 1 && StopLOCK == 0 && mcp_2.digitalRead(BUTTON_STOP) == 1) {  // INVERTED logic as using Pull-Down
    StopLOCK = 1;
    mcp_1.digitalWrite(LED_STOP, 0);
    mcp_1.digitalWrite(LED_FF, 1);
    // New code to tell ALT_SCANN_8 to perform fast forward
    SendToRPi(ALT_SCAN_8_FF, 0, 0);  // Request RPi to move film fast forward
  }                                  // LED_RPI_PinchRollerDetect will Blink briefly to remember that FF and RW are not allowed if Pinch-Roller is Inserted

  // RW Rewind Button
  if (!mcp_1.digitalRead(BUTTON_RW) == 1 && StopLOCK == 0 && mcp_2.digitalRead(BUTTON_STOP) == 1) {  // INVERTED logic as using Pull-Down
    StopLOCK = 1;
    mcp_1.digitalWrite(LED_STOP, 0);
    mcp_1.digitalWrite(LED_RW, 1);
    // New code to tell ALT_SCANN_8 to perform rewind
    SendToRPi(ALT_SCAN_8_RW, 0, 0);  // Request RPi to move film rewind
  }                                  // LED_RPI_PinchRollerDetect will Blink briefly to remember that FF and RW are not allowed if Pinch-Roller is Inserted

  // Code copied from ALT-Scann8-Controller, to retrieve commands from RPi
  if (dataInCmdQueue())
    UI_Command = pop_cmd(&param);  // Get next command from queue if one exists
  else
    UI_Command = 0;

  // RPi Command processing switch: Create #defines and functions as required
  // At this point panel module should handle actions on RPi UI side - To be implemented
  if (UI_Command != 0) {
    switch (UI_Command) {  // RPi commands
      case CMD_START_SCAN:
        break;
      case CMD_STOP_SCAN:
        break;
    }
  }
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

//*****************************************************************************
// 2024/12/29 - Code below copied from ALT-Scann8-Controller, to handle I2C bus
//*****************************************************************************

// ---- Send commands to RPi
void SendToRPi(byte rsp, int param1, int param2) {
  push_rsp(rsp, param1, param2);
}

// ---- Receive I2C command from Raspberry PI, ScanFilm... and more ------------
// JRE 13/09/22: Theoretically this might happen any time, thu UI_Command might change in the middle of the loop. Adding a queue...
void receiveEvent(int byteCount) {
  int IncomingIc, param = 0;

  if (Wire.available())
    IncomingIc = Wire.read();
  if (Wire.available())
    param = Wire.read();
  if (Wire.available())
    param += 256 * Wire.read();
  while (Wire.available())
    Wire.read();

  if (IncomingIc > 0) {
    push_cmd(IncomingIc, param);  // No error treatment for now
  }
}

// -- Sending I2C command to Raspberry PI, take picture now -------
void sendEvent() {
  int cmd, p1, p2;
  cmd = pop_rsp(&p1, &p2);
  if (cmd != -1) {
    BufferForRPi[0] = cmd;
    BufferForRPi[1] = p1 / 256;
    BufferForRPi[2] = p1 % 256;
    BufferForRPi[3] = p2 / 256;
    BufferForRPi[4] = p2 % 256;
    Wire.write(BufferForRPi, 5);
  } else {
    BufferForRPi[0] = 0;
    BufferForRPi[1] = 0;
    BufferForRPi[2] = 0;
    BufferForRPi[3] = 0;
    BufferForRPi[4] = 0;
    Wire.write(BufferForRPi, 5);
  }
}

boolean push(Queue* queue, int IncomingIc, int param, int param2) {
  boolean retvalue = false;
  if ((queue->in + 1) % QUEUE_SIZE != queue->out) {
    queue->Data[queue->in] = IncomingIc;
    queue->Param[queue->in] = param;
    queue->Param2[queue->in] = param2;
    queue->in++;
    queue->in %= QUEUE_SIZE;
    retvalue = true;
  }
  // else: Queue full: Should not happen. Not sure how this should be handled
  return (retvalue);
}

int pop(Queue* queue, int* param, int* param2) {
  int retvalue = -1;  // default return value: -1 (error)
  if (queue->out != queue->in) {
    retvalue = queue->Data[queue->out];
    if (param != NULL)
      *param = queue->Param[queue->out];
    if (param2 != NULL)
      *param2 = queue->Param2[queue->out];
    queue->out++;
    queue->out %= QUEUE_SIZE;
  }
  // else: Queue empty: Nothing to do
  return (retvalue);
}

boolean push_cmd(int cmd, int param) {
  push(&CommandQueue, cmd, param, 0);
}
int pop_cmd(int* param) {
  return (pop(&CommandQueue, param, NULL));
}
boolean push_rsp(int rsp, int param, int param2) {
  push(&ResponseQueue, rsp, param, param2);
}
int pop_rsp(int* param, int* param2) {
  return (pop(&ResponseQueue, param, param2));
}

boolean dataInCmdQueue(void) {
  return (CommandQueue.out != CommandQueue.in);
}

boolean dataInRspQueue(void) {
  return (ResponseQueue.out != ResponseQueue.in);
}
