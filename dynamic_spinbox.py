"""
****************************************************************************************************************
Class DynamicSpinbox
Custom Spinbox to block keyboard entries while scanning
Since we allow invalid values to be entered in spinboxes (to enter '100' in a field validated to be between 100
and 600 you need to start typing a '1'), we need to be carefull ti doesn't happen while scanning, since a wrong
value could break the process. Therefore while scanning values can only be tuned using arrow keys or spinbox
arrows, since then the limits are enforced by the spinbox and it is not possible to produce invalid values
****************************************************************************************************************
"""
__author__ = 'Juan Remirez de Esparza'
__copyright__ = "Copyright 2022/24, Juan Remirez de Esparza"
__credits__ = ["Juan Remirez de Esparza"]
__license__ = "MIT"
__module__ = "DynamicSpinbox"
__version__ = "1.0.1"
__date__ = "2024-02-19"
__version_highlight__ = "DynamicSpinbox - Class extracted to dedicated file"
__maintainer__ = "Juan Remirez de Esparza"
__email__ = "jremirez@hotmail.com"
__status__ = "Development"


from tkinter import Spinbox

class DynamicSpinbox(Spinbox):
    def __init__(self, master=None, custom_state=None, **kwargs):
        super().__init__(master, **kwargs)
        self.block_keyboard_entry = False  # Flag to indicate whether keyboard entry is blocked
        self._custom_state = custom_state

        # Bind keyboard events
        self.bind("<KeyPress>", self.on_key_press)
        self.bind("<KeyRelease>", self.on_key_release)

    def on_key_press(self, event):
        disabled = self.config('state')[-1] == 'readonly'
        # Block keyboard entry if the flag is set
        if disabled and event.keysym not in {'Tab', 'ISO_Left_Tab'} or self._custom_state == 'block_kbd_entry' and event.keysym not in {'Up', 'Down', 'Left', 'Right', 'Tab', 'ISO_Left_Tab'}:
            return "break"

    def on_key_release(self, event):
        # Release the block on key release
        pass

    def set_custom_state(self, value):
        self._custom_state = value
