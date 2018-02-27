import os
from io import BytesIO
from time import time
import logging
from collections import namedtuple

import youtube_dl
from ffmpy import FFmpeg
from pygogo import Gogo
from telegram.ext import Updater, RegexHandler
import telegram

from parser import parse_youtube_url, timestamp_to_seconds, HMS_PATTERN
from config import TOKEN


formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = Gogo(
    __name__,
    low_formatter=formatter,
    high_formatter=formatter
).logger


def get_videofile_url(youtube_url):
    options = dict(quiet=True)
    with youtube_dl.YoutubeDL(options) as ydl:
        r = ydl.extract_info(youtube_url, download=False)

    def is_mp4_with_audio(x):
        return (x['ext'] == 'mp4'
            and x['acodec'] != 'none')

    mp4_formats_with_audio = list(filter(is_mp4_with_audio, r['formats']))
    best_format = mp4_formats_with_audio[-1]
    return best_format['url']


def download_clip(url, start, length=10):
    ext = 'mp4'
    out_file_path = '{name}.{ext}'.format(name=time(), ext=ext)

    ff = FFmpeg(
        inputs={url: ['-ss', str(start)]},
        outputs={out_file_path: ['-t', str(length), '-c', 'copy', '-avoid_negative_ts', '1']},
        global_options='-v warning'
    )
    logger.info(ff.cmd)
    ff.run()

    with open(out_file_path, 'rb') as f:
        out_file = BytesIO(f.read())
        out_file.seek(0)
    os.remove(out_file_path)

    return out_file


Request = namedtuple('Request', 'video_id start length')


def parse_request(url, length=10, end=None):
    link = parse_youtube_url(url)

    if end:
        if timestamp_to_seconds(end) <= start:
            raise ValueError('End position should be greater than start position.')
        length = timestamp_to_seconds(end) - link.start

    if length <= 0:
        raise ValueError('Length should be greater than zero')

    return Request(link.id, link.start, length)


def handle_link(bot, update, groupdict):
    message = update.message

    try:
        request_info = parse_request(**groupdict)
    except ValueError as e:
        message.reply_text(str(e))
        return

    logger.info(request_info)

    bot.send_chat_action(message.chat.id, telegram.ChatAction.UPLOAD_VIDEO)

    file_url = get_videofile_url('https://youtu.be/' + request_info.video_id)
    downloaded_file = download_clip(file_url, request_info.start, request_info.length)

    message.reply_video(downloaded_file, quote=False)


def error_handler(bot, update, error):
    logger.warning('Update "%s" caused error "%s"', update, error)


if __name__ == '__main__':
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    pattern = (
        r'.*?'
         '(?P<url>'
             '(https?://)?(youtu\.be/'
             '|(?:www\.)?youtube\.com/watch)'
             '\S*[?&]t={}'.format(HMS_PATTERN) +
         ')'
         '(?:\s+(?:(?P<end>(?=\d+[hms]){})|(?P<length>\d+)))?'.format(HMS_PATTERN)  # optional
    )

    logger.info(pattern)

    dp.add_handler(RegexHandler(pattern, handle_link, pass_groupdict=True))

    dp.add_error_handler(error_handler)

    updater.start_polling()
    updater.idle()
