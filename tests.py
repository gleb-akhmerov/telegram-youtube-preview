from collections import namedtuple

from parser import parse_youtube_url, YoutubeLinkInfo

import hy
from parse_interval import str_to_ts, Timestamp, colons_to_ts


def test_youtube_url_parsing():
    test_cases = [
        ['https://youtu.be/urOhWPAS8OI?t=1h18m18s',
         YoutubeLinkInfo(id='urOhWPAS8OI', start='1h18m18s')],

        ['https://www.youtube.com/watch?v=urOhWPAS8OI&feature=youtu.be&t=1h18m18s',
         YoutubeLinkInfo(id='urOhWPAS8OI', start='1h18m18s')],
    ]

    for url, expected in test_cases:
        assert expected == parse_youtube_url(url)


def test_hms_timestamp_parsing():
    test_cases = [
        [  '3m52s', Timestamp(0, 3, 52) ],
        [     '5m', Timestamp(0, 5, 0)  ],
        [   '111s', Timestamp(0, 0, 111)],
        [     '1h', Timestamp(1, 0, 0)  ],
        ['2h32m6s', Timestamp(2, 32, 6) ],
    ]

    for timestamp, expected in test_cases:
        assert expected == str_to_ts(timestamp)


def test_colon_timestamp_parsing():
    test_cases = [
        [   '3:52', Timestamp(0, 3, 52) ],

        [   '5:00', Timestamp(0, 5, 0)  ],
        [    '5:0', Timestamp(0, 5, 0)  ],

        [  '0:111', Timestamp(0, 0, 111)],
        [   ':111', Timestamp(0, 0, 111)],

        ['1:00:00', Timestamp(1, 0, 0)  ],
        [  '1:0:0', Timestamp(1, 0, 0)  ],

        [ '2:32:6', Timestamp(2, 32, 6) ],
    ]

    for timestamp, expected in test_cases:
        assert expected == colons_to_ts(timestamp)
