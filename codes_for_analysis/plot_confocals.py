import numpy as np
import matplotlib.pyplot as plt
import os
import glob
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

def select_folder():
    """Open dialog to select folder containing the data files."""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    folder_path = filedialog.askdirectory(title="Select folder containing confocal scan data")
    return folder_path

def find_files(folder_path, pattern):
    """Find files matching pattern in the folder."""
    return sorted(glob.glob(os.path.join(folder_path, pattern)))

def process_confocal_data(folder_path=None, downsample_timepoints=True, downsample_factor=100):
    """
    Process confocal scan data and generate plots.
    
    Parameters:
    folder_path: Path to folder containing the data files. If None, a dialog will open.
    downsample_timepoints: Whether to downsample timepoints for plotting (default: True)
    downsample_factor: Downsampling factor when downsample_timepoints is True (default: 100)
    """
    
    # If no folder path provided, open dialog to select folder
    if folder_path is None:
        folder_path = select_folder()
    
    if not folder_path:
        print("No folder selected. Exiting.")
        return
    
    print(f"Processing data from: {folder_path}")
    print(f"Downsampling timepoints: {downsample_timepoints} (factor: {downsample_factor if downsample_timepoints else 'N/A'})")
    
    # Find APD trace files
    apd_pattern = "*_confocal_apd_traces_*.npy"
    apd_files = find_files(folder_path, apd_pattern)
    
    if not apd_files:
        print(f"No APD trace files found with pattern: {apd_pattern}")
        return
    
    print(f"Found {len(apd_files)} APD trace files")
    
    # Create output directory for plots
    output_dir = os.path.join(folder_path, "confocal_plots")
    os.makedirs(output_dir, exist_ok=True)
    
    # Process each APD file
    for apd_file in apd_files:
        print(f"\nProcessing: {os.path.basename(apd_file)}")
        
        # Extract base name to find related files
        base_name = os.path.basename(apd_file)
        # Remove '_confocal_apd_traces_' and extension to get prefix
        prefix = base_name.split('_confocal_apd_traces_')[0]
        
        # Find corresponding files
        coords_pattern = f"{prefix}_xy_coords_*.npy"
        image_pattern = f"{prefix}_image_*.npy"
        monitor_pattern = f"{prefix}_confocal_monitor_traces_*.npy"
        
        coords_files = find_files(folder_path, coords_pattern)
        image_files = find_files(folder_path, image_pattern)
        monitor_files = find_files(folder_path, monitor_pattern)
        
        if not coords_files:
            print(f"Warning: No coordinate file found for {prefix}")
            print(f"  Looking for pattern: {coords_pattern}")
            # Try alternative spelling for backward compatibility
            alt_coords_pattern = f"{prefix}_xy_cords_*.npy"
            coords_files = find_files(folder_path, alt_coords_pattern)
            if coords_files:
                print(f"  Found file with alternative spelling: {os.path.basename(coords_files[0])}")
        
        if not image_files:
            print(f"Warning: No image file found for {prefix}")
            continue
        
        # Load the data
        try:
            apd_traces = np.load(apd_file)
            coords = np.load(coords_files[0]) if coords_files else None
            image_data = np.load(image_files[0])
            
            # Check if monitor file exists
            monitor_traces = None
            if monitor_files:
                monitor_traces = np.load(monitor_files[0])
            
            # Generate base name for output files
            file_id = base_name.split('_')[-1].replace('.npy', '')
            plot_prefix = f"{prefix}_{file_id}"
            
            print(f"  APD traces shape: {apd_traces.shape} (rows × cols × timepoints)")
            if monitor_traces is not None:
                print(f"  Monitor traces shape: {monitor_traces.shape} (rows × cols × timepoints)")
            if coords is not None:
                print(f"  Coordinates shape: {coords.shape}")
            
            # 1. Plot all APD intensity traces (with spatial order preserved)
            plot_apd_traces(apd_traces, output_dir, plot_prefix, 
                           downsample_timepoints, downsample_factor)
            
            # 2. Plot all MONITOR intensity traces (if available, with spatial order preserved)
            if monitor_traces is not None:
                plot_monitor_traces(monitor_traces, output_dir, plot_prefix,
                                   downsample_timepoints, downsample_factor)
            
            # 3. Plot the 2D scan image with actual coordinates
            plot_2d_scan_image_with_coords(image_data, coords, output_dir, plot_prefix)
            
            # 4-6. Create 2D maps from APD traces with actual coordinates
            create_apd_statistics_maps_with_coords(apd_traces, coords, output_dir, plot_prefix)
            
        except Exception as e:
            print(f"Error processing {apd_file}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\nAll plots saved to: {output_dir}")

def get_coordinate_grids(coords, grid_shape):
    """
    Extract x and y coordinate grids from the coordinate array.
    
    Parameters:
    coords: 2D array of shape (total_positions, 2) with (x, y) coordinates in microns
    grid_shape: tuple (n_rows, n_cols) of the scan grid
    
    Returns:
    x_grid: 2D array of x-coordinates with shape (n_rows, n_cols)
    y_grid: 2D array of y-coordinates with shape (n_rows, n_cols)
    """    
    # Create the grid
    x_coords = coords[:, 0]
    y_coords = coords[:, 1]

    # Assuming coordinates are in raster scan order (row-major)
    x_coords_mesh, y_coords_mesh = np.meshgrid(x_coords, y_coords)
    
    return x_coords_mesh, y_coords_mesh     

def flatten_traces_preserving_order(traces_3d):
    """
    Convert 3D array (rows × cols × timepoints) to 2D array (timepoints × total_traces)
    while preserving the spatial raster order.
    
    The spatial order is preserved by flattening in C-order (row-major).
    For a 2D grid, this corresponds to scanning row by row.
    """
    n_rows, n_cols, n_timepoints = traces_3d.shape
    total_traces = n_rows * n_cols
    
    # Reshape to 2D while preserving spatial order
    # First transpose to (timepoints × rows × cols)
    traces_transposed = np.transpose(traces_3d, (2, 0, 1))
    # Then reshape to (timepoints × total_traces)
    # This flattening preserves the row-major (C-order) spatial arrangement
    traces_2d = traces_transposed.reshape(n_timepoints, total_traces)
    
    return traces_2d, n_rows, n_cols, total_traces

def get_spatial_indices(n_rows, n_cols):
    """
    Create a list of spatial indices (row, col) in raster scan order.
    Returns a list of tuples and a mapping from flat index to spatial position.
    """
    spatial_indices = []
    index_to_position = {}
    
    for i in range(n_rows):
        for j in range(n_cols):
            spatial_indices.append((i, j))
            flat_idx = i * n_cols + j
            index_to_position[flat_idx] = (i, j)
    
    return spatial_indices, index_to_position

def plot_apd_traces(apd_traces_3d, output_dir, prefix, downsample=True, downsample_factor=100):
    """Plot all APD intensity traces with spatial order preserved."""
    # Flatten while preserving spatial order
    apd_traces_2d, n_rows, n_cols, total_traces = flatten_traces_preserving_order(apd_traces_3d)
    
    n_timepoints = apd_traces_2d.shape[0]
    
    print(f"  Plotting {total_traces} APD traces (from {n_rows}×{n_cols} grid) with {n_timepoints} timepoints each")
    print(f"  Trace order: raster scan (row-major)")
    
    # Get spatial indices for reference
    spatial_indices, index_to_position = get_spatial_indices(n_rows, n_cols)
    
    # Apply downsampling to timepoints if requested
    if downsample and n_timepoints > downsample_factor:
        # Downsample along time dimension
        indices = np.linspace(0, n_timepoints - 1, downsample_factor).astype(int)
        traces_to_plot = apd_traces_2d[indices, :]
        n_plotted_points = traces_to_plot.shape[0]
        print(f"  Downsampled to {n_plotted_points} timepoints")
    else:
        traces_to_plot = apd_traces_2d
        indices = np.arange(n_timepoints)
    
    # Create figure with two subplots: one for all traces, one for selected traces
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))
    
    # Plot 1: ALL traces (downsampled in time dimension only)
    ax1 = axes[0]
    for i in range(total_traces):
        ax1.plot(indices, traces_to_plot[:, i], alpha=0.3, linewidth=0.5)
    
    ax1.set_xlabel('Time point index')
    ax1.set_ylabel('APD Intensity (a.u.)')
    
    if downsample and n_timepoints > downsample_factor:
        title1 = f'APD Intensity Traces - {prefix} (All {n_rows}×{n_cols} = {total_traces} traces)\nTimepoints downsampled {downsample_factor}x from {n_timepoints}'
    else:
        title1 = f'APD Intensity Traces - {prefix} (All {n_rows}×{n_cols} = {total_traces} traces)\n{n_timepoints} timepoints each'
    
    ax1.set_title(title1)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Selected traces from different spatial positions (to show spatial variation)
    ax2 = axes[1]
    
    # Select representative traces from different spatial positions
    # Corners and center of the grid
    positions_to_plot = [
        (0, 0), 
        (10, 0), 
        (10, 6), 
        (10, 10),  
        (10, 13),  
        (10, 16),  
        (10, 19), 
    ]
    
    # Filter to valid positions
    positions_to_plot = [(r, c) for r, c in positions_to_plot 
                         if r < n_rows and c < n_cols]
    
    # Create a color map for different positions
    colors = plt.cm.Set1(np.linspace(0, 1, len(positions_to_plot)))
    
    for idx, (row, col) in enumerate(positions_to_plot):
        # Calculate flat index for this position
        flat_idx = row * n_cols + col
        
        # Get the trace (downsampled if applicable)
        if downsample and n_timepoints > downsample_factor:
            trace = apd_traces_2d[indices, flat_idx]
        else:
            trace = apd_traces_2d[:, flat_idx]
        
        # Plot with label showing position
        ax2.plot(indices, trace, color=colors[idx], linewidth=1.5, 
                label=f'Pos ({row},{col})')
    
    ax2.set_xlabel('Time point index')
    ax2.set_ylabel('APD Intensity (a.u.)')
    ax2.set_title(f'Selected APD Traces from Different Spatial Positions - {prefix}')
    ax2.legend(loc='upper right', fontsize=9)
    ax2.grid(True, alpha=0.3)
    
    # Adjust layout and save
    plt.tight_layout()
    output_path = os.path.join(output_dir, f"{prefix}_apd_traces.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved APD traces plot: {os.path.basename(output_path)}")

def plot_monitor_traces(monitor_traces_3d, output_dir, prefix, downsample=True, downsample_factor=100):
    """Plot all MONITOR intensity traces with spatial order preserved."""
    # Flatten while preserving spatial order
    monitor_traces_2d, n_rows, n_cols, total_traces = flatten_traces_preserving_order(monitor_traces_3d)
    
    n_timepoints = monitor_traces_2d.shape[0]
    
    print(f"  Plotting {total_traces} monitor traces (from {n_rows}×{n_cols} grid) with {n_timepoints} timepoints each")
    print(f"  Trace order: raster scan (row-major)")
    
    # Apply downsampling to timepoints if requested
    if downsample and n_timepoints > downsample_factor:
        # Downsample along time dimension
        indices = np.linspace(0, n_timepoints - 1, downsample_factor).astype(int)
        traces_to_plot = monitor_traces_2d[indices, :]
        n_plotted_points = traces_to_plot.shape[0]
        print(f"  Downsampled to {n_plotted_points} timepoints")
    else:
        traces_to_plot = monitor_traces_2d
        indices = np.arange(n_timepoints)
    
    # Create figure with two subplots: one for all traces, one for selected traces
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))
    
    # Plot 1: ALL traces (downsampled in time dimension only)
    ax1 = axes[0]
    for i in range(total_traces):
        ax1.plot(indices, traces_to_plot[:, i], alpha=0.3, linewidth=0.5)
    
    # Calculate mean trace (using all timepoints for accuracy)
    mean_trace_full = np.mean(monitor_traces_2d, axis=1)
    
    # Plot mean trace (downsampled if applicable)
    if downsample and n_timepoints > downsample_factor:
        mean_trace_plot = mean_trace_full[indices]
        ax1.plot(indices, mean_trace_plot, 'k-', linewidth=2, 
                label=f'Mean of {total_traces} traces (timepoints downsampled {downsample_factor}x)')
    else:
        ax1.plot(indices, mean_trace_full, 'k-', linewidth=2, 
                label=f'Mean of {total_traces} traces')
    
    ax1.set_xlabel('Time point index')
    ax1.set_ylabel('Monitor Intensity (a.u.)')
    
    if downsample and n_timepoints > downsample_factor:
        title1 = f'Monitor Intensity Traces - {prefix} (All {n_rows}×{n_cols} = {total_traces} traces)\nTimepoints downsampled {downsample_factor}x from {n_timepoints}'
    else:
        title1 = f'Monitor Intensity Traces - {prefix} (All {n_rows}×{n_cols} = {total_traces} traces)\n{n_timepoints} timepoints each'
    
    ax1.set_title(title1)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Selected traces from different spatial positions
    ax2 = axes[1]
    
    # Select representative traces from different spatial positions
    positions_to_plot = [
        (0, 0),  # Top-left
        (0, n_cols-1),  # Top-right
        (n_rows-1, 0),  # Bottom-left
        (n_rows-1, n_cols-1),  # Bottom-right
        (n_rows//2, n_cols//2),  # Center
    ]
    
    # Filter to valid positions
    positions_to_plot = [(r, c) for r, c in positions_to_plot 
                         if r < n_rows and c < n_cols]
    
    # Create a color map for different positions
    colors = plt.cm.Set2(np.linspace(0, 1, len(positions_to_plot)))
    
    for idx, (row, col) in enumerate(positions_to_plot):
        # Calculate flat index for this position
        flat_idx = row * n_cols + col
        
        # Get the trace (downsampled if applicable)
        if downsample and n_timepoints > downsample_factor:
            trace = monitor_traces_2d[indices, flat_idx]
        else:
            trace = monitor_traces_2d[:, flat_idx]
        
        # Plot with label showing position
        ax2.plot(indices, trace, color=colors[idx], linewidth=1.5, 
                label=f'Pos ({row},{col})')
    
    ax2.set_xlabel('Time point index')
    ax2.set_ylabel('Monitor Intensity (a.u.)')
    ax2.set_title(f'Selected Monitor Traces from Different Spatial Positions - {prefix}')
    ax2.legend(loc='upper right', fontsize=9)
    ax2.grid(True, alpha=0.3)
    
    # Adjust layout and save
    plt.tight_layout()
    output_path = os.path.join(output_dir, f"{prefix}_monitor_traces.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved monitor traces plot: {os.path.basename(output_path)}")

def plot_2d_scan_image_with_coords(image_data, coords, output_dir, prefix):
    """Plot the 2D scan image with actual coordinates in microns."""
    n_rows, n_cols = image_data.shape
    
    # Get coordinate grids
    # These are the centers of the pixels
    x_grid, y_grid = get_coordinate_grids(coords, (n_rows, n_cols))
    
    # Create figure
    fig, ax = plt.subplots()
    
    # Use extent for imshow based on coordinate ranges
    x_min, x_max = x_grid.min(), x_grid.max()
    y_min, y_max = y_grid.min(), y_grid.max()
    step_x = (x_max - x_min) / (n_cols - 1) if n_cols > 1 else 1
    step_y = (y_max - y_min) / (n_rows - 1) if n_rows > 1 else 1
    # Adjust extent to the edges of the pixels
    x_min_edge = x_min - step_x / 2
    x_max_edge = x_max + step_x / 2
    y_min_edge = y_min - step_y / 2
    y_max_edge = y_max + step_y / 2
    extent = [x_min_edge, x_max_edge, y_min_edge, y_max_edge]
    # Set ticks (user can adjust as needed)
    x_label_list = np.linspace(x_min_edge, x_max_edge, num=4)
    y_label_list = np.linspace(y_min_edge, y_max_edge, num=4)

    # Plot with actual coordinates
    im = ax.imshow(image_data, cmap='viridis', aspect='equal', 
                    extent=extent, origin='upper')
    plt.xticks(x_label_list, fontsize=22)
    plt.yticks(y_label_list, fontsize=22)
    ax.set_xlabel('X position (µm)', fontsize=22)
    ax.set_ylabel('Y position (µm)', fontsize=22)
    ax.set_title(f'2D Confocal Scan - {prefix}', pad=40, fontsize=18)       
    # Add colorbar
    colorbar_ticks = np.linspace(np.min(image_data), np.max(image_data), num=5)
    colorbar_ticks_labels = [f"{tick:.3f}" for tick in colorbar_ticks]
    cbar = plt.colorbar(im, ax=ax, ticks=colorbar_ticks)
    cbar.ax.set_yticklabels(colorbar_ticks_labels)  # vertically oriented colorbar
    cbar.ax.set_title('Intensity (arb. units)', size=22, pad=15)
    cbar.ax.tick_params(labelsize=22)
    
    # Save with tight layout and 300 dpi
    output_path = os.path.join(output_dir, f"{prefix}_2d_scan_coords.png")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    
    # Save but with a scale bar
    # Add scale bar (example: 10 µm)
    scale_bar_length = 0.5 # in microns
    # Calculate the position of the scale bar
    scale_bar_x = x_min + 0.05 * (x_max - x_min)
    scale_bar_y = y_min + 0.05 * (y_max - y_min)
    # Draw the scale bar
    ax.plot([scale_bar_x, scale_bar_x + scale_bar_length], [scale_bar_y, scale_bar_y], 
            color='white', linewidth=8)
    # Add text label for the scale bar
    ax.text(scale_bar_x + scale_bar_length/2, scale_bar_y + 0.1*(y_max-y_min), 
            f'{int(scale_bar_length*1000)} nm', ha='center', va='top', fontsize=16, color='white')
    # Hide axes, tick labels and axes labels for cleaner look
    ax.set_axis_off()
    ax.set_title('')
    # ax.set_xlabel('')
    # ax.set_ylabel('')
    # ax.set_xticklabels([])
    # ax.set_yticklabels([])
    # plt.tight_layout()
    output_path_pdf = os.path.join(output_dir, f"{prefix}_2d_scan_coords.pdf")
    plt.savefig(output_path_pdf, dpi=300, bbox_inches='tight', format='pdf')
    plt.close()
    print(f"  Saved 2D scan plot with coordinates: {os.path.basename(output_path)}")

def create_apd_statistics_maps_with_coords(apd_traces_3d, coords, output_dir, prefix):
    """Create 2D maps of mean, std dev, and SNR from APD traces using actual coordinates."""
    
    n_rows, n_cols, n_timepoints = apd_traces_3d.shape
    total_traces = n_rows * n_cols
    
    print(f"  Creating statistics maps from {total_traces} traces ({n_timepoints} timepoints each)")

    # Get coordinate grids
    x_grid, y_grid = get_coordinate_grids(coords, (n_rows, n_cols))
    
    # Calculate statistics directly on the 3D array
    mean_map = np.mean(apd_traces_3d, axis=2)
    std_map = np.std(apd_traces_3d, axis=2)
    
    # Calculate SNR, handling potential division by zero
    with np.errstate(divide='ignore', invalid='ignore'):
        snr_map = np.where(std_map != 0, mean_map / std_map, np.nan)
    
     # Use extent for imshow based on coordinate ranges
    x_min, x_max = x_grid.min(), x_grid.max()
    y_min, y_max = y_grid.min(), y_grid.max()
    step_x = (x_max - x_min) / (n_cols - 1) if n_cols > 1 else 1
    step_y = (y_max - y_min) / (n_rows - 1) if n_rows > 1 else 1
    # Adjust extent to the edges of the pixels
    x_min_edge = x_min - step_x / 2
    x_max_edge = x_max + step_x / 2
    y_min_edge = y_min - step_y / 2
    y_max_edge = y_max + step_y / 2
    extent = [x_min_edge, x_max_edge, y_min_edge, y_max_edge]
    # # Set ticks (user can adjust as needed)
    # x_label_list = np.linspace(x_min_edge, x_max_edge, num=4)
    # y_label_list = np.linspace(y_min_edge, y_max_edge, num=4)

    # Create a figure with 3 subplots
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    
    # Plot mean map with coordinates
    im1 = axes[0].imshow(mean_map, cmap='viridis', aspect='equal', 
                        extent=extent, origin='upper')
    axes[0].set_xlabel('X position (µm)', fontsize=22)
    axes[0].set_ylabel('Y position (µm)', fontsize=22)
    axes[0].set_title(f'Mean APD Intensity - {prefix}', fontsize=22, pad=60)
    # Add colorbar
    colorbar_ticks = np.linspace(np.min(mean_map), np.max(mean_map), num=5)
    colorbar_ticks_labels = [f"{tick:.3f}" for tick in colorbar_ticks]
    cbar = plt.colorbar(im1, ax=axes[0], ticks=colorbar_ticks)
    cbar.ax.set_yticklabels(colorbar_ticks_labels)  # vertically oriented colorbar
    cbar.ax.set_title('Mean Intensity (arb. units)', size=22, pad=15)
    cbar.ax.tick_params(labelsize=22)

    # Plot std dev map with coordinates
    im2 = axes[1].imshow(std_map, cmap='viridis', aspect='equal', 
                        extent=extent, origin='upper')
    axes[1].set_xlabel('X position (µm)', fontsize=22)
    axes[1].set_ylabel('Y position (µm)', fontsize=22)
    axes[1].set_title(f'Std Dev APD Intensity - {prefix}', fontsize=22, pad=60)
    # Add colorbar
    colorbar_ticks = np.linspace(np.min(std_map), np.max(std_map), num=5)
    colorbar_ticks_labels = [f"{tick:.4f}" for tick in colorbar_ticks]
    cbar = plt.colorbar(im2, ax=axes[1], ticks=colorbar_ticks)
    cbar.ax.set_yticklabels(colorbar_ticks_labels)  # vertically oriented colorbar
    cbar.ax.set_title('Std Dev (arb. units)', size=22, pad=15)
    cbar.ax.tick_params(labelsize=22)

    # Plot SNR map with coordinates   
    im3 = axes[2].imshow(snr_map, cmap='viridis', aspect='equal', 
                            extent=extent, origin='upper')
    
    axes[2].set_xlabel('X position (µm)', fontsize=22)
    axes[2].set_ylabel('Y position (µm)', fontsize=22)
    axes[2].set_title(f'APD SNR (Mean/Std Dev) - {prefix}', fontsize=22, pad=60)
        # Add colorbar
    colorbar_ticks = np.linspace(np.min(snr_map), np.max(snr_map), num=5)
    colorbar_ticks_labels = [f"{tick:.1f}" for tick in colorbar_ticks]
    cbar = plt.colorbar(im3, ax=axes[2], ticks=colorbar_ticks)
    cbar.ax.set_yticklabels(colorbar_ticks_labels)  # vertically oriented colorbar
    cbar.ax.set_title('SNR', size=22, pad=15)
    cbar.ax.tick_params(labelsize=22)
    
    # Save with tight layout and 300 dpi
    output_path = os.path.join(output_dir, f"{prefix}_apd_statistics_maps_coords.png")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    output_path = os.path.join(output_dir, f"{prefix}_apd_statistics_maps_coords.pdf")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', format='pdf')
    plt.close()
    print(f"  Saved APD statistics maps with coordinates: {os.path.basename(output_path)}")

def main():
    """Main function to run the analysis."""
    print("Confocal Scan Data Analysis Tool")
    print("=" * 40)
    print("This script will:")
    print("1. Open a folder selection dialog")
    print("2. Find and load confocal scan data files")
    print("3. Generate and save various plots in PNG format (300 dpi)")
    print("\nExpected file patterns:")
    print("  - APD traces: XN_confocal_apd_traces_%04d.npy (shape: rows × cols × timepoints)")
    print("  - Coordinates: XN_xy_coords_%04d.npy (x, y positions in microns)")
    print("  - 2D image: XN_image_%04d.npy")
    print("  - Monitor traces: XN_confocal_monitor_traces_%04d.npy (shape: rows × cols × timepoints)")
    print("\nImages will use actual coordinates in microns from xy_coords file")
    
    # Start processing with default downsampling
    process_confocal_data(downsample_timepoints=False, downsample_factor=100)

if __name__ == "__main__":
    main()