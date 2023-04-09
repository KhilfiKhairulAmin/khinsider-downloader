# This script will mass download soundtracks of an album from downloads.khinsider.com
import os.path
import sys
from urllib.parse import unquote
from urllib.request import urlopen
from bs4 import BeautifulSoup
from os import mkdir
from pathlib import Path
import requests
from tqdm import tqdm


def get_input(prompt, default=None):
    """
    Get user input with a default value if none is provided.
    :param prompt:
    :param default:
    :return:
    """
    return input(prompt) or default


def format_byte(bytes_):
    """
    Format a file size in bytes as a human-readable string
    :param bytes_:
    :return:
    """


# URL to the album's page
album_url = str(input("Link to the album's page (from downloads.khinsider.com):\n"))
html = urlopen(album_url)
soup = BeautifulSoup(html, 'html.parser')
print('\nALBUM')


# Get album name
album_name = soup.find('h2').text
print(f'Title: {album_name}')


# Get the soundtracks table (at index 1 a.k.a the 2nd table in the page)
tables = soup.find_all('table')
soundtracks_table = tables[1]


# Get table header to extract information of album's soundtracks
ths = soundtracks_table.find_all_next('th')


# Finds the index of <th> containing MP3 audio format
mp3_index = 0
for i in range(len(ths)):
    if ths[i].text == 'MP3':
        mp3_index = i
        break


# Gets available audio formats starting from MP3...
audio_formats = []
for i in range(mp3_index, len(ths)):
    if audio_format := ths[i].text.strip():  # If str is not empty (truthy), it means an audio format is listed here
        audio_formats.append(audio_format)
    else:
        break


# Get the total space requirements for each format and total time
num_of_format = len(audio_formats)
time, *spaces = ths[-(num_of_format + 2):-1]  # <--- Print `ths` to understand this code 🤯
time = time.text
spaces = list(map(lambda s: s.text, spaces))

print(f'Playtime: {time}')
print('Available format:')
for format_, space in zip(audio_formats, spaces):
    print(f'✓ {format_} ({space})')


# Choose an audio format
audio_format = 0
if num_of_format > 1:
    print('\nChoose a format:')
    for i in range(num_of_format):
        print(f'{i} - {audio_formats[i]}')
    audio_format = int(input(''))
else:
    print(f'Only {audio_formats[0]} is found. Skipped choosing format.')


# Get all urls to soundtrack source page
tds = soundtracks_table.find_all_next('td', class_='clickable-row')[::4]
soundtracks_source_pages = list(map(lambda td: td.next_element['href'].rsplit('/', maxsplit=1)[1], tds))


# Preset the output directory of audio file
default_dir_out = f'{str(Path.home())}/Music/{album_name}'
dir_out = str(input(f'\nDownload location (Press Enter to use default: {default_dir_out} ):\n'))
dir_out = dir_out if dir_out else default_dir_out

try:
    mkdir(dir_out)
except FileExistsError as error:
    pass


print('\nPreparing download...')
print(f'{len(soundtracks_source_pages)} files will be downloaded...')


# Create this bar_progress method which is invoked automatically from wget
def bar_progress(current, total, width=80):
    bytes_left = total - current
    ratio = current / total
    percentage = int(ratio * 100)
    progress_fill = '.' * int(ratio * 40)
    is_complete = f'{bytes_left} bytes left' if percentage != 100 else 'Completed!'
    progress_message = f"{str(percentage) + '%': <4} [{progress_fill: <40}] {is_complete}"
    # Don't use print() as it will print in new line every time.
    sys.stdout.write("\r" + progress_message)
    sys.stdout.flush()


soundtracks_source_pages = soundtracks_source_pages[38:40]
# Open all source download pages and download the audio files
for source_page in soundtracks_source_pages:
    # Open source page
    source_page = source_page.replace('%23', '%2523')  # The '#' character is bugged when URL encoded, this fixes it!
    html = urlopen(f'{album_url}/{source_page}')
    soup = BeautifulSoup(html, 'html.parser')

    # Scrape the link to download resource
    source = soup.find_all(class_='songDownloadLink')[audio_format].parent['href']

    # The website's url already formatted some characters to their corresponding code (%XX)
    # Unquote will reformat it from code back to its original character
    # Refer https://docs.python.org/3.10/library/urllib.parse.html#urllib.parse.unquote
    source = unquote(source)
    source = source.replace('#', '%23')  # The '#' character is bugged when URL encoded, this fixes it!

    filename = source.split('/')[-1]
    filepath = f'{dir_out}/{filename}'

    # Checks if file already exists
    if os.path.isfile(filepath):
        print(f'Skipping {filename}, it already exists...')
        continue

    print(f'Downloading {filename}...')
    # Code and comment generated by ChatGPT-3
    # Make a GET request to the URL, but don't download the entire response at once
    response = requests.get(source, stream=True)

    total_size_in_bytes = int(response.headers.get('content-length', 0))
    block_size = 1024  # 1 Kilobyte

    progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)

    # Open a file to write the downloaded data to
    with open(filepath, 'wb') as f:
        for data in response.iter_content(block_size):
            progress_bar.update(len(data))
            f.write(data)

    progress_bar.close()

    if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
        print("ERROR, something went wrong")

    # wget.download(source, '--no-check-certificate', b ar=bar_progress)

print('\nFinished downloads.')
