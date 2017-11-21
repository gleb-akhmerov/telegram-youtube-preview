import os
from io import BytesIO
from time import time
import logging
from datetime import timedelta

import youtube_dl
from ffmpy import FFmpeg
from pygogo import Gogo
from telegram.ext import Updater, RegexHandler
import telegram

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


def download_clip(url, start, length='10'):
    try:
        ext = 'mp4'
        out_file_path = '{name}.{ext}'.format(name=time(), ext=ext)

        ff = FFmpeg(
            inputs={url: ['-ss', start]},
            outputs={out_file_path: ['-t', length, '-c', 'copy', '-avoid_negative_ts', '1']},
            global_options='-v quiet'
        )
        logger.info(ff.cmd)
        ff.run()

        with open(out_file_path, 'rb') as f:
            out_file = BytesIO(f.read())
            out_file.seek(0)
        os.remove(out_file_path)

        return out_file
    except Exception as e:
        logger.exception(e)


def summarize_total_seconds(h, m, s, **groups):
    """Summarizes arbitrary combinations of hours, minutes and seconds
       into total number of seconds."""
    h = 0 if h is None else int(h)
    m = 0 if m is None else int(m)
    s = 0 if s is None else int(s)

    delta = timedelta(hours=h, minutes=m, seconds=s)
    return str(int(delta.total_seconds()))


def handle_link(bot, update, groupdict):
    message = update.message

    start = summarize_total_seconds(**groupdict)
    youtube_url = groupdict['url']
    length = groupdict['length']
    logger.info('Url: %s, start: %s, lenght: %s', youtube_url, start, length)
    if not length:
        length = '10'

    bot.send_chat_action(message.chat.id, telegram.ChatAction.UPLOAD_VIDEO)

    url = get_videofile_url(youtube_url)
    downloaded_file = download_clip(url, start, length)

    message.reply_video(downloaded_file, quote=False)


def error_handler(bot, update, error):
    logger.warning('Update "%s" caused error "%s"', update, error)


if __name__ == '__main__':
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    hour_min_sec_pattern = (
        r'(?:(?P<h>\d+)h)?'  # optional
         '(?:(?P<m>\d+)m)?'  # optional
            '(?P<s>\d+)s'
    )

    pattern = (
        r'.*?'
         '(?P<url>(?:https?://)?youtu\.be/[A-Za-z0-9_-]{11})'
         '\?t=' + hour_min_sec_pattern +
         '(?:\s+(?P<length>\d+))?'  # optional
    )

    dp.add_handler(RegexHandler(pattern, handle_link, pass_groupdict=True))

    dp.add_error_handler(error_handler)

    updater.start_polling()
    updater.idle()
