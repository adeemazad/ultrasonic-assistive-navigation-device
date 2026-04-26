import pyfirmata2
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import time
from scipy.signal import butter, sosfilt
import unittest
import threading  

# ==================== Constants ====================
SAMPLING_RATE = 80             # Sampling rate
LOW_CUTOFF = 2                 # Low cutoff frequency
MAX_SAMPLES = 2000             # Max samples for plotting window
MAX_BUFFER_SIZE = 4000         # Max buffer size before trimming data
BUZZER_BEEP_DURATION = 0.05    # Buzzer beep duration
MIN_DISTANCE = 10              # Min distance to trigger buzzer
MAX_DISTANCE = 300             # Max distance for buzzer
MIN_INTERVAL = 0.02            # Min beep interval 
MAX_INTERVAL = 2.0             # Max beep interval

# ==================== Filter Classes ====================
class IIRFilterDirectForm1SingleSOS:            
    def __init__(self, sos_row):
        self.b = sos_row[:3]                    # Numerator coeff.
        self.a = sos_row[3:]                    # Denominator coeff.
        self.x_delays = np.zeros(2)             # 2 prev. input samples
        self.y_delays = np.zeros(2)             # 2 prev. output samples 

    def filter(self, input_sample):             # Applies IIR to single sample 
        output = (
            self.b[0] * input_sample +          # Direct form 1 equation
            self.b[1] * self.x_delays[0] +
            self.b[2] * self.x_delays[1] -
            self.a[1] * self.y_delays[0] -
            self.a[2] * self.y_delays[1]
        )
        self.x_delays[1] = self.x_delays[0]     # Update delay buffers
        self.x_delays[0] = input_sample
        self.y_delays[1] = self.y_delays[0]
        self.y_delays[0] = output
        return output

class IIRFilterChain:       # Processes input through a chain of second-order IIR filters
    def __init__(self, sos):
        self.filters = [IIRFilterDirectForm1SingleSOS(s) for s in sos]  # Initialise filters from sos coeff.

    def filter(self, input_sample):
        for f in self.filters:
            input_sample = f.filter(input_sample)       # Sequentially apply each filter
        return input_sample

# ==================== SOS Coefficients ====================
sos = butter(4, LOW_CUTOFF / (SAMPLING_RATE / 2), btype='low', output='sos')    # 4th order Butterworth lowpass

# ==================== Unit Tests ====================
class TestIIRFilters(unittest.TestCase):        # Validates test signals in our iir implementation vs scipy's sosfilt.
    def setUp(self):
        self.sos = sos
        self.impulse = [1] + [0]*19     # Delta function
        self.step = [1]*20      # Step signal
        t = np.arange(0, 1, 1/SAMPLING_RATE)  # Time vector 
        np.random.seed(0)       # Seed for fixed starting point
        self.noisy_signal = np.sin(2*np.pi*20*t) + 0.5*np.random.randn(len(t)) # 20Hz sin wave with noise 

    def test_single_sos_impulse_response(self):
        single_sos_filter = IIRFilterDirectForm1SingleSOS(self.sos[0])
        output = [single_sos_filter.filter(x) for x in self.impulse]
        expected_output = sosfilt([self.sos[0]], self.impulse)
        np.testing.assert_almost_equal(output, expected_output, decimal=5)

    def test_single_sos_step_response(self):
        single_sos_filter = IIRFilterDirectForm1SingleSOS(self.sos[0])
        output = [single_sos_filter.filter(x) for x in self.step]
        expected_output = sosfilt([self.sos[0]], self.step)
        np.testing.assert_almost_equal(output, expected_output, decimal=5)

    def test_chain_impulse_response(self):
        chain_filter = IIRFilterChain(self.sos)
        output = [chain_filter.filter(x) for x in self.impulse]
        expected_output = sosfilt(self.sos, self.impulse)
        np.testing.assert_almost_equal(output, expected_output, decimal=5)

    def test_chain_step_response(self):
        chain_filter = IIRFilterChain(self.sos)
        output = [chain_filter.filter(x) for x in self.step]
        expected_output = sosfilt(self.sos, self.step)
        np.testing.assert_almost_equal(output, expected_output, decimal=5)

    def test_chain_noisy_signal(self):
        chain_filter = IIRFilterChain(self.sos)
        output = [chain_filter.filter(x) for x in self.noisy_signal]
        expected_output = sosfilt(self.sos, self.noisy_signal)
        np.testing.assert_almost_equal(output, expected_output, decimal=5)

# ==================== Buzzer Controller ====================
class BuzzerController:         # Controls the buzzer based on filtered distance measurements.
    def __init__(self, buzzer_pin):
        self.buzzer_pin = buzzer_pin
        self.buzzer_on = False
        self.buzzer_last_toggle_time = time.perf_counter()
        self.buzzer_beep_interval = 0

    def update_buzzer(self, filtered_distance):          # Compute beep interval based on distance
        current_time = time.perf_counter()
        if filtered_distance <= MIN_DISTANCE:
            self.buzzer_beep_interval = MIN_INTERVAL     # Close = fast beeps
        elif filtered_distance >= MAX_DISTANCE:    
            self.buzzer_beep_interval = MAX_INTERVAL     # Far = slow beeps
        else:           # Logarithmical interval based on min max distance
            normalized_distance = (filtered_distance - MIN_DISTANCE) / (MAX_DISTANCE - MIN_DISTANCE)
            k = np.log(MAX_INTERVAL / MIN_INTERVAL)
            beep_interval = MIN_INTERVAL * np.exp(k * normalized_distance)
            beep_interval = max(MIN_INTERVAL, min(beep_interval, MAX_INTERVAL))
            self.buzzer_beep_interval = beep_interval
        if self.buzzer_on:       # Toggle buzzer state
            if current_time - self.buzzer_last_toggle_time >= BUZZER_BEEP_DURATION:
                self.buzzer_pin.write(0)
                self.buzzer_on = False
                self.buzzer_last_toggle_time = current_time
        else:
            if current_time - self.buzzer_last_toggle_time >= self.buzzer_beep_interval:
                self.buzzer_pin.write(1)
                self.buzzer_on = True
                self.buzzer_last_toggle_time = current_time

# ==================== Real-Time Plot Class ====================
class RealtimeFilteredPlot:         # Realtime raw and filtered data plots 
    def __init__(self, max_samples=MAX_SAMPLES):
        self.fig, self.ax = plt.subplots(2, 1, figsize=(12, 8))     # 2 plots: raw and filtered
        self.max_samples = max_samples
        self.raw_buffer = []
        self.filtered_buffer = []
        self.raw_line, = self.ax[0].plot([], [], label='Raw Data')
        self.filtered_line, = self.ax[1].plot([], [], label='Filtered Data')
        # Titles and labels 
        self.ax[0].set_title('Raw Ultrasonic Data')
        self.ax[1].set_title('Filtered Ultrasonic Data')
        self.ax[1].set_xlabel('Sample Index')
        self.ax[0].set_ylabel('Distance (cm)')
        self.ax[1].set_ylabel('Distance (cm)')
        self.ax[0].grid(True)       # Finer gridlines on plot
        self.ax[1].grid(True)
        self.ax[0].legend()
        self.ax[1].legend()

        self.sampling_rate_text = self.ax[0].text(      #live samplerate on plot
            0.02, 0.92, 'Sample Rate: 0.0 Hz', transform=self.ax[0].transAxes,
            fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        )
        self.ani = animation.FuncAnimation(     #initialise plt animation 
            self.fig, self.update_plot, interval=50, cache_frame_data=False
        )
        self.closed = False     # Flag
        self.fig.canvas.mpl_connect('close_event', self.handle_close)  

        self.global_sample_count = 0  # Initialize sample counter
        self.lock = threading.Lock()  # Lock threads

    def handle_close(self, event):  # When window is closed
        print('Figure closed')
        self.closed = True     
        if self.ani.event_source is not None:        # Stop the animation to prevent further updates
            self.ani.event_source.stop()
        plt.close(self.fig)

    def update_plot(self, frame):       # Updates the plot with new data
        with self.lock:
            buffer_length_raw = len(self.raw_buffer)
            buffer_length_filtered = len(self.filtered_buffer)
            
            if buffer_length_raw != buffer_length_filtered:         # Ensure both buffers have the same length for synced plotting
                min_length = min(buffer_length_raw, buffer_length_filtered)
                print(f"Buffer length mismatch: raw={buffer_length_raw}, filtered={buffer_length_filtered}. Trimming to {min_length}")
                raw_data = self.raw_buffer[-min_length:]
                filtered_data = self.filtered_buffer[-min_length:]
            else:
                min_length = buffer_length_raw
                raw_data = self.raw_buffer
                filtered_data = self.filtered_buffer

            if min_length > 0:          
                x_start = self.global_sample_count - min_length     # x-axis based on global_sample_count
                x_end = self.global_sample_count
                x_data = np.arange(x_start, x_end)
                
                if min_length > self.max_samples:           # Limit data to max no. of samples
                    x_data = x_data[-self.max_samples:]
                    raw_data = raw_data[-self.max_samples:]
                    filtered_data = filtered_data[-self.max_samples:]

                self.raw_line.set_data(x_data, raw_data)        # Update plot lines with new data
                self.filtered_line.set_data(x_data, filtered_data)

                if len(x_data) > 0:
                    if len(x_data) > self.max_samples:
                        self.ax[0].set_xlim(x_data[0], x_data[-1])      # Adjust x-axis limits based on data
                        self.ax[1].set_xlim(x_data[0], x_data[-1])
                    else:
                        self.ax[0].set_xlim(max(0, self.global_sample_count - self.max_samples), self.global_sample_count)
                        self.ax[1].set_xlim(max(0, self.global_sample_count - self.max_samples), self.global_sample_count)

                    self.ax[0].set_ylim(        # Update Y-limits based on data
                        min(raw_data) - 10,
                        max(raw_data) + 10
                    )
                    self.ax[1].set_ylim(
                        min(filtered_data) - 10,
                        max(filtered_data) + 10
                    )
            else:           # If no data yet, set default limits
                self.ax[0].set_xlim(0, self.max_samples)
                self.ax[1].set_xlim(0, self.max_samples)

        return self.raw_line, self.filtered_line, self.sampling_rate_text

    def add_data(self, raw_value, filtered_value):      # Adds new data to buffers
        with self.lock:
            self.raw_buffer.append(raw_value)
            self.filtered_buffer.append(filtered_value)
            self.global_sample_count += 1  # Increment sample counter

            if len(self.raw_buffer) > MAX_BUFFER_SIZE:
                trimmed = MAX_BUFFER_SIZE // 2
                del self.raw_buffer[:trimmed]       # Trims buffer to manage ram consumption
                del self.filtered_buffer[:trimmed]

    def update_sampling_rate_display(self, sampling_rate):  # Updates sampling rate on plot
        with self.lock:
            self.sampling_rate_text.set_text(f'Sample Rate: {sampling_rate:.1f} Hz')

# ==================== Sensor Controller ====================
class SensorController:        # Manages the Arduino
    def __init__(self, board, analog_pin, digital_pin, buzzer_pin, filter_chain, plot_window):
        self.board = board
        self.analog_pin = analog_pin
        self.digital_pin = digital_pin
        self.buzzer_pin = buzzer_pin
        self.filter_chain = filter_chain
        self.plot_window = plot_window
        self.buzzer_controller = BuzzerController(self.buzzer_pin)

        # Setup sensor and buzzer
        self.digital_pin.write(1)   # Trigger ultrasonic sensor
        self.buzzer_pin.write(0)    # Ensure buzzer is off
        self.analog_pin.register_callback(self.sensor_callback)     
        self.analog_pin.enable_reporting()      # Start data stream

        self.sample_count = 0       # Initialise Fs calculation
        self.start_time = time.perf_counter()       # Time stamp

    def sensor_callback(self, data):        # Triggred by analogue pin data
        if data is not None:
            adc_value = data * 1023.0   # 10 bit ADC (L-1)
            distance_measured = ((adc_value * 1.1) - 100.0)        # (SensorValue * 5000 / 1024 ) / 4.125 - 100 
            filtered_distance = self.filter_chain.filter(distance_measured)     # Apply IIR
            self.plot_window.add_data(distance_measured, filtered_distance)     # Add new data to window
            self.buzzer_controller.update_buzzer(filtered_distance) # Update buzzer based on dist.
            
            # Update sampling rate
            self.sample_count += 1
            current_time = time.perf_counter()
            elapsed_time = current_time - self.start_time
            if elapsed_time >= 1.0:
                sampling_rate = self.sample_count / elapsed_time    # calculate samples/sec for Fs
                self.plot_window.update_sampling_rate_display(sampling_rate)    # Update plot display
                self.sample_count = 0       # Reset counter
                self.start_time = current_time

    def trigger_sensor(self):       # 1/0 to D5 COMP/TRIG
        self.digital_pin.write(0)
        time.sleep(0.01)
        self.digital_pin.write(1)

# ==================== Main Function ====================
def main():
    # Start Tests
    print("Running unit tests...")
    test_loader = unittest.TestLoader()
    test_suite = test_loader.loadTestsFromTestCase(TestIIRFilters)
    test_runner = unittest.TextTestRunner(verbosity=2)
    test_results = test_runner.run(test_suite)
    if not test_results.wasSuccessful():
        print("Unit tests failed. Exiting the program.")
        return 

    print("Unit tests passed. Starting real-time processing...")

    PORT = pyfirmata2.Arduino.AUTODETECT    # Autodetect arduino
    board = None
    try:
        board = pyfirmata2.Arduino(PORT)
        print("Connected to Arduino.")
    except Exception as e:
        print(f"Error: Unable to connect to board. {e}")
        return
    # Define pins on Arduino
    analog_pin = board.get_pin('a:0:i')
    digital_pin = board.get_pin('d:5:o')
    buzzer_pin = board.get_pin('d:6:o')
    # Initialisation 
    filter_chain = IIRFilterChain(sos)
    plot_window = RealtimeFilteredPlot()
    sensor_controller = SensorController(board, analog_pin, digital_pin, buzzer_pin, filter_chain, plot_window)

    try:
        board.samplingOn(1000 / SAMPLING_RATE)  # Sampling interval in ms
        print(f"Sampling started at {SAMPLING_RATE} Hz.")
        while not plot_window.closed:
            sensor_controller.trigger_sensor()  # trigger D5
            time.sleep(1 / SAMPLING_RATE)       # Wait for next sampling interval
            plt.pause(0.01)             # Allow plt to process

    except KeyboardInterrupt:
        print("Exiting program.")       # ctrl + c
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if board is not None:
            try:
                buzzer_pin.write(0)      # Ensure buzzer is turned off
                board.exit()             # Closes connection to arduino
                print("Arduino connection closed.")
            except AttributeError:
                print("Board was not fully initialized. Skipping exit.")
            except Exception as e:
                print(f"Error during board exit: {e}")  

if __name__ == "__main__":
    main()