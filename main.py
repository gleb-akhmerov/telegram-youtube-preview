import asyncio
import logging
import os
from io import BytesIO
from time import time
from uuid import uuid4

import aiogram
import youtube_dl
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher, filters
from aiogram.types import InputMediaVideo, InlineQuery, InlineQueryResultPhoto, InlineKeyboardMarkup, \
    InlineKeyboardButton
from aiogram.utils import executor
from cachetools import TTLCache
from ffmpy import FFmpeg
from pygogo import Gogo

from config import TOKEN, BOT_CHANNEL_ID
from parse import Request, match_request, request_to_start_timestamp_url, first_some, request_to_query

try:
    import ujson as json
except ImportError:
    import json as json

try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

loop = asyncio.get_event_loop()
bot = Bot(token=TOKEN, loop=loop)
dispatcher = Dispatcher(bot)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = Gogo(
    __name__,
    low_formatter=formatter,
    high_formatter=formatter
).logger


async def get_videofile_url(youtube_url):
    options = dict(quiet=True)
    with youtube_dl.YoutubeDL(options) as ydl:
        r = ydl.extract_info(youtube_url, download=False)

    def is_mp4_with_audio(x):
        return (x['ext'] == 'mp4'
                and x['acodec'] != 'none')

    mp4_formats_with_audio = list(filter(is_mp4_with_audio, r['formats']))
    best_format = mp4_formats_with_audio[-1]
    return best_format['url']


async def download_clip(url, start, end):
    ext = 'mp4'
    temp_file_path = '{name}.temp.{ext}'.format(name=time(), ext=ext)
    out_file_path = '{name}.{ext}'.format(name=time(), ext=ext)

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


@dispatcher.message_handler(filters.Text(contains="https", ignore_case=False))
async def handle_message(message: types.Message):
    try:
        try:
            request = match_request(message.text)
        except ValueError as e:
            message.reply_text(str(e))
            return
        else:
            if not request:
                return

        logger.info("Message: %s, request: %s", message.text, request)

        await bot.send_chat_action(message.chat.id, aiogram.types.chat.ChatActions.UPLOAD_VIDEO)

        file_url = await get_videofile_url('https://youtu.be/' + request.youtube_id)
        downloaded_file = await download_clip(file_url, request.start, request.end)
        video_mes = await bot.send_video(message.chat.id, downloaded_file,
                                         reply_to_message_id=message.message_id,
                                         caption=request_to_start_timestamp_url(request))

        last_messages[(message.chat.id, message.message_id)] = video_mes.message_id
    except Exception as e:
        logger.exception(e)


@dispatcher.edited_message_handler(filters.Text(contains="https", ignore_case=False))
async def handle_message_edit(message: types.Message):
    try:
        try:
            video_mes_id = last_messages[(message.chat.id, message.message_id)]
        except KeyError:
            know_message = False
        else:
            know_message = True

        try:
            request = match_request(message.text)
        except ValueError as e:
            if know_message:
                await bot.edit_message_caption(message.chat.id, video_mes_id, caption=str(e))
            else:
                await message.answer(str(e))
            return
        else:
            if not request:
                return

        logger.info("Message: %s, request: %s", message.text, request)

        await bot.send_chat_action(message.chat.id, aiogram.types.chat.ChatActions.UPLOAD_VIDEO)

        file_url = await get_videofile_url('https://youtu.be/' + request.youtube_id)
        downloaded_file = await download_clip(file_url, request.start, request.end)

        if know_message:
            await bot.edit_message_media(chat_id=message.chat.id,
                                         message_id=video_mes_id,
                                         media=InputMediaVideo(downloaded_file,
                                                               caption=request_to_start_timestamp_url(request)))
        else:
            video_mes = await bot.send_video(message.chat.id, downloaded_file,
                                             reply_to_message_id=message.message_id,
                                             caption=request_to_start_timestamp_url(request))

            last_messages[(message.chat.id, message.message_id)] = video_mes.message_id
    except Exception as e:
        logger.exception(e)


def make_inline_keyboard(request) -> InlineKeyboardMarkup:
    actions = [
        [('+1', 1), ('-1', -1)],
        [('+2', 2), ('-2', -2)],
        [('+5', 5), ('-5', -5)],
        [('+10', 10), ('-10', -10)],
        [('+30', 30), ('-30', -30)],
        [('Обрезать', 'send')],
    ]

    return InlineKeyboardMarkup(
        row_width=1,
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text,
                    callback_data=f'{request.youtube_id} {request.start} {request.end} {action}',
                )
                for text, action in row
            ]
            for row in actions
        ],
    )


@dispatcher.inline_handler()
async def inline_query(inline_query: InlineQuery) -> None:
    """Handle the inline query."""
    try:
        query = inline_query.query

        try:
            request = first_some([
                match_request(query),
                match_request(query + ' 10'),
            ])
        except ValueError:
            await bot.answer_inline_query(inline_query.id, [])
            return

        if request is None:
            await bot.answer_inline_query(inline_query.id, [])
            return

        results = [
            InlineQueryResultPhoto(
                id=str(uuid4()),
                title="",
                photo_url="https://i.ytimg.com/vi/{id}/mqdefault.jpg".format(id=request.youtube_id),
                thumb_url="https://i.ytimg.com/vi/{id}/mqdefault.jpg".format(id=request.youtube_id),
                reply_markup=make_inline_keyboard(request),
                caption=request_to_query(request),
            ),
        ]
        await bot.answer_inline_query(inline_query.id, results, cache_time=60 * 60 * 24)
    except Exception as e:
        logger.exception("a")


#@dispatcher.chosen_inline_handler(lambda chosen_inline_query: True)
async def chosen_inline_handler(chosen_inline_query: types.ChosenInlineResult):
    try:
        request = match_request(chosen_inline_query.query)

        file_url = await get_videofile_url('https://youtu.be/' + request.youtube_id)
        downloaded_file = await download_clip(file_url, request.start, request.end)
        video_mes = await bot.send_video(BOT_CHANNEL_ID, downloaded_file)
        await bot.edit_message_media(inline_message_id=chosen_inline_query.inline_message_id,
                                     media=InputMediaVideo(video_mes.video.file_id,
                                                           caption=request_to_start_timestamp_url(request)))
    except Exception as e:
        logger.exception("a")


@dispatcher.callback_query_handler(lambda callback_query: True)
async def inline_kb_answer_callback_handler(callback_query: types.CallbackQuery):
    try:
        await callback_query.answer()

        youtube_id, start, end, action = callback_query.data.split()
        request = Request(youtube_id=youtube_id, start=int(start), end=int(end))

        if action == 'send':
            file_url = await get_videofile_url('https://youtu.be/' + request.youtube_id)
            downloaded_file = await download_clip(file_url, request.start, request.end)
            video_mes = await bot.send_video(BOT_CHANNEL_ID, downloaded_file)
            await bot.edit_message_media(inline_message_id=callback_query.inline_message_id,
                                         media=InputMediaVideo(video_mes.video.file_id,
                                                               caption=request_to_start_timestamp_url(request)))
        else:
            delta = int(action)
            request.end += delta
            await bot.edit_message_caption(
                inline_message_id=callback_query.inline_message_id,
                reply_markup=make_inline_keyboard(request),
                caption=request_to_query(request),
            )
    except Exception as e:
        logger.exception("a")


@dispatcher.errors_handler()
async def error_handler(update: types.Update, exception: Exception):
    logger.warning('Update "%s" caused error "%s"', update, exception)


last_messages = TTLCache(maxsize=1000, ttl=86400)

if __name__ == '__main__':
    executor.start_polling(dispatcher, loop=loop)
