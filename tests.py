from parse import is_youtube_url, youtube_url_as_dict, match_start, hms_to_seconds, match_request, Request


def test_is_youtube_url():
    yt_urls = [
        'https://www.youtube.com/watch?v=Bx51eegLTY8',
        'https://youtube.com/watch?v=Bx51eegLTY8',

        'http://www.youtube.com/watch?v=Bx51eegLTY8',
        'http://youtube.com/watch?v=Bx51eegLTY8',

        'www.youtube.com/watch?v=Bx51eegLTY8',
        'youtube.com/watch?v=Bx51eegLTY8',

        'https://youtu.be/Bx51eegLTY8',
        'http://youtu.be/Bx51eegLTY8',
        'youtu.be/Bx51eegLTY8',
    ]

    for u in yt_urls:
        assert is_youtube_url(u)


def test_not_youtube_url():
    not_yt_urls = [
        'www.youtu.be/Bx51eegLTY8',
        'youtu.bee/Bx51eegLTY8',
    ]

    for u in not_yt_urls:
        assert not is_youtube_url(u)


def test_youtube_url_as_dict_without_time():
    yt_urls = [
        'https://www.youtube.com/watch?v=Bx51eegLTY8',
        'https://youtube.com/watch?v=Bx51eegLTY8',

        'http://www.youtube.com/watch?v=Bx51eegLTY8',
        'http://youtube.com/watch?v=Bx51eegLTY8',

        'www.youtube.com/watch?v=Bx51eegLTY8',
        'youtube.com/watch?v=Bx51eegLTY8',

        'https://youtu.be/Bx51eegLTY8',
        'http://youtu.be/Bx51eegLTY8',
        'youtu.be/Bx51eegLTY8',
    ]

    for u in yt_urls:
        assert youtube_url_as_dict(u) == {'v': 'Bx51eegLTY8'}


def test_youtube_url_as_dict_with_time():
    yt_urls = [
        'https://www.youtube.com/watch?v=Bx51eegLTY8&t=2m33s',
        'https://youtube.com/watch?v=Bx51eegLTY8&t=2m33s',

        'http://www.youtube.com/watch?v=Bx51eegLTY8&t=2m33s',
        'http://youtube.com/watch?v=Bx51eegLTY8&t=2m33s',

        'www.youtube.com/watch?v=Bx51eegLTY8&t=2m33s',
        'youtube.com/watch?v=Bx51eegLTY8&t=2m33s',

        'https://youtu.be/Bx51eegLTY8?t=2m33s',
        'http://youtu.be/Bx51eegLTY8?t=2m33s',
        'youtu.be/Bx51eegLTY8?t=2m33s',
    ]

    for u in yt_urls:
        assert youtube_url_as_dict(u) == {'v': 'Bx51eegLTY8', 't': '2m33s'}


def test_match_start():
    assert match_start('1h20m18s') == hms_to_seconds(1, 20, 18)
    assert match_start('1:20:18')  == hms_to_seconds(1, 20, 18)
    assert match_start('20:18')    == hms_to_seconds(0, 20, 18)
    assert match_start('4818')     == 4818


def test_match_request():
    cases = [
        ("https://youtu.be/C0DPdy98e4c?t=1h20m18s 1h20m40s",
         Request("C0DPdy98e4c",
                 hms_to_seconds(1, 20, 18),
                 hms_to_seconds(1, 20, 40))),

        ("https://youtu.be/C0DPdy98e4c?t=1h20m18s ..40s",
         Request("C0DPdy98e4c",
                 hms_to_seconds(1, 20, 18),
                 hms_to_seconds(1, 20, 40))),

        # TODO: test that this raises an exception
        # ("https://youtu.be/C0DPdy98e4c?t=1h20m18s ..5s",
        #  Request("C0DPdy98e4c",
        #          hms_to_seconds(1, 20, 18),
        #          hms_to_seconds(1, 20,  5))),

        ("https://youtu.be/C0DPdy98e4c?t=1h20m18s 10",
         Request("C0DPdy98e4c",
                 hms_to_seconds(1, 20, 18),
                 hms_to_seconds(1, 20, 28))),

        ("https://youtu.be/C0DPdy98e4c 1h20m18s 1h20m40s",
         Request("C0DPdy98e4c",
                 hms_to_seconds(1, 20, 18),
                 hms_to_seconds(1, 20, 40))),

        ("https://youtu.be/C0DPdy98e4c 1:20:18 1:20:40",
         Request("C0DPdy98e4c",
                 hms_to_seconds(1, 20, 18),
                 hms_to_seconds(1, 20, 40))),

        ("https://youtu.be/C0DPdy98e4c?t=4818 10",
         Request("C0DPdy98e4c",
                 4818,
                 4828)),

        # TODO: test that `youtube-link` can only have a `t-start`
    ]

    for inp, out in cases:
        assert match_request(inp) == out
