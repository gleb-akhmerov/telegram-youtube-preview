import asyncio
import logging
import os
from io import BytesIO
from time import time
from typing import Literal
from uuid import uuid4

import aiogram
import yt_dlp
from yt_dlp.utils import YoutubeDLError
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher, filters
from aiogram.types import (
    InputFile,
    InputMediaVideo,
    InputMediaAudio,
    InlineQuery,
    InlineQueryResultCachedPhoto,
    InlineKeyboardMarkup,
)
from aiogram.utils import executor
from cachetools import TTLCache
from ffmpy import FFmpeg, FFRuntimeError
from pygogo import Gogo
import requests

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


FORMATS_BY_TYPE = {
    'preview': ['best[height<720]'],
    'video': ['best', 'best[height<720]'],
    'audio': ['bestaudio/best'],
}


def get_file_url(youtube_url: str, format: str) -> str:
    options = dict(format=format, check_formats='selected', verbose=True)
    with yt_dlp.YoutubeDL(options) as ydl:
        r = ydl.extract_info(youtube_url, download=False)

    return (r['ext'], r['url'])


def download_clip(url, start, end, type_: Literal['video', 'audio']):
    source_ext, url = url

    if type_ == 'video':
        ext = 'mp4'
    elif type_ == 'audio':
        ext = 'mp3'

    temp_file_path = f'{time()}.temp.{source_ext}'
    out_file_path = f'{time()}.{ext}'

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
                                 '-c:a', 'libopus',
                                 '-b:a', '128000']
                                if type_ == 'video'
                                else []},
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


def download_file(request, type_: Literal['preview', 'video', 'audio']):
    media_type = 'audio' if type_ == 'audio' else 'video'
    for i, format in enumerate(FORMATS_BY_TYPE[type_]):
        try:
            logger.info(f"Trying format: {format}")
            file_url = get_file_url('https://youtu.be/' + request.youtube_id, format)
            return download_clip(file_url, request.start, request.end, media_type)
        except (FFRuntimeError, yt_dlp.utils.DownloadError) as e:
            if i < len(FORMATS_BY_TYPE[type_]) - 1:
                continue
            else:
                raise e


@dispatcher.message_handler()
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

        downloaded_file = download_file(request, 'video')
        video_mes = await bot.send_video(message.chat.id, downloaded_file,
                                         reply_to_message_id=message.message_id,
                                         caption=request_to_start_timestamp_url(request))

        last_messages[(message.chat.id, message.message_id)] = video_mes.message_id
    except Exception as e:
        logger.exception(e)


@dispatcher.edited_message_handler()
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

        downloaded_file = download_file(request, 'video')

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


def make_inline_keyboard(
    user_id: int, request: Request,
    start_end_mode: Literal['start', 'end'] = 'end',
    int_frac_mode: Literal['int', 'frac'] = 'int',
) -> InlineKeyboardMarkup:
    keyboard = []
    if start_end_mode == 'start':
        start_end_caption = 'Начало 🖋 / Конец'
    elif start_end_mode == 'end':
        start_end_caption = 'Начало / Конец 🖋 '

    if int_frac_mode == 'int':
        int_frac_caption = '1 🖋 / 0.1'
    elif int_frac_mode == 'frac':
        int_frac_caption = '1 / 0.1 🖋 '

    # sw_m = switch start/end mode
    # sw_i = switch integer/fractional mode
    keyboard.extend([[(start_end_caption, 'sw_m'), (int_frac_caption, 'sw_i')]])

    if int_frac_mode == 'int':
        keyboard.extend([
            [('+1', '1'), ('+2', '2'), ('+5', '5'), ('+10', '10'), ('+30', '30')],
            [('-1', '-1'), ('-2', '-2'), ('-5', '-5'), ('-10', '-10'), ('-30', '-30')]
        ])
    elif int_frac_mode == 'frac':
        keyboard.extend([
            [('+0.1', '0.1'), ('+0.2', '0.2'), ('+0.5', '0.5')],
            [('-0.1', '-0.1'), ('-0.2', '-0.2'), ('-0.5', '-0.5')]
        ])
    keyboard.extend([
        [('Предпросмотр', 'preview')],
        [('Видео', 'video'), ('Аудио', 'audio')]
    ])

    return InlineKeyboardMarkup(
        row_width=1,
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text,
                    callback_data=f'{user_id} {request.youtube_id} {round(request.start, 1)} {round(request.end, 1)} {start_end_mode} {int_frac_mode} {action}',
                )
                for text, action in row
            ]
            for row in keyboard
        ],
    )


@dispatcher.inline_handler()
async def inline_query(inline_query: InlineQuery) -> None:
    try:
        query = inline_query.query
        logger.info(f"Inline query: {query}")

        try:
            request = first_some([
                match_request(query),
                match_request(query + ' 10'),
                match_request(query + ' 0 10'),
            ])
        except ValueError:
            await bot.answer_inline_query(inline_query.id, [])
            return

        if request is None:
            await bot.answer_inline_query(inline_query.id, [])
            return

        r = requests.get("https://i.ytimg.com/vi/{id}/mqdefault.jpg".format(id=request.youtube_id), timeout=10)
        r.raise_for_status()
        thumbnail_file = BytesIO(r.content)
        thumbnail_mes = await bot.send_photo(BOT_CHANNEL_ID, thumbnail_file)

        results = [
            InlineQueryResultCachedPhoto(
                id=str(uuid4()),
                photo_file_id=thumbnail_mes.photo[-1].file_id,
                reply_markup=make_inline_keyboard(inline_query.from_user.id, request),
                caption=request_to_query(request),
            ),
        ]
        success = await bot.answer_inline_query(inline_query.id, results)
        logger.info(f"Sent answer: inline_query.id = {inline_query.id}, results = {results}, success = {success}")
    except Exception as e:
        logger.exception("a")


@dispatcher.callback_query_handler(lambda callback_query: True)
async def inline_kb_answer_callback_handler(callback_query: types.CallbackQuery):
    try:
        user_id, youtube_id, start, end, start_end_mode, int_frac_mode, action = callback_query.data.split()

        if callback_query.from_user.id != int(user_id):
            await callback_query.answer(text='You shall not press!')
            return

        await callback_query.answer()

        request = Request(youtube_id=youtube_id, start=float(start), end=float(end))

        if action in ['video', 'audio']:
            await bot.edit_message_caption(
                inline_message_id=callback_query.inline_message_id,
                reply_markup=InlineKeyboardMarkup(
                    row_width=1,
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                'Загружаем...',
                                url=request_to_start_timestamp_url(request),
                            )
                        ]
                    ],
                ),
                caption=request_to_start_timestamp_url(request),
            )

        if action in ['video', 'audio', 'preview']:
            try:
                downloaded_file = download_file(request, action)
            except YoutubeDLError as e:
                await bot.edit_message_caption(
                    inline_message_id=callback_query.inline_message_id,
                    reply_markup=InlineKeyboardMarkup(
                        row_width=1,
                        inline_keyboard=[
                            [
                                types.InlineKeyboardButton(
                                    "Error",
                                    url=request_to_start_timestamp_url(request),
                                )
                            ]
                        ],
                    ),
                    caption=request_to_start_timestamp_url(request) + "\n\n" + str(e),
                )
                raise

        if action == 'video':
            video_mes = await bot.send_video(BOT_CHANNEL_ID, downloaded_file)
            await bot.edit_message_media(
                inline_message_id=callback_query.inline_message_id,
                media=InputMediaVideo(
                    video_mes.video.file_id,
                    caption=request_to_start_timestamp_url(request)
                )
            )
        elif action == 'audio':
            audio_mes = await bot.send_audio(BOT_CHANNEL_ID, downloaded_file)
            await bot.edit_message_media(
                inline_message_id=callback_query.inline_message_id,
                media=InputMediaAudio(
                    audio_mes.audio.file_id,
                    caption=request_to_start_timestamp_url(request)
                ),
            )
        elif action == 'preview':
            video_mes = await bot.send_video(BOT_CHANNEL_ID, downloaded_file)
            await bot.edit_message_media(
                inline_message_id=callback_query.inline_message_id,
                media=InputMediaVideo(
                    video_mes.video.file_id,
                    caption=request_to_query(request),
                ),
                reply_markup=make_inline_keyboard(callback_query.from_user.id, request, start_end_mode, int_frac_mode),
            )
        elif action == 'sw_m':
            start_end_mode = 'end' if start_end_mode == 'start' else 'start'
            await bot.edit_message_reply_markup(
                inline_message_id=callback_query.inline_message_id,
                reply_markup=make_inline_keyboard(callback_query.from_user.id, request, start_end_mode, int_frac_mode)
            )
        elif action == 'sw_i':
            int_frac_mode = 'frac' if int_frac_mode == 'int' else 'int'
            await bot.edit_message_reply_markup(
                inline_message_id=callback_query.inline_message_id,
                reply_markup=make_inline_keyboard(callback_query.from_user.id, request, start_end_mode, int_frac_mode)
            )
        else:

            delta = float(action)
            old_start, old_end = (request.start, request.end)
            if start_end_mode == 'end':
                request.end += delta
                request.end = max(request.start, request.end)
                request.end = round(request.end, 1)
            elif start_end_mode == 'start':
                request.start += delta
                request.start = max(request.start, 0)
                request.start = min(request.start, request.end)
                request.start = round(request.start, 1)

            if old_start == request.start and old_end == request.end:
                return

            await bot.edit_message_caption(
                inline_message_id=callback_query.inline_message_id,
                reply_markup=make_inline_keyboard(callback_query.from_user.id, request, start_end_mode, int_frac_mode),
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
