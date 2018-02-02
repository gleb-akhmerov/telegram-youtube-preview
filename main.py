import os
from io import BytesIO
from time import time
import logging

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


def download_clip(url, start, length='10'):
    ext = 'mp4'
    out_file_path = '{name}.{ext}'.format(name=time(), ext=ext)

    ff = FFmpeg(
        inputs={url: ['-ss', start]},
        outputs={out_file_path: ['-t', length, '-c', 'copy', '-avoid_negative_ts', '1']},
        global_options='-v warning'
    )
    logger.info(ff.cmd)
    ff.run()

    with open(out_file_path, 'rb') as f:
        out_file = BytesIO(f.read())
        out_file.seek(0)
    os.remove(out_file_path)

    return out_file


def handle_link(bot, update, groupdict):
    try:
        message = update.message

        link_info = parse_youtube_url(groupdict['url'])

        start = link_info.start
        youtube_url = 'https://youtu.be/' + link_info.id

        if groupdict['end']:
            length = str(int(timestamp_to_seconds(groupdict['end'])) - int(start))
        elif groupdict['length']:
            length = groupdict['length']
        else:
            length = '10'

        logger.info('Url: %s, start: %s, length: %s', youtube_url, start, length)

        bot.send_chat_action(message.chat.id, telegram.ChatAction.UPLOAD_VIDEO)

        url = get_videofile_url(youtube_url)
        downloaded_file = download_clip(url, start, length)

        message.reply_video(downloaded_file, quote=False)
    except Exception as e:
        logger.exception(e)


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
         '(?:\s+(?:(?P<end>{})|(?P<length>\d+)))?'.format(HMS_PATTERN)  # optional
    )

    logger.info(pattern)

    dp.add_handler(RegexHandler(pattern, handle_link, pass_groupdict=True))

    dp.add_error_handler(error_handler)

    updater.start_polling()
    updater.idle()
