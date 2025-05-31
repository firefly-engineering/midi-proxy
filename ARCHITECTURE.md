# Architecture

This document outlines the architecture of the MIDI proxy system. The system consists of three main components:

*   **Proxy:** The core component that acts as a MIDI passthrough. It forwards MIDI messages between a client application and a MIDI device.
*   **Device:** A virtual MIDI device used for testing purposes. It responds to specific MIDI messages, including System Exclusive (SysEx) messages.
*   **Client:** A virtual MIDI client used for testing purposes. It sends MIDI messages, including SysEx messages, to interact with the Device, either directly or via the Proxy.

## Components

### Proxy

The Proxy component is the main application. Its primary responsibilities are:

*   Discovering available MIDI devices on the system.
*   Allowing the user to select an existing MIDI device to be proxied.
*   Creating a virtual MIDI input and output port.
*   Forwarding MIDI messages received on its virtual input port to the selected real MIDI output device.
*   Forwarding MIDI messages received from the selected real MIDI input device to its virtual output port.

### Device

The Device component is a test utility that emulates a MIDI device. Its key features are:

*   Creates a virtual MIDI input and output port.
*   Listens for incoming MIDI messages, particularly SysEx messages.
*   Responds to predefined SysEx messages. The exact nature of these messages will be defined in the Interface Definitions section.

### Client

The Client component is a test utility that emulates a MIDI client application. Its key features are:

*   Creates a virtual MIDI output and input port.
*   Sends MIDI messages, including predefined SysEx messages, to a MIDI device (either the real Device or the Proxy).
*   Listens for MIDI messages from the connected MIDI device.

## Interactions

The system supports two primary interaction modes:

1.  **Direct Client-Device Communication:** The Client connects directly to the Device. This mode is used to establish a baseline for the expected behavior.
2.  **Proxied Client-Device Communication:** The Client connects to the Proxy, and the Proxy connects to the Device. This mode is used to test the Proxy's functionality and ensure it doesn't alter the communication.

The main invariant for the project is that the behavior observed during direct Client-Device communication should be identical to the behavior observed during proxied Client-Device communication.

## Interface Definitions

This section defines the MIDI messages used for communication between the Client, Device, and Proxy.

### Standard MIDI Messages

All components should support standard MIDI messages, such as:

*   Note On / Note Off
*   Control Change
*   Program Change
*   Pitch Bend
*   Timing Clock, Start, Stop, Continue

The Proxy must forward these messages transparently.

### System Exclusive (SysEx) Messages

SysEx messages are used for custom communication, primarily between the Client and the Device.

**Manufacturer ID:** For the purpose of this project, we will use a placeholder Manufacturer ID: `0x7D` (Non-Commercial).

**Device Identification:**

*   **Client -> Device (or Proxy):**
    *   Purpose: Request device identification.
    *   Message: `F0 7E 7F 06 01 F7` (Universal System Exclusive - Identity Request)
*   **Device -> Client (or Proxy):**
    *   Purpose: Respond to Identity Request.
    *   Message: `F0 7E 7F 06 02 7D <Device FamilyL> <Device FamilyM> <Device ModelL> <Device ModelM> <VersionL> <VersionM> <VersionByte2> <VersionByte3> F7`
        *   `<Device FamilyL/M>`: Placeholder `0x01 0x01`
        *   `<Device ModelL/M>`: Placeholder `0x01 0x01`
        *   `<VersionL/M/Byte2/Byte3>`: Placeholder `0x01 0x01 0x01 0x01` (representing version 1.1.1.1)

**Custom Device Control SysEx Messages:**

The Device will respond to a set of custom SysEx messages. These messages will allow the Client to control specific parameters or trigger actions on the Device.

*   **Message Format:** `F0 7D <Device ID> <Command ID> <Payload...> F7`
    *   `<Device ID>`: A unique ID for the virtual device, e.g., `0x01`.
    *   `<Command ID>`: Specifies the action to be performed.

*   **Example Commands:**

    *   **Set Parameter:**
        *   Client -> Device: `F0 7D 01 01 <Parameter ID> <Parameter Value> F7`
        *   Device -> Client (Ack): `F0 7D 01 01 <Parameter ID> <Parameter Value> F7` (echoes the command on success)
        *   `<Parameter ID>`: e.g., `0x01` for "Volume", `0x02` for "Filter Cutoff".
        *   `<Parameter Value>`: e.g., `0x00` - `0x7F`.

    *   **Get Parameter:**
        *   Client -> Device: `F0 7D 01 02 <Parameter ID> F7`
        *   Device -> Client (Response): `F0 7D 01 02 <Parameter ID> <Parameter Value> F7`

    *   **Trigger Action:**
        *   Client -> Device: `F0 7D 01 03 <Action ID> F7`
        *   Device -> Client (Ack): `F0 7D 01 03 <Action ID> F7` (echoes the command on success)
        *   `<Action ID>`: e.g., `0x01` for "Reset Device", `0x02` for "Play Test Sound".

*   **Error Reporting (Optional):**
    *   Device -> Client: `F0 7D 01 7F <Error Code> <Original Command ID> F7`
        *   `<Error Code>`: e.g., `0x01` (Unknown Command), `0x02` (Invalid Parameter).

The Proxy's role regarding SysEx messages is to forward them verbatim between the Client and the Device.

## Observability

The Proxy component must provide mechanisms to observe and log the MIDI traffic flowing through it. This is crucial for debugging and verifying that the proxy operates transparently.

### Logging Levels

The Proxy should support configurable logging levels, such as:

*   **None:** No logging.
*   **Error:** Only log errors encountered by the proxy.
*   **Info:** Log significant events, such as device connections/disconnections and proxy start/stop.
*   **Debug/Trace:** Log all MIDI messages passing through the proxy. This level is essential for detailed communication analysis.

### Message Dumping

When logging at the Debug/Trace level, the Proxy should dump the full content of each MIDI message. The format should be human-readable and clearly indicate the direction of the message (Client -> Device or Device -> Client).

**Example Log Output (Debug/Trace Level):**

```
[PROXY - INFO] Proxy started. Virtual input: "Proxy MIDI In", Virtual output: "Proxy MIDI Out"
[PROXY - INFO] Connected to real device: "Real MIDI Device X"
...
[PROXY - TRACE] C->D: F0 7E 7F 06 01 F7 (Identity Request)
[PROXY - TRACE] D->C: F0 7E 7F 06 02 7D 01 01 01 01 01 01 01 01 F7 (Identity Reply)
[PROXY - TRACE] C->D: 90 3C 7F (Note On, Channel 1, Note C4, Velocity 127)
[PROXY - TRACE] D->C: (No message - if device doesn't echo Note On)
[PROXY - TRACE] C->D: F0 7D 01 01 01 40 F7 (Set Parameter: ID 0x01, Value 0x40)
[PROXY - TRACE] D->C: F0 7D 01 01 01 40 F7 (Set Parameter ACK)
...
```

### Output Options

Logged messages could be output to:

*   Standard output (console).
*   A log file.
*   (Optional) A dedicated UI panel within the proxy application if it has a GUI.

The choice of output and the logging level should be configurable by the user.

## Testing Strategy

The primary goal of the testing strategy is to verify the core invariant: client-device communication remains unchanged when the Proxy is introduced.

### Test Setup

1.  **Client Instance:** An instance of the Client component.
2.  **Device Instance:** An instance of the Device component.
3.  **Proxy Instance:** An instance of the Proxy component.

### Test Scenarios

**Scenario 1: Direct Client-Device Communication**

1.  Configure the Client to connect directly to the Device's virtual MIDI ports.
2.  Execute a predefined sequence of interactions from the Client:
    *   Send Identity Request, verify Device's response.
    *   Send various standard MIDI messages (Note On/Off, CC, Program Change).
    *   Send custom SysEx messages to set and get parameters on the Device.
    *   Send custom SysEx messages to trigger actions on the Device.
3.  Log all messages sent by the Client and received from the Device. This log serves as the "expected" communication pattern.
4.  Verify that the Device responds correctly to all messages as per its defined behavior.

**Scenario 2: Proxied Client-Device Communication**

1.  Configure the Proxy to connect to the Device's real MIDI ports (or its virtual ports if the Device is purely virtual).
2.  Configure the Client to connect to the Proxy's virtual MIDI ports.
3.  Execute the *exact same* predefined sequence of interactions from the Client as in Scenario 1.
4.  Enable full message dumping on the Proxy.
5.  Log all messages sent by the Client (as seen by the Proxy's input) and received from the Device (as seen by the Proxy's output before being forwarded to the Client).
6.  Verify that the Device responds correctly to all messages.
7.  **Crucially, compare the Proxy's log of messages between Client and Device with the log from Scenario 1.** They should be identical in terms of message content and sequence (allowing for minor timing differences if not strictly controlled).

### Verification Points

*   **Message Integrity:** Ensure that the Proxy does not alter the content of any MIDI message, including SysEx.
*   **Message Sequence:** Ensure that the Proxy maintains the order of messages.
*   **Behavioral Equivalence:** The Device's responses and overall behavior must be the same in both scenarios.
*   **Proxy Observability:** Verify that the Proxy's logging accurately reflects the communication.

### Automation

Where possible, these test scenarios should be automated. This involves:

*   Scripting the Client's actions.
*   Programmatically checking the Device's responses (e.g., by having the Client listen for expected replies).
*   Comparing log files for equivalence.

This testing strategy will provide strong confidence that the Proxy component fulfills its role as a transparent intermediary.
