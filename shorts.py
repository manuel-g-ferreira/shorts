import os
import subprocess
from PIL import Image
import tempfile
import shutil
from anime_quotes import anime_quotes
import random
import re
from gtts import gTTS
from pydub import AudioSegment
import logging

# Get the project's root directory
project_root = os.path.dirname(os.path.abspath(__file__))

# Define a path for the temporary folder within the project root
temp_folder = os.path.join(project_root, 'tmp')

# Ensure the temporary folder exists
os.makedirs(temp_folder, exist_ok=True)

# Configure the logging module
log_file_path = os.path.join(project_root, 'video_creation.log')
logging.basicConfig(filename=log_file_path, level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

# Function to create a voice file using gTTS
def create_voice_file(text, output_file):
    tts = gTTS(text, lang='en')
    tts.save(output_file)
    logging.info(f'Voice file created: {output_file}')

# Function to resize and pad an image to a target size
def resize_and_pad(image_path, target_size):
    original_image = Image.open(image_path)
    original_width, original_height = original_image.size
    target_width, target_height = target_size

    # Calculate the scaling factors for resizing
    width_ratio = target_width / original_width
    height_ratio = target_height / original_height

    # Use the larger scaling factor to maintain aspect ratio
    scale_factor = max(width_ratio, height_ratio)

    # Calculate the new size with the same aspect ratio
    new_width = int(original_width * scale_factor)
    new_height = int(original_height * scale_factor)

    # Create a new image with the target size and paste the original image with black padding
    resized_image = Image.new("RGB", target_size, (0, 0, 0))
    position = ((target_width - new_width) // 2, (target_height - new_height) // 2)
    resized_image.paste(original_image.resize((new_width, new_height)), position)
    logging.info(f'Image resized and padded: {image_path}')

    return resized_image

# Function to divide a quote into parts
def divide_quote_into_parts(quote):
    # Split the quote into sentences based on common punctuation marks (.?!), as well as "..."
    sentences = re.split(r'(?<=[.?!...])\s', quote)
    
    # Initialize a list to store the divided parts.
    parts = []

    # Process each sentence to create meaningful parts.
    for i, sentence in enumerate(sentences):
        # If it's not the last sentence, add the punctuation back to the end.
        if i < len(sentences) - 1:
            sentence += re.search(r'[.?!...]', sentence).group()
        parts.append(sentence)
    logging.info('Quote divided into parts')

    return parts

# Function to create a video with text and voice-over using ffmpeg
def create_video(quote, background_image, output_video, anime, character, target_resolution, hide_output=True):
    temp_video_parts_folder = os.path.join(temp_folder, 'temp_video_parts')
    os.makedirs(temp_video_parts_folder, exist_ok=True)
    logging.info(f'Temporary folders created: {temp_folder}, {temp_video_parts_folder}')

    try:
        # Divide the quote into parts
        parts = divide_quote_into_parts(quote)

        # Track the audio time offset
        audio_time_offset = 0

        video_parts = []  # List to store temporary video part files

        for i, part in enumerate(parts):
            # Create a voice file for the part
            temp_part_voice_file = os.path.join(temp_video_parts_folder, f"part_{i}_voice.mp3")
            create_voice_file(part, temp_part_voice_file)

            # Calculate the duration of the audio part
            audio = AudioSegment.from_file(temp_part_voice_file)
            audio_duration = audio.duration_seconds

            # Generate a video part
            temp_part_video_file = os.path.join(temp_video_parts_folder, f"part_{i}.ts")

            cmd = [
                "ffmpeg",
                "-loglevel", "panic" if hide_output else "info",
                "-loop", "1",
                "-i", background_image,
                "-i", temp_part_voice_file,
                "-vf", f"drawtext=text='{part}':fontfile=font.ttf:fontsize=36:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-t", str(audio_duration),  # Set the duration
                "-y",  # Overwrite output file if it exists
                temp_part_video_file
            ]
            subprocess.run(cmd)
            logging.info(f'Video part created: {temp_part_video_file}')
            video_parts.append(f"file '{temp_part_video_file}'")

            # Update the audio time offset for the next part
            audio_time_offset += audio_duration

        # Create a text file listing the video parts for concatenation
        concat_txt = os.path.join(temp_video_parts_folder, 'concat.txt')
        with open(concat_txt, 'w') as file:
            for part in video_parts:
                file.write(part + '\n')
        logging.info('Video parts listed for concatenation')

        # Concatenate the video parts
        cmd = [
            "ffmpeg",
            "-loglevel", "panic" if hide_output else "info",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_txt,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-strict", "experimental",
            "-shortest",
            output_video
        ]
        subprocess.run(cmd)
        logging.info(f'Video concatenated: {output_video}')

    except Exception as e:
        logging.error(f'Error occurred: {str(e)}')

if __name__ == "__main__":
    # Choose a random quote
    anime_quote = random.choice(anime_quotes)

    # Extract the quote text and other details from the chosen quote
    quote_text = anime_quote["quote"]
    character = anime_quote["character"]
    anime = anime_quote["anime"]

    # Define the target video resolution (1080x1920)
    target_resolution = (1080, 1920)

    # Path to your original background image
    background_image_path = "background.jpg"

    # Resize and pad the background image to match the target resolution
    resized_background_image = resize_and_pad(background_image_path, target_resolution)
    resized_background_image.save("resized_background.jpg")

    # Output video file
    output_video_path = os.path.join(project_root, f"{anime}_{character}_quote.mp4")

    # Create the video with the anime quote and voice-over, hiding the ffmpeg output
    create_video(quote_text, "resized_background.jpg", output_video_path, anime, character, target_resolution, hide_output=True)
