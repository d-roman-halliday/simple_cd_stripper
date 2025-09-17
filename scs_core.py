import io
import os
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Tuple, List, Dict, Optional, Literal

import discogs_client
from dotenv import load_dotenv
from fpdf import FPDF


@dataclass
class DiscTrack:
    position: str          # Original position string (e.g., "1-1", "A1", "1")
    title: str
    disc_number: int      # Extracted disc number
    track_number: int     # Extracted track number
    overall_number: int   # Sequential track number across all discs

@dataclass
class DiscData:
    album: str
    artist: str
    disc: int
    tracks: List[DiscTrack]

class DiscogsClientError(Exception):
    """Custom exception for Discogs client errors."""
    pass

class PDFGenerationError(Exception):
    """Custom exception for PDF generation errors."""
    pass

def initialize_discogs_client() -> discogs_client.Client:
    """
    Initialize and return a Discogs client with authentication.
    
    Returns:
        discogs_client.Client: Authenticated Discogs client
    
    Raises:
        DiscogsClientError: If the user token is not found or invalid
    """
    load_dotenv()
    user_token = os.getenv("DISCOGS_USER_TOKEN")

    # There should be a token but for initial usage, skipping
    #if not user_token:
        #raise DiscogsClientError("Discogs user token not found in environment variables")
    return discogs_client.Client('simple_cd_stripper/1.0', user_token=user_token)

# Initialize the client at the module level
try:
    discogs = initialize_discogs_client()
except DiscogsClientError as e:
    print(f"Warning: {e}")
    discogs = None

def extract_discogs_id(url: str) -> Tuple[str, int]:
    """
    Extract the type and ID from a Discogs URL.
    
    Args:
        url: Discogs release or master URL
    
    Returns:
        Tuple containing the ID type ('release' or 'master') and the numeric ID
    
    Raises:
        ValueError: If the URL format is invalid
    """
    match = re.search(r"discogs\.com/(release|master)/(\d+)", url)
    if not match:
        raise ValueError("Invalid Discogs URL format")
    return match.group(1), int(match.group(2))

def _parse_track_position(position: str, track_map: Dict[str, int]) -> Tuple[int, int, int]:
    """
    Parse track position string to extract disc and track numbers.
    
    Args:
        position: Track position string (e.g., "1-1", "A1", "1")
        track_map: Dictionary to maintain running count for lettered tracks
    
    Returns:
        Tuple of (disc_number, track_number, overall_number)
    """
    # Handle disc-track format (e.g., "1-1")
    if '-' in position:
        disc_str, track_str = position.split('-', 1)
        try:
            disc_num = int(disc_str)
            track_num = int(track_str)
            overall_num = (disc_num - 1) * 100 + track_num  # Use 100 tracks per disc as a buffer
            return disc_num, track_num, overall_num
        except ValueError:
            pass

    # Handle lettered format (e.g., "A1", "B2")
    if position and position[0].isalpha():
        letter = position[0].upper()
        try:
            if letter not in track_map:
                # Initialize a new letter sequence
                track_map[letter] = max(track_map.values(), default=0) + 1
            else:
                # Increment the track count
                track_map[letter] = track_map[letter] + 1
            disc_num=1# This might be wrong, but in cases where there are A/B values, it's for LPs, rather than CDs, assuming a single disk (this is a dirty hack)
            track_num=max(track_map.values(), default=0)# get the rolling value
            overall_num = track_num # This might be wrong if there are A/B/C listings for multiple disks
            return disc_num, track_num, overall_num
        except ValueError:
            pass

    # Handle simple numeric format (e.g., "1")
    try:
        # noinspection PyTypeChecker
        num = int(''.join(filter(str.isdigit, position)))
        return 1, num, num
    except ValueError:
        return 1, 0, 0  # Default fallback

def fetch_release_data(id_type: str, discogs_id: int) -> List[DiscData]:
    """
    Fetch release data from Discogs API.
    
    Args:
        id_type: Type of ID ('release' or 'master')
        discogs_id: Discogs release or master ID
    
    Returns:
        List of DiscData objects containing album information
    
    Raises:
        DiscogsClientError: If there's an error fetching data from Discogs
        ValueError: If the ID type is invalid
    """
    if not discogs:
        raise DiscogsClientError("Discogs client not initialized")

    discs: Dict[int, DiscData] = {}
    track_map: Dict[str, int] = {}  # For tracking lettered positions
    
    try:
        # Validate and fetch release
        if id_type == "release":
            release = discogs.release(discogs_id)
        elif id_type == "master":
            release = discogs.master(discogs_id).main_release
        else:
            raise ValueError(f"Unknown Discogs ID type: {id_type}")

        # First pass: Parse all tracks to determine disc structure
        for track in release.tracklist:
            disc_num, track_num, overall_num = _parse_track_position(track.position, track_map)

            # Skip 'Bonus Tracks' lable/info rows from listing
            if track_num == 0 and overall_num == 0:
                continue
            
            if disc_num not in discs:
                discs[disc_num] = DiscData(
                    album=release.title,
                    artist=release.artists[0].name,
                    disc=disc_num,
                    tracks=[]
                )
            
            track_obj = DiscTrack(
                position=track.position,
                title=track.title,
                disc_number=disc_num,
                track_number=track_num,
                overall_number=overall_num
            )
            discs[disc_num].tracks.append(track_obj)

        # Sort tracks within each disc by overall_number
        for disc in discs.values():
            disc.tracks.sort(key=lambda x: x.overall_number)

        # Sort discs by disc number
        return sorted(discs.values(), key=lambda x: x.disc)

    except (AttributeError, KeyError) as e:
        raise DiscogsClientError(f"Invalid or incomplete data received from Discogs: {str(e)}")
    except Exception as e:
        raise DiscogsClientError(f"Unexpected error while fetching release data: {str(e)}")

# Constants for PDF generation
TRACK_STRIP_WIDTH = 74  # mm
TRACK_STRIP_HEIGHT = 109  # mm
MARGIN = 2  # mm
DEFAULT_FONT = 'helvetica'
DEFAULT_FONT_SIZE_ALBUM = 14
DEFAULT_FONT_SIZE_ARTIST = 12
DEFAULT_FONT_SIZE = 10
MIN_FONT_SIZE = 6
ALTERNATE_COLOR = (255, 255, 200)  # Light yellow in RGB
STRIP_BRACKETS = True # For now some titles have brackets in them which contain extra information and make them too long, strip them out

def generate_pdf(
    data: List[DiscData], 
    output_path: Optional[str] = None,
    alternate_backgrounds: bool = False,
    show_title_bg: bool = False,
    show_ruler: bool = False,
) -> Optional[BytesIO]:
    """
    Generate a PDF with the album information.
    
    Args:
        data: List of DiscData objects containing album information
        output_path: Optional path to save the PDF file
        alternate_backgrounds: Whether to use alternating backgrounds for tracks
        show_title_bg: Whether to add a background for the album title and artist
        show_ruler: Whether to draw a ruler to help visualize the sizing in the PDF print
    
    Returns:
        BytesIO object containing the PDF if output_path is None, None otherwise
    
    Raises:
        PDFGenerationError: If there's an error generating the PDF
    """
    try:
        pdf = FPDF("P", "mm", "A4")
        pdf.set_auto_page_break(auto=False)
        pdf.set_margins(10, 10, 10)

        # All text is black
        pdf.set_draw_color(0) # Black
        pdf.set_text_color(0) # Black

        # I'm out of black ink - use Magenta
        #pdf.set_draw_color(r=255, g=0, b=255)
        #pdf.set_text_color(r=255, g=0, b=255)

        def draw_ruler(x: float, y: float, width: float) -> None:
            """Draw a ruled line. Include markings for each mm"""
            pdf.line(x, y, x+width, y)
            mm_count = width
            mm_point = 0
            while mm_point <= mm_count:
                draw_height = 1
                if mm_point % 10 == 0:
                    draw_height = 3
                pdf.line(x+mm_point, y, x+mm_point, y+draw_height)
                mm_point+=1

        def add_crop_marks(x: float, y: float, right_wing=True, left_wing=True, bottom_wing=True, top_wing=True) -> None:
            # Crop marks should be outside so not seen in the content
            # Top left
            if top_wing:
                pdf.dashed_line(x, y, x - 5, y)
            if left_wing:
                pdf.dashed_line(x, y, x, y - 5)
            # Top right
            if right_wing:
                pdf.dashed_line(x + TRACK_STRIP_WIDTH, y, x + TRACK_STRIP_WIDTH + 5, y)
            if top_wing:
                pdf.dashed_line(x + TRACK_STRIP_WIDTH, y, x + TRACK_STRIP_WIDTH, y - 5)
            # Bottom left
            if bottom_wing:
                pdf.dashed_line(x, y + TRACK_STRIP_HEIGHT, x - 5, y + TRACK_STRIP_HEIGHT)
            if left_wing:
                pdf.dashed_line(x, y + TRACK_STRIP_HEIGHT, x, y + TRACK_STRIP_HEIGHT + 5)
            # Bottom right
            if bottom_wing:
                pdf.dashed_line(x + TRACK_STRIP_WIDTH, y + TRACK_STRIP_HEIGHT, x + TRACK_STRIP_WIDTH + 5, y + TRACK_STRIP_HEIGHT)
            if right_wing:
                pdf.dashed_line(x + TRACK_STRIP_WIDTH, y + TRACK_STRIP_HEIGHT, x + TRACK_STRIP_WIDTH, y + TRACK_STRIP_HEIGHT + 5)

        def create_album_artist_background(x: float, y: float) -> None:
            """Create a background image for the album artist."""
            # This can go as an option elsewhere
            TITLE_BG_COLOR: Tuple[int, int, int] = (255, 230, 128)  # soft yellow
            TITLE_BG_MARGIN: float = 2

            background_color=TITLE_BG_COLOR
            #plot points
            tl_x = x - TITLE_BG_MARGIN
            tl_y = y + TITLE_BG_MARGIN
            br_x_length = TITLE_BG_MARGIN + TRACK_STRIP_WIDTH + TITLE_BG_MARGIN
            br_y_length = 15 - ( 2 * TITLE_BG_MARGIN)
            # Draw filled rectangle
            r, g, b = background_color
            pdf.set_fill_color(r, g, b)
            pdf.rect(tl_x, tl_y, br_x_length, br_y_length, style="F")

        def find_fitting_font_size(text: str, max_width: float,
                                   font_family=DEFAULT_FONT,
                                   initial_size: int = DEFAULT_FONT_SIZE,
                                   font_style: Literal["", "B", "I", "U", "BU", "UB", "BI", "IB", "IU", "UI", "BIU", "BUI", "IBU", "IUB", "UBI", "UIB"] = ""
                                   ) -> float:
            """Find the largest font size that fits the text within max_width."""
            font_size = initial_size
            pdf.set_font(family=font_family, size=font_size, style=font_style)
            while pdf.get_string_width(text) > max_width and font_size > MIN_FONT_SIZE:
                font_size -= 0.5
                pdf.set_font(family=font_family, size=font_size, style=font_style)
            return font_size

        # noinspection PyTypeChecker
        def write_text_box(text: str, x: float, y: float, max_width: float,
                           font_family=DEFAULT_FONT,
                           font_size: float =DEFAULT_FONT_SIZE,
                           font_style: Literal["", "B", "I", "U", "BU", "UB", "BI", "IB", "IU", "UI", "BIU", "BUI", "IBU", "IUB", "UBI", "UIB"]=""
                           ) -> float:
            """Write text that fits within max_width, returning the height used."""
            words = text.split()
            lines = []
            current_line = []
            
            pdf.set_font(family=font_family, size=font_size, style=font_style)
            for word in words:
                test_line = ' '.join(current_line + [word])
                if not current_line or pdf.get_string_width(test_line) <= max_width:
                    current_line.append(word)
                else:
                    lines.append(' '.join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(' '.join(current_line))

            # Find a font size that fits all lines
            min_font = MIN_FONT_SIZE
            for line in lines:
                font_size = find_fitting_font_size(line, max_width, initial_size=font_size, font_style=font_style)
                font_size = max(min_font, font_size)
            
            # Write all lines with the same font size
            pdf.set_font(family=font_family, size=font_size, style=font_style)
            line_height = pdf.font_size * 1.2
            current_y = y
            for line in lines:
                pdf.set_xy(x, current_y)
                pdf.cell(max_width, line_height, line, ln=1, align='C')
                current_y += line_height
            
            return current_y - y  # Return total height used

        ########################################################################
        # Main steps
        ########################################################################
        # Create page
        pdf.add_page()

        # Visual debugging:
        # To be checked with a ruler to make sure that printout is in correct proportions
        # Printers/drivers/settings resize things to be helpful (but measurements need to fit)
        if show_ruler:
            draw_ruler(x=10, y=20+(2*TRACK_STRIP_HEIGHT), width=TRACK_STRIP_WIDTH)

        # Plot & add content
        starting_x, starting_y = 10, 10
        # idx will range from 0 to len(data)-1, two strips per page
        total_iterations=len(data)-1
        for idx, disc in enumerate(data):
            if idx >= 4:
                # Not supporting more than 4 CDs on one page for now
                print('Warning: More than 4 disks; Ignoring extra disks/data')
                break
            # Calculate position based on index (0-3 for each page)
            page_position = idx % 4  # Will be 0, 1, 2, or 3
            if page_position == 0:
                # Top left
                x, y = starting_x, starting_y
            elif page_position == 1:
                # Top right
                x, y = starting_x + TRACK_STRIP_WIDTH, starting_y
            elif page_position == 2:
                # Bottom left
                x, y = starting_x, starting_y + TRACK_STRIP_HEIGHT
            elif page_position == 3:
                # Bottom right
                x, y = starting_x + TRACK_STRIP_WIDTH, starting_y + TRACK_STRIP_HEIGHT
            else:  # More than 4 strips to a page. Ignore them for now
                continue

            # Add crop marks
            add_crop_marks(x, y)

            # Calculate available space
            content_x = x + MARGIN
            content_y = y + MARGIN
            content_width = TRACK_STRIP_WIDTH - (2 * MARGIN)

            current_y = content_y

            # Add background for Title/Artist
            if show_title_bg:
                create_album_artist_background(x, y)
            
            # Add Disk title
            title_disk = f"{disc.album}"
            title_font_size = find_fitting_font_size(title_disk, content_width, font_style='B', initial_size=DEFAULT_FONT_SIZE_ALBUM)
            title_height = write_text_box(title_disk, content_x, current_y, content_width, font_style='B', font_size=title_font_size)
            current_y = content_y + title_height

            # Add Disk artist
            title_artist = f"{disc.artist}"
            # Discogs ads a number to the name of the artist (if there is more than one artist with the same name), remove it if present:
            title_artist = re.sub(r'\([^)]*\)', '', title_artist).strip()
            title_font_size = find_fitting_font_size(title_artist, content_width, font_style='B', initial_size=DEFAULT_FONT_SIZE_ARTIST)
            title_height = write_text_box(title_artist, content_x, current_y, content_width, font_style='B', font_size=title_font_size)
            current_y = content_y + title_height

            #If more than one disk - do we add this?
            #(Disc {disc.disc})

            # Add tracks
            current_y = current_y + title_height + MARGIN
            available_height = y + TRACK_STRIP_HEIGHT - MARGIN - current_y
            
            # Calculate track height and font size
            tracks_count = len(disc.tracks)
            max_track_height = available_height / tracks_count
            
            for track_idx, track in enumerate(disc.tracks):
                if alternate_backgrounds and track_idx % 2 == 1:
                    pdf.set_fill_color(*ALTERNATE_COLOR)
                else:
                    pdf.set_fill_color(255, 255, 255)
                
                track_text = f"{track.track_number:02d} {track.title}"

                # Remove any text in brackets
                if STRIP_BRACKETS:
                    track_text = re.sub(r'\([^)]*\)', '', track_text).strip()

                pdf.set_font(DEFAULT_FONT, size=DEFAULT_FONT_SIZE)
                track_font_size = find_fitting_font_size(track_text, content_width)
                # noinspection PyTypeChecker
                pdf.set_font(DEFAULT_FONT, size=track_font_size)
                
                pdf.set_xy(content_x, current_y)
                track_height = min(pdf.font_size * 1.2, max_track_height)
                pdf.cell(content_width, track_height, track_text, ln=1, fill=alternate_backgrounds)
                current_y += track_height

        if output_path:
            pdf.output(output_path)
            return None
        else:
            buf = io.BytesIO()
            # noinspection PyTypeChecker
            pdf.output(buf)
            buf.seek(0)
            return buf

    except Exception as e:
        raise PDFGenerationError(f"Failed to generate PDF: {str(e)}")

if __name__ == "__main__":
    print("This module is not meant to be run directly.")