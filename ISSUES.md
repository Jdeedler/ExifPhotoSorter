# Known Issues and Missing Features

## 1. Geocoding Service Support
- The code currently only supports the Nominatim geocoding service from OpenStreetMap.
- Support for other geocoding services like Google Maps or MapQuest is not implemented, although the configuration option `geocoding_service` is present.

## 2. Geocoding API Key
- The configuration option `geocoding_api_key` is present, but it's not being used in the code.
- This might be required for other geocoding services that require an API key.

## 3. Duplicate Check Method
- The configuration option `duplicate_check_method` supports `hash`, `filename`, and `exif`, but the code currently only implements the `hash` method for detecting duplicate files.

## 4. Image Preprocessing
- The code has configuration options for image preprocessing tasks like rotating, optimizing, and resizing images, but these features are not implemented yet.

## 5. Parallel Processing
- The configuration option `parallel_processing` is present, but the code doesn't seem to leverage parallel processing for improved performance.

## 6. Caching Geocoding Results
- The configuration option `cache_geocoding_results` is present, and the code implements caching of geocoding results, but the cache size is fixed to 100 entries.
- The configuration option `geocoding_cache_size` is not being used.

## 7. Operation Modes
- The configuration option `operation_mode` supports `sort`, `organize`, and `rename` modes, but the code only implements the `sort` mode.

## 8. File Size Filtering
- The configuration options `min_file_size` and `max_file_size` are present, but the code doesn't seem to filter files based on their size.

## 9. Unsortable Photo Handling
- The configuration options `move_unsortable` and `copy_unsortable` are present, but the code only implements the `copy_unsortable` option.
- The `move_unsortable` option is not implemented.

## 10. Interface Theme
- The configuration option `theme` supports `default`, `dark`, and `light` themes, but the code doesn't seem to implement different themes for the GUI.

## 11. Confirm Actions
- The configuration option `confirm_actions` is present, but the code doesn't seem to implement any confirmation prompts for user actions.

## 12. Ignore Errors
- The configuration option `ignore_errors` is present, but the code doesn't seem to have any error handling logic related to this option.