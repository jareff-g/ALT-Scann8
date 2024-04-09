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
__version__ = "1.0.0"
__date__ = "2024-02-24"
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
    hwpanel_first_add = 0x20
    hwpanel_num_add = 4
    hwpanel_current_add = 0 # Round robin counter to poll all MCP23017 chip addresses
    CMD_GET_CNT_STATUS = 2

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, master_win, i2c):
        if not hasattr(self, 'initialized'):
            self.main_win = master_win
            self.i2c = i2c
            print(f"master_win: {master_win}, self.main_win: {self.main_win}")
            self.hwpanel_after = self.main_win.after(10, self.hwpanel_listen_loop)

    def hwpanel_listen_loop(self):  # Waits for events from MCP23017 chips
        try:
            HwPanelData = self.i2c.read_i2c_block_data(self.hwpanel_first_add+self.hwpanel_current_add, self.CMD_GET_CNT_STATUS, 5)
            HwPanelTrigger = HwPanelData[0]
            HwPanelParam1 = HwPanelData[1] * 256 + HwPanelData[2]
            HwPanelParam2 = HwPanelData[3] * 256 + HwPanelData[4]  # Sometimes this part arrives as 255, 255, no idea why
            hwpanel_current_add += 1
            hwpanel_current_add %= hwpanel_num_add
        except IOError as e:
            HwPanelTrigger = 0
            # Log error to console
            # When error is 121, not really an error, means HwPanel has nothing to data available for us
            if e.errno != 121:
                logging.warning(
                    f"Non-critical IOError ({e}) while checking incoming event from HwPanel. Will check again.")

        if HwPanelTrigger == 0:  # Do nothing
            pass
        # Code below just an example, to be redefined
        elif HwPanelTrigger == 1:  # Button 1
            pass
        elif HwPanelTrigger == 2:
            pass
        elif HwPanelTrigger == 2:
            pass

        if not self.ExitingApp:
            self.hwpanel_after = self.main_win.after(10, self.hwpanel_listen_loop)

    def ALT_Scann8_init_completed(self):
        pass
        # Replace pass statement with whatever you want to do at init time

    def ALT_Scann8_shutdown_started(self):
        global ExitingApp
        self.ExitingApp = True
        # Add more statements with whatever you want to do at termination time

    def ALT_Scann8_captured_frame(self):
        pass
        # Replace pass statement with whatever you want to do when a frame is captured
