import os
import requests
import email.utils
import time
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='download.log')

url_list_file = "pbf_list.txt"
with open(url_list_file, 'r') as f:
    files = [line.strip() for line in f if line.strip()]
logger.info(f"Start processing {len(files)} files")
for file in files:
    url = "https://download.geofabrik.de/" + file
    file_path = os.path.dirname(file)
    if file_path and not os.path.exists(file_path):
        os.makedirs(file_path)
    if os.path.exists(file):
        local_ts = os.path.getmtime(file)
        try:
            response = requests.head(url, allow_redirects=True)
            remote_mtime = response.headers.get('Last-Modified')
            remote_ts = time.mktime(email.utils.parsedate(remote_mtime))
        except Exception as e:
            logger.warning(f"Could not get headers for {file}: {e}")
            remote_ts = 0
        if local_ts >= remote_ts:
            logger.info(f"Skipping {file} - local: {local_ts} - remote: {remote_ts}")
            continue
    logger.info(f"Downloading {file}")
    try:
        with requests.get(url, allow_redirects=True, stream=True) as r:
            r.raise_for_status()
            with open(file, 'wb') as f_out:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f_out.write(chunk)
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
logger.info(f"Processing completed")
