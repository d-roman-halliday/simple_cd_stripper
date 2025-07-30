from scs_core import extract_discogs_id, fetch_release_data, generate_pdf
import argparse

def process_url(url: str, output_path: str) -> None:
    """
    Process a Discogs URL and generate a PDF file.
    
    Args:
        url: The Discogs release or master URL
        output_path: Path where to save the PDF file
    """
    try:
        id_type, discogs_id = extract_discogs_id(url)
        data = fetch_release_data(id_type, discogs_id)
        generate_pdf(data, output_path=output_path)
        print(f"PDF saved to {output_path}")
    except Exception as e:
        print(f"Error: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Generate jukebox labels from Discogs URL.")
    parser.add_argument(
        "url", 
        help="Discogs release or master URL",
        nargs="?",  # Make the argument optional
        default="https://www.discogs.com/master/41155-Ozzy-Osbourne-Blizzard-Of-Ozz"
    )
    parser.add_argument(
        "--out",
        help="Output PDF file path",
        default="jukebox_labels.pdf"
    )
    args = parser.parse_args()
    
    process_url(args.url, args.out)

if __name__ == "__main__":
    main()