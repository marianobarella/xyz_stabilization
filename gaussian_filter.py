import numpy as np
import matplotlib.pyplot as plt
from scipy.fft import fft, fftfreq
from scipy.signal import gaussian, convolve

def gaussian_filter_time_domain(signal, sample_rate, cutoff_freq):
    """
    Apply a Gaussian filter in the time domain.
    
    Parameters:
    signal (array): Input signal in volts
    sample_rate (float): Sampling rate in Hz (100000 for your data)
    cutoff_freq (float): Desired cutoff frequency in Hz (e.g., 10000)
    
    Returns:
    array: Filtered signal
    """
    # Calculate the standard deviation for the Gaussian kernel
    # The relationship between sigma and cutoff frequency is:
    # sigma = sample_rate / (2 * pi * cutoff_freq)
    sigma = sample_rate / (2 * np.pi * cutoff_freq)
    
    # Create a Gaussian window
    # The window size is chosen to be 6*sigma (covers >99% of the area)
    window_size = int(6 * sigma)
    if window_size % 2 == 0:
        window_size += 1  # make sure it's odd
    
    gaussian_window = gaussian(window_size, sigma)
    gaussian_window /= np.sum(gaussian_window)  # normalize
    
    # Apply convolution
    filtered_signal = convolve(signal, gaussian_window, mode='same')
    
    return filtered_signal

def plot_signals(original, filtered, sample_rate, cutoff_freq, time_window=None):
    """
    Plot original and filtered signals in time and frequency domains.
    
    Parameters:
    original (array): Original signal
    filtered (array): Filtered signal
    sample_rate (float): Sampling rate in Hz
    cutoff_freq (float): Cutoff frequency used in Hz
    time_window (tuple): (start, end) in seconds for time domain plot
    """
    # Time domain plot
    plt.figure(figsize=(12, 8))
    
    # Create time array
    t = np.arange(len(original)) / sample_rate
    
    if time_window is not None:
        mask = (t >= time_window[0]) & (t <= time_window[1])
        t = t[mask]
        original = original[mask]
        filtered = filtered[mask]
    
    plt.subplot(2, 1, 1)
    plt.plot(t, original, label='Original Signal')
    plt.plot(t, filtered, label=f'Filtered (fc={cutoff_freq/1000:.1f} kHz)')
    plt.xlabel('Time (s)')
    plt.ylabel('Voltage (V)')
    plt.title('Time Domain')
    plt.legend()
    plt.grid(True)
    
    # Frequency domain plot
    n = len(original)
    yf_orig = fft(original)
    yf_filt = fft(filtered)
    xf = fftfreq(n, 1/sample_rate)[:n//2]
    
    plt.subplot(2, 1, 2)
    plt.semilogy(xf, 2/n * np.abs(yf_orig[0:n//2]), label='Original')
    plt.semilogy(xf, 2/n * np.abs(yf_filt[0:n//2]), label='Filtered')
    plt.axvline(cutoff_freq, color='red', linestyle='--', label=f'Cutoff: {cutoff_freq/1000:.1f} kHz')
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude')
    plt.title('Frequency Domain')
    plt.legend()
    plt.grid(True)
    
    plt.tight_layout()
    plt.show()

def process_signal_file(filename, sample_rate, cutoff_freq, plot=False):
    """
    Load a signal from .npy file and apply Gaussian filter.
    
    Parameters:
    filename (str): Path to .npy file
    sample_rate (float): Sampling rate in Hz
    cutoff_freq (float): Desired cutoff frequency in Hz
    plot (bool): Whether to plot the results
    
    Returns:
    tuple: (original_signal, filtered_signal)
    """
    # Load the signal
    signal = np.load(filename).flatten()  # Ensure it's a 1D array
    if signal.ndim > 1:
        raise ValueError("Signal must be a 1D array.")
    
    # Apply filter
    filtered_signal = gaussian_filter_time_domain(signal, sample_rate, cutoff_freq)
    
    # Plot results
    if plot:
        # Show first 0.1 seconds for clarity (adjust as needed)
        plot_signals(signal, filtered_signal, sample_rate, cutoff_freq, time_window=(0, 0.01))
    
    return signal, filtered_signal

# Example usage
if __name__ == "__main__":
    # Parameters
    filename = 'your_signal.npy'  # Replace with your file path
    sample_rate = 100000  # 100 kHz
    cutoff_freq = 10000  # 10 kHz
    
    # Process the signal
    original, filtered = process_signal_file(filename, sample_rate, cutoff_freq)
    
    # Save filtered signal if needed
    np.save('filtered_signal.npy', filtered)