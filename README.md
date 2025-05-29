# LCP EPUB Fetcher

This project is a tool for extracting and repackaging the contents of LCP-protected EPUB files using Thorium Reader's remote debugging interface.

## Features
- Launches Thorium Reader with remote debugging enabled
- Connects to the Thorium debugging port to fetch decrypted EPUB resources
- Repackages the EPUB with the fetched, decrypted content

## Requirements
- Python 3.8+
- Thorium Reader (installed at the default path or adjust in `main.py`)
- Required Python packages: `requests`

## Installation
1. Clone or download this repository.
2. Install dependencies:
   ```powershell
   pip install requests
   ```
3. Ensure Thorium Reader is installed. Update the path in `main.py` if needed.

## Usage
Run the script with the path to your LCP-protected EPUB file:

```powershell
python main.py <epub_path>
```

A new file with `_fetched.epub` appended to the name will be created, containing the decrypted resources.

## Notes
- The script uses Thorium Reader's remote debugging interface to access decrypted content. Thorium must not be running before you start the script.
- Only tested on Windows.

## File Structure
- `main.py` — Main script for fetching and repackaging EPUBs
- `utils/` — Helper modules for content fetching and path handling

## License
This project is for educational and personal use only.

## Credits

Thanks to [Terence Eden](https://shkspr.mobi/) for the [inspiration](https://shkspr.mobi/blog/2025/03/towards-extracting-content-from-an-lcp-protected-epub/) 
