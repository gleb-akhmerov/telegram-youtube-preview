from collections import namedtuple

from parser import parse_youtube_url, timestamp_to_seconds, YoutubeLinkInfo


def test_extracting():
    test_cases = [
        ['https://youtu.be/urOhWPAS8OI?t=1h18m18s',
         YoutubeLinkInfo(id='urOhWPAS8OI', start=4698)],

        ['https://www.youtube.com/watch?v=urOhWPAS8OI&feature=youtu.be&t=1h18m18s',
         YoutubeLinkInfo(id='urOhWPAS8OI', start=4698)],
    ]

    for url, expected in test_cases:
        assert expected == parse_youtube_url(url)


def test_request_parsing():
    test_cases = [
        [  '3m52s',  232],
        [     '5m',  300],
        [   '111s',  111],
        [     '1h', 3600],
        ['2h32m6s', 9126],
    ]

    for timestamp, expected in test_cases:
        assert expected == timestamp_to_seconds(timestamp)
