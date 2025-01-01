"""
****************************************************************************************************************
Class CameraResolutions
Upon creation, extracts from the camera (using PiCamera2 sensor_modes) a list of supported resolutions and
associated attributes (exposure range, format)
In case of simulated run, it uses a copy of the info returned for the Raspberry Pi HD camera.
****************************************************************************************************************
"""
__author__ = 'Juan Remirez de Esparza'
__copyright__ = "Copyright 2022/24, Juan Remirez de Esparza"
__credits__ = ["Juan Remirez de Esparza"]
__license__ = "MIT"
__module__ = "CameraResolutions"
__version__ = "1.0.2"
__date__ = "2025-01-01"
__version_highlight__ = "Set default lower resolution to 1 usec"
__maintainer__ = "Juan Remirez de Esparza"
__email__ = "jremirez@hotmail.com"
__status__ = "Development"

class CameraResolutions():
    """
    Singleton class - ensures only one instance is ever created.
    """
    _instance = None
    resolution_dict = {}
    active = ''

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, camera_sensor_modes):
        if not hasattr(self, 'initialized'):
            self.resolution_dict.clear()
            # Identify the smallest sensor resolution that will fix the two extra resolutions ("1024x768", "640x480")
            aux_width = 10000
            aux_height = 10000
            aux_key = None
            # Add dictionary entries where the key is the value shown in the drop down list (XxY)
            for mode in camera_sensor_modes:
                key = f"{mode['size'][0]}x{mode['size'][1]}"
                if mode['crop_limits'][0] != 0 or mode['crop_limits'][1] != 0:
                    key = key + ' *'
                self.resolution_dict[key] = {}
                self.resolution_dict[key]['sensor_resolution'] = mode['size']
                self.resolution_dict[key]['image_resolution'] = mode['size']
                if 1024 < mode['size'][0] < aux_width and 768 < mode['size'][1] < aux_height:
                    aux_width = mode['size'][1]
                    aux_height = mode['size'][1]
                    aux_key = key
                self.resolution_dict[key]['format'] = mode['format'].format
                # self.resolution_dict[key]['min_exp'] = mode['exposure_limits'][0]
                # self.resolution_dict[key]['max_exp'] = mode['exposure_limits'][1]
                # Force lower exposure range 0-1sec
                self.resolution_dict[key]['min_exp'] = 1
                self.resolution_dict[key]['max_exp'] = 1000000
            # Add two extra resolutions - "1024x768", "640x480"
            if aux_key is not None:
                aux_entry = self.resolution_dict[aux_key]
                self.resolution_dict['1024x768 *'] = {}
                self.resolution_dict['1024x768 *']['sensor_resolution'] = aux_entry['sensor_resolution']
                self.resolution_dict['1024x768 *']['image_resolution'] = (1024, 768)
                self.resolution_dict['1024x768 *']['min_exp'] = aux_entry['min_exp']
                self.resolution_dict['1024x768 *']['max_exp'] = aux_entry['max_exp']
                self.resolution_dict['1024x768 *']['format'] = aux_entry['format']
                self.resolution_dict['640x480 *'] = {}
                self.resolution_dict['640x480 *']['sensor_resolution'] = aux_entry['sensor_resolution']
                self.resolution_dict['640x480 *']['image_resolution'] = (640, 480)
                self.resolution_dict['640x480 *']['min_exp'] = aux_entry['min_exp']
                self.resolution_dict['640x480 *']['max_exp'] = aux_entry['max_exp']
                self.resolution_dict['640x480 *']['format'] = aux_entry['format']

            first_entry_key = next(iter(self.resolution_dict))  # Get the key of the first entry
            self.active = self.resolution_dict[first_entry_key]
            self.initialized = True

    def get_list(self):
        return list(self.resolution_dict.keys())

    def get_format(self, resolution=None):
        if resolution is None:
            return self.active['format']
        else:
            return self.resolution_dict[resolution]['format']

    def get_sensor_resolution(self, resolution=None):
        if resolution is None:
            return self.active['sensor_resolution']
        else:
            return self.resolution_dict[resolution]['sensor_resolution']

    def get_image_resolution(self, resolution=None):
        if resolution is None:
            return self.active['image_resolution']
        else:
            return self.resolution_dict[resolution]['image_resolution']

    def get_min_exp(self, resolution=None):
        if resolution is None:
            return self.active['min_exp']
        else:
            return self.resolution_dict[resolution]['min_exp']

    def get_max_exp(self, resolution=None):
        if resolution is None:
            return self.active['max_exp']
        else:
            return self.resolution_dict[resolution]['max_exp']

    def set_active(self, resolution):
        self.active = self.resolution_dict[resolution]

    def get_active(self):
        return self.active


