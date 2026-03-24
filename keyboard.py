import asyncio
import logging
import sys
from aiogram import Dispatcher, Bot, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton
from aiogram.filters import CommandStart,Command
from aiogram.utils.keyboard import InlineKeyboardBuilder



TOKEN = "8663353553:AAHYwIdG5IyKPzgZrux_rAUV7JCHKKUUu-w"
bot = Bot(token=TOKEN)
dp = Dispatcher()


MaxsumaningReplyKeyboardlar = ReplyKeyboardMarkup(
    keyboard= [
        [KeyboardButton(text="about"),KeyboardButton(text="menu"),KeyboardButton(text="Muqaddas")],
        [KeyboardButton(text="sozlamalar"),KeyboardButton(text="MirSaid")],
        [KeyboardButton(text="Maxsuma"),KeyboardButton(text="Muslima")]
    ],
    resize_keyboard=True
)

keyword_replay2=ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="nima di"),KeyboardButton(text="Maxsuma")],
        [KeyboardButton(text="Muqaddas")]
    ],
    resize_keyboard=True
)

@dp.message(Command("keyboard_Maxsuma"))
async def birinchi_tugmalar_handler(message:Message):
    await message.answer(text="tugmalarni top",reply_markup=keyword_replay2)


@dp.message(Command("keyboard"))
async def reply_markub_handler(message:Message):
    await message.answer(text="tugmalarni tanlang", reply_markup=MaxsumaningReplyKeyboardlar)


def get_inline_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="LAVASH",callback_data="lavash")
    builder.button(text="CLUP",callback_data="klap")
    builder.button(text="BURGER",callback_data="burger")
    builder.adjust(2)
    return builder.as_markup()

@dp.message(Command("menu"))
async def menu_handler(message:Message):
    await message.answer(text="kerakli ovqatni tanlang🌮", reply_markup=get_inline_keyboard())


@dp.callback_query(F.data == "lavash")
async def product_handler(calback :CallbackQuery):
    # await calback.answer(text="o'tdi",show_alert=True)
    await calback.message.answer("Lavash buyurtma qilindi")

@dp.message(F.text == "button")
async def send_colored_keyboard(message: Message):
    # Create the buttons with specific styles
    button_success = KeyboardButton(text="Success", style="success")
    button_danger = KeyboardButton(text="Danger", style="danger")
    button_primary = KeyboardButton(text="Primary", style="primary")

    # Create the reply keyboard markup
    # Note: Telegram will only show the color for the supported styles ('danger', 'success', 'primary')
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[button_success, button_danger, button_primary]],
        resize_keyboard=True # Optional: resizes the keyboard to fit the number of buttons
    )

    await message.answer("Choose a button:", reply_markup=keyboard)


@dp.message(F.text == "inline_buttons")
async def inline_collor_button(message:Message):
    keyboards = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="bu inline keyboard",callback_data="hello",)]
        ]
    )
    await message.answer(text="inlinelar",reply_markup=keyboards)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("Bot ishga tushdi")
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
