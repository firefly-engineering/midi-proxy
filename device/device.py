import time
import rtmidi # type: ignore
import os # For file operations

# SysEx constants
SYSEX_START = 0xF0
SYSEX_END = 0xF7
UNIVERSAL_NON_REALTIME_SYSEX = 0x7E
GENERAL_INFORMATION = 0x06
IDENTITY_REQUEST = 0x01
IDENTITY_REPLY = 0x02
MANUFACTURER_ID = 0x7D  # Non-Commercial Manufacturer ID
DEVICE_ID_SYSEX = 0x01 # Our device's ID for custom SysEx

# Custom Command IDs
COMMAND_TRIGGER_ACTION = 0x03

# Action IDs for Trigger Action
ACTION_ID_LOG = 0x01

LOG_FILE_NAME = "device_actions.log"

class Device:
    def __init__(self, port_name='Python Test Device'):
        self.port_name = port_name
        self.midi_in = rtmidi.MidiIn()
        self.midi_out = rtmidi.MidiOut()
        self.shutdown_flag = False
        self._setup_ports()
        # Ensure log file is clear at start if it exists
        if os.path.exists(LOG_FILE_NAME):
            try:
                os.remove(LOG_FILE_NAME)
                print(f"Device: Cleared log file {LOG_FILE_NAME}")
            except OSError as e:
                print(f"Device: Error removing log file {LOG_FILE_NAME}: {e}")

    def _setup_ports(self):
        try:
            self.midi_in.open_virtual_port(f"{self.port_name} In")
            print(f"Device: Opened virtual input port: {self.port_name} In")
        except rtmidi.RtMidiError as e:
            print(f"Device: Error opening virtual input port: {e}")
            available_ports_in = self.midi_in.get_ports()
            if available_ports_in:
                print(f"Device: Attempting to open available input port: {available_ports_in[0]}")
                try:
                    self.midi_in.open_port(0)
                    print(f"Device: Successfully opened input port: {available_ports_in[0]}")
                except rtmidi.RtMidiError as e_open:
                    print(f"Device: Error opening available input port {available_ports_in[0]}: {e_open}")
            else:
                print("Device: No MIDI input ports available.")

        try:
            self.midi_out.open_virtual_port(f"{self.port_name} Out")
            print(f"Device: Opened virtual output port: {self.port_name} Out")
        except rtmidi.RtMidiError as e:
            print(f"Device: Error opening virtual output port: {e}")
            available_ports_out = self.midi_out.get_ports()
            if available_ports_out:
                print(f"Device: Attempting to open available output port: {available_ports_out[0]}")
                try:
                    self.midi_out.open_port(0)
                    print(f"Device: Successfully opened output port: {available_ports_out[0]}")
                except rtmidi.RtMidiError as e_open:
                    print(f"Device: Error opening available output port {available_ports_out[0]}: {e_open}")
            else:
                print("Device: No MIDI output ports available.")

        if self.midi_in.is_port_open():
            self.midi_in.set_callback(self.on_midi_message)
            print("Device: MIDI callback set.")
        else:
            print("Device: MIDI input port not open. Cannot set callback.")

    def _handle_identity_request(self, message_bytes):
        print("Device: Received Identity Request.")
        # F0 7E 7F 06 02 7D <Device FamilyL> <Device FamilyM> <Device ModelL> <Device ModelM> <VersionL> <VersionM> <VersionByte2> <VersionByte3> F7
        reply_message = [
            SYSEX_START,
            UNIVERSAL_NON_REALTIME_SYSEX,
            0x7F, # Device ID (target for reply, 7F for 'all call' context)
            GENERAL_INFORMATION,
            IDENTITY_REPLY,
            MANUFACTURER_ID,
            0x01, 0x01,          # Device Family (LSB, MSB)
            0x01, 0x01,          # Device Model (LSB, MSB)
            0x01, 0x01, 0x01, 0x01, # Version (LSB, MSB, Byte2, Byte3)
            SYSEX_END
        ]
        self.send_midi_message(reply_message)

    def _handle_custom_sysex(self, message_bytes):
        print(f"Device: Received Custom SysEx: {message_bytes}")
        # Expected format: F0 7D <Device ID> <Command ID> <Payload...> F7
        if len(message_bytes) < 5 or message_bytes[1] != MANUFACTURER_ID or message_bytes[2] != DEVICE_ID_SYSEX:
            print("Device: Custom SysEx not for this device or malformed.")
            return

        command_id = message_bytes[3]

        if command_id == COMMAND_TRIGGER_ACTION:
            if len(message_bytes) >= 6: # F0 7D DevID CmdID ActionID F7
                action_id = message_bytes[4]
                self._handle_trigger_action(action_id, list(message_bytes)) # Pass as list
            else:
                print("Device: Trigger Action SysEx too short for Action ID.")
        else:
            print(f"Device: Unknown custom SysEx command ID: {command_id}")

    def _handle_trigger_action(self, action_id, original_message):
        print(f"Device: Handling Trigger Action, Action ID: {action_id}")
        if action_id == ACTION_ID_LOG:
            log_content = f"TriggerAction: ID={action_id}, FullMsg={original_message}\n"
            try:
                with open(LOG_FILE_NAME, "a") as f:
                    f.write(log_content)
                print(f"Device: Logged action to {LOG_FILE_NAME}")
                # Acknowledge by echoing the command as per ARCHITECTURE.md
                self.send_midi_message(original_message)
            except IOError as e:
                print(f"Device: Error writing to log file {LOG_FILE_NAME}: {e}")
        else:
            print(f"Device: Unknown Action ID for Trigger Action: {action_id}")

    def on_midi_message(self, message_tuple, data):
        message_bytes, deltatime = message_tuple
        # print(f'Device: Raw Received MIDI: {message_bytes} (delta: {deltatime})')

        if not message_bytes:
            return

        status_byte = message_bytes[0]

        if status_byte == SYSEX_START and message_bytes[-1] == SYSEX_END:
            # print("Device: SysEx message detected.")
            # Universal Non-Realtime SysEx (e.g., Identity Request)
            # F0 7E <device ID from message> 06 01 F7
            if len(message_bytes) == 6 and \
               message_bytes[0] == SYSEX_START and \
               message_bytes[1] == UNIVERSAL_NON_REALTIME_SYSEX and \
               message_bytes[3] == GENERAL_INFORMATION and \
               message_bytes[4] == IDENTITY_REQUEST and \
               message_bytes[5] == SYSEX_END:
                self._handle_identity_request(list(message_bytes))
            # Custom SysEx for our Manufacturer ID
            # F0 7D <Device ID> <Command ID> <Payload...> F7
            elif message_bytes[1] == MANUFACTURER_ID and message_bytes[2] == DEVICE_ID_SYSEX:
                self._handle_custom_sysex(list(message_bytes))
            else:
                print(f"Device: Unrecognized or non-targeted SysEx: {message_bytes}")
        elif status_byte >= 0x80 and status_byte <= 0xEF: # Channel Voice/Mode Messages
            message_type = status_byte & 0xF0
            channel = (status_byte & 0x0F) + 1
            if message_type == 0x90: # Note On
                 print(f"Device: Note On (Ch: {channel}, Note: {message_bytes[1]}, Vel: {message_bytes[2]})")
            elif message_type == 0x80: # Note Off
                 print(f"Device: Note Off (Ch: {channel}, Note: {message_bytes[1]}, Vel: {message_bytes[2]})")
            elif message_type == 0xB0: # Control Change
                 print(f"Device: Control Change (Ch: {channel}, CC: {message_bytes[1]}, Val: {message_bytes[2]})")
            else:
                print(f"Device: Other Channel Message (Type: {hex(message_type)}, Ch: {channel}): {message_bytes}")
        elif status_byte >= 0xF0: # System Common Messages (excluding SysEx already handled)
            print(f"Device: System Common Message: {message_bytes}")
        else:
            print(f"Device: Unknown or malformed message: {message_bytes}")

    def send_midi_message(self, message):
        if self.midi_out.is_port_open():
            self.midi_out.send_message(message)
            print(f'Device: Sent MIDI: {message}')
        else:
            print("Device: Output port not open. Cannot send message.")

    def run(self):
        print("Device: Starting main loop. Press Ctrl+C to exit.")
        try:
            while not self.shutdown_flag:
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("Device: KeyboardInterrupt received, shutting down.")
        finally:
            self.shutdown()

    def shutdown(self):
        print("Device: Shutting down...")
        self.shutdown_flag = True
        if hasattr(self, 'midi_in') and self.midi_in:
            if self.midi_in.is_port_open():
                 self.midi_in.close_port()
                 print("Device: MIDI In port closed.")
            del self.midi_in
            print("Device: MIDI In object deleted.")

        if hasattr(self, 'midi_out') and self.midi_out:
            if self.midi_out.is_port_open():
                self.midi_out.close_port()
                print("Device: MIDI Out port closed.")
            del self.midi_out
            print("Device: MIDI Out object deleted.")

        print("Device: Shutdown complete.")

if __name__ == '__main__':
    device = Device()
    device.run()
