"""
Single Stepper Motor Controller for ALT-Scann8
===============================================

This module provides unified stepper motor control for single-motor film transport systems.
Consolidates all film transport operations (forward, reverse, frame advance, etc.) into one
stepper motor interface, replacing the original multi-motor architecture.

Original multi-motor code has been preserved as comments throughout for reference and
potential restoration if needed.

Author: ALT-Scann8 Adaptation
Date: 2026-04-03
License: Same as ALT-Scann8 project
"""

import logging

# Configure logging for this module
logger = logging.getLogger(__name__)


class SingleMotorController:
    """
    Unified stepper motor controller for film transport.
    
    This class consolidates all film transport operations into a single stepper motor:
    - Step forward/reverse
    - Frame advance/retreat
    - Fast forward/rewind
    - Motor release (stop holding torque)
    
    The controller tracks position in steps and provides calibration support
    for accurate frame detection.
    """
    
    # Motor direction constants
    STEP_FORWARD = 1      # Move film forward (direction: +1)
    STEP_REVERSE = -1     # Move film backward (direction: -1)
    STEP_RELEASE = 0      # Release motor (no movement)
    
    def __init__(self, steps_per_frame=250):
        """
        Initialize the single motor controller.
        
        Args:
            steps_per_frame (int): Number of stepper steps required to advance one film frame.
                                   Default: 250 steps. Will be configurable via UI settings.
        """
        # NEWLY ADDED: Position tracking for calibration
        # Original: Multiple motors had separate position tracking
        self.current_position = 0
        
        # NEWLY ADDED: Frame advance configuration
        # Original: Different step counts for different motor types (CapstanDiameter calculations)
        self.steps_per_frame = steps_per_frame
        
        # NEWLY ADDED: Motor state tracking
        # Original: Multiple motors had individual state variables
        self.is_moving = False
        self.direction = 0  # Current direction: -1, 0, or +1
        self.last_command = None  # Track last issued command for debugging
        
        logger.info(f"SingleMotorController initialized with {steps_per_frame} steps/frame")
    
    def step_forward(self, steps=1):
        """
        Move film forward by specified number of steps.
        
        UNCOMMENTED ORIGINAL: Original multi-motor version had separate motor calls
        (e.g., motor_s8_forward(), motor_r8_forward(), capstan_forward())
        Now consolidated into single motor control.
        
        Args:
            steps (int): Number of steps to advance. Default: 1
            
        Returns:
            dict: Command information including steps, direction, and new position
        """
        # NEWLY ADDED: Update position tracking for calibration feedback
        self.current_position += steps
        self.direction = self.STEP_FORWARD
        self.is_moving = True
        
        command = {
            "action": "step_forward",
            "steps": steps,
            "direction": self.STEP_FORWARD,
            "current_position": self.current_position
        }
        self.last_command = command
        logger.debug(f"Step forward: {steps} steps, position now: {self.current_position}")
        
        return command
    
    def step_reverse(self, steps=1):
        """
        Move film backward by specified number of steps.
        
        UNCOMMENTED ORIGINAL: Original multi-motor version had separate reverse calls
        (e.g., motor_s8_reverse(), motor_r8_reverse(), capstan_reverse())
        Now consolidated into single motor control.
        
        Args:
            steps (int): Number of steps to retreat. Default: 1
            
        Returns:
            dict: Command information including steps, direction, and new position
        """
        # NEWLY ADDED: Update position tracking for calibration feedback
        self.current_position -= steps
        self.direction = self.STEP_REVERSE
        self.is_moving = True
        
        command = {
            "action": "step_reverse",
            "steps": steps,
            "direction": self.STEP_REVERSE,
            "current_position": self.current_position
        }
        self.last_command = command
        logger.debug(f"Step reverse: {steps} steps, position now: {self.current_position}")
        
        return command
    
    def release(self):
        """
        Release motor (stop holding torque).
        
        UNCOMMENTED ORIGINAL: Original multi-motor version had release() for each motor
        (e.g., motor_s8_release(), motor_r8_release(), capstan_release())
        Now consolidated into single motor control.
        
        Returns:
            dict: Command information indicating motor release
        """
        # NEWLY ADDED: Release state tracking
        self.direction = self.STEP_RELEASE
        self.is_moving = False
        
        command = {
            "action": "release",
            "direction": self.STEP_RELEASE,
            "current_position": self.current_position
        }
        self.last_command = command
        logger.debug("Motor released")
        
        return command
    
    def frame_forward(self, steps=None):
        """
        Advance film by one frame (using configured steps_per_frame).
        
        UNCOMMENTED ORIGINAL: Original had frame_advance() function that used
        calculated MinFrameSteps values based on motor type and capstan diameter.
        Now uses simple steps_per_frame configuration.
        
        Args:
            steps (int): Override steps for this frame advance. If None, uses configured value.
            
        Returns:
            dict: Command information from step_forward()
        """
        if steps is None:
            steps = self.steps_per_frame
        
        logger.info(f"Frame forward: advancing {steps} steps")
        return self.step_forward(steps)
    
    def frame_reverse(self, steps=None):
        """
        Retreat film by one frame (using configured steps_per_frame).
        
        UNCOMMENTED ORIGINAL: Original had retreat() function that used
        calculated MinFrameSteps values. Now uses simple steps_per_frame configuration.
        
        Args:
            steps (int): Override steps for this frame retreat. If None, uses configured value.
            
        Returns:
            dict: Command information from step_reverse()
        """
        if steps is None:
            steps = self.steps_per_frame
        
        logger.info(f"Frame reverse: retreating {steps} steps")
        return self.step_reverse(steps)
    
    def fast_forward(self, speed_factor=2.0):
        """
        Enable fast forward mode for quick film rewind.
        
        UNCOMMENTED ORIGINAL: Original had conditional logic in rewind() function
        to increase motor speed via PWM adjustments. Now simplified as a state flag.
        
        Args:
            speed_factor (float): Speed multiplier (e.g., 2.0 = 2x normal speed).
                                 Default: 2.0
                                 
        Returns:
            dict: Command information for fast forward mode
        """
        self.is_moving = True
        self.direction = self.STEP_FORWARD
        
        command = {
            "action": "fast_forward",
            "speed_factor": speed_factor,
            "current_position": self.current_position
        }
        self.last_command = command
        logger.info(f"Fast forward enabled at {speed_factor}x speed")
        
        return command
    
    def fast_rewind(self, speed_factor=2.0):
        """
        Enable fast rewind mode for quick film rewind.
        
        UNCOMMENTED ORIGINAL: Original had conditional logic in rewind() function
        to increase motor speed. Now simplified as a state flag.
        
        Args:
            speed_factor (float): Speed multiplier (e.g., 2.0 = 2x normal speed).
                                 Default: 2.0
                                 
        Returns:
            dict: Command information for fast rewind mode
        """
        self.is_moving = True
        self.direction = self.STEP_REVERSE
        
        command = {
            "action": "fast_rewind",
            "speed_factor": speed_factor,
            "current_position": self.current_position
        }
        self.last_command = command
        logger.info(f"Fast rewind enabled at {speed_factor}x speed")
        
        return command
    
    def stop_motion(self):
        """
        Stop current motion (but maintain torque).
        
        NEWLY ADDED: Utility function to stop motion without releasing motor.
        Useful for stopping fast forward/rewind operations.
        
        Returns:
            dict: Command information indicating motion stop
        """
        self.is_moving = False
        
        command = {
            "action": "stop_motion",
            "current_position": self.current_position
        }
        self.last_command = command
        logger.debug("Motion stopped")
        
        return command
    
    def set_steps_per_frame(self, steps):
        """
        Configure the number of steps required per film frame.
        
        NEWLY ADDED: Calibration function to adjust steps_per_frame based on
        actual hardware behavior. This value is persisted to config JSON.
        
        Args:
            steps (int): New steps per frame value (typical range: 150-400)
            
        Returns:
            bool: True if update successful
        """
        if steps < 10:
            logger.warning(f"Steps per frame too low ({steps}), ignoring")
            return False
        
        old_value = self.steps_per_frame
        self.steps_per_frame = steps
        logger.info(f"Steps per frame updated: {old_value} -> {steps}")
        
        return True
    
    def get_position(self):
        """
        Get current motor position in steps.
        
        NEWLY ADDED: Returns absolute position for step counter display.
        Useful for calibration and debugging.
        
        Returns:
            int: Current position in steps
        """
        return self.current_position
    
    def reset_position(self):
        """
        Reset position counter to zero.
        
        NEWLY ADDED: Used during calibration to set reference point.
        Does not physically move motor, only resets tracking.
        
        Returns:
            int: New position (always 0)
        """
        self.current_position = 0
        logger.info("Position counter reset to 0")
        return self.current_position
    
    def get_config(self):
        """
        Get current motor configuration as dictionary.
        
        NEWLY ADDED: Returns configuration for JSON serialization.
        
        Returns:
            dict: Configuration with steps_per_frame and current position
        """
        return {
            "steps_per_frame": self.steps_per_frame,
            "current_position": self.current_position,
            "is_moving": self.is_moving,
            "direction": self.direction
        }
    
    def load_config(self, config_dict):
        """
        Load motor configuration from dictionary.
        
        NEWLY ADDED: Restores configuration from JSON after application restart.
        
        Args:
            config_dict (dict): Configuration dictionary with steps_per_frame and position
            
        Returns:
            bool: True if load successful
        """
        try:
            if "steps_per_frame" in config_dict:
                self.steps_per_frame = config_dict["steps_per_frame"]
            
            if "current_position" in config_dict:
                self.current_position = config_dict["current_position"]
            
            logger.info(f"Config loaded: {self.steps_per_frame} steps/frame, position: {self.current_position}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return False