import unittest
import time
import rtmidi # type: ignore
import os
import threading # To run device in a separate thread

# Assuming device.py is in the parent directory or PYTHONPATH is set up
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from device.device import Device, LOG_FILE_NAME, MANUFACTURER_ID, DEVICE_ID_SYSEX, COMMAND_TRIGGER_ACTION, ACTION_ID_LOG

# SysEx constants for test messages
SYSEX_START = 0xF0
SYSEX_END = 0xF7
UNIVERSAL_NON_REALTIME_SYSEX = 0x7E
GENERAL_INFORMATION = 0x06
IDENTITY_REQUEST_MSG = 0x01
IDENTITY_REPLY_MSG = 0x02

TEST_DEVICE_PORT_NAME = "TestMIDIDevice"
CLIENT_PORT_NAME_OUT = "TestClientOut"
CLIENT_PORT_NAME_IN = "TestClientIn"

class TestDeviceSysExHandling(unittest.TestCase):

    def setUp(self):
        self.device_instance = None
        self.device_thread = None
        self.midi_out_to_device = rtmidi.MidiOut()
        self.midi_in_from_device = rtmidi.MidiIn()
        self.received_messages = []

        # Open client output port to send to device's input
        self.midi_out_to_device.open_virtual_port(CLIENT_PORT_NAME_OUT)
        # Open client input port to receive from device's output
        self.midi_in_from_device.open_virtual_port(CLIENT_PORT_NAME_IN)

        # Callback for capturing messages from device
        self.midi_in_from_device.set_callback(self._message_callback)

        # Ensure log file is clean before test (Device also does this on init)
        if os.path.exists(LOG_FILE_NAME):
            os.remove(LOG_FILE_NAME)

    def _message_callback(self, message, data):
        msg_bytes, deltatime = message
        print(f"TestClient: Received MIDI: {msg_bytes}")
        self.received_messages.append(list(msg_bytes))

    def _start_device(self):
        self.device_instance = Device(port_name=TEST_DEVICE_PORT_NAME)
        # Connect client output to device input
        # Connect device output to client input
        # This relies on rtmidi's port naming and discovery.
        # We assume the virtual ports become available for connection.
        # Note: rtmidi doesn't have explicit connect, it's about opening ports with known names
        # or finding them and opening by index.

        # For virtual ports, we send from CLIENT_PORT_NAME_OUT to TEST_DEVICE_PORT_NAME In
        # and receive on CLIENT_PORT_NAME_IN from TEST_DEVICE_PORT_NAME Out.
        # The Device class opens its ports as TEST_DEVICE_PORT_NAME In/Out.
        # The test client opens CLIENT_PORT_NAME_OUT and CLIENT_PORT_NAME_IN.

        # Find and open the device's input port for the client's output
        time.sleep(0.2) # Give time for device ports to register
        found_port = False
        for i, port_name in enumerate(self.midi_out_to_device.get_ports()):
            if TEST_DEVICE_PORT_NAME + " In" in port_name:
                try:
                    self.midi_out_to_device.close_port() # Close virtual if open
                    self.midi_out_to_device.open_port(i, name=CLIENT_PORT_NAME_OUT) # name is for ALSA
                    print(f"TestClient: Output connected to {port_name}")
                    found_port = True
                    break
                except rtmidi.RtMidiError as e:
                    print(f"TestClient: Failed to open output port {port_name} for sending: {e}")
        if not found_port:
             print(f"TestClient: Could not find device input port '{TEST_DEVICE_PORT_NAME} In' to connect client output. Available: {self.midi_out_to_device.get_ports()}")

        # Find and open the device's output port for the client's input
        found_port = False
        for i, port_name in enumerate(self.midi_in_from_device.get_ports()):
            if TEST_DEVICE_PORT_NAME + " Out" in port_name:
                try:
                    self.midi_in_from_device.close_port() # Close virtual if open
                    self.midi_in_from_device.open_port(i, name=CLIENT_PORT_NAME_IN)
                    self.midi_in_from_device.set_callback(self._message_callback) # re-set callback
                    print(f"TestClient: Input connected to {port_name}")
                    found_port = True
                    break
                except rtmidi.RtMidiError as e:
                     print(f"TestClient: Failed to open input port {port_name} for receiving: {e}")
        if not found_port:
            print(f"TestClient: Could not find device output port '{TEST_DEVICE_PORT_NAME} Out' to connect client input. Available: {self.midi_in_from_device.get_ports()}")


        self.device_thread = threading.Thread(target=self.device_instance.run, daemon=True)
        self.device_thread.start()
        time.sleep(0.5) # Allow device to fully initialize and open ports

    def tearDown(self):
        if self.device_instance:
            self.device_instance.shutdown_flag = True # Signal shutdown
            if self.device_thread:
                 self.device_thread.join(timeout=2) # Wait for thread to finish

        # Close client ports
        if self.midi_out_to_device.is_port_open():
            self.midi_out_to_device.close_port()
        del self.midi_out_to_device

        if self.midi_in_from_device.is_port_open():
            self.midi_in_from_device.close_port()
        del self.midi_in_from_device

        # Clean up log file after tests if it was created
        # if os.path.exists(LOG_FILE_NAME):
        #     os.remove(LOG_FILE_NAME) # Device clears it on init, so maybe not needed here.
        print("TestClient: Teardown complete.")

    def test_identity_request(self):
        print("\nTestClient: Running test_identity_request")
        self._start_device()
        if not self.midi_out_to_device.is_port_open() or not self.midi_in_from_device.is_port_open():
            self.skipTest("MIDI ports for testing device not properly opened. Skipping test.")

        identity_request_sysex = [
            SYSEX_START,
            UNIVERSAL_NON_REALTIME_SYSEX,
            0x7F,  # Device ID (All Call)
            GENERAL_INFORMATION,
            IDENTITY_REQUEST_MSG,
            SYSEX_END
        ]

        print(f"TestClient: Sending Identity Request: {identity_request_sysex}")
        self.midi_out_to_device.send_message(identity_request_sysex)
        time.sleep(0.5)  # Give device time to respond

        self.assertTrue(len(self.received_messages) > 0, "Device did not send any message in response.")

        expected_reply = [
            SYSEX_START,
            UNIVERSAL_NON_REALTIME_SYSEX,
            0x7F, # Device ID for reply to all-call
            GENERAL_INFORMATION,
            IDENTITY_REPLY_MSG,
            MANUFACTURER_ID,     # 0x7D
            0x01, 0x01,          # Device Family LSB, MSB
            0x01, 0x01,          # Device Model LSB, MSB
            0x01, 0x01, 0x01, 0x01, # Version LSB, MSB, B2, B3
            SYSEX_END
        ]
        self.assertIn(expected_reply, self.received_messages,
                        f"Device did not send correct Identity Reply. Expected: {expected_reply}, Got: {self.received_messages}")
        print("TestClient: test_identity_request PASSED")

    def test_trigger_action_log_and_ack(self):
        print("\nTestClient: Running test_trigger_action_log_and_ack")
        self._start_device()
        if not self.midi_out_to_device.is_port_open() or not self.midi_in_from_device.is_port_open():
            self.skipTest("MIDI ports for testing device not properly opened. Skipping test.")

        action_id_to_log = ACTION_ID_LOG # 0x01
        trigger_action_sysex = [
            SYSEX_START,
            MANUFACTURER_ID,    # 0x7D
            DEVICE_ID_SYSEX,    # 0x01 (Our virtual device's ID)
            COMMAND_TRIGGER_ACTION, # 0x03
            action_id_to_log,   # Action ID
            SYSEX_END
        ]

        print(f"TestClient: Sending Trigger Action: {trigger_action_sysex}")
        self.midi_out_to_device.send_message(trigger_action_sysex)
        time.sleep(0.5)  # Give device time to process, log, and ACK

        # 1. Check for ACK (echoed message)
        self.assertTrue(len(self.received_messages) > 0, "Device did not send any message (ACK) in response.")
        self.assertIn(trigger_action_sysex, self.received_messages,
                        f"Device did not ACK TriggerAction correctly. Expected: {trigger_action_sysex}, Got: {self.received_messages}")

        # 2. Check log file content
        self.assertTrue(os.path.exists(LOG_FILE_NAME), f"Log file '{LOG_FILE_NAME}' was not created.")
        with open(LOG_FILE_NAME, 'r') as f:
            log_content = f.read()

        expected_log_entry_part = f"TriggerAction: ID={action_id_to_log}, FullMsg={trigger_action_sysex}"
        self.assertIn(expected_log_entry_part, log_content,
                        f"Log file does not contain expected entry. Expected part: '{expected_log_entry_part}', Got: '{log_content}'")
        print("TestClient: test_trigger_action_log_and_ack PASSED")

if __name__ == '__main__':
    unittest.main()
