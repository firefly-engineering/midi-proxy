# MIDI Device Emulator

This component (`device/device.py`) emulates a simple MIDI device for testing purposes within the MIDI proxy system. It creates virtual MIDI input and output ports and responds to specific MIDI messages, particularly System Exclusive (SysEx) messages.

## Features

- Creates virtual MIDI input ("Python Test Device In") and output ("Python Test Device Out") ports.
- Listens for incoming MIDI messages.
- Handles standard MIDI messages (Note On/Off, Control Change) by logging them to the console.
- Responds to specific SysEx messages.

## Running the Device

The device can be run as a standalone script for testing:

```bash
python device/device.py
```

Upon running, it will attempt to create its virtual MIDI ports and then wait for incoming MIDI messages. Press `Ctrl+C` to shut down the device.

## Dependencies

- `python-rtmidi`: For MIDI communication.
- On Linux, ALSA utilities (`alsa-utils`) and development libraries (`libasound2-dev`) might be needed for `python-rtmidi` to function correctly, especially for virtual port creation.

## SysEx Message Handling

The device handles the following SysEx messages:

### 1. Identity Request (Universal SysEx)

-   **Received by Device:** `F0 7E 7F 06 01 F7`
    -   `F0`: SysEx Start
    -   `7E`: Universal Non-Realtime Message
    -   `7F`: Target Device ID (All Call)
    -   `06`: Sub-ID #1 (General Information)
    -   `01`: Sub-ID #2 (Identity Request)
    -   `F7`: SysEx End
-   **Sent by Device (Identity Reply):** `F0 7E 7F 06 02 7D 01 01 01 01 01 01 01 01 F7`
    -   `F0`: SysEx Start
    -   `7E`: Universal Non-Realtime Message
    -   `7F`: Device ID (Replying to All Call)
    -   `06`: Sub-ID #1 (General Information)
    -   `02`: Sub-ID #2 (Identity Reply)
    -   `7D`: Manufacturer ID (Non-Commercial)
    -   `01 01`: Device Family (LSB, MSB) - Placeholder
    -   `01 01`: Device Model (LSB, MSB) - Placeholder
    -   `01 01 01 01`: Version (LSB, MSB, Byte2, Byte3) - Placeholder (1.1.1.1)
    -   `F7`: SysEx End

### 2. Custom Trigger Action (Manufacturer Specific)

This is a custom SysEx message defined for this device.

-   **Manufacturer ID:** `0x7D` (Non-Commercial)
-   **Device ID (for custom messages):** `0x01`

-   **Message Format (Client -> Device):** `F0 7D <Device ID> <Command ID> <Action ID> F7`
    -   `<Device ID>`: Must be `0x01`.
    -   `<Command ID>`: Must be `0x03` (Trigger Action).
    -   `<Action ID>`: Specifies the action. Currently, `0x01` is supported.

-   **Example: Trigger Log Action (Action ID `0x01`)**
    -   **Client -> Device:** `F0 7D 01 03 01 F7`
    -   **Device Behavior:**
        1.  Writes an entry to `device_actions.log` in the current working directory. The log entry includes the Action ID and the full SysEx message.
            Example log line: `TriggerAction: ID=1, FullMsg=[240, 125, 1, 3, 1, 247]`
        2.  Sends an acknowledgment (ACK) by echoing the received message back to the client: `F0 7D 01 03 01 F7`.

## Observability

-   **Console Logs:** The device prints information about its status (port opening, messages received/sent) to the console.
-   **Action Log File (`device_actions.log`):** Specific actions, like the "Trigger Log Action" SysEx, are logged to this file. This file is cleared when the device starts.

This README provides a basic overview for users and developers interacting with this test device.
