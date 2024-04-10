"""
EXIF PhotoSorter Application

This standalone executable Python script organizes digital photos into a structured
directory format based on their EXIF data and geolocation information. It sorts and
optionally renames photos leveraging the embedded metadata for date and GPS coordinates,
utilizing reverse geocoding to translate GPS data into readable locations.

Features:
- EXIF Data Extraction: Analyzes photos for metadata including capture date and GPS coordinates.
- Advanced Geolocation: Employs reverse geocoding to sort photos by cities, states, or countries.
- Customizable Configuration: Utilizes an .ini file for easy adjustment of operation modes, paths, and criteria.
- Logging: Provides operational feedback and error logging for auditing and troubleshooting.

Requirements:
- Python 3.6 or later.
- External libraries: geopy, configparser, and exif. See requirements.txt for details.
- An active internet connection for geolocation features using OpenStreetMap's API.

Usage:
1. Ensure all prerequisites are installed and an active internet connection is available.
2. Configure the `config.ini` file to specify input/output directories, file types, and other preferences.
3. Run the script directly from the command line or by double-clicking the compiled executable.

Author: James Deedler
License: MIT License
Version: 1.0.1
Date: 04/10/2024

Please see the accompanying README.md file for more detailed information and usage instructions.
"""

# Standard library imports
import asyncio
import concurrent.futures
import configparser
import json
import logging
import os
import shutil
import tkinter as tk
import re
import logging
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

# Related third party imports
from exif import Image
from geopy.distance import geodesic
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim
from typing import List, Optional, Tuple
from unidecode import unidecode

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config(config_file: str) -> dict:
    """ Load configuration settings from a file. If the file is missing or incomplete, use default values for missing options. """
    default_config = {
        'general': {
            'operation_mode': 'sort',
            'copy_files': 'True',
            'preserve_directory_structure': 'True',
            'min_file_size': '0',
            'max_file_size': '0'
        },
        'input': {
            'input_directory': 'C:\\Users\\',
            'recursive_search': 'True',
            'file_extensions': '.jpg, .jpeg, .png, .bmp, .tiff, .heic'
        },
        'output': {
            'output_directory': 'C:\\Users\\',
            'create_date_subdirectories': 'True',
            'log_file': 'photo_sort.log',
            'log_level': 'INFO'
        },
        'sorting': {
            'sort_by_location': 'True',
            'sort_by_date': 'True',
            'group_by_country': 'False',
            'group_by_state': 'False',
            'group_by_city': 'True',
            'date_format': '%%Y-%%m-%%d',
            'group_by_year': 'False',
            'group_by_month': 'False'
        },
        'renaming': {
            'rename_photos': 'False',
            'rename_format': '{date}_{location}_{original_name}',
            'original_name_placeholder': '{original_name}',
            'date_placeholder': '{date}',
            'location_placeholder': '{location}'
        },
        'geocoding': {
            'cache_distance_threshold': '1.0',
            'geocoding_service': 'nominatim',
            'geocoding_api_key': '',
            'geocoding_timeout': '10',
            'geocoding_max_retries': '3'
        },
        'exif': {
            'use_exif_date': 'True',
            'fallback_to_file_date': 'True',
            'date_taken_key': 'DateTime',
            'use_exif_gps': 'True'
        },
        'preprocessing': {
            'rotate_images': 'False',
            'optimize_images': 'False',
            'target_quality': '85',
            'resize_images': 'False',
            'max_width': '1920',
            'max_height': '1080'
        },
        'duplicates': {
            'skip_duplicates': 'True',
            'duplicate_suffix': '_duplicate',
            'duplicate_check_method': 'hash',
            'duplicate_similarity_threshold': '0.9'
        },
        'unsortable': {
            'unsortable_folder': 'Unsortable',
            'move_unsortable': 'False',
            'copy_unsortable': 'True'
        },
        'interface': {
            'theme': 'default',
            'show_preview': 'True',
            'confirm_actions': 'True'
        },
        'advanced': {
            'parallel_processing': 'True',
            'max_processes': '4',
            'cache_geocoding_results': 'True',
            'geocoding_cache_size': '100',
            'ignore_errors': 'False'
        }
    }

    config = configparser.ConfigParser()

    if os.path.exists(config_file):
        config.read(config_file)
    else:
        logger.warning(f"Configuration file not found: {config_file}. Using default values.")
        with open(config_file, 'w') as configfile:
            config.write(configfile)

    # Check for missing options and add default values
    for section, options in default_config.items():
        if not config.has_section(section):
            config.add_section(section)
        for option, value in options.items():
            if not config.has_option(section, option):
                config.set(section, option, value)

    return config

def save_config(config: configparser.ConfigParser, config_file: str) -> None:
    """
    Save the configuration to a file.
    """
    try:
        with open(config_file, 'w') as file:
            config.write(file)
        logger.info(f"Configuration saved to {config_file}")
    except IOError as e:
        logger.error(f"Error saving configuration to {config_file}: {str(e)}")

def configure_file_logging(log_file: str, log_level: str) -> None:
    """
    Configure logging to write log messages to a file.
    """
    handler = logging.FileHandler(log_file)
    handler.setLevel(getattr(logging, log_level))
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

# Load configuration
config_file = "config.ini"
config = load_config(config_file)

# Configure file logging based on the configuration
log_file = config.get('output', 'log_file')
log_level = config.get('output', 'log_level')
configure_file_logging(log_file, log_level)

class ExifExtractor:
    def __init__(self, config):
        self.config = config

    def extract_exif_data(self, photo_path: str) -> Optional[Image]:
        """
        Extract EXIF data from the photo file.
        
        Parameters:
            photo_path (str): The path to the photo file.
        
        Returns:
            Optional[Image]: The Image object if successful, None otherwise.
        """
        try:
            with open(photo_path, 'rb') as file:
                return Image(file)
        except FileNotFoundError:
            logger.error(f"File not found: {photo_path}")
        except Exception as e:
            logger.error(f"Error extracting EXIF data from {photo_path}: {str(e)}")
        return None

    def get_gps_coordinates(self, image: Image) -> Tuple[Optional[float], Optional[float]]:
        """
        Get the GPS coordinates from the image's EXIF data.
        
        Parameters:
            image (Image): The image object.
        
        Returns:
            Tuple[Optional[float], Optional[float]]: The latitude and longitude in decimal degrees if available, None otherwise.
        """
        if not (image and image.has_exif):
            return None, None

        try:
            if self.config.getboolean('exif', 'use_exif_gps'):
                latitude = image.gps_latitude
                longitude = image.gps_longitude

                if not (latitude and longitude):
                    logger.warning("No GPS coordinates found in the image")
                    return None, None

                if isinstance(latitude, tuple) and isinstance(longitude, tuple):
                    lat_ref = image.gps_latitude_ref
                    lon_ref = image.gps_longitude_ref
                    lat = self._convert_to_decimal_degrees(latitude, lat_ref)
                    lon = self._convert_to_decimal_degrees(longitude, lon_ref)
                    return lat, lon
                elif isinstance(latitude, float) and isinstance(longitude, float):
                    return latitude, longitude
                else:
                    logger.warning("GPS coordinates not in the expected format for the image")
            else:
                logger.info("EXIF GPS coordinates extraction disabled in the configuration")
        except (AttributeError, TypeError, IndexError):
            logger.warning("Error retrieving GPS coordinates from the image")
        return None, None

    @staticmethod
    def _convert_to_decimal_degrees(coord: Tuple[float, float, float], ref: str) -> Optional[float]:
        """
        Convert GPS coordinates from degrees, minutes, seconds to decimal degrees.
        
        Parameters:
            coord (Tuple[float, float, float]): The GPS coordinate.
            ref (str): The direction reference (N, S, E, W).
        
        Returns:
            Optional[float]: The coordinate in decimal degrees.
        """
        try:
            decimal_degrees = coord[0] + coord[1] / 60 + coord[2] / 3600
            if ref == "S" or ref == "W":
                decimal_degrees = -decimal_degrees
            return decimal_degrees
        except (TypeError, IndexError):
            logger.warning("Error converting GPS coordinates to decimal degrees")
            return None

    def get_photo_date(self, image: Image) -> Optional[datetime]:
        """
        Get the photo capture date from the image's EXIF data.
        
        Parameters:
            image (Image): The image object.
        
        Returns:
            Optional[datetime]: The date as a datetime object if available, None otherwise.
        """
        if not (image and image.has_exif):
            return None

        try:
            if self.config.getboolean('exif', 'use_exif_date'):
                date_key = self.config.get('exif', 'date_taken_key')
                date_str = getattr(image, date_key, None)
                if date_str:
                    return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            else:
                logger.info("EXIF date extraction disabled in the configuration")
        except AttributeError:
            if self.config.getboolean('exif', 'fallback_to_file_date'):
                logger.warning("No date information found in the image.")
                # return datetime.fromtimestamp(os.path.getmtime(image))
            else:
                logger.warning("No date information found in the image.")
        return None

class Geolocator:
    def __init__(self, config):
        self.config = config
        self.geolocator = Nominatim(user_agent=self.config.get('geocoding', 'geocoding_service'))
        self.reverse = RateLimiter(self.geolocator.reverse, min_delay_seconds=1.5)
        self.cache_file = "location_cache.json"
        self.cache_distance_threshold = self.config.getfloat('geocoding', 'cache_distance_threshold')
        self.location_cache = self._load_cache()

    def _load_cache(self) -> dict:
        """
        Load the location cache from file.
        
        Returns:
            dict: The location cache as a dictionary.
        """
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_cache(self) -> None:
        """
        Save the location cache to file.
        """
        with open(self.cache_file, 'w') as f:
            json.dump(self.location_cache, f)

    def _parse_location(self, location) -> Optional[str]:
        """
        Parse the location details from the geocoding result.
        
        Parameters:
            location: The geocoding result.
        
        Returns:
            Optional[str]: The location string (city, state, country) if found, None otherwise.
        """
        if location:
            address = location.raw['address']
            city = address.get('city') or address.get('town') or address.get('village')
            state = address.get('state') or address.get('county')
            country = address.get('country')
            location_str = ', '.join(filter(None, [city, state, country]))
            return location_str
        return None

    def _is_cached_location_nearby(self, latitude: float, longitude: float) -> Optional[str]:
        """
        Check if a nearby location is already cached.
        
        Parameters:
            latitude (float): The latitude of the location.
            longitude (float): The longitude of the location.
        
        Returns:
            Optional[str]: The cached location string if found, None otherwise.
        """
        for cached_location, location_str in self.location_cache.items():
            if geodesic((latitude, longitude), tuple(map(float, cached_location.split(', ')))).km <= self.cache_distance_threshold:
                return location_str
        return None

    def reverse_geocode(self, latitude: float, longitude: float) -> Optional[str]:
        """
        Reverse geocode the GPS coordinates to get the location details.
        
        Parameters:
            latitude (float): The latitude of the coordinates.
            longitude (float): The longitude of the coordinates.
        
        Returns:
            Optional[str]: The location string (city, state, country) if found, None otherwise.
        """
        try:
            if self.config.getboolean('advanced', 'cache_geocoding_results'):
                cached_location = self._is_cached_location_nearby(latitude, longitude)
                if cached_location:
                    return cached_location

            location = self.reverse(f"{latitude}, {longitude}", timeout=self.config.getint('geocoding', 'geocoding_timeout'))
            location_str = self._parse_location(location)

            if location_str:
                if self.config.getboolean('advanced', 'cache_geocoding_results'):
                    self.location_cache[f"{latitude}, {longitude}"] = location_str
                    self._save_cache()

            return location_str
        except Exception as e:
            logger.error(f"Error reverse geocoding coordinates ({latitude}, {longitude}): {str(e)}")
            return None
        
class PhotoProcessor:
    def __init__(self, exif_extractor, geolocator, config):
        self.exif_extractor = exif_extractor
        self.geolocator = geolocator
        self.config = config
        logger.info("PhotoProcessor initialized")

    async def process_photos(self, photo_paths: List[str], output_directory: str):
        """
        Asynchronously process multiple photo files.

        Parameters:
            photo_paths (List[str]): A list of paths to the photo files.
            output_directory (str): The directory to save processed photos.

        Yields:
            A tuple containing progress information and the current file being processed.
        """
        total_photos = len(photo_paths)
        processed_photos = 0
        sortable_photos = 0
        unsortable_photos = 0
        logger.info(f"Processing {total_photos} photos")

        for photo_path in photo_paths:
            try:
                logger.info(f"Processing photo: {photo_path}")
                exif_data = self.exif_extractor.extract_exif_data(photo_path)
                if not exif_data:
                    logger.warning(f"No EXIF data found for {photo_path}")
                    unsortable_photos += 1
                    yield processed_photos + 1, total_photos, sortable_photos, unsortable_photos, photo_path
                    continue

                latitude, longitude = self._get_gps_coordinates(exif_data)
                photo_date = self._get_photo_date(exif_data)

                if self._validate_gps_coordinates(latitude, longitude):
                    logger.info(f"Valid GPS coordinates found for {photo_path}")
                    city_rgeo = await self._reverse_geocode(latitude, longitude)
                    city = self._apply_location_filters(city_rgeo)
                    if city:
                        logger.info(f"Reverse geocoded city: {city}")
                        output_path = self._create_output_path(output_directory, city, photo_date)
                        is_sortable = True
                    else:
                        logger.warning(f"No city found for {photo_path}")
                        output_path = self._create_unsortable_path(output_directory, photo_date)
                        is_sortable = False
                else:
                    logger.warning(f"Invalid GPS coordinates for {photo_path}")
                    output_path = self._create_unsortable_path(output_directory, photo_date)
                    is_sortable = False

                if self.config.getboolean('general', 'copy_files'):
                    logger.info(f"Copying {photo_path} to {output_path}")
                    destination_path = await self._copy_photo(photo_path, output_path)
                else:
                    logger.info(f"Moving {photo_path} to {output_path}")
                    destination_path = await self._move_photo(photo_path, output_path)

                processed_photos += 1
                if is_sortable:
                    sortable_photos += 1
                else:
                    unsortable_photos += 1

                yield processed_photos, total_photos, sortable_photos, unsortable_photos, photo_path
            except Exception as e:
                logger.error(f"Error processing photo {photo_path}: {str(e)}")
                unsortable_photos += 1
                yield processed_photos, total_photos, sortable_photos, unsortable_photos, photo_path

        logger.info(f"Photo processing completed: {processed_photos}/{total_photos} processed, {sortable_photos} sortable, {unsortable_photos} unsortable")

    def _get_gps_coordinates(self, exif_data: Image) -> Tuple[Optional[float], Optional[float]]:
        """
        Extract GPS coordinates from EXIF data of an image.

        Parameters:
            exif_data (Image): The image object containing EXIF data.

        Returns:
            Tuple[Optional[float], Optional[float]]: The latitude and longitude extracted from the EXIF data, or (None, None) if not available or an error occurs.
        """
        try:
            latitude, longitude = self.exif_extractor.get_gps_coordinates(exif_data)
            logger.info(f"Latitude: {latitude}, Longitude: {longitude}")
            return latitude, longitude
        except Exception as e:
            logger.error(f"Error getting GPS coordinates: {str(e)}")
            return None, None

    def _validate_gps_coordinates(self, latitude: Optional[float], longitude: Optional[float]) -> bool:
        """
        Validate the GPS coordinates to check if they fall within a predefined range (e.g., within the USA).

        Parameters:
            latitude (Optional[float]): The latitude to validate.
            longitude (Optional[float]): The longitude to validate.

        Returns:
            bool: True if the coordinates are within the valid range, False otherwise.
        """
        if latitude is None or longitude is None:
            logger.warning("No GPS coordinates found")
            return False
        if not (24 <= latitude <= 49 and -125 <= longitude <= -66):
            logger.warning("GPS coordinates outside USA range")
            return False
        return True

    async def _reverse_geocode(self, latitude: float, longitude: float) -> Optional[str]:
        """
        Asynchronously reverse geocode GPS coordinates to get the nearest city name.

        Parameters:
            latitude (float): The latitude of the coordinates.
            longitude (float): The longitude of the coordinates.

        Returns:
            Optional[str]: The name of the closest city if found, None otherwise.
        """
        try:
            city = await asyncio.to_thread(self.geolocator.reverse_geocode, latitude, longitude)
            if not city:
                logger.warning("No city found")
            else:
                city = unidecode(city)
                logger.info(f"Closest city: {city}")
            return city
        except Exception as e:
            logger.error(f"Error reverse geocoding coordinates ({latitude}, {longitude}): {str(e)}")
            return None

    def _apply_location_filters(self, city_rgeo: str) -> str:
        """
        Apply location-based filters to the city name based on the configuration settings.

        Parameters:
            city_rgeo (str): The reverse-geocoded city name.

        Returns:
            str: The filtered city name.
        """
        location_parts = city_rgeo.split(', ')

        if self.config.getboolean('sorting', 'group_by_country'):
            return location_parts[-1]
        elif self.config.getboolean('sorting', 'group_by_state'):
            return ', '.join(location_parts[-2:])
        elif self.config.getboolean('sorting', 'group_by_city'):
            return ', '.join(reversed(location_parts))
        else:
            return ', '.join(reversed(location_parts))

    def _get_photo_date(self, exif_data: Image) -> Optional[datetime]:
        """
        Extract the photo date from an image's EXIF data.

        Parameters:
            exif_data (Image): The image object containing EXIF data.

        Returns:
            Optional[datetime]: The date the photo was taken, if available. None otherwise.
        """
        try:
            photo_date = self.exif_extractor.get_photo_date(exif_data)
            if not photo_date:
                logger.warning("No date information found")
            else:
                logger.info(f"Photo date: {photo_date}")
            return photo_date
        except Exception as e:
            logger.error(f"Error getting photo date: {str(e)}")
            return None

    def _create_output_path(self, output_directory: str, city: str, photo_date: Optional[datetime]) -> str:
        """
        Create an output path for a photo based on its geolocation and date.

        Parameters:
            output_directory (str): The base directory for output.
            city (str): The city name for directory structuring.
            photo_date (Optional[datetime]): The date the photo was taken.

        Returns:
            str: The path to the directory where the photo should be saved.
        """
        try:
            if self.config.getboolean('sorting', 'sort_by_date') and photo_date:
                date_format = self.config.get('sorting', 'date_format')
                date_dir = photo_date.strftime(date_format)
                if self.config.getboolean('sorting', 'sort_by_location'):
                    output_path = os.path.join(output_directory, city, date_dir)
                else:
                    output_path = os.path.join(output_directory, date_dir)
            else:
                if self.config.getboolean('sorting', 'sort_by_location'):
                    output_path = os.path.join(output_directory, city)
                else:
                    output_path = output_directory
            os.makedirs(output_path, exist_ok=True)
            logger.info(f"Output directory created: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error creating output directory: {str(e)}")
            raise

    def _create_unsortable_path(self, output_directory: str, photo_date: Optional[datetime]) -> str:
        """
        Create a path for photos that cannot be sorted by location.

        Parameters:
            output_directory (str): The base directory for output.
            photo_date (Optional[datetime]): The date the photo was taken, if available.

        Returns:
            str: The path to the directory for unsortable photos.
        """
        try:
            unsortable_folder = self.config.get('unsortable', 'unsortable_folder')
            unsortable_dir = os.path.join(output_directory, unsortable_folder)
            if self.config.getboolean('sorting', 'sort_by_date') and photo_date:
                date_format = self.config.get('sorting', 'date_format')
                date_dir = photo_date.strftime(date_format)
                output_path = os.path.join(unsortable_dir, date_dir)
            else:
                output_path = unsortable_dir
            os.makedirs(output_path, exist_ok=True)
            logger.info(f"Unsortable directory created: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error creating unsortable directory: {str(e)}")
            raise

    async def _copy_photo(self, photo_path: str, output_path: str) -> Optional[str]:
        """
        Asynchronously copy a photo to the specified output path.

        Parameters:
            photo_path (str): The path to the original photo.
            output_path (str): The destination directory for the photo.

        Returns:
            Optional[str]: The path to the copied photo, or None if an error occurs.
        """
        try:
            photo_name = os.path.basename(photo_path)
            destination_path = os.path.join(output_path, photo_name)

            if self.config.getboolean('duplicates', 'skip_duplicates') and os.path.exists(destination_path):
                logger.info(f"Skipping duplicate file: {photo_path}")
                return None

            if os.path.exists(destination_path):
                base, ext = os.path.splitext(photo_name)
                duplicate_suffix = self.config.get('duplicates', 'duplicate_suffix')
                i = 1
                while os.path.exists(os.path.join(output_path, f"{base}{duplicate_suffix}{i}{ext}")):
                    i += 1
                destination_path = os.path.join(output_path, f"{base}{duplicate_suffix}{i}{ext}")
                logger.info(f"Duplicate file detected. New destination path: {destination_path}")

            await asyncio.to_thread(shutil.copy2, photo_path, destination_path)
            logger.info(f"Photo copied to: {destination_path}")
            return destination_path
        except Exception as e:
            logger.error(f"Error copying photo {photo_path} to {destination_path}: {str(e)}")
            return None

    async def _move_photo(self, photo_path: str, output_path: str) -> Optional[str]:
        """
        Asynchronously move a photo to the specified output path.

        Parameters:
            photo_path (str): The path to the original photo.
            output_path (str): The destination directory for the photo.

        Returns:
            Optional[str]: The path to the moved photo, or None if an error occurs.
        """
        try:
            photo_name = os.path.basename(photo_path)
            destination_path = os.path.join(output_path, photo_name)

            if self.config.getboolean('duplicates', 'skip_duplicates') and os.path.exists(destination_path):
                logger.info(f"Skipping duplicate file: {photo_path}")
                return None

            if os.path.exists(destination_path):
                base, ext = os.path.splitext(photo_name)
                duplicate_suffix = self.config.get('duplicates', 'duplicate_suffix')
                i = 1
                while os.path.exists(os.path.join(output_path, f"{base}{duplicate_suffix}{i}{ext}")):
                    i += 1
                destination_path = os.path.join(output_path, f"{base}{duplicate_suffix}{i}{ext}")
                logger.info(f"Duplicate file detected. New destination path: {destination_path}")

            await asyncio.to_thread(shutil.move, photo_path, destination_path)
            logger.info(f"Photo moved to: {destination_path}")
            return destination_path
        except Exception as e:
            logger.error(f"Error moving photo {photo_path} to {destination_path}: {str(e)}")
            return None
                
class GUI:
    def __init__(self, config, photo_processor):
        self.root = tk.Tk()
        self.root.title("Photo Sorter")
        self.root.geometry("400x500")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.config = config
        self.cache_distance_threshold = config.getfloat('geocoding', 'cache_distance_threshold')
        self.photo_processor = photo_processor
        self.photo_paths = [] 
        self.output_directory = ''  
        self.run_async_task = None  
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.create_menu()
        self.create_widgets()
        self.root.after(100, self.update_async_loop)  # Schedule periodic async loop update
        self.run()  # Start the asyncio event loop
        

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Configuration", command=self.open_config_window)
        menubar.add_cascade(label="Settings", menu=settings_menu)

    def open_config_window(self):
        config_window = tk.Toplevel(self.root)
        config_window.title("Configuration")
        config_window.geometry("660x350")

        notebook = ttk.Notebook(config_window)
        notebook.pack(fill=tk.BOTH, expand=True)

        sections = self.config.sections()
        self.config_vars = {}

        for section in sections:
            section_frame = ttk.Frame(notebook)
            notebook.add(section_frame, text=section)

            options = self.config.options(section)
            self.config_vars[section] = {}

            for option in options:
                option_frame = ttk.Frame(section_frame)
                option_frame.pack(anchor=tk.W, padx=10, pady=5)

                label = ttk.Label(option_frame, text=option)
                label.pack(side=tk.LEFT)

                value = self.config.get(section, option)
                var = tk.StringVar(value=value)
                self.config_vars[section][option] = var

                if self.is_boolean_option(section, option):
                    checkbox = ttk.Checkbutton(option_frame, variable=var, onvalue="True", offvalue="False")
                    checkbox.pack(side=tk.LEFT)
                else:
                    entry = ttk.Entry(option_frame, textvariable=var)
                    entry.pack(side=tk.LEFT)

        save_button = tk.Button(config_window, text="Save", command=lambda: self.save_config(config_window))
        save_button.pack(pady=10)

    def is_boolean_option(self, section, option):
        boolean_options = {
            'general': ['copy_files', 'preserve_directory_structure'],
            'input': ['recursive_search'],
            'output': ['create_date_subdirectories'],
            'sorting': ['sort_by_location', 'sort_by_date', 'group_by_country', 'group_by_state', 'group_by_city', 'group_by_year', 'group_by_month'],
            'renaming': ['rename_photos'],
            'exif': ['use_exif_date', 'fallback_to_file_date', 'use_exif_gps'],
            'preprocessing': ['rotate_images', 'optimize_images', 'resize_images'],
            'duplicates': ['skip_duplicates'],
            'unsortable': ['move_unsortable', 'copy_unsortable'],
            'interface': ['show_preview', 'confirm_actions'],
            'advanced': ['parallel_processing', 'cache_geocoding_results', 'ignore_errors']
        }
        return option in boolean_options.get(section, [])

    def save_config(self, config_window):
        def validate_boolean(value: str) -> bool:
            return value.lower() in ['true', 'false']

        def validate_integer(value: str) -> bool:
            try:
                int(value)
                return True
            except ValueError:
                return False

        def validate_float(value: str) -> bool:
            try:
                float(value)
                return True
            except ValueError:
                return False

        def validate_range(value: str, min_value: float, max_value: float) -> bool:
            try:
                float_value = float(value)
                return min_value <= float_value <= max_value
            except ValueError:
                return False

        def validate_regex(value: str, pattern: str) -> bool:
            return bool(re.match(pattern, value))

        validators = {
            'boolean': validate_boolean,
            'integer': validate_integer,
            'float': validate_float,
            'range': validate_range,
            'regex': validate_regex,
        }

        # Define validation rules for each option
        validation_rules = {
            'general': {
                'operation_mode': lambda value: value in ['sort', 'organize', 'rename'],
                'copy_files': validate_boolean,
                'preserve_directory_structure': validate_boolean,
                'min_file_size': validate_integer,
                'max_file_size': validate_integer,
            },
            'input': {
                'input_directory': lambda value: os.path.isdir(value),  # Validate if the input directory exists
                'recursive_search': validate_boolean,
                'file_extensions': lambda value: all(
                    ext.strip().lstrip('.').lower() in ['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'heic']
                    for ext in value.split(',')
                ),
            },
            'output': {
                'output_directory': lambda value: os.path.isdir(value) or os.path.exists(os.path.dirname(value)),  # Validate if the output directory exists or its parent directory exists
                'create_date_subdirectories': validate_boolean,
                'log_file': lambda value: os.path.isfile(value) or os.path.exists(os.path.dirname(value)),  # Validate if the log file exists or its parent directory exists
                'log_level': lambda value: value.upper() in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],  # Validate log level
            },
            'sorting': {
                'sort_by_location': validate_boolean,
                'sort_by_date': validate_boolean,
                'group_by_country': validate_boolean,
                'group_by_state': validate_boolean,
                'group_by_city': validate_boolean,
                'date_format': lambda value: validate_regex(value, r'%[%a-zA-Z]+'),  # Validate strftime format
                'group_by_year': validate_boolean,
                'group_by_month': validate_boolean,
            },
            'renaming': {
                'rename_photos': validate_boolean,
                'rename_format': lambda value: all(placeholder in value for placeholder in ['{original_name}', '{date}', '{location}']),  # Validate placeholders in rename format
                'original_name_placeholder': lambda value: value == '{original_name}',  # Validate original name placeholder
                'date_placeholder': lambda value: value == '{date}',  # Validate date placeholder
                'location_placeholder': lambda value: value == '{location}',  # Validate location placeholder
            },
            'geocoding': {
                'cache_distance_threshold': lambda value: validate_float(value) and float(value) >= 0,  # Validate non-negative float
                'geocoding_service': lambda value: value.lower() in ['nominatim', 'google', 'mapquest'],  # Validate geocoding service
                'geocoding_api_key': lambda value: True,  # No validation for API key
                'geocoding_timeout': validate_integer,
                'geocoding_max_retries': validate_integer,
            },
            'exif': {
                'use_exif_date': validate_boolean,
                'fallback_to_file_date': validate_boolean,
                'date_taken_key': lambda value: value in ['DateTimeOriginal', 'DateTimeDigitized', 'DateTime'],  # Validate EXIF date taken key
                'use_exif_gps': validate_boolean,
            },
            'preprocessing': {
                'rotate_images': validate_boolean,
                'optimize_images': validate_boolean,
                'target_quality': lambda value: validate_integer(value) and int(value) in range(1, 101),  # Validate integer in range 1-100
                'resize_images': validate_boolean,
                'max_width': validate_integer,
                'max_height': validate_integer,
            },
            'duplicates': {
                'skip_duplicates': validate_boolean,
                'duplicate_suffix': lambda value: True,  # No validation for duplicate suffix
                'duplicate_check_method': lambda value: value.lower() in ['hash', 'filename', 'exif'],  # Validate duplicate check method
                'duplicate_similarity_threshold': lambda value: validate_float(value) and 0 <= float(value) <= 1,  # Validate float in range 0-1
            },
            'unsortable': {
                'unsortable_folder': lambda value: True,  # No validation for unsortable folder name
                'move_unsortable': validate_boolean,
                'copy_unsortable': validate_boolean,
            },
            'interface': {
                'theme': lambda value: value.lower() in ['default', 'dark', 'light'],  # Validate theme
                'show_preview': validate_boolean,
                'confirm_actions': validate_boolean,
            },
            'advanced': {
                'parallel_processing': validate_boolean,
                'max_processes': lambda value: validate_integer(value) and int(value) > 0,  # Validate positive integer
                'cache_geocoding_results': validate_boolean,
                'geocoding_cache_size': validate_integer,
                'ignore_errors': validate_boolean,
            },
        }

        for section, options in self.config_vars.items():
            for option, var in options.items():
                option_value = var.get()
                validator_func = validation_rules.get(section, {}).get(option)

                if validator_func:
                    if not validator_func(option_value):
                        messagebox.showerror("Invalid Value", f"Invalid value for {option} in section {section}")
                        return
                else:
                    # No validation rule defined for this option, skip validation
                    pass

                # Escape the % characters in the date_format option
                if section == 'sorting' and option == 'date_format':
                    option_value = option_value.replace('%', '%%')

                self.config.set(section, option, option_value)

        self.config.write(open(config_file, 'w'))
        config_window.destroy()

    def create_widgets(self):
        """ Create and arrange the widgets within the main window. This method sets up buttons for selecting photos and the output directory, entry fields for setting the cache distance threshold, and labels and progress bars for showing the processing progress. """
        # Create a frame for the buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        self.select_photos_button = tk.Button(button_frame, text="Select Photos", command=self.select_photo_paths)
        self.select_photos_button.pack(side=tk.LEFT, padx=5)
        self.select_output_button = tk.Button(button_frame, text="Select Output Directory", command=self.select_output_directory)
        self.select_output_button.pack(side=tk.LEFT, padx=5)

        # Create a frame for the input directory
        input_directory_frame = tk.Frame(self.root)
        input_directory_frame.pack(pady=10)
        self.input_directory_label = tk.Label(input_directory_frame, text="Input Directory:", width=15)
        self.input_directory_label.pack(side=tk.LEFT)
        # Retrieve and display the input directory from the config
        input_directory = config['input']['input_directory']  # Assuming 'config' is a dictionary
        self.input_directory = input_directory
        self.input_directory_display = tk.Label(input_directory_frame, text="", relief=tk.SUNKEN, borderwidth=1, width=30, anchor='w')
        self.input_directory_display.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Create a frame for the output directory
        output_directory_frame = tk.Frame(self.root)
        output_directory_frame.pack(pady=10)
        self.output_directory_label = tk.Label(output_directory_frame, text="Output Directory:", width=15)
        self.output_directory_label.pack(side=tk.LEFT)
        # Retrieve and display the output directory from the config
        output_directory = config['output']['output_directory']  # Assuming 'config' is a dictionary
        self.output_directory = output_directory
        self.output_directory_display = tk.Label(output_directory_frame, text="", relief=tk.SUNKEN, borderwidth=1, width=30, anchor='w')
        self.output_directory_display.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Create a frame for the cache distance threshold and start button
        threshold_frame = tk.Frame(self.root)
        threshold_frame.pack(pady=10)
        self.threshold_label = tk.Label(threshold_frame, text="Cache Distance Threshold (km):")
        self.threshold_label.pack(side=tk.LEFT)
        self.threshold_entry = tk.Entry(threshold_frame, width=10)
        self.threshold_entry.insert(0, str(self.cache_distance_threshold))
        self.threshold_entry.pack(side=tk.LEFT, padx=5)
        self.start_button = tk.Button(threshold_frame, text="Start", command=self.start_processing)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.progress_label = tk.Label(self.root, text="")
        self.progress_label.pack()
        self.progress_bar = ttk.Progressbar(self.root, length=200, mode='determinate')
        self.progress_bar.pack()
        self.current_file_label = tk.Label(self.root, text="")
        self.current_file_label.pack()
        self.sortable_photos_label = tk.Label(self.root, text="Sortable Photos: 0")
        self.sortable_photos_label.pack()
        self.unsortable_photos_label = tk.Label(self.root, text="Unsortable Photos: 0")
        self.unsortable_photos_label.pack()

    def select_photo_paths(self):
        """
        Open a file dialog to allow the user to select photo files for processing.

        Supports selection of multiple files with specified file types (JPEG, PNG, BMP, RAW, and all files).
        """
        file_extensions = self.config.get('input', 'file_extensions').split(',')
        filetypes = [
            ("Photo files", " ".join(file_extensions)),
            ("All files", "*.*")
        ]
        selected_paths = filedialog.askopenfilenames(title="Select photo files", filetypes=filetypes)
        self.photo_paths = list(selected_paths)
        if self.photo_paths:
            self.input_directory_display.config(text=os.path.dirname(self.photo_paths[0]))
        else:
            self.input_directory_display.config(text="")

    def select_output_directory(self):
        """
        Open a directory dialog to allow the user to select an output directory where processed photos will be saved.
        """
        selected_directory = filedialog.askdirectory(title="Select output directory")
        self.output_directory = selected_directory
        self.output_directory_display.config(text=self.output_directory)

    def start_processing(self):
        """
        Validate input fields and start the asynchronous photo processing task.

        Initializes progress indicators and starts processing the selected photos asynchronously. Displays error messages if input validation fails.
        """
        if not self.validate_inputs():
            return

        self.initialize_progress()
        self.processing_task = self.loop.create_task(self.process_photos_async())

    def validate_inputs(self):
        """
        Validate the cache distance threshold, photo paths, and output directory specified by the user.

        Checks for valid numerical input for the cache distance threshold, non-empty photo paths selection, and non-empty output directory selection.

        Returns:
            bool: True if all inputs are valid, False otherwise, along with displaying appropriate error messages.
        """
        try:
            self.cache_distance_threshold = float(self.threshold_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid cache distance threshold value.")
            return False

        if not self.photo_paths:
            messagebox.showerror("Error", "No photo files selected.")
            return False

        if not self.output_directory:
            messagebox.showerror("Error", "No output directory selected.")
            return False

        return True

    def initialize_progress(self):
        """
        Initialize or reset the progress indicators to their default states at the beginning of photo processing.
        """
        self.progress_bar['value'] = 0
        self.progress_label.config(text="Processing photos...")
        self.sortable_photos_label.config(text="Sortable Photos: 0")
        self.unsortable_photos_label.config(text="Unsortable Photos: 0")

    async def process_photos_async(self):
        """
        Asynchronously process the selected photos and update the GUI with progress information.
        Iterates over the photo files, processing each asynchronously and updating the progress bar,
        current file label, and sortable/unsortable photo counts as the task progresses.
        """
        log_file_path = os.path.join(self.output_directory, self.config.get('output', 'log_file'))
        logger.info(f"Saving log to {log_file_path}")
        configure_file_logging(log_file_path, self.config.get('output', 'log_level'))

        try:
            photo_processor = self.photo_processor.process_photos(self.photo_paths, self.output_directory)
            async for progress_info in photo_processor:
                self.root.after(0, self.update_progress, *progress_info)
            total_photos, processed_photos, sortable_photos, unsortable_photos, _ = progress_info
            self.show_completion_message(total_photos, processed_photos, sortable_photos, unsortable_photos)
        except Exception as e:
            logger.error(f"Error processing photos: {str(e)}")
            messagebox.showerror("Error", "An error occurred while processing photos.")
        finally:
            self.photo_processor.geolocator._save_cache()

    def update_progress(self, processed_photos, total_photos, sortable_photos, unsortable_photos, current_file):
        """
        Update the GUI's progress indicators based on the current state of photo processing.

        Parameters:
            processed_photos (int): The number of photos processed so far.
            total_photos (int): The total number of photos to process.
            sortable_photos (int): The number of photos that were successfully sorted.
            unsortable_photos (int): The number of photos that could not be sorted.
            current_file (str): The path to the photo currently being processed.
        """
        self.progress_bar['value'] = (processed_photos / total_photos) * 100
        self.sortable_photos_label.config(text=f"Sortable Photos: {sortable_photos}")
        self.unsortable_photos_label.config(text=f"Unsortable Photos: {unsortable_photos}")
        self.current_file_label.config(text=f"Current File: {current_file}")
        self.root.update_idletasks()

    def show_completion_message(self, total_photos, processed_photos, sortable_photos, unsortable_photos):
        """
        Display a completion message box with a summary of the photo processing task.

        Parameters:
            total_photos (int): The total number of photos processed.
            processed_photos (int): The number of photos processed.
            sortable_photos (int): The number of photos successfully sorted.
            unsortable_photos (int): The number of photos that could not be sorted.
        """
        message = f"Photo sorting completed.\nTotal photos: {total_photos}\nProcessed photos: {processed_photos}\nSortable photos: {sortable_photos}\nUnsortable photos: {unsortable_photos}"
        messagebox.showinfo("Completion", message)
        self.reset_gui()

    def reset_gui(self):
        """
        Reset the GUI to its initial state, clearing selections and progress indicators.
        """
        self.photo_paths = []
        self.output_directory = self.config.get('output', 'output_directory')
        self.threshold_entry.delete(0, tk.END)
        self.threshold_entry.insert(0, str(self.cache_distance_threshold))
        self.progress_bar['value'] = 0
        self.progress_label.config(text="")
        self.sortable_photos_label.config(text="Sortable Photos: 0")
        self.unsortable_photos_label.config(text="Unsortable Photos: 0")
        self.current_file_label.config(text="")

    def run(self):
        try:
            self.run_async_task = self.loop.run_until_complete(self.run_async())
        except RuntimeError as e:
            if str(e) == "Event loop stopped before Future completed.":
                # Handle the exception gracefully by canceling the run_async_task
                if self.run_async_task is not None:
                    self.run_async_task.cancel()
            else:
                # Re-raise any other RuntimeError exceptions
                raise e

    async def run_async(self):
        try:
            while True:
                self.root.update()
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            # Handle the cancellation gracefully
            pass
        except Exception as e:
            logging.error(f"An error occurred in the async loop: {e}")
        finally:
            self.root.destroy()
            self.cleanup()

    def update_async_loop(self):
        try:
            self.loop.call_soon_threadsafe(self.update_async_callback)
            self.root.after(100, self.update_async_loop)  # Schedule the next update
        except Exception as e:
            logging.error(f"An error occurred in update_async_loop: {e}")

    def update_async_callback(self):
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0), self.loop)

    def cleanup(self):
        try:
            # Cancel all pending asyncio tasks.
            for task in asyncio.all_tasks(self.loop):
                task.cancel()
            
            # Run the loop until all tasks are cancelled.
            if self.loop.is_running():
                self.loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(self.loop), return_exceptions=True))
            
            # Stop the event loop if it's still running.
            if self.loop.is_running():
                self.loop.stop()
            
            # Close the event loop if it's not closed.
            if not self.loop.is_closed():
                self.loop.close()
        except RuntimeError as e:
            if str(e) != "This event loop is already running":
                raise
        finally:
            # Destroy the Tkinter root window if it exists.
            if self.root.winfo_exists():
                self.root.destroy()

    def on_closing(self):
        if tk.messagebox.askyesno("Quit", "Are you sure you want to quit?"):
            self.cleanup()

def main():
    try:
        config_file = "config.ini"
        config = load_config(config_file)

        # Configure file logging based on the configuration
        log_file = config.get('output', 'log_file')
        log_level = config.get('output', 'log_level')
        configure_file_logging(log_file, log_level)

        # Create instances of ExifExtractor and Geolocator
        exif_extractor = ExifExtractor(config)
        geolocator = Geolocator(config)

        # Create an instance of PhotoProcessor
        photo_processor = PhotoProcessor(exif_extractor, geolocator, config)

        gui = GUI(config, photo_processor)
        gui.run()
    except Exception as e:
        logger.error(f"An error occurred in the main function: {str(e)}")
        # Handle the exception or display an error message to the user
    finally:
        # Perform any necessary cleanup or resource release
        # For example, closing file handles, database connections, etc.
        pass

if __name__ == "__main__":
    main()