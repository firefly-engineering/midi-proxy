import unittest
from unittest.mock import MagicMock, patch, call
import time # For potential timing related tests if any

# Add client directory to sys.path to allow direct import
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from client.client import Client, SYSEX_START, SYSEX_END, MANUFACTURER_ID, DEVICE_ID_CLIENT_TARGETS,                           UNIVERSAL_NON_REALTIME_SYSEX, GENERAL_INFORMATION, IDENTITY_REQUEST_MSG_ID,                           COMMAND_SET_PARAMETER, COMMAND_GET_PARAMETER, COMMAND_TRIGGER_ACTION

# Define a name for the mock client ports that won't conflict with real ports
MOCK_CLIENT_PORT_NAME = "MockTestClient"

class TestClientUnit(unittest.TestCase):

    @patch('client.client.rtmidi.MidiIn')
    @patch('client.client.rtmidi.MidiOut')
    def setUp(self, MockMidiOut, MockMidiIn):
        # Instantiate mocks for MidiIn and MidiOut
        self.mock_midi_in_instance = MockMidiIn.return_value
        self.mock_midi_out_instance = MockMidiOut.return_value

        # Configure mocks to simulate successful port opening
        self.mock_midi_in_instance.is_port_open.return_value = True
        self.mock_midi_out_instance.is_port_open.return_value = True
        self.mock_midi_in_instance.get_ports.return_value = [] # Default for connect_to_device
        self.mock_midi_out_instance.get_ports.return_value = [] # Default for connect_to_device

        # Store the callback
        self.callback_info = {'function': None, 'data': None}

        def mock_set_callback(func, data=None):
            self.callback_info['function'] = func
            self.callback_info['data'] = data

        self.mock_midi_in_instance.set_callback = mock_set_callback

        # Create Client instance. This will call _open_client_ports
        self.client = Client(client_port_name=MOCK_CLIENT_PORT_NAME)

        # Clear any messages that might have been logged during init by print statements
        self.client.clear_received_messages()


    def tearDown(self):
        self.client.shutdown()
        # Reset mocks if necessary, though typically new mocks are created per test method by @patch
        pass

    def test_client_opens_virtual_ports_on_init(self):
        # Check if open_virtual_port was called on the mock instances
        self.mock_midi_in_instance.open_virtual_port.assert_called_with(f"{MOCK_CLIENT_PORT_NAME} In")
        self.mock_midi_out_instance.open_virtual_port.assert_called_with(f"{MOCK_CLIENT_PORT_NAME} Out")
        self.assertIsNotNone(self.callback_info['function'], "Callback should be set on MIDI input.")

    def test_send_midi_message(self):
        test_message = [0x90, 0x3C, 0x7F] # Note On
        self.client.send_midi_message(test_message)
        self.mock_midi_out_instance.send_message.assert_called_once_with(test_message)

    def test_receive_midi_message_callback(self):
        # Simulate a message arrival via the callback
        test_midi_message = ([0xB0, 0x07, 0x7F], 0.0) # Control Change, delta time

        # Ensure callback is set up
        self.assertIsNotNone(self.callback_info['function'])

        # Call the callback directly
        self.callback_info['function'](test_midi_message, self.callback_info['data'])

        received = self.client.pop_received_message(timeout_sec=0.01) # Should be instant
        self.assertEqual(received, test_midi_message[0])

    def test_pop_received_message_timeout(self):
        message = self.client.pop_received_message(timeout_sec=0.01)
        self.assertIsNone(message, "Should return None if no message received within timeout")

    def test_clear_received_messages(self):
        # Simulate a message arrival
        test_midi_message = ([0x90, 0x40, 0x70], 0.0)
        self.callback_info['function'](test_midi_message, self.callback_info['data'])

        # Verify it's there
        self.assertIsNotNone(self.client.pop_received_message(timeout_sec=0.01))

        # Simulate another message and clear
        self.callback_info['function'](test_midi_message, self.callback_info['data'])
        self.client.clear_received_messages()
        self.assertIsNone(self.client.pop_received_message(timeout_sec=0.01), "Messages should be cleared")

    # --- Test SysEx Message Formatting ---
    def test_send_identity_request(self):
        self.client.send_identity_request()
        expected_message = [
            SYSEX_START, UNIVERSAL_NON_REALTIME_SYSEX, 0x7F,
            GENERAL_INFORMATION, IDENTITY_REQUEST_MSG_ID, SYSEX_END
        ]
        self.mock_midi_out_instance.send_message.assert_called_once_with(expected_message)

    def test_send_set_parameter(self):
        param_id, param_val = 0x10, 0x5A
        self.client.send_set_parameter(param_id, param_val)
        expected_message = [
            SYSEX_START, MANUFACTURER_ID, DEVICE_ID_CLIENT_TARGETS,
            COMMAND_SET_PARAMETER, param_id, param_val, SYSEX_END
        ]
        self.mock_midi_out_instance.send_message.assert_called_once_with(expected_message)

    def test_send_get_parameter(self):
        param_id = 0x12
        self.client.send_get_parameter(param_id)
        expected_message = [
            SYSEX_START, MANUFACTURER_ID, DEVICE_ID_CLIENT_TARGETS,
            COMMAND_GET_PARAMETER, param_id, SYSEX_END
        ]
        self.mock_midi_out_instance.send_message.assert_called_once_with(expected_message)

    def test_send_trigger_action(self):
        action_id = 0x05
        self.client.send_trigger_action(action_id)
        expected_message = [
            SYSEX_START, MANUFACTURER_ID, DEVICE_ID_CLIENT_TARGETS,
            COMMAND_TRIGGER_ACTION, action_id, SYSEX_END
        ]
        self.mock_midi_out_instance.send_message.assert_called_once_with(expected_message)

    @patch('client.client.rtmidi.MidiOut') # Need fresh MidiOut for this test
    @patch('client.client.rtmidi.MidiIn')
    def test_connect_to_device_success(self, MockMidiInAgain, MockMidiOutAgain):
        # Setup fresh mocks for this specific test to control get_ports
        mock_in = MockMidiInAgain.return_value
        mock_out = MockMidiOutAgain.return_value

        mock_in.is_port_open.return_value = True # Simulates virtual port being open initially
        mock_out.is_port_open.return_value = True

        device_in_port_name = "MockDevice MIDI In"
        device_out_port_name = "MockDevice MIDI Out"

        # Simulate get_ports returning the target device ports
        mock_out.get_ports.return_value = ["Other Port", device_in_port_name, "Another Port"]
        mock_in.get_ports.return_value = [device_out_port_name, "Some Other Input"]

        # Create a new client instance for this test to use the new mocks for port opening
        client_for_connect_test = Client(client_port_name="ConnectClient")

        # Override the default mock instances with the ones for this test
        client_for_connect_test.midi_in = mock_in
        client_for_connect_test.midi_out = mock_out

        # Mock the set_callback method on the fresh mock_in
        mock_in.set_callback = MagicMock()


        result = client_for_connect_test.connect_to_device(
            device_in_port_name_substr="MockDevice MIDI In",
            device_out_port_name_substr="MockDevice MIDI Out"
        )
        self.assertTrue(result, "Connection should be successful")

        # Check that close_port was called (to close virtual) and open_port was called (to connect to specific)
        mock_out.close_port.assert_called_once()
        mock_out.open_port.assert_called_once_with(1) # Index of "MockDevice MIDI In"

        mock_in.close_port.assert_called_once()
        mock_in.open_port.assert_called_once_with(0) # Index of "MockDevice MIDI Out"
        mock_in.set_callback.assert_called() # Callback should be re-set

        client_for_connect_test.shutdown()


    @patch('client.client.rtmidi.MidiOut')
    @patch('client.client.rtmidi.MidiIn')
    def test_connect_to_device_fail_input_not_found(self, MockMidiInAgain, MockMidiOutAgain):
        mock_in = MockMidiInAgain.return_value
        mock_out = MockMidiOutAgain.return_value
        mock_in.is_port_open.return_value = True
        mock_out.is_port_open.return_value = True

        device_in_port_name = "MockDevice MIDI In"

        mock_out.get_ports.return_value = [device_in_port_name]
        mock_in.get_ports.return_value = ["Some Other Input"] # Target device output not present

        client_for_connect_test = Client(client_port_name="ConnectFailClient")
        client_for_connect_test.midi_in = mock_in
        client_for_connect_test.midi_out = mock_out

        # Need to mock open_virtual_port on these instances as it's called in _open_client_ports
        mock_in.open_virtual_port = MagicMock()
        mock_out.open_virtual_port = MagicMock()
        def mock_set_callback_local(func, data=None): pass
        mock_in.set_callback = mock_set_callback_local


        result = client_for_connect_test.connect_to_device(
            device_in_port_name_substr="MockDevice MIDI In",
            device_out_port_name_substr="NonExistentDeviceOutput"
        )
        self.assertFalse(result, "Connection should fail if device output port not found")

        # Check that it attempts to re-open client's own virtual input port
        mock_in.open_virtual_port.assert_called_with(f"ConnectFailClient In")

        client_for_connect_test.shutdown()

    def test_shutdown_closes_ports(self):
        # This test relies on the mocks set up in setUp
        self.client.shutdown()
        self.mock_midi_in_instance.close_port.assert_called_once()
        self.mock_midi_out_instance.close_port.assert_called_once()
        # Check if 'del' was called - this is harder to check directly for instance variables.
        # We rely on the print statements in the actual shutdown for now, or by checking
        # if the objects are truly gone if we had access, but for unit tests,
        # checking close_port is the primary interaction.


if __name__ == '__main__':
    unittest.main()
