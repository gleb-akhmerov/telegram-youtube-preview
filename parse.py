from dataclasses import dataclass
from typing import Optional, Tuple, Dict
import re

from furl import furl
from funcy import project, walk_values, first


@dataclass
class Request:
    youtube_id: str
    start: int
    end: int


@dataclass
class Timestamp:
    h: int
    m: int
    s: int



def first_some(seq):
    return first(x for x in seq if x is not None)


def is_youtube_url(possible_yt_video_url: str) -> bool:
    return bool(re.match(r'(https?://)?((www\.)?youtube\.com|youtu\.be)\b', possible_yt_video_url))


def youtube_url_as_dict(yt_url: str) -> Dict[str, str]:
    yt_url_with_schema = yt_url if yt_url.startswith('http') else 'https://' + yt_url
    f = furl(yt_url_with_schema)

    if f.host.endswith('youtube.com'):
        if str(f.path) == '/watch' and 'v' in f.args:
            return project(f.args, ['v', 't'])
        else:
            return {}

    else:  # youtu.be
        if f.path.segments:
            return {
                'v': f.path.segments[0],
                **project(f.args, ['t']),
            }
        else:
            return {}


HMS_PATTERN = (
    r'(?=\d+[hms])'  # require at least one group
    r'(?:(?P<h>\d+)h)?'
    r'(?:(?P<m>\d+)m)?'
    r'(?:(?P<s>\d+)s)?'
)


COLONS_PATTERN = (
    r'(?:'
      r'(?P<h>\d+)'
      r':'
    r')?'
    r'(?P<m>\d+)'
    r':'
    r'(?P<s>\d+)'
)


def hms_to_seconds(h: int, m: int, s: int) -> int:
    return (
          h * 60 * 60
        + m * 60
        + s
    )


def match_to_seconds(m):
    return hms_to_seconds(**walk_values(int, m.groupdict(default='0')))


def match_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except ValueError:
        return None


def match_time_pattern(time_pattern: str, s: str) -> Optional[int]:
    found = re.search(r'^' + time_pattern + r'$', s)
    if found:
        return match_to_seconds(found)
    else:
        return None


def match_start(s: str) -> Optional[int]:
    return first_some([match_int(s),
                       match_time_pattern(HMS_PATTERN, s),
                       match_time_pattern(COLONS_PATTERN, s)])


def match_t_start(s: str) -> Optional[int]:
    return first_some([match_int(s),
                       match_time_pattern(HMS_PATTERN, s)])



def match_end(s: str) -> Optional[Tuple[str, int]]:
    try:
        return ('relative', int(s))
    except ValueError:
        pass

    found = first_some([re.search(r'^\+' +    HMS_PATTERN + r'$', s),
                        re.search(r'^\+' + COLONS_PATTERN + r'$', s)])
    if found:
        return ('relative', match_to_seconds(found))

    found = first_some([re.search(r'^\.\.' +    HMS_PATTERN + r'$', s),
                        re.search(r'^\.\.' + COLONS_PATTERN + r'$', s)])
    if found:
        return ('ellipsis', match_to_seconds(found))

    found = first_some([re.search(r'^' +    HMS_PATTERN + r'$', s),
                        re.search(r'^' + COLONS_PATTERN + r'$', s)])
    if found:
        return ('absolute', match_to_seconds(found))

    return None


def seconds_to_ts(val: int) -> Timestamp:
    left, s = divmod(val,  60)
    h, m    = divmod(left, 60)
    return Timestamp(h, m, s)


def ts_to_hms(ts: Timestamp) -> str:
    return (
          (str(ts.h) + 'h' if ts.h > 0 else '')
        + (str(ts.m) + 'm' if ts.m > 0 else '')
        + (str(ts.s) + 's' if ts.s > 0 else '')
    )


def ts_to_columns(ts: Timestamp) -> str:
    return (
          (f'{ts.h:02d}' + ':' if ts.h > 0 else '')
        + f'{ts.m:02d}' + ':'
        + f'{ts.s:02d}'
    )


def request_to_start_timestamp_url(r: Request) -> str:
    start_hms = ts_to_hms(seconds_to_ts(r.start))
    return ('https://youtu.be/' + r.youtube_id
            + ('?t=' + start_hms if start_hms else ''))


def request_to_query(r: Request) -> str:
    start = ts_to_columns(seconds_to_ts(r.start))
    end = ts_to_columns(seconds_to_ts(r.end))
    return f'https://youtu.be/{r.youtube_id} {start} {end}'


def merge_ellipsis(s: int, e: int) -> Optional[int]:
    start = seconds_to_ts(s)
    end   = seconds_to_ts(e)
    if end.m > 0:
        return hms_to_seconds(start.h, end.m, end.s)
    elif end.s > 0:
        return hms_to_seconds(start.h, start.m, end.s)
    else:
        return None


def raw_end_to_absolute(start: int, raw_end: Tuple[str, int]) -> Optional[int]:
    end_type, end = raw_end
    if end_type == 'absolute':
        return end
    elif end_type == 'relative':
        return start + end
    elif end_type == 'ellipsis':
        return merge_ellipsis(start, end)
    else:
        raise ValueError(raw_end)


def match_request(s: str) -> Optional[Request]:
    tokens = s.split()
    if len(tokens) == 2:
        maybe_yt_url_with_hms, maybe_end = tokens

        if not is_youtube_url(maybe_yt_url_with_hms):
            return None

        yt_dict = youtube_url_as_dict(maybe_yt_url_with_hms)

        if 'v' not in set(yt_dict):
            return None
        youtube_id = yt_dict['v']

        if 't' not in set(yt_dict):
            if maybe_end == 'full':
                maybe_end = '10:00'
                start = 0
            else:
                return None
        else:
            start = match_t_start(yt_dict['t'])
            if start is None:
                return None

    elif len(tokens) == 3:
        maybe_yt_url, maybe_start, maybe_end = tokens

        if not is_youtube_url(maybe_yt_url):
            return None

        yt_dict = youtube_url_as_dict(maybe_yt_url)
        if {'v'} != set(yt_dict):
            return None

        youtube_id = yt_dict['v']

        start = match_start(maybe_start)
        if start is None:
            return None

    else:
        return None

    raw_end = match_end(maybe_end)
    if raw_end is None:
        return None

    end = raw_end_to_absolute(start, raw_end)
    if end is None:
        return None

    if start >= end:
        raise ValueError('End position should be greater than start position.')

    if end - start > 10 * 60:
        raise ValueError('Maximum clip length is 10 minutes')

    return Request(youtube_id, start, end)
