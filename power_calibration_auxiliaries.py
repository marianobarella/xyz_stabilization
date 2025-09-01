# -*- coding: utf-8 -*-
"""
Created on Mon September 1, 2025

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""
param_power_calib_filename = 'C:\\Users\\superuser\\Documents\\repos\\xyz_stabilization\\power_calibration_parameters.txt'

def read_power_calibration_params_file(filename):
    with open(filename, 'r') as file:
        content = file.read()
        data_section = content.split("### INPUT MODIFY BELOW THIS LINE ###")[1]
        
        # Parse the variables into a dictionary
        config = {}
        for line in data_section.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    factor = float(config['factor'])
    offset = float(config['offset'])
    print('\nPower calibration parameters are:')
    print(config)
    return factor, offset

def update_power_calibration_params_file(filename, factor=None, offset=None):
    try:
        with open(filename, 'r') as file:
            lines = file.readlines()
        
        # Find the header line index
        header_index = -1
        for i, line in enumerate(lines):
            if "### INPUT MODIFY BELOW THIS LINE ###" in line:
                header_index = i
                break
        
        if header_index == -1:
            raise ValueError("Header not found in file")
        
        # Modify lines after the header
        for i in range(header_index + 1, len(lines)):
            line = lines[i].strip()
            if not line or line.startswith('#'):
                continue
            
            if factor is not None and line.startswith('factor ='):
                lines[i] = f"factor = {str(factor)}\n"
            elif offset is not None and line.startswith('offset ='):
                lines[i] = f"offset = {str(offset)}\n"
        
        # Write back to the file
        with open(filename, 'w') as file:
            file.writelines(lines)
            
        print("File updated successfully!")
        
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found")
    except Exception as e:
        print(f"Error: {e}")