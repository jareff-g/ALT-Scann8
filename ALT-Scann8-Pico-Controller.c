/*
ALT-Scann8 UI - Alternative software for T-Scann 8

ALT-Scann8 is a fork of the application of T-Scann 8, By Torulf H.
This file is an adaptation for RPi Pico, based on Arduino code I wrote, based on Torulf's code,

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

#include <stdio.h>
#include "pico/stdlib.h"
#include "pico/binary_info.h"
#include "hardware/i2c.h"

// ######### Pin definition section ##########
#define PIN_PT              28  // ADC2
#define PIN_BUZZER          12
#define PIN_TRACTION_STOP   4
#define PIN_UV_LED          5
#define PIN_GREEN_LED       6
#define PIN_AUX1            7
#define PIN_AUX2            8
#define PIN_AUX3            9
#define PIN_AUX4            10
#define PIN_AUX5            11
#define PIN_MOTOR_A_STEP    22
#define PIN_MOTOR_A_NEUTRAL 26
#define PIN_MOTOR_A_DIR     21
#define PIN_MOTOR_B_STEP    19
#define PIN_MOTOR_B_NEUTRAL 20
#define PIN_MOTOR_B_DIR     18
#define PIN_MOTOR_C_STEP    14
#define PIN_MOTOR_C_NEUTRAL 13
#define PIN_MOTOR_C_DIR     15
// ALT-Scann8 uses I2C0 on GP16/GP17 to talk to RPi, I2C1 on GP2/GP3 to talk to the on-board screen
#define PIN_I2C0_SDA        16
#define PIN_I2C0_SCL        17
#define PIN_I2C1_SDA        2
#define PIN_I2C1_SCL        3

// ######### Define I2C instances (to use instead of i2c_default in examples
#define i2c_RPi     i2c0
#define I2C_Screen  i2c1

// ######### Variable section ##########
// Handling of PT values dynamically
int MaxPT = 0;
int MinPT = 200;
// These two vars are to keep max/min pt values for the recent past
// Since keeping a sliding window will be too memory heavy (too manu samples) for Arduino, instead the max/min values
// are decrease/increased each time a new sample is taken. Stored values are multiplied by 10, to have more resolution
// (avoid decreasing/increasing too fast).
// The idea is to see if we can mak ethe PT level value automatically set by the software, so that it adapt sto different
// part of the film (clear/dark around the holes) dynamically.
int MaxPT_Dynamic = 0;
int MinPT_Dynamic = 10000;

boolean GreenLedOn = false;

enum {
  PT_Level,
  FrameSteps,
  DebugInfo,
  DebugInfoSingle,
  None
} DebugState = PT_Level;

int MaxDebugRepetitions = 3;
#define MAX_DEBUG_REPETITIONS_COUNT 30000

int UI_Command; // Stores I2C command from Raspberry PI
// I2C commands: Constant definition
#define CMD_VERSION_ID_CHECK 1
#define CMD_START_SCAN 10
#define CMD_TERMINATE 11
#define CMD_GET_NEXT_FRAME 12
#define CMD_SET_REGULAR_8 18
#define CMD_SET_SUPER_8 19
#define CMD_SWITCH_REEL_LOCK_STATUS 20
#define CMD_FILM_FORWARD 30
#define CMD_SINGLE_STEP 40
#define CMD_SET_PT_LEVEL 50
#define CMD_SET_MIN_FRAME_STEPS 52
#define CMD_SET_EXTRA_FRAME_STEPS 54
#define CMD_REWIND 60
#define CMD_FAST_FORWARD 61
#define CMD_INCREASE_WIND_SPEED 62
#define CMD_DECREASE_WIND_SPEED 63
#define CMD_UNCONDITIONAL_REWIND 64
#define CMD_UNCONDITIONAL_FAST_FORWARD 65

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
unsigned int UVLedBrightness = 65535;       // Brightness UV led, may need to be changed depending on LED type
unsigned long ScanSpeed = 250 ;             // 250 - Delay in microseconds used to adjust speed of stepper motor during scan process
unsigned long FetchFrameScanSpeed = 500;    // 500 - Delay (microsec also) for slower stepper motor speed once minimum number of steps reached
unsigned long DecreaseScanSpeedStep = 100;  // 100 - Increment in microseconds of delay to slow down progressively scanning speed, to improve detection (set to zero to disable)
int RewindSpeed = 4000;                     // Initial delay in microseconds used to determine speed of rewind/FF movie
int TargetRewindSpeedLoop = 200;            // Final delay  in microseconds for rewind/SS speed (Originally hardcoded)
int PerforationMaxLevel = 550;              // Phototransistor reported value, max level
int PerforationMinLevel = 50;               // Phototransistor reported value, min level (originalyl hardcoded)
int PerforationThresholdLevelR8 = 180;      // Default value for R8
int PerforationThresholdLevelS8 = 90;       // Default value for S8
int PerforationThresholdLevel = PerforationThresholdLevelS8;    // Phototransistor value to decide if new frame is detected
int MinFrameStepsR8 = 257;                  // Default value for R8
int MinFrameStepsS8 = 288;                  // Default value for S8
int MinFrameSteps = MinFrameStepsS8;        // Minimum number of steps to allow frame detection
int ExtraFrameSteps = 0;                    // Allow framing adjustment on the fly (manual, automatic would require using CV2 pattern matching, maybe to be checked)
int DecreaseSpeedFrameStepsBefore = 20;     // 20 - No need to anticipate slow down, the default MinFrameStep should be always less
int DecreaseSpeedFrameSteps = MinFrameSteps - DecreaseSpeedFrameStepsBefore;    // Steps at which the scanning speed starts to slow down to improve detection
// ------------------------------------------------------------------------------------------

boolean ReelsUnlocked = false;
boolean FrameDetected = false;  // Used for frame detection, in play ond single step modes
boolean UVLedOn = false;
int FilteredSignalLevel = 0;
int OriginalPerforationThresholdLevel = PerforationThresholdLevel; // stores value for resetting PerforationThresholdLevel
int FrameStepsDone = 0;                     // Count steps
int MaxFrameSteps = 100;                      // Required to calculate led brightness (init with non-zero value, below potential real max)
unsigned long OriginalScanSpeed = ScanSpeed;          // Keep to restore original value when needed
int OriginalMinFrameSteps = MinFrameSteps;  // Keep to restore original value when needed

int LastFrameSteps = 0;                     // Stores number of steps required to reach current frame (stats only)

boolean IsS8 = true;

boolean TractionSwitchActive = true;  // When traction micro-switch is closed

unsigned long StartFrameTime = 0;           // Time at which we get RPi command to get next frame (stats only)
unsigned long StartPictureSaveTime = 0;     // Time at which we tell RPi to save current frame (stats only)

int EventForRPi = 0;    // Used by Pico to pass an event to RPi
int ParamForRPi = 0;    // Used by CMD_SET_PT_LEVEL (pass autocalculated value to RPi for display)

int PT_SignalLevelRead;   // Raw signal level from phototransistor
boolean PT_Level_Auto = true;   // Automatic calculation of PT level threshold

// Flag to detect ALT UI version
// Need to prevent operation with main version since compatibility cannot be maintained
boolean ALT_Scann8_UI_detected = false;

// Forward definition
void CollectOutgoingFilm(bool);

// JRE - Support data variables
#define QUEUE_SIZE 20
volatile struct {
  int Data[QUEUE_SIZE];
  int Param[QUEUE_SIZE];
  int in;
  int out;
} CommandQueue;

void scan_i2c() {
    for (int i2c_instance = 0; i2c_instance <= 1; i2c_instance++) {
        printf("\nI2C%i Bus Scan\n", i2c_instance);
        printf("   0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F\n");

        for (int addr = 0; addr < (1 << 7); ++addr) {
            if (addr % 16 == 0) {
                printf("%02x ", addr);
            }

            // Perform a 1-byte dummy read from the probe address. If a slave
            // acknowledges this address, the function returns the number of bytes
            // transferred. If the address byte is ignored, the function returns
            // -1.

            // Skip over any reserved addresses.
            int ret;
            uint8_t rxdata;
            if (reserved_addr(addr))
                ret = PICO_ERROR_GENERIC;
            else
                ret = i2c_read_blocking(i2c_instance, addr, &rxdata, 1, false);

            printf(ret < 0 ? "." : "@");
            printf(addr % 16 == 15 ? "\n" : "  ");
        }
    }
    printf("Done.\n");
}

void setup() {
    uint BuzzerSliceNum;
    uint UVSliceNum;

    // stdio_init_all initializes serial over USB on Pico. Kind of 'Serial.begin(9600)' on Arduino.
    // Once initialized, use a plain printf to send stuff over serial
    stdio_init_all();

    // This example will use I2C0 on the default SDA and SCL pins (GP4, GP5 on a Pico)
    // ALT-Scann8 uses I2C0 on GP16/GP17 to talk to RPi, I2C1 on GP2/GP3 to talk to the on-board screen
    i2c_init(i2c_default, 100 * 1000);
    gpio_set_function(PIN_I2C0_SDA, GPIO_FUNC_I2C);
    gpio_set_function(PIN_I2C0_SCL, GPIO_FUNC_I2C);
    gpio_set_function(PIN_I2C1_SDA, GPIO_FUNC_I2C);
    gpio_set_function(PIN_I2C1_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(PIN_I2C0_SDA);
    gpio_pull_up(PIN_I2C0_SCL);
    gpio_pull_up(PIN_I2C1_SDA);
    gpio_pull_up(PIN_I2C1_SCL);
    // Make the I2C pins available to picotool
    bi_decl(bi_2pins_with_func(PIN_I2C0_SDA, PIN_I2C0_SCL, GPIO_FUNC_I2C));
    bi_decl(bi_2pins_with_func(PIN_I2C1_SDA, PIN_I2C1_SCL, GPIO_FUNC_I2C));

    scan_i2c(); // For debugging purposes, to remove later

    // Initialize I2C slave for I2C0 (comm with RPi). Init queue pointers before defining callback
    CommandQueue.in = 0;
    CommandQueue.out = 0;
    i2c_slave_init (i2c0, 0x33, receiveEvent);    // Init pico as I2C slave, set callback for receive events

    // Assign function to pins
    adc_init(); // Initialize ADC HW
    adc_gpio_init(PIN_PT);  // Initialize PIN_PT as ADC (ADC2)
    gpio_init(PIN_TRACTION_STOP);
    gpio_set_dir(PIN_TRACTION_STOP, false);
    gpio_pull_up(PIN_TRACTION_STOP);
    gpio_init(PIN_BUZZER);
    gpio_set_dir(PIN_BUZZER, true);
    gpio_set_function(PIN_BUZZER, GPIO_FUNC_PWM);
    gpio_init(PIN_UV_LED);
    gpio_set_dir(PIN_UV_LED, true);
    gpio_set_function(PIN_UV_LED, GPIO_FUNC_PWM);
    gpio_init(PIN_GREEN_LED);
    gpio_set_dir(PIN_GREEN_LED, true);
    gpio_set_function(PIN_GREEN_LED, GPIO_FUNC_PWM);
    gpio_init(PIN_AUX1);
    gpio_set_dir(PIN_AUX1, true);   // Odd aux jumpers are OUT, even are IN
    gpio_init(PIN_AUX2);
    gpio_set_dir(PIN_AUX2, false);
    gpio_init(PIN_AUX3);
    gpio_set_dir(PIN_AUX3, true);   // Odd aux jumpers are OUT, even are IN
    gpio_init(PIN_AUX4);
    gpio_set_dir(PIN_AUX4, false);
    gpio_init(PIN_AUX5);
    gpio_set_dir(PIN_AUX5, true);   // Odd aux jumpers are OUT, even are IN
    gpio_init(PIN_MOTOR_A_STEP);
    gpio_set_dir(PIN_MOTOR_A_STEP, true);   // Odd aux jumpers are OUT, even are IN
    gpio_init(PIN_MOTOR_A_NEUTRAL);
    gpio_set_dir(PIN_MOTOR_A_NEUTRAL, true);   // Odd aux jumpers are OUT, even are IN
    gpio_init(PIN_MOTOR_A_DIR);
    gpio_set_dir(PIN_MOTOR_A_DIR, true);   // Odd aux jumpers are OUT, even are IN
    gpio_init(PIN_MOTOR_B_STEP);
    gpio_set_dir(PIN_MOTOR_B_STEP, true);   // Odd aux jumpers are OUT, even are IN
    gpio_init(PIN_MOTOR_B_NEUTRAL);
    gpio_set_dir(PIN_MOTOR_B_NEUTRAL, true);   // Odd aux jumpers are OUT, even are IN
    gpio_init(PIN_MOTOR_B_DIR);
    gpio_set_dir(PIN_MOTOR_B_DIR, true);   // Odd aux jumpers are OUT, even are IN
    gpio_init(PIN_MOTOR_C_STEP);
    gpio_set_dir(PIN_MOTOR_C_STEP, true);   // Odd aux jumpers are OUT, even are IN
    gpio_init(PIN_MOTOR_C_NEUTRAL);
    gpio_set_dir(PIN_MOTOR_C_NEUTRAL, true);   // Odd aux jumpers are OUT, even are IN
    gpio_init(PIN_MOTOR_C_DIR);
    gpio_set_dir(PIN_MOTOR_C_DIR, true);   // Odd aux jumpers are OUT, even are IN

    // Init PWM
    BuzzerSliceNum = pwm_gpio_to_slice_num(PIN_BUZZER);
    pwm_config BuzzerConfig = pwm_get_default_config();
    pwm_init(BuzzerSliceNum, &BuzzerConfig, false); // Buzzer PWM will be started on demand only, by a 'tone' function TBD
    UVSliceNum = pwm_gpio_to_slice_num(PIN_UV_LED);
    pwm_config UVConfig = pwm_get_default_config();
    pwm_init(UVSliceNum, &UVConfig, true);
    pwm_set_gpio_level (PIN_UV_LED, 0);   // UV off on startup
    GreenLedSliceNum = pwm_gpio_to_slice_num(PIN_GREEN_LED);
    pwm_config GreenLedConfig = pwm_get_default_config();
    pwm_init(GreenLedSliceNum, &GreenLedConfig, true);
    pwm_set_gpio_level (PIN_GREEN_LED, 0);   // Grren led off on startup


    // neutral position for Motor A
    gpio_put(PIN_MOTOR_A_NEUTRAL,1);

    // set direction on stepper motors
    gpio_put(PIN_MOTOR_A_DIR,0);
    gpio_put(PIN_MOTOR_B_DIR,0);

    gpio_put(PIN_MOTOR_A_STEP,0);
    gpio_put(PIN_MOTOR_B_STEP,0);
    gpio_put(PIN_MOTOR_C_STEP,0);
}

void loop() {
    int param;
    while (1) {
        if (dataInQueue())
            UI_Command = pop(&param);   // Get next command from queue if one exists
        else
            UI_Command = 0;

        TractionSwitchActive = !gpio_get(PIN_TRACTION_STOP);    // 0 means traction switch active

        ReportPlotterInfo();    // Regular report of plotter info

        switch (UI_Command) {
            case CMD_SET_PT_LEVEL:
                if (param >= 0 && param <= 900) {
                    if (param == 0)
                      PT_Level_Auto = true;     // zero means we go in automatic mode
                    else{
                      PT_Level_Auto = false;     // zero means we go in automatic mode
                      PerforationThresholdLevel = param;
                      OriginalPerforationThresholdLevel = param;
                    }
                    DebugPrint(">PTLevel",param);
                }
                break;
            case CMD_SET_MIN_FRAME_STEPS:
                if (param >= 100 && param <= 600) {
                  MinFrameSteps = param;
                  OriginalMinFrameSteps = param;
                  if (IsS8)
                    MinFrameStepsS8 = param;
                  else
                    MinFrameStepsR8 = param;
                  MinFrameSteps = param;
                  DecreaseSpeedFrameSteps = MinFrameSteps - DecreaseSpeedFrameStepsBefore;
                  DebugPrint(">MinSteps",param);
                }
                break;
            case CMD_SET_EXTRA_FRAME_STEPS:
                ExtraFrameSteps = param;
                break;
        }

        switch (ScanState) {
            case Sts_Idle:
                switch (UI_Command) {
                    case CMD_START_SCAN:
                        DebugPrintStr(">Scan");
                        ScanState = Sts_Scan;
                        pwm_set_gpio_level (PIN_UV_LED, UVLedBrightness);   // Need to check if this maps to Arduino (see next commented line)
                        // analogWrite(11, UVLedBrightness); // Turn on UV LED
                        UVLedOn = true;
                        sleep_ms(500);
                        StartFrameTime = get_absolute_time();
                        ScanSpeed = OriginalScanSpeed;
                        MinFrameSteps = 100;
                        //tone(A2, 2000, 50);   // No tone in pico, to be checked
                        break;
                    case CMD_TERMINATE:  //Exit app
                        if (UVLedOn) {
                            pwm_set_gpio_level (PIN_UV_LED, UVLedBrightness);   // Need to check if this maps to Arduino (see next commented line)
                            UVLedOn = false;
                        }
                        break;
                    case CMD_GET_NEXT_FRAME:  // Continue scan to next frame
                        ScanState = Sts_Scan;
                        MinFrameSteps = OriginalMinFrameSteps;
                        StartFrameTime = get_absolute_time();
                        ScanSpeed = OriginalScanSpeed;
                        DebugPrint("Save t.",StartFrameTime-StartPictureSaveTime);
                        DebugPrintStr(">Next fr.");
                        // Also send, if required, to RPi autocalculated threshold level every frame
                        if (PT_Level_Auto) {
                            EventForRPi = CMD_SET_PT_LEVEL;
                            ParamForRPi = PerforationThresholdLevel;
                            digitalWrite(13, HIGH);
                        }
                        break;
                    case CMD_SET_REGULAR_8:  // Select R8 film
                        IsS8 = false;
                        MinFrameSteps = MinFrameStepsR8;
                        DecreaseSpeedFrameSteps = MinFrameSteps - DecreaseSpeedFrameStepsBefore;
                        PerforationThresholdLevel = PerforationThresholdLevelR8;
                        OriginalMinFrameSteps = MinFrameSteps;
                        OriginalPerforationThresholdLevel = PerforationThresholdLevel;
                        if (!PT_Level_Auto)
                            PerforationThresholdLevel = PerforationThresholdLevelR8;
                        OriginalPerforationThresholdLevel = PerforationThresholdLevelR8;
                        break;
                    case CMD_SET_SUPER_8:  // Select S8 film
                        IsS8 = true;
                        MinFrameSteps = MinFrameStepsS8;
                        DecreaseSpeedFrameSteps = MinFrameSteps - DecreaseSpeedFrameStepsBefore;
                        PerforationThresholdLevel = PerforationThresholdLevelS8;
                        OriginalMinFrameSteps = MinFrameSteps;
                        OriginalPerforationThresholdLevel = PerforationThresholdLevel;
                        if (!PT_Level_Auto)
                            PerforationThresholdLevel = PerforationThresholdLevelS8;
                        OriginalPerforationThresholdLevel = PerforationThresholdLevelS8;
                        break;
                    case CMD_SWITCH_REEL_LOCK_STATUS:
                        ScanState = Sts_UnlockReels;
                        sleep_ms(50);
                        break;
                    case CMD_FILM_FORWARD:
                        ScanState = Sts_SlowForward;
                        sleep_ms(50);
                        break;
                    case CMD_SINGLE_STEP:
                        DebugPrintStr(">SStep");
                        ScanState = Sts_SingleStep;
                        MinFrameSteps = 100; // Used to be 100
                        sleep_ms(50);
                        break;
                    case CMD_REWIND: // Rewind
                    case CMD_UNCONDITIONAL_REWIND: // Rewind unconditional
                        if (FilmInFilmgate() and UI_Command == CMD_REWIND) { // JRE 13 Aug 22: Cannot rewind, there is film loaded
                            DebugPrintStr("Rwnd err");
                            EventForRPi = CMD_UNCONDITIONAL_REWIND;
                            i2c_write_byte_raw(i2c0, EventForRPi);
                            /*
                            tone(A2, 2000, 100);
                            sleep_ms(150);
                            tone(A2, 1000, 100);
                            */
                        }
                        else {
                            DebugPrintStr("Rwnd");
                            ScanState = Sts_Rewind;
                            sleep_ms(50);
                            gpio_put(PIN_MOTOR_A_NEUTRAL,0);
                            gpio_put(PIN_MOTOR_B_NEUTRAL,1);
                            gpio_put(PIN_MOTOR_C_NEUTRAL,1);
                            /*
                            tone(A2, 2200, 100);
                            sleep_ms(150);
                            tone(A2, 2200, 100);
                            sleep_ms(150);
                            tone(A2, 2000, 200);
                            */
                            RewindSpeed = 4000;
                        }
                        sleep_ms(50);
                        break;
                    case CMD_FAST_FORWARD:  // Fast Forward
                    case CMD_UNCONDITIONAL_FAST_FORWARD:  // Fast Forward unconditional
                        if (FilmInFilmgate() and UI_Command == CMD_FAST_FORWARD) { // JRE 13 Aug 22: Cannot fast forward, there is film loaded
                            DebugPrintStr("FF err");
                            EventForRPi = CMD_UNCONDITIONAL_FAST_FORWARD;
                            i2c_write_byte_raw(i2c0, EventForRPi);
                            /*
                            tone(A2, 2000, 100);
                            sleep_ms(150);
                            tone(A2, 1000, 100);
                            */
                        }
                        else {
                            DebugPrintStr(">FF");
                            ScanState = Sts_FastForward;
                            sleep_ms(100);
                            gpio_put(PIN_MOTOR_A_NEUTRAL,1);
                            gpio_put(PIN_MOTOR_B_NEUTRAL,1);
                            gpio_put(PIN_MOTOR_C_NEUTRAL,0);
                            /*
                            tone(A2, 2000, 100);
                            sleep_ms(150);
                            tone(A2, 2000, 100);
                            sleep_ms(150);
                            tone(A2, 2200, 200);
                            */
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
                break;
            case Sts_SingleStep:
                if (scan(UI_Command) != SCAN_NO_FRAME_DETECTED) {
                    ScanState = Sts_Idle;
                }
                break;
            case Sts_UnlockReels:
                if (UI_Command == CMD_SWITCH_REEL_LOCK_STATUS) { //request to lock reels again
                    ReelsUnlocked = false;
                    gpio_put(PIN_MOTOR_B_NEUTRAL,0);
                    gpio_put(PIN_MOTOR_C_NEUTRAL,0);
                    ScanState = Sts_Idle;
                    pwm_set_gpio_level (PIN_UV_LED, 0);   // Need to check if this maps to Arduino (see next commented line)
                    //analogWrite(11, 0); // Turn off UV LED
                    UVLedOn = false;
                }
                else {
                    if (not ReelsUnlocked){
                        ReelsUnlocked = true;
                        gpio_put(PIN_MOTOR_B_NEUTRAL,1);
                        gpio_put(PIN_MOTOR_C_NEUTRAL,1);
                        pwm_set_gpio_level (PIN_UV_LED, UVLedBrightness);   // Need to check if this maps to Arduino (see next commented line)
                        // analogWrite(11, UVLedBrightness); // Turn on UV LED
                        UVLedOn = true;
                    }
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
                    sleep_ms(50);
                    ScanState = Sts_Idle;
                }
                else {
                    CollectOutgoingFilm(true);
                    sleep_ms(1);
                    gpio_put(PIN_MOTOR_B_STEP,1);
                }
                break;
        }

        // ----- Speed on stepper motors ------------------ JRE: To be checked if needed, here or elsewhere
        sleep_us(1);
    }
}



// ------ rewind the movie ------
boolean RewindFilm(int UI_Command) {
    boolean retvalue = true;
    static boolean stopping = false;
  
    //Wire.begin(16);

    if (UI_Command == CMD_REWIND) {
        stopping = true;
    }
    else if (stopping) {
        if (RewindSpeed < 4000) {
            gpio_put(PIN_MOTOR_A_STEP,1);
            sleep_us(RewindSpeed);
            gpio_put(PIN_MOTOR_A_STEP,0);
            RewindSpeed += round(max(1,RewindSpeed/400));
        }
        else {
            retvalue = false;
            stopping = false;
            gpio_put(PIN_MOTOR_A_NEUTRAL,1);
            gpio_put(PIN_MOTOR_B_NEUTRAL,0);
            gpio_put(PIN_MOTOR_C_NEUTRAL,0);
            sleep_ms(100);
            EventForRPi = CMD_REWIND;
            i2c_write_byte_raw(i2c0, EventForRPi);
            //digitalWrite(13, HIGH);
        }
    }
    else {
        gpio_put(PIN_MOTOR_A_STEP,1);
        sleep_us(RewindSpeed);
        gpio_put(PIN_MOTOR_A_STEP,0);
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

  //Wire.begin(16);  // join I2c bus with address #16

    if (UI_Command == CMD_FAST_FORWARD) {
        stopping = true;
    }
    else if (stopping) {
        if (RewindSpeed < 4000) {
            gpio_put(PIN_MOTOR_C_STEP,1);
            sleep_us(RewindSpeed);
            gpio_put(PIN_MOTOR_C_STEP,0);
            RewindSpeed += round(max(1,RewindSpeed/400));
        }
        else {
            retvalue = false;
            stopping = false;
            gpio_put(PIN_MOTOR_A_NEUTRAL,1);
            gpio_put(PIN_MOTOR_B_NEUTRAL,0);
            gpio_put(PIN_MOTOR_C_NEUTRAL,0);
            sleep_ms(100);
            EventForRPi = CMD_FAST_FORWARD;
            i2c_write_byte_raw(i2c0, EventForRPi);
            //digitalWrite(13, HIGH);
        }
    }
    else {
        gpio_put(PIN_MOTOR_C_STEP,1);
        sleep_us(RewindSpeed);
        gpio_put(PIN_MOTOR_C_STEP,0);
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
void CollectOutgoingFilm(bool ff_collect = false) {
    static int collect_modulo = 10;
    static int loop_counter = 0;
    static boolean CollectOngoing = true;

    static unsigned long LastSwitchActivationTime = 0L;
    static unsigned long LastSwitchActivationCheckTime = delayed_by_ms(get_absolute_time(),10000); // millis()+10000;
    unsigned long CurrentTime = get_absolute_time();    // millis();

    if (loop_counter % collect_modulo == 0) {
        TractionSwitchActive = !gpio_get(PIN_TRACTION_STOP);    // 0 means traction switch active
        if (!TractionSwitchActive) {  //Motor allowed to turn
            CollectOngoing = true;
            gpio_put(PIN_MOTOR_C_STEP,0);
            gpio_put(PIN_MOTOR_C_STEP,1);
            gpio_put(PIN_MOTOR_C_STEP,0);
        }
        TractionSwitchActive = !gpio_get(PIN_TRACTION_STOP);    // 0 means traction switch active
        if (TractionSwitchActive) {
            if (CollectOngoing) {
                if (CurrentTime < delayed_by_ms(LastSwitchActivationTime, 1000)){  // Collecting too often: Increase modulo
                    collect_modulo++;
                }
                DebugPrint("Collect Mod", collect_modulo);
                LastSwitchActivationTime = CurrentTime;
            }
            CollectOngoing = false;
        }
        else if (collect_modulo > 1 && CurrentTime > delayed_by_ms(LastSwitchActivationTime, 1000)) {  // Not collecting enough : Decrease modulo
            LastSwitchActivationTime = CurrentTime;
            collect_modulo--;
            DebugPrint("Collect Mod", collect_modulo);
        }
    }
    loop_counter++;
}

// ------------- Centralized phototransistor level read ---------------
int GetLevelPT() {
    static int count = 0;
    int SignalLevel;

    // Select ADC input 2 (GPIO28)
    adc_select_input(2);
    SignalLevel =  adc_read();

    MaxPT = max(SignalLevel, MaxPT);
    MinPT = min(SignalLevel, MinPT);
    MaxPT_Dynamic = max(SignalLevel*10, MaxPT_Dynamic);
    MinPT_Dynamic = min(SignalLevel*10, MinPT_Dynamic);
    if (MaxPT_Dynamic > MinPT_Dynamic) MaxPT_Dynamic-=2;
    if (MinPT_Dynamic < MaxPT_Dynamic) MinPT_Dynamic+=int((MaxPT_Dynamic-MinPT_Dynamic)/10);  // need to catch up quickly for overexposed frames (proportional to MaxPT to adapt to any scanner)
    if (PT_Level_Auto)
        PerforationThresholdLevel = int(((MinPT_Dynamic + (MaxPT_Dynamic-MinPT_Dynamic) * 0.5))/10);

    return(SignalLevel);
}


// ------------ Reports info (PT level, steps/frame, etc) to Serial Plotter 10 times/sec ----------
void ReportPlotterInfo() {
    static unsigned long NextReport = 0;
    static int Previous_PT_Signal = 0, PreviousFrameSteps = 0;
    static char out[100];

    if (DebugState == PlotterInfo && get_absolute_time() > NextReport) {
        if (Previous_PT_Signal != PT_SignalLevelRead || PreviousFrameSteps != LastFrameSteps) {
            NextReport = delayed_by_ms(get_absolute_time(),20);
            sprintf(out,"PT:%i,MaxPT:%i,MinPT:%i,Threshold:%i", PT_SignalLevelRead,int(MaxPT_Dynamic/10),int(MinPT_Dynamic/10),PerforationThresholdLevel);
            SerialPrintStr(out);
            Previous_PT_Signal = PT_SignalLevelRead;
            PreviousFrameSteps = LastFrameSteps;
        }
    }
}

// ------------- is there film loaded in filmgate? ---------------
boolean FilmInFilmgate() {
    int SignalLevel;
    boolean retvalue = false;
    int mini=300, maxi=0;

    pwm_set_gpio_level (PIN_UV_LED, UVLedBrightness);   // Need to check if this maps to Arduino (see next commented line)
    // analogWrite(11, UVLedBrightness); // Turn on UV LED
    UVLedOn = true;
    sleep_ms(500);  // Give time to FT to stabilize

    // MinFrameSteps used here as a reference, just to skip two frames in worst case
    // Anyhow this funcion is used only for protection in rewind/ff, no film expected to be in filmgate
    for (int x = 0; x <= 300; x++) {
        gpio_put(PIN_MOTOR_B_STEP,0);
        gpio_put(PIN_MOTOR_B_STEP,1);
        SignalLevel = GetLevelPT();
        if (SignalLevel > maxi) maxi = SignalLevel;
        if (SignalLevel < mini) mini = SignalLevel;
    }
    gpio_put(PIN_MOTOR_B_STEP,0);
    pwm_set_gpio_level (PIN_UV_LED, 0);   // Need to check if this maps to Arduino (see next commented line)
    // analogWrite(11, 0); // Turn off UV LED
    UVLedOn = false;

    if (abs(maxi-mini) > 0.5*(MaxPT-MinPT))
        retvalue = true;

    return(retvalue);
}


// ------------- is the film perforation in position to take picture? ---------------
// Returns false if status should change to idle
boolean IsHoleDetected() {
    boolean hole_detected = false;
    int PT_Level;

    PT_Level = GetLevelPT();

    // ------------- Frame detection ----
    if (FrameStepsDone >= MinFrameSteps && PT_Level >= PerforationThresholdLevel) {
        hole_detected = true;
        GreenLedOn = true;
        pwm_set_gpio_level (PIN_GREEN_LED, (FrameStepsDone*65535)/MaxFrameSteps);   // Green led off on startup
        //gpio_put(PIN_GREEN_LED,1); // Light green led
    }

    return(hole_detected);
}

void capstan_advance(int steps)
{
    for (int x = 0; x < steps; x++) {    // Advance steps five at a time, otherwise too slow
        gpio_put(PIN_MOTOR_B_STEP,0);
        gpio_put(PIN_MOTOR_B_STEP,1);
    }
    gpio_put(PIN_MOTOR_B_STEP,0);
}



// ----- This is the function to "ScanFilm" -----
// Returns false when done
ScanResult scan(int UI_Command) {
    static long LastTime = 0;   // Reference used to throttle scanner speed (to limit the number of times entering scan function)
    ScanResult retvalue = SCAN_NO_FRAME_DETECTED;
    int steps_to_do = 5;
    unsigned long CurrentTime = get_absolute_time();

    pwm_set_gpio_level (PIN_UV_LED, UVLedBrightness);   // Need to check if this maps to Arduino (see next commented line)
    //analogWrite(11, UVLedBrightness);
    UVLedOn = true;

    if (GreenLedOn) {  // If last time frame was detected ...
        GreenLedOn = false;
        pwm_set_gpio_level (PIN_GREEN_LED, 0);   // Turn off green led
    }

    TractionSwitchActive = !gpio_get(PIN_TRACTION_STOP);    // 0 means traction switch active

    if (FrameStepsDone > DecreaseSpeedFrameSteps) {
        ScanSpeed = FetchFrameScanSpeed + min(20000, DecreaseScanSpeedStep * (FrameStepsDone - DecreaseSpeedFrameSteps + 1));
        steps_to_do = 1;    // Only one step per loop once we are close to frame detection
    }
    else
        steps_to_do = 5;    // 5 steps per loop if not yet there


    //-------------ScanFilm-----------
    if (UI_Command == CMD_START_SCAN) {   // UI Requesting to end current scan
        retvalue = SCAN_TERMINATION_REQUESTED;
        FrameDetected = false;
        //DecreaseSpeedFrameSteps = 260; // JRE 20/08/2022 - Disabled, added option to set manually from UI
        LastFrameSteps = 0;
        if (UVLedOn) {
            pwm_set_gpio_level (PIN_UV_LED, 0);   // Need to check if this maps to Arduino (see next commented line)
            //analogWrite(11, 0); // Turn off UV LED
            UVLedOn = false;
        }
    }
    else {
        FrameDetected = IsHoleDetected();
        if (!FrameDetected) {
            capstan_advance(steps_to_do);
            FrameStepsDone += steps_to_do;
            MaxFrameSteps = max(MaxFrameSteps, FrameStepsDone);
        }
    }

    if (FrameDetected) {
        DebugPrintStr("Frame!");
        if (ExtraFrameSteps > 0)
            capstan_advance(ExtraFrameSteps);
        LastFrameSteps = FrameStepsDone;
        FrameStepsDone = 0;
        StartPictureSaveTime = get_absolute_time();
        // Tell UI (Raspberry PI) a new frame is available for processing
        if (ScanState == Sts_SingleStep) {  // Do not send event to RPi for single step
            //tone(A2, 2000, 35);
        }
        else {
            EventForRPi = 11;
            i2c_write_byte_raw(i2c0, EventForRPi);
        }

        FrameDetected = false;
        retvalue = SCAN_FRAME_DETECTED;
        DebugPrint("FrmS",LastFrameSteps);
        DebugPrint("FrmT",CurrentTime-StartFrameTime);
        if (DebugState == FrameSteps)
          SerialPrintInt(LastFrameSteps);
    }
    else if (FrameStepsDone > 3*DecreaseSpeedFrameSteps) {
        retvalue = SCAN_FRAME_DETECTION_ERROR;
        FrameStepsDone = 0;
        DebugPrintStr("Err/scan");
        // Tell UI (Raspberry PI) an error happened during scanning
        EventForRPi = 12;
        i2c_write_byte_raw(i2c0, EventForRPi);
    }

    return (retvalue);
}


// ---- Receive I2C command from Raspberry PI, ScanFilm... and more ------------
void receiveEvent(i2c_inst_t *i2c, i2c_slave_event_t event) {
    int BytesToRead, IncomingIc, param = 0;

    if (gpio == i2c0 && event == I2C_SLAVE_RECEIVE) {
        BytesToRead = i2c_get_read_available();
        while (BytesToRead >= 3) {   // Read at least three, otherwise wait for next
            IncomingIc = i2c_read_byte_raw();
            param = i2c_read_byte_raw();
            param +=  256*i2c_read_byte_raw();
            if (IncomingIc > 0) {
                push(IncomingIc, param); // No error treatment for now
            }
        }
    }
}

// To be defined
// -- Sending I2C command to Raspberry PI, take picture now -------
void sendEvent() {
  byte cmd_array[3];

  cmd_array[0] = EventForRPi;
  cmd_array[1] = ParamForRPi/256;
  cmd_array[2] = ParamForRPi%256;
  Wire.write(cmd_array,3);
  EventForRPi = 0;
}

boolean push(int IncomingIc, int param) {
    boolean retvalue = false;
    if ((CommandQueue.in+1) % QUEUE_SIZE != CommandQueue.out) {
        CommandQueue.Data[CommandQueue.in] = IncomingIc;
        CommandQueue.Param[CommandQueue.in] = param;
        CommandQueue.in++;
        CommandQueue.in %= QUEUE_SIZE;
        retvalue = true;
    }
    // else: Queue full: Should not happen. Not sure how this should be handled
    return(retvalue);
}

int pop(int * param) {
    int retvalue = -1;  // default return value: -1 (error)
    if (CommandQueue.out != CommandQueue.in) {
        retvalue = CommandQueue.Data[CommandQueue.out];
        if (param != NULL)
            *param =  CommandQueue.Param[CommandQueue.out];
        CommandQueue.out++;
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
  
  if (DebugState != DebugInfo && DebugState != DebugInfoSingle) return;

  if (strlen(str) >= 50) {
    printf("Cannot print debug line, too long");
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
      printf(AuxLine);
    }
    CurrentRepetitions = 0;
  }
  strcpy(PreviousDebug, PrintLine);

  if (GoPrint) printf(PrintLine);
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
  if (DebugState != DebugInfo) printf(str);
}

void SerialPrintInt(int i) {
  if (DebugState != DebugInfo) printf(i);
}
