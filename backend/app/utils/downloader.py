import yt_dlp
from pathlib import Path
import logging
import uuid

logger = logging.getLogger(__name__)

def download_media(url: str, output_dir: Path) -> Path | None:
    """Downloads audio/video from URL using yt-dlp."""
    logger.info(f"Attempting to download media from: {url}")
    output_template = str(output_dir / f"{uuid.uuid4()}.%(ext)s")

    ydl_opts = {
        'format': 'bestaudio/best', # Prioritize audio
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3', # Convert to mp3 for consistency
            'preferredquality': '192',
        }],
        # Consider adding options for video download if needed later
        # 'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            downloaded_path_template = ydl.prepare_filename(info_dict)
            # yt-dlp might add .mp3 automatically *or* based on postprocessor
            # We need the *final* path after postprocessing
            base_path = Path(downloaded_path_template).with_suffix('')
            final_path_mp3 = base_path.with_suffix('.mp3')

            if final_path_mp3.exists():
                logger.info(f"Successfully downloaded and converted to MP3: {final_path_mp3}")
                return final_path_mp3
            else:
                 # Fallback if only original format was downloaded (less likely with ffmpeg pp)
                 original_ext = info_dict.get('ext')
                 original_path = base_path.with_suffix(f'.{original_ext}')
                 if original_path.exists():
                     logger.warning(f"Downloaded original format, conversion might have failed: {original_path}")
                     return original_path # Return original if conversion failed
                 else:
                     logger.error(f"Download finished but couldn't find output file for {url}. Template: {downloaded_path_template}")
                     return None


    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp download failed for {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during download for {url}: {e}")
        return None
