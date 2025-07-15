import random
import string
import time
from typing import Literal
from playwright.sync_api import Locator, Page

from loguru import logger

# === Параметры по умолчанию (для режима "manual") ===

# --- Базовая скорость и стиль набора ---
KEY_PRESS_DELAY_RANGE = (0.04, 0.12)  # Диапазон задержки (в сек) между нажатиями клавиш. Основа скорости печати.
# Уменьшение: более быстрая печать. Увеличение: более медленная, "вдумчивая" печать.

# --- "Очеловечивание" процесса набора ---
MISTAKE_PROBABILITY = 0.1  # Вероятность (0.0 до 1.0) сделать опечатку на каждый символ.
# 0.0 отключает ошибки. 0.03 = 3% шанс на ошибку.
MISTAKE_CORRECTION_DELAY_RANGE = (
0.1, 0.4)  # Пауза (в сек) после совершения ошибки, перед нажатием Backspace.
BACKSPACE_DELAY_RANGE = (0.05, 0.15)  # Пауза (в сек) ПОСЛЕ нажатия Backspace, перед набором правильного символа.

# --- Паузы во время набора ---
WORD_PAUSE_PROBABILITY = 0.10  # Вероятность (0.0 до 1.0) сделать короткую паузу после набора пробела (между словами).
WORD_PAUSE_DURATION_RANGE = (0.1, 0.5)  # Длительность (в сек) короткой паузы между словами.
LONG_PAUSE_PROBABILITY = 0.01  # Вероятность (0.0 до 1.0) сделать длинную "задумчивую" паузу во время набора.
LONG_PAUSE_DURATION_RANGE = (0.8, 2.5)  # Длительность (в сек) длинной паузы.

# --- Chunking ---
# Имитирует набор нескольких символов подряд и короткую паузу перед следующей пачкой.
ENABLE_CHUNK_TYPING = True  # True: использовать набор "пачками" (чанки). False: монотонный набор по 1 символу.
CHUNK_SIZE_RANGE = (2, 7)  # Диапазон (min, max) количества символов в одном чанке.
CHUNK_DELAY_RANGE = (0.08, 0.25)  # Пауза (в сек) между чанками символов.

# --- Предустановленные профили скорости для набора текста (можете изменить под себя) ---
TYPING_PROFILES = {
    "fast": {
        "KEY_PRESS_DELAY_RANGE": (0.02, 0.06),
        "MISTAKE_PROBABILITY": 0.01,
        "MISTAKE_CORRECTION_DELAY_RANGE": (0.05, 0.15),
        "BACKSPACE_DELAY_RANGE": (0.03, 0.08),
        "WORD_PAUSE_PROBABILITY": 0.05,
        "WORD_PAUSE_DURATION_RANGE": (0.05, 0.2),
        "LONG_PAUSE_PROBABILITY": 0.005,
        "LONG_PAUSE_DURATION_RANGE": (0.4, 1.0),
        "ENABLE_CHUNK_TYPING": True,
        "CHUNK_SIZE_RANGE": (4, 10),
        "CHUNK_DELAY_RANGE": (0.06, 0.15),
    },
    "medium": {
        "KEY_PRESS_DELAY_RANGE": (0.05, 0.12),
        "MISTAKE_PROBABILITY": 0.03,
        "MISTAKE_CORRECTION_DELAY_RANGE": (0.1, 0.4),
        "BACKSPACE_DELAY_RANGE": (0.05, 0.15),
        "WORD_PAUSE_PROBABILITY": 0.10,
        "WORD_PAUSE_DURATION_RANGE": (0.1, 0.5),
        "LONG_PAUSE_PROBABILITY": 0.01,
        "LONG_PAUSE_DURATION_RANGE": (0.8, 2.5),
        "ENABLE_CHUNK_TYPING": True,
        "CHUNK_SIZE_RANGE": (2, 7),
        "CHUNK_DELAY_RANGE": (0.08, 0.25),
    },
    "slow": {
        "KEY_PRESS_DELAY_RANGE": (0.1, 0.25),
        "MISTAKE_PROBABILITY": 0.08,
        "MISTAKE_CORRECTION_DELAY_RANGE": (0.3, 0.8),
        "BACKSPACE_DELAY_RANGE": (0.1, 0.3),
        "WORD_PAUSE_PROBABILITY": 0.18,
        "WORD_PAUSE_DURATION_RANGE": (0.4, 1.2),
        "LONG_PAUSE_PROBABILITY": 0.03,
        "LONG_PAUSE_DURATION_RANGE": (1.5, 4.0),
        "ENABLE_CHUNK_TYPING": False,  # Медленный набор обычно посимвольный
        "CHUNK_SIZE_RANGE": (1, 1),  # Не используется, если ENABLE_CHUNK_TYPING = False
        "CHUNK_DELAY_RANGE": (0.0, 0.0),  # Не используется
    }
}


def human_like_type(
        locator: Locator,
        text_to_type: str,
        speed_mode: Literal["fast", "medium", "slow", "manual"] = "medium",
        clear_before: bool = True,
        focus_with_click: bool = True
) -> bool:
    page: Page = locator.page
    logger.info(f"Typing '{text_to_type[:30]}...' into locator. Mode: {speed_mode}")

    if speed_mode == "manual":
        logger.debug("Using 'manual' typing profile (global defaults).")
        current_params = {
            "KEY_PRESS_DELAY_RANGE": KEY_PRESS_DELAY_RANGE, "MISTAKE_PROBABILITY": MISTAKE_PROBABILITY,
            "MISTAKE_CORRECTION_DELAY_RANGE": MISTAKE_CORRECTION_DELAY_RANGE,
            "BACKSPACE_DELAY_RANGE": BACKSPACE_DELAY_RANGE,
            "WORD_PAUSE_PROBABILITY": WORD_PAUSE_PROBABILITY, "WORD_PAUSE_DURATION_RANGE": WORD_PAUSE_DURATION_RANGE,
            "LONG_PAUSE_PROBABILITY": LONG_PAUSE_PROBABILITY, "LONG_PAUSE_DURATION_RANGE": LONG_PAUSE_DURATION_RANGE,
            "ENABLE_CHUNK_TYPING": ENABLE_CHUNK_TYPING, "CHUNK_SIZE_RANGE": CHUNK_SIZE_RANGE,
            "CHUNK_DELAY_RANGE": CHUNK_DELAY_RANGE
        }
    elif speed_mode in TYPING_PROFILES:
        logger.debug(f"Using '{speed_mode}' typing profile.")
        current_params = TYPING_PROFILES[speed_mode]
    else:
        logger.warning(f"Unknown typing speed_mode '{speed_mode}'. Defaulting to 'medium'.")
        current_params = TYPING_PROFILES["medium"]

    p_key_delay = current_params["KEY_PRESS_DELAY_RANGE"]
    p_mistake_prob = current_params["MISTAKE_PROBABILITY"]
    p_mistake_delay = current_params["MISTAKE_CORRECTION_DELAY_RANGE"]
    p_backspace_delay = current_params["BACKSPACE_DELAY_RANGE"]
    p_word_pause_prob = current_params["WORD_PAUSE_PROBABILITY"]
    p_word_pause_dur = current_params["WORD_PAUSE_DURATION_RANGE"]
    p_long_pause_prob = current_params["LONG_PAUSE_PROBABILITY"]
    p_long_pause_dur = current_params["LONG_PAUSE_DURATION_RANGE"]
    p_chunk_typing = current_params["ENABLE_CHUNK_TYPING"]
    p_chunk_size = current_params["CHUNK_SIZE_RANGE"]
    p_chunk_delay = current_params["CHUNK_DELAY_RANGE"]

    try:
        locator.wait_for(state="visible", timeout=10000)

        if focus_with_click:
            locator.click()  #TODO заменить на свой "человеческий" клик
        else:
            locator.focus()

        time.sleep(random.uniform(0.12, 0.20))

        if clear_before:
            logger.trace("Clearing field before typing.")
            # Имитация Ctrl+A -> Backspace для очистки
            locator.press("Meta+A") # Для Windows Ctrl+A
            time.sleep(random.uniform(0.35, 0.95))
            locator.press("Backspace")
            time.sleep(random.uniform(0.35, 0.95))

        keyboard = page.keyboard
        text_len = len(text_to_type)
        cursor = 0

        while cursor < text_len:
            if p_chunk_typing:
                chunk_size = random.randint(*p_chunk_size)
                chunk = text_to_type[cursor: cursor + chunk_size]
            else:
                chunk = text_to_type[cursor: cursor + 1]

            for char in chunk:
                if random.random() < p_long_pause_prob:
                    pause_dur = random.uniform(*p_long_pause_dur)
                    logger.trace(f"Taking a long pause: {pause_dur:.2f}s")
                    time.sleep(pause_dur)

                if random.random() < p_mistake_prob and char.isalpha():
                    mistake_char = random.choice(string.ascii_lowercase)
                    logger.trace(f"Making a mistake: typed '{mistake_char}' instead of '{char}'")
                    keyboard.press(mistake_char)
                    time.sleep(random.uniform(*p_mistake_delay))
                    keyboard.press("Backspace")
                    time.sleep(random.uniform(*p_backspace_delay))


                keyboard.press(char)

                time.sleep(random.uniform(*p_key_delay))

                if char.isspace() and random.random() < p_word_pause_prob:
                    pause_dur = random.uniform(*p_word_pause_dur)
                    logger.trace(f"Taking a word pause: {pause_dur:.2f}s")
                    time.sleep(pause_dur)

            cursor += len(chunk)
            if p_chunk_typing and cursor < text_len:
                time.sleep(random.uniform(*p_chunk_delay))

        logger.success(f"Successfully typed text into the locator.")
        return True

    except Exception as e:
        logger.error(f"Global error in human_like_type: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
