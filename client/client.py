import time
import rtmidi # type: ignore

# SysEx constants from ARCHITECTURE.md
SYSEX_START = 0xF0
SYSEX_END = 0xF7
UNIVERSAL_NON_REALTIME_SYSEX = 0x7E
GENERAL_INFORMATION = 0x06
IDENTITY_REQUEST_MSG_ID = 0x01 # ID for Identity Request message
# MANUFACTURER_ID will be used for custom messages
MANUFACTURER_ID = 0x7D # Non-Commercial
DEVICE_ID_CLIENT_TARGETS = 0x01 # Assuming client targets device with ID 0x01

# Custom Command IDs from ARCHITECTURE.md
COMMAND_SET_PARAMETER = 0x01
COMMAND_GET_PARAMETER = 0x02
COMMAND_TRIGGER_ACTION = 0x03

class Client:
    def __init__(self, client_port_name='Python Test Client'):
        self.client_port_name = client_port_name
        self.midi_in = rtmidi.MidiIn()
        self.midi_out = rtmidi.MidiOut()

        self.target_device_in_port_name = None
        self.target_device_out_port_name = None

        self._received_messages = []
        self._message_callback_event = None # For synchronization if needed

        self._open_client_ports()

    def _open_client_ports(self):
        try:
            self.midi_in.open_virtual_port(f"{self.client_port_name} In")
            print(f"Client: Opened virtual input port: {self.client_port_name} In")
        except rtmidi.RtMidiError as e:
            print(f"Client: Error opening virtual input port: {e}")
            # Fallback or error handling if needed

        try:
            self.midi_out.open_virtual_port(f"{self.client_port_name} Out")
            print(f"Client: Opened virtual output port: {self.client_port_name} Out")
        except rtmidi.RtMidiError as e:
            print(f"Client: Error opening virtual output port: {e}")
            # Fallback or error handling if needed

        if self.midi_in.is_port_open():
            self.midi_in.set_callback(self._on_midi_message)
            print("Client: MIDI callback set on input port.")
        else:
            print("Client: Client MIDI input port not open. Cannot set callback.")

    def _on_midi_message(self, message_tuple, data):
        message_bytes, deltatime = message_tuple
        print(f'Client: Raw Received MIDI: {message_bytes} (delta: {deltatime})')
        self._received_messages.append(list(message_bytes))
        # If using an event to signal message arrival:
        # if self._message_callback_event:
        #     self._message_callback_event.set()

    def connect_to_device(self, device_in_port_name_substr, device_out_port_name_substr):
        self.target_device_in_port_name = device_in_port_name_substr
        self.target_device_out_port_name = device_out_port_name_substr

        # Connect client's output to device's input port
        connected_out = False
        available_ports = self.midi_out.get_ports()
        # print(f"Client: Available MIDI output ports for connection: {available_ports}")
        for i, port_name in enumerate(available_ports):
            if self.target_device_in_port_name in port_name:
                try:
                    self.midi_out.close_port() # Close virtual port first
                    self.midi_out.open_port(i)
                    print(f"Client: Output connected to device input port: {port_name}")
                    connected_out = True
                    break
                except rtmidi.RtMidiError as e:
                    print(f"Client: Error connecting output to {port_name}: {e}")
        if not connected_out:
            print(f"Client: Could not find or connect to device input port containing '{self.target_device_in_port_name}'. Available: {available_ports}")
            return False

        # Connect client's input to device's output port
        connected_in = False
        available_ports_in = self.midi_in.get_ports()
        # print(f"Client: Available MIDI input ports for connection: {available_ports_in}")
        for i, port_name in enumerate(available_ports_in):
            if self.target_device_out_port_name in port_name:
                try:
                    self.midi_in.close_port() # Close virtual port first
                    self.midi_in.open_port(i)
                    self.midi_in.set_callback(self._on_midi_message) # Re-set callback
                    print(f"Client: Input connected to device output port: {port_name}")
                    connected_in = True
                    break
                except rtmidi.RtMidiError as e:
                    print(f"Client: Error connecting input to {port_name}: {e}")
        if not connected_in:
            print(f"Client: Could not find or connect to device output port containing '{self.target_device_out_port_name}'. Available: {available_ports_in}")
            # Attempt to re-open virtual port if connection failed
            self._open_client_ports() # This might re-open the virtual port if it was closed
            return False

        return connected_out and connected_in

    def send_midi_message(self, message_list):
        if self.midi_out.is_port_open():
            self.midi_out.send_message(message_list)
            print(f'Client: Sent MIDI: {message_list}')
        else:
            print("Client: Output port not open or not connected. Cannot send message.")

    def pop_received_message(self, timeout_sec=0.1):
        start_time = time.time()
        while (time.time() - start_time) < timeout_sec:
            if self._received_messages:
                return self._received_messages.pop(0)
            time.sleep(0.01) # short sleep to avoid busy waiting
        return None

    def clear_received_messages(self):
        self._received_messages = []

    # --- SysEx Sending Methods ---
    def send_identity_request(self):
        # Message: F0 7E 7F 06 01 F7 (Universal System Exclusive - Identity Request)
        # 7F as device ID in request means "all devices"
        message = [
            SYSEX_START,
            UNIVERSAL_NON_REALTIME_SYSEX,
            0x7F, # Target Device ID (7F for "all call")
            GENERAL_INFORMATION,
            IDENTITY_REQUEST_MSG_ID,
            SYSEX_END
        ]
        self.send_midi_message(message)

    def send_set_parameter(self, parameter_id, parameter_value):
        # Message Format: F0 7D <Device ID> <Command ID> <Parameter ID> <Parameter Value> F7
        message = [
            SYSEX_START,
            MANUFACTURER_ID,
            DEVICE_ID_CLIENT_TARGETS,
            COMMAND_SET_PARAMETER,
            parameter_id,
            parameter_value,
            SYSEX_END
        ]
        self.send_midi_message(message)

    def send_get_parameter(self, parameter_id):
        # Message Format: F0 7D <Device ID> <Command ID> <Parameter ID> F7
        message = [
            SYSEX_START,
            MANUFACTURER_ID,
            DEVICE_ID_CLIENT_TARGETS,
            COMMAND_GET_PARAMETER,
            parameter_id,
            SYSEX_END
        ]
        self.send_midi_message(message)

    def send_trigger_action(self, action_id):
        # Message Format: F0 7D <Device ID> <Command ID> <Action ID> F7
        message = [
            SYSEX_START,
            MANUFACTURER_ID,
            DEVICE_ID_CLIENT_TARGETS,
            COMMAND_TRIGGER_ACTION,
            action_id,
            SYSEX_END
        ]
        self.send_midi_message(message)

    def shutdown(self):
        print("Client: Shutting down...")
        if hasattr(self, 'midi_in') and self.midi_in:
            if self.midi_in.is_port_open():
                self.midi_in.close_port()
                print("Client: MIDI In port closed.")
            del self.midi_in

        if hasattr(self, 'midi_out') and self.midi_out:
            if self.midi_out.is_port_open():
                self.midi_out.close_port()
                print("Client: MIDI Out port closed.")
            del self.midi_out
        print("Client: Shutdown complete.")

if __name__ == '__main__':
    # Example Usage (Optional - for basic manual testing)
    print("Client: Basic test script started.")
    client = Client()

    # In a real scenario, you'd need a device running.
    # For this example, we'll just try to send.
    # These port names would correspond to a running Device instance's ports.
    DEVICE_IN_PORT_SUBSTR = "Test Device In" # Or whatever the device calls its input
    DEVICE_OUT_PORT_SUBSTR = "Test Device Out" # Or whatever the device calls its output

    print(f"Client: Attempting to connect to device ports containing '{DEVICE_IN_PORT_SUBSTR}' (for client out) and '{DEVICE_OUT_PORT_SUBSTR}' (for client in)")

    # Give a moment for ports to be potentially available if a device was just started
    time.sleep(1)

    if client.connect_to_device(DEVICE_IN_PORT_SUBSTR, DEVICE_OUT_PORT_SUBSTR):
        print("Client: Successfully connected to device ports.")
        client.send_identity_request()

        # Wait for a response (if any)
        response = client.pop_received_message(timeout_sec=1.0)
        if response:
            print(f"Client: Received response: {response}")
        else:
            print("Client: No response received for Identity Request within timeout.")

        # Example: Send a trigger action
        ACTION_ID_TEST = 0x01 # Example Action ID
        print(f"Client: Sending Trigger Action with Action ID {ACTION_ID_TEST}")
        client.send_trigger_action(ACTION_ID_TEST)
        response_action = client.pop_received_message(timeout_sec=1.0)
        if response_action:
            print(f"Client: Received response for action: {response_action}")
        else:
            print("Client: No response received for Trigger Action within timeout.")

    else:
        print("Client: Failed to connect to device ports. Please ensure a compatible MIDI device is running and its ports are discoverable.")

    client.shutdown()
    print("Client: Basic test script finished.")
