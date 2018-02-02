import re
from datetime import timedelta
from collections import namedtuple

from furl import furl


YoutubeLinkInfo = namedtuple('YoutubeLinkInfo', ['id', 'start'])


HMS_PATTERN = (
    '(?:(\d+)h)?'
    '(?:(\d+)m)?'
    '(?:(\d+)s)?'
)


def timestamp_to_seconds(timestamp):
    pattern = (
        '(?:(?P<h>\d+)h)?'
        '(?:(?P<m>\d+)m)?'
        '(?:(?P<s>\d+)s)?'
    )

    d = re.match(pattern, timestamp).groupdict()

    h = 0 if d['h'] is None else int(d['h'])
    m = 0 if d['m'] is None else int(d['m'])
    s = 0 if d['s'] is None else int(d['s'])

    delta = timedelta(hours=h, minutes=m, seconds=s)
    return str(int(delta.total_seconds()))


def parse_youtube_url(url):
    """Extracts id and timestamp from a youtube url"""

    f = furl(url)

    if 'youtu.be' in f.host:
        return YoutubeLinkInfo(
            id=f.path.segments[0],
            start=timestamp_to_seconds(f.args['t'])
        )

    elif 'youtube.com' in f.host:
        return YoutubeLinkInfo(
            id=f.args['v'],
            start=timestamp_to_seconds(f.args['t'])
        )
