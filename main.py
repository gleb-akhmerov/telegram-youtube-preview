import asyncio
import logging
import os
from io import BytesIO
from time import time
from typing import Literal
from uuid import uuid4

import aiogram
import yt_dlp
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher, filters
from aiogram.types import InputMediaVideo, InputMediaAudio, InlineQuery, InlineQueryResultCachedPhoto, InlineKeyboardMarkup
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
    'preview': ['worst'],
    'clip': ['best', 'best[height<720]'],
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
                                 '-c:a', 'copy']
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


def download_file(request, type_: Literal['preview', 'clip', 'audio']):
    media_type = 'audio' if type_ == 'audio' else 'video'
    for format in FORMATS_BY_TYPE[type_]:
        file_url = get_file_url('https://youtu.be/' + request.youtube_id, format)
        try:
            return download_clip(file_url, request.start, request.end, media_type)
        except FFRuntimeError as e:
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

        downloaded_file = download_file(request, 'clip')
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

        downloaded_file = download_file(request, 'clip')

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


def make_inline_keyboard(user_id: int, request: Request,
                         mode: Literal['start', 'end'] = 'end') -> InlineKeyboardMarkup:
    keyboard = []
    if mode == 'start':
        keyboard.extend([[('Начало 🖋 / Конец', 'sw_m')]])  # sw_m = switch mode
    elif mode == 'end':
        keyboard.extend([[('Начало / Конец 🖋 ', 'sw_m')]])

    keyboard.extend([
        [('+0.1', '0.1'), ('+0.5', '0.5'), ('+1', '1'), ('+2', '2'), ('+5', '5'), ('+10', '10'), ('+30', '30')],
        [('-0.1', '-0.1'), ('-0.5', '-0.5'), ('-1', '-1'), ('-2', '-2'), ('-5', '-5'), ('-10', '-10'), ('-30', '-30')]])
    keyboard.extend([
        [('Предпросмотр', 'preview')],
        [('Видео', 'video'), ('Аудио', 'audio')]])

    return InlineKeyboardMarkup(
        row_width=1,
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text,
                    callback_data=f'{user_id} {request.youtube_id} {round(request.start, 1)} {round(request.end, 1)} {mode} {action}',
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
        user_id, youtube_id, start, end, edit_mode, action = callback_query.data.split()

        if callback_query.from_user.id != int(user_id):
            await callback_query.answer(text='You shall not press!')
            return

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

        if action == 'video':
            downloaded_file = download_file(request, 'clip')
            video_mes = await bot.send_video(BOT_CHANNEL_ID, downloaded_file)
            await bot.edit_message_media(
                inline_message_id=callback_query.inline_message_id,
                media=InputMediaVideo(
                    video_mes.video.file_id,
                    caption=request_to_start_timestamp_url(request)
                )
            )
        elif action == 'audio':
            downloaded_file = download_file(request, 'audio')
            audio_mes = await bot.send_audio(BOT_CHANNEL_ID, downloaded_file)
            await bot.edit_message_media(
                inline_message_id=callback_query.inline_message_id,
                media=InputMediaAudio(
                    audio_mes.audio.file_id,
                    caption=request_to_start_timestamp_url(request)
                ),
            )
        elif action == 'preview':
            downloaded_file = download_file(request, 'preview')
            video_mes = await bot.send_video(BOT_CHANNEL_ID, downloaded_file)
            await bot.edit_message_media(
                inline_message_id=callback_query.inline_message_id,
                media=InputMediaVideo(
                    video_mes.video.file_id,
                    caption=request_to_query(request),
                ),
                reply_markup=make_inline_keyboard(callback_query.from_user.id, request, edit_mode),
            )
        elif action == 'sw_m':
            edit_mode = 'end' if edit_mode == 'start' else 'start'
            await bot.edit_message_reply_markup(
                inline_message_id=callback_query.inline_message_id,
                reply_markup=make_inline_keyboard(callback_query.from_user.id, request, edit_mode)
            )
        else:

            delta = float(action)
            old_start, old_end = (request.start, request.end)
            if edit_mode == 'end':
                request.end += delta
                request.end = max(request.start, request.end)
            elif edit_mode == 'start':
                request.start += delta
                request.start = max(request.start, 0)
                request.start = min(request.start, request.end)

            if old_start == request.start and old_end == request.end:
                await callback_query.answer()
                return

            await bot.edit_message_caption(
                inline_message_id=callback_query.inline_message_id,
                reply_markup=make_inline_keyboard(callback_query.from_user.id, request, edit_mode),
                caption=request_to_query(request),
            )
        await callback_query.answer()
    except Exception as e:
        logger.exception("a")


@dispatcher.errors_handler()
async def error_handler(update: types.Update, exception: Exception):
    logger.warning('Update "%s" caused error "%s"', update, exception)


last_messages = TTLCache(maxsize=1000, ttl=86400)

if __name__ == '__main__':
    executor.start_polling(dispatcher, loop=loop)
