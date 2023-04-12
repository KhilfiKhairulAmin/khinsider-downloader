# This script will mass download soundtracks of an album from downloads.khinsider.com
# Built-in dependencies
from os.path import isfile
from os import mkdir
from pathlib import Path
from typing import Dict, Tuple, List
from urllib.parse import unquote

# External dependencies
from requests import get
from bs4 import BeautifulSoup
from tqdm import tqdm


class InvalidUrl(Exception):
    pass


def get_input(prompt: str, default: str = None) -> str:
    """
    Prompts the user for input with the given prompt message and returns the user's response.
    If the user enters nothing and a default value is provided, returns the default value.

    Args:
        prompt (str): The message to display to the user when prompting for input.
        default (str, optional): The default value to return if the user enters nothing. Default is None.

    Returns:
        str: The user's input, or the default value if provided and the user entered nothing.
    """
    return input(prompt) or default


def display_album(title: str, total_duration: str, audios: Dict[str, str]):
    """
    Displays information about an album, including its title, total duration,
    and available audio formats and their corresponding file sizes.

    Args:
        title (str): The title of the album.
        total_duration (str): The total duration of the album.
        audios (dict): A dictionary containing the available audio formats and their corresponding file sizes.

    Returns:
        None
    """
    print('ALBUM')
    print(f'Title: {title}')
    print(f'Total Duration: {total_duration}')
    print('Available format:')
    for format_, space in audios.items():
        print(f'✓ {format_} ({space})')


def mb_to_gb(megabytes: int | float):
    """
    Convert a value in megabytes to gigabytes.

    Args:
        megabytes (int or float): A value in megabytes to convert to gigabytes.

    Returns:
        float: The equivalent value in gigabytes, rounded to two decimal places.

    Examples:
        >>> mb_to_gb(5000)
        5.0
        >>> mb_to_gb(12345.67)
        12.35
    """
    return round(megabytes / 1000, 2)


def get_album_info(url: str) -> Tuple[str, str, Dict[str, str], List[str]]:
    """
    Retrieves information about an album from downloads.khinsider.com

    Args:
        url: A string representing the URL of the album page.

    Returns:
        A tuple containing the album title, total duration, dictionary of available audio formats and their sizes,
        and a list of URLs to the soundtrack source pages.
    """

    if 'https://downloads.khinsider.com/game-soundtracks/album/' not in url:
        raise InvalidUrl('Invalid URL: URL must contain https://downloads.khinsider.com/game-soundtracks/album'
                         '/<album_name>')

    # Make a request to the album page URL and parse the HTML with BeautifulSoup
    html = get(url)
    album_page = BeautifulSoup(html.text, 'html.parser')

    # Get the album title.
    album_title = album_page.find("h2").text

    # Get the soundtracks table.
    tables = album_page.find_all("table")
    soundtracks_table = tables[1]

    # Extract information about the soundtracks.
    ths = soundtracks_table.find_all("th")
    mp3_index = next(i for i, th in enumerate(ths) if th.text == "MP3")
    audio_formats = []
    for i in range(mp3_index, len(ths)):
        if audio_format := ths[i].text.strip():  # If str is not empty (truthy), it means an audio format is listed here
            audio_formats.append(audio_format)
        else:
            break

    duration, *spaces = ths[-(len(audio_formats) + 2):-1]
    duration = duration.text

    spaces = list(map(lambda s: int((s.text.split(' ')[0]).replace(',', '')), spaces))

    more_than_1000 = [s for s in spaces if s >= 1000]

    if more_than_1000:
        spaces = list(map(lambda s: f'{mb_to_gb(s)} GB', spaces))
    else:
        spaces = list(map(lambda s: f'{s} MB', spaces))

    # Create dictionary containing formats and its corresponding size
    audios = dict(zip(audio_formats, spaces))

    # Get all urls to soundtrack source page
    tds = soundtracks_table.find_all_next('td', class_='clickable-row')[::4]  # [::4] to avoid repetition of same URL
    soundtracks_page_url = list(map(lambda td: f"https://downloads.khinsider.com{td.next_element['href']}", tds))

    return album_title, duration, audios, soundtracks_page_url


def choose_audio_format(audios: Dict[str, str], prompt: str = 'Choose a format:') -> str:
    """
    Allows the user to choose an audio format from a given dictionary of audio formats and their corresponding sizes.

    Args:
        audios (Dict[str, str]): A dictionary containing audio formats and their corresponding sizes.
        prompt (str, optional): The prompt message to display to the user. Defaults to "Choose a format:".

    Returns:
        str: The chosen audio format.
    """
    print(prompt)

    for i, audio in enumerate(audios.items()):
        print(f'{i} - {audio[0]}')

    length = len(audios)
    while True:
        try:
            input_ = get_input("", default='0')
            selection = range(0, length)
            if int(input_) in list(range(0, length)):
                return input_
            raise Exception
        except Exception as err:
            print(f"Invalid input: Please enter number {' or '.join(map(lambda t: str(t), selection))} only.")


def prepare_download_directory(default: str):
    """
    Creates a new directory at the given path if it does not already exist.

    Args:
        default: A string representing the default path to the directory to create.
    Returns:
        None
    """
    while True:
        out = str(get_input(f'Download location (Press Enter to use default: {default} ):\n', default=default))

        try:
            mkdir(out)
            return out
        except FileExistsError:
            return out
        except Exception:
            print('Invalid location: Please provide a valid download location or use default.\n')


def download_soundtracks(soundtracks_page_url: List[str], audio_format: int, dir_out: str) -> None:
    """Download the soundtracks listed in the given URLs in the specified audio format.

    Args:
        soundtracks_page_url (List[str]): URLs of the pages where the soundtracks are listed.
        audio_format (int): Index of the audio format to download from the list of available formats for each soundtrack.
        dir_out (str): Path to the directory where the downloaded files will be saved.

    Returns:
        None. The function downloads the files and displays progress information on the console.
    """
    print(f'{len(soundtracks_page_url)} files will be downloaded...')
    download_count = 0
    for url in soundtracks_page_url:
        # Open source page
        soundtrack_page = BeautifulSoup(get(url).text, 'html.parser')

        # Scrape the link to download resource
        source_url = soundtrack_page.find_all(class_='songDownloadLink')[audio_format].parent['href']

        # The website's url already formatted some characters to their corresponding code (%XX)
        # Unquote will reformat it from code back to its original character
        # Refer https://docs.python.org/3.10/library/urllib.parse.html#urllib.parse.unquote
        # The '#' special character is used in certain URLs (in the filename), replace for URL purpose
        source_url = unquote(source_url).replace('#', '%23')

        filename = source_url.rsplit('/', 1)[1].replace('%23', '#')
        filepath = f'{dir_out}/{filename}'

        # Checks if file already exists
        if isfile(filepath):
            print(f'Skipping {filename}, it already exists...')
            continue

        print(f'Downloading {filename}...')

        # Make a GET request to the URL, but don't download the entire response at once
        response = get(source_url, stream=True)

        total_size_in_bytes = int(response.headers.get('content-length', 0))
        block_size = 1048576  # 1MB

        progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)

        # Open a file to write the downloaded data to
        with open(filepath, 'wb') as file:
            for data in response.iter_content(block_size):
                progress_bar.update(len(data))
                file.write(data)

        progress_bar.close()

        download_count += 1
    print(f'Downloads finished! {download_count} files have been downloaded')


while True:
    # URL to the album's page
    album_url = str(get_input("Link to the album's page (from downloads.khinsider.com):\n"))

    try:
        # Get soundtrack information
        album_title, duration, audios, soundtracks_page_url = get_album_info(album_url)

        print('')

        # Display the information
        display_album(album_title, duration, audios)

        print('')

        # Choose an audio format if there are more than one format available
        audio_format = int(choose_audio_format(audios, '\nChoose a format:') if len(audios) > 1 else 0)

        print('')

        # Preset the output directory of audio file
        dir_out = prepare_download_directory(f'{str(Path.home())}/Music/{album_title}')

        print('\nPreparing download...')
        download_soundtracks(soundtracks_page_url, audio_format, dir_out)
        print('')

        while True:
            continue_ = get_input('Do you want to continue? [Y/n]\n', default='y').lower()

            match continue_:
                case 'y' | 'yes' | 'ok':
                    break
                case 'n' | 'no' | 'nope':
                    exit(0)
                case _:
                    continue

    except InvalidUrl as err:
        print(err)
        continue

    except Exception as err:
        print('\nSomething went wrong!')
        print(f'URL: {album_url}')
        print(f'Error: {err}')
        print('\nKindly bring this error to the attention of the seller by reporting it to them. Thank you.')

    finally:
        print('')
