from collections import namedtuple

from parser import parse_youtube_url, YoutubeLinkInfo


ExpectedResult = YoutubeLinkInfo


def test_extracting():
    test_cases = {
        'https://youtu.be/urOhWPAS8OI?t=1h18m18s':
            ExpectedResult(id='urOhWPAS8OI', start='4698'),

        'https://www.youtube.com/watch?v=urOhWPAS8OI&feature=youtu.be&t=1h18m18s':
            ExpectedResult(id='urOhWPAS8OI', start='4698'),
    }

    for url, expected in test_cases.items():
        result = parse_youtube_url(url)
        assert expected == result, 'Expected: {}, got: {}'.format(expected, result)


if __name__ == '__main__':
    test_extracting()
