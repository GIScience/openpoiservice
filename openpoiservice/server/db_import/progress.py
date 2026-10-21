# openpoiservice/server/db_import/progress.py
import datetime as dt


def format_duration(seconds):
    return str(dt.timedelta(seconds=round(seconds)))


def format_size(size_bytes):
    for unit in ("B", "kB", "MB"):
        if size_bytes < 1000:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} B"
        size_bytes /= 1000
    return f"{size_bytes:.1f} GB"


class Progress:
    """
    Counts items of a long running pass and logs the count each time it passes another multiple of step, so the
    console shows that the pass is still making progress.
    """

    def __init__(self, logger, label, what, step):
        self.logger = logger
        self.label = label
        self.what = what
        self.step = step
        self.count = 0

    def add(self, number=1):
        previous = self.count
        self.count += number
        if self.count // self.step > previous // self.step:
            self.logger.info(f"{self.label}   {self.count:,} {self.what}")
