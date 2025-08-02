from scs_core import extract_discogs_id, fetch_release_data, generate_pdf
import click
import argparse
from typing import List


def process_urls(urls: List[str], output_path: str) -> None:
    """
    Process multiple Discogs URLs and generate a PDF file.

    Args:
        urls: List of Discogs release or master URLs
        output_path: Path where to save the PDF file
    """
    all_disc_data: List[DiscData] = []

    try:
        for url in urls:
            try:
                id_type, discogs_id = extract_discogs_id(url)
                disc_data = fetch_release_data(id_type, discogs_id)
                all_disc_data.extend(disc_data)
            except Exception as e:
                print(f"Warning: Failed to process URL {url}: {e}")
                continue

        if not all_disc_data:
            raise Exception("No valid data was retrieved from any of the URLs")

        generate_pdf(all_disc_data, output_path=output_path)
        print(f"PDF saved to {output_path}")
    except Exception as e:
        print(f"Error: {e}")
        raise


@click.command()
@click.argument('urls', nargs=-1, required=True)
@click.option('--output', '-o', default='labels.pdf', help='Output PDF file path')
def main(urls: tuple, output: str) -> None:
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
    
    process_urls(list(urls), output)

if __name__ == "__main__":
    main()