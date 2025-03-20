"""
****************************************************************************************************************
Class HwPanel
Class to encapsulate hardware panel done by Mariano
****************************************************************************************************************
"""
__author__ = 'Juan Remirez de Esparza'
__copyright__ = "Copyright 2022/24, Juan Remirez de Esparza"
__credits__ = ["Juan Remirez de Esparza"]
__license__ = "MIT"
__module__ = "HwPanel"
__version__ = "1.0.1"
__date__ = "2024-12-29"
__version_highlight__ = "HwPanel - First version"
__maintainer__ = "Juan Remirez de Esparza"
__email__ = "jremirez@hotmail.com"
__status__ = "Development"

"""
FUNCTION	    BUTTON or
		        Extra PIN	LED NOTE
--------        ---------   --- ----
Movie Forward	1		    1	ON*
Rewind		    1		    1	ON*
Forward		    1		    1	ON*
Focus View	    1		    1	ON-OFF
Zoom View	    1		    1	ON-OFF
Zoom Joystick	3	    		Set Focus Zoom view Position
Zoom +-		    2	    		Focus Zoom View IN/Out
Auto Exposure	1		    1	ON-OFF
Exposure Value	3		    1	Rotary Encoder	
AWB RED		    1		    1	ON-OFF
Red Value	    3		    1	Rotary Encoder
AWB BLUE	    1		    1	ON-OFF
Blue Value	    3		    1	Rotary Encoder
START Scan	    1		    1	ON*
STOP		    1		    1	OFF all/every ON*
FilmType	    1		    2	Switch FilmType
Movie Backward	1		    1	
Unlock reels	1		    1
Time Counter 	1			    Send to Extra HwPanel Nano
Reset Frame	    1			    Reset Scanned Frame and Time Counter
Raspb.ry OnOff	2		    1	Turn ON and OFF Raspberry
Raspb.ry SD LED			    1	Raspberry SD Read/Write Activity LED
HDMI no Signal			    1	HDMI no Signal LED at Shutdown
		__________________
TOTAL		31		20
		__________________
TOTAL			51


using 4 x MCP23017
remaining available 13 extra pins
"""

class HwPanel():
    """
    Singleton class - ensures only one instance is ever created.
    """
    _instance = None
    ExitingApp = False
    active = ''
    hwpanel_after = None
    hwpanel_first_i2c_add = 0x20
    hwpanel_num_i2c_add = 4
    hwpanel_current_add = 0 # Round robin counter to poll all MCP23017 chip addresses

    # Panel 'buttons'
    HWPANEL_REGISTER = 1
    HWPANEL_START_STOP  = 2
    HWPANEL_FORWARD = 3
    HWPANEL_BACKWARD = 4
    HWPANEL_FF = 5
    HWPANEL_RW = 6

    rpi_after = None
    rpi_i2c_add = 17
    AltScan8Callback = None

    CMD_GET_CNT_STATUS = 2

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, master_win, callback):
        print("Entered HwPanel.__init__")
        if not hasattr(self, 'initialized'):
            self.main_win = master_win
            self.AltScan8Callback = callback
            # Use self.AltScan8Callback to call functions on ALT-Scann8 UI
            print(f"hwpanel initialized: win={master_win}, self.main_win={self.main_win}, callback={callback}")
            self.register_to_altscann8()
            self.initialized = True

    def init_completed(self):
        pass
        # Replace pass statement with whatever you want to do at init time

    def shutdown_started(self):
        global ExitingApp
        self.ExitingApp = True
        # Add more statements with whatever you want to do at termination time

    def captured_frame(self):
        pass
        # Replace pass statement with whatever you want to do when a frame is captured

    def register_to_altscann8(self):
        self.AltScan8Callback(self.HWPANEL_REGISTER, True)

    def start_stop_scan(self):
        self.AltScan8Callback(self.HWPANEL_START_STOP, None)

    def fast_forward(self):
        self.AltScan8Callback(self.HWPANEL_FF, None)

    def rewind(self):
        self.AltScan8Callback(self.HWPANEL_RW, None)

    def film_forward(self):
        self.AltScan8Callback(self.HWPANEL_FORWARD, None)

    def film_backward(self):
        self.AltScan8Callback(self.HWPANEL_BACKWARD, None)

    def film_in_filmgate_warning(self):
        # Mariano: Implement her ewhichever code is required to determine next step usign panel inputs
        # Return 'False' to cancel Rewind/FF operation, 'True' to proceed with it despite the issue
        return False    # By default return cancel
