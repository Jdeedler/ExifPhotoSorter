
# EXIF PhotoSorter

![PhotoSorter](PhotoSorter.PNG?raw=true "PhotoSorter")

## Overview
The EXIF PhotoSorter Application is a standalone executable designed to automatically sort your digital photos into a neatly organized folder structure. It analyzes each photo's EXIF data for date and location information, allowing you to categorize images by date, location, or both. This application is perfect for photographers, travelers, or anyone looking to bring order to their digital photo collection.

## Key Features
- **Standalone Executable**: No need for a separate Python environment or dependencies.
- **EXIF Data Utilization**: Organizes photos based on embedded metadata, including capture date and GPS coordinates.
- **Advanced Geolocation**: Uses reverse geocoding to translate GPS data into readable locations, facilitating sorting by cities, states, or countries.
- **Customizable through `.ini` File**: All preferences, including paths and sorting criteria, are configurable in an easy-to-edit `.ini` file.
- **Logging Support**: Monitors and records operational processes, assisting in troubleshooting and auditing of the application's activities.

## Getting Started

### Internet Connection Requirement

For geolocation features, this application utilizes OpenStreetMap through the `geopy` library for reverse geocoding. An active internet connection is required to fFetch geolocation data for organizing photos based on location.

API calls to OpenStreetMap are made and cached every 1.5 seconds to avoid breaking OpenStreetMap API usage policy.


Ensure your firewall or internet security settings allow the application to make external requests to OpenStreetMap's services.

### Installation
Download and place it in your desired location. Ensure the accompanying `config.ini` file is in the same directory as the executable.

### Configuration
Before running the application, open the `config.ini` file in a text editor to adjust the settings to your preferences. Important sections include:
- `[general]`: Basic operation settings, such as whether to copy or move files.
- `[input]`: Specifies the directory to scan for photos and which file types to include.
- `[output]`: Defines the output directory, logging options, and directory structure for organized photos.
- `[geocoding]`: Adjustments for geolocation features, like API keys and rate limiting.
Ensure to save your changes before closing the editor.

### Usage
To start the photo organization process, simply double-click the executable file. The application will read your configuration from `config.ini` and begin processing photos accordingly. Progress and any issues encountered will be logged as per the settings specified in the configuration file.

## Support
For troubleshooting, refer to the `photo_sort.log` file in your output directory.

## Contribution
Feedback and contributions are welcome.

## License
The EXIF PhotoSorter is freely available under the MIT License.
