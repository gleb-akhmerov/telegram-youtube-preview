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


# def timestamp_to_seconds(timestamp):
#     pattern = (
#         '(?:(?P<h>\d+)h)?'
#         '(?:(?P<m>\d+)m)?'
#         '(?:(?P<s>\d+)s)?'
#     )

#     d = re.match(pattern, timestamp).groupdict(default=0)

#     h = int(d['h'])
#     m = int(d['m'])
#     s = int(d['s'])

#     delta = timedelta(hours=h, minutes=m, seconds=s)
#     return round(delta.total_seconds())


def parse_youtube_url(url):
    """Extracts id and timestamp from a youtube url"""

    f = furl(url)
    if f.host is None:
        raise ValueError('Unknown URL', url)

    if 'youtu.be' in f.host:
        try:
            return YoutubeLinkInfo(
                id=f.path.segments[0],
                start=f.args['t']
            )
        except KeyError:
            raise ValueError('"youtu.be" URL should have a "t" parameter', url)

    elif 'youtube.com' in f.host:
        try:
            return YoutubeLinkInfo(
                id=f.args['v'],
                start=f.args['t']
            )
        except KeyError:
            raise ValueError('"youtube.com" URL should have parameters "t" and "v"', url)

    else:
        raise ValueError('Not a YouTube URL', url)
