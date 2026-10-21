import datetime as dt
import os
import requests
import logging
import time

from osmium.replication.utils import get_replication_header
from osmium.tools.pyosmium_up_to_date import pyosmium_up_to_date

logger = logging.getLogger(__name__)

# seconds to wait for the connection and for each chunk; a stalled download fails instead of hanging
request_timeout = 60

# pyosmium-up-to-date keeps the downloaded diffs in memory and needs about 1 GB more for processing;
# 8 GB suits the 12 GB server and is far more than the daily diffs of any extract
max_diff_size_mb = 8192

# pyosmium-up-to-date refuses files older than 90 days; download those again instead
max_update_age = dt.timedelta(days=85)

# pyosmium-up-to-date returns 1 while the server has more diffs than fit into one round
max_update_rounds = 10


def download_file(url, file):
    """
    Downloads url into a temporary file next to file and only replaces file once the download is complete, so an
    interrupted download never leaves a truncated file for the importer. The temporary file doesn't end in .pbf,
    so the importer ignores it.

    :return: True if file was replaced
    """
    temp_file = temp_file_for(file)
    try:
        with requests.get(url, allow_redirects=True, stream=True, timeout=request_timeout) as r:
            r.raise_for_status()
            with open(temp_file, 'wb') as f_out:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f_out.write(chunk)
            expected_size = r.headers.get('Content-Length')
        if expected_size is not None and os.path.getsize(temp_file) != int(expected_size):
            raise IOError(f"incomplete download, {os.path.getsize(temp_file)} of {expected_size} bytes")
        os.replace(temp_file, file)
        return True
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return False
    finally:
        # also on Ctrl-C or SystemExit, which the except above doesn't catch
        remove_if_exists(temp_file)


def is_updatable(file):
    """
    True if file names a replication server in its header and is recent enough for pyosmium-up-to-date.
    """
    try:
        header = get_replication_header(file)
    except RuntimeError as e:
        logger.warning(f"Cannot read the header of {file}: {e}")
        return False
    if header.url is None or header.sequence is None or header.timestamp is None:
        return False
    return dt.datetime.now(dt.timezone.utc) - header.timestamp < max_update_age


def update_file(file):
    """
    Applies the diffs from the replication server named in the file's header. Like download_file, it writes to a
    temporary file and only replaces file with a complete result; on failure file stays as it was.

    :return: True if file is up to date
    """
    temp_file = temp_file_for(file)
    try:
        for _ in range(max_update_rounds):
            exit_code = pyosmium_up_to_date(["--format", "pbf", "--size", str(max_diff_size_mb),
                                             "-o", temp_file, file])
            if exit_code in (0, 1) and os.path.exists(temp_file):
                os.replace(temp_file, file)
            if exit_code != 1:
                break
    finally:
        # osmium refuses to write to an existing file, so never leave one behind, not even on Ctrl-C
        remove_if_exists(temp_file)
    if exit_code != 0:
        logger.error(f"Failed to update {file}, pyosmium-up-to-date exited with {exit_code}")
    return exit_code == 0


def temp_file_for(file):
    """
    Returns the name of file's temporary file, after removing a leftover from an interrupted earlier run.
    """
    temp_file = file + ".part"
    remove_if_exists(temp_file)
    return temp_file


def remove_if_exists(file):
    if os.path.exists(file):
        os.remove(file)


def main():
    url_list_file = "pbf_list.txt"
    with open(url_list_file, 'r') as f:
        files = [line.strip() for line in f if line.strip()]
    logger.info(f"Start processing {len(files)} files")
    for file in files:
        url = "https://download.geofabrik.de/" + file
        file_path = os.path.dirname(file)
        if file_path and not os.path.exists(file_path):
            os.makedirs(file_path)
        if os.path.exists(file) and is_updatable(file):
            run_logged("update", file, lambda: update_file(file))
        else:
            run_logged("download", file, lambda: download_file(url, file))
    logger.info("Processing completed")


def run_logged(process, file, action):
    """
    Runs action, logging when the process starts and ends, with its outcome and duration.

    :return: what action returned, True if it succeeded
    """
    logger.info(f"Starting {process} of {file}")
    started = time.monotonic()
    succeeded = action()
    duration = dt.timedelta(seconds=round(time.monotonic() - started))
    if succeeded:
        logger.info(f"Finished {process} of {file}: succeeded after {duration}")
    else:
        logger.warning(f"Finished {process} of {file}: failed after {duration}")
    return succeeded


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                        filename='download.log')
    main()
