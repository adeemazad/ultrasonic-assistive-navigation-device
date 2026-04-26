## Ultrasonic Sensor-Based Assistive Device for Visually Impaired People

# Overview
This project aims to develop an assistive device for visually impaired individuals using an ultrasonic sensor, Arduino, and real-time data processing. 
The device measures distances to surrounding objects, filters the data using an IIR filter, and alerts the user via a buzzer as distance between user and object decreases.
A real-time plot visualizes both raw and filtered distance data in real time.

# Features
Distance Measurement: Uses an ultrasonic sensor connected to an Arduino to measure distances in real-time.
IIR Filtering: Implements a custom chain of second-order sections (SOS) IIR filters for smoothing distance data.
Dynamic Alert System: A buzzer sounds at varying intervals based on the proximity of obstacles. Closest objects trigger faster beeps.
Real-Time Visualization: Displays raw and filtered distance data in real-time using matplotlib.
Sampling rate dynamically calculated and displayed.
Unit Testing: Ensures the accuracy of filter implementation using impulse, step, and noisy signal test cases.
Data is continuously captured in real time from the Arduino's analog pin at 80Hz using pyfirmata2.

# Hardware Requirements
Arduino UNO R3
URM37 DFROBOT Ultrasonic Sensor
Buzzer
Breadboard
Necessary cables and connectors
A bit of RAM for matplotlib

# Software Requirements
Python 3.7 or higher
Arduino IDE with Firmata firmware installed on the board

# Python Libraries
pyfirmata2
numpy
matplotlib
scipy
unittest
threading
Install required libraries using pip:
```bash
pip3 install pyfirmata2 numpy matplotlib scipy 
```
# Setup Instructions
1. Configure Arduino
Upload the Standard Firmata sketch to the Arduino board using the Arduino IDE.
Connect the ultrasonic sensor and buzzer to appropriate analog and digital pins:
Analog Pin:
    A0 for ultrasonic sensor's analogue output (DAC_OUT)
Digital Pins:
    ~D5 for sensor trigger(COMP/TRIG)
    ~D6 for buzzer
Power pins:
    5v DC to buzzer(+) and Ultrasonic Sensor (VCC)
    GND to buzzer(-) and Ultrasonic Sensor (GND)

2. Run the Code
Ensure the Arduino is connected to your computer via USB.
Execute the script:
```bash
python3 main.py
```
# Video Demonstration
https://youtu.be/iYUFY_aObfE?si=qANDlZyPqdgixqjn 