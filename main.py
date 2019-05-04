import os
from io import BytesIO
from time import time
import logging
from functools import partial

import youtube_dl
from ffmpy import FFmpeg
from pygogo import Gogo
from telegram.ext import Updater, MessageHandler, Filters
from telegram import InputMediaVideo
import telegram
from cachetools import TTLCache

from parse import parse_request, request_to_start_timestamp_url
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


def download_clip(url, start, end):
    ext = 'mp4'
    temp_file_path = '{name}.{ext}'.format(name=time(), ext=ext)
    out_file_path  = '{name}.{ext}'.format(name=time(), ext=ext)

    ff = FFmpeg(
        inputs={url: ['-ss', str(start)]},
        outputs={temp_file_path: ['-t', str(end - start),
                                  '-c', 'copy']},
        global_options='-v warning'
    )
    logger.info(ff.cmd)
    ff.run()

    ff = FFmpeg(
        inputs={temp_file_path: ['-seek_timestamp',
                                 '1', '-ss', '0']},
        outputs={out_file_path: ['-c:v', 'libx264',
                                 '-preset', 'veryfast',
                                 '-c:a', 'copy']},
        global_options='-v warning'
    )
    logger.info(ff.cmd)
    ff.run()

    with open(out_file_path, 'rb') as f:
        out_file = BytesIO(f.read())
        out_file.seek(0)

    os.remove(temp_file_path)
    os.remove(out_file_path)

    return out_file


def handle_message(bot, update, last_messages):
    try:
        message = update.message

        try:
            request = parse_request(message.text)
        except ValueError as e:
            message.reply_text(str(e))
            return
        else:
            if not request:
                return

        logger.info("Message: %s, request: %s", message.text, request)

        bot.send_chat_action(message.chat.id, telegram.ChatAction.UPLOAD_VIDEO)

        file_url = get_videofile_url('https://youtu.be/' + request.youtube_id)
        downloaded_file = download_clip(file_url, request.start, request.end)

        video_mes = bot.send_video(message.chat_id, downloaded_file,
                                   reply_to_message_id=message.message_id,
                                   caption=request_to_start_timestamp_url(request))

        last_messages[(message.chat.id, message.message_id)] = video_mes.message_id
    except Exception as e:
        logger.exception(e)


def handle_message_edit(bot, update, last_messages):
    try:
        message = update.edited_message

        try:
            video_mes_id = last_messages[(message.chat.id, message.message_id)]
        except KeyError:
            know_message = False
        else:
            know_message = True

        try:
            request = parse_request(message.text)
        except ValueError as e:
            if know_message:
                bot.edit_message_caption(message.chat.id, video_mes_id, caption=str(e))
            else:
                message.reply_text(str(e))
            return
        else:
            if not request:
                return

        logger.info("Message: %s, request: %s", message.text, request)

        bot.send_chat_action(message.chat.id, telegram.ChatAction.UPLOAD_VIDEO)

        file_url = get_videofile_url('https://youtu.be/' + request.youtube_id)
        downloaded_file = download_clip(file_url, request.start, request.end)

        if know_message:
            bot.edit_message_media(message.chat.id, video_mes_id,
                                   media=InputMediaVideo(
                                       downloaded_file,
                                       caption=request_to_start_timestamp_url(request)
                                   ))
        else:
            video_mes = bot.send_video(message.chat_id, downloaded_file,
                                       reply_to_message_id=message.message_id,
                                       caption=request_to_start_timestamp_url(request))

            last_messages[(message.chat.id, message.message_id)] = video_mes.message_id
    except Exception as e:
        logger.exception(e)


def error_handler(bot, update, error):
    logger.warning('Update "%s" caused error "%s"', update, error)


if __name__ == '__main__':
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    last_messages = TTLCache(maxsize=1000, ttl=86400)

    dp.add_handler(MessageHandler(Filters.text,
                                  partial(handle_message, last_messages=last_messages)))
    dp.add_handler(MessageHandler(Filters.text,
                                  partial(handle_message_edit, last_messages=last_messages),
                                  message_updates=False,
                                  edited_updates=True))

    dp.add_error_handler(error_handler)

    updater.start_polling()
    updater.idle()
