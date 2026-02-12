# bot.py - ПОЛНЫЙ БОТ ДЛЯ RAILWAY (BEGINNER VERSION)
import asyncio
import os
import json
import csv
import re
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, FSInputFile, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

# Загружаем токен
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не найден!")
    exit()

TEACHER_ID = 156811764
TEST_TIMEOUT = 1800

# Загружаем вопросы
try:
    from full_questions import questions
    print(f"✅ Загружено {len(questions)} вопросов")
except ImportError:
    print("❌ Ошибка: файл full_questions.py не найден")
    questions = []

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилища
user_sessions = {}
user_timers = {}
waiting_for_open_answer = {}
user_contact_info = {}
user_form_step = {}
timer_messages = {}

# ========== INLINE-КНОПКА START TEST ==========
def get_start_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="🚀 START TEST / НАЧАТЬ ТЕСТ",
        callback_data="start_test_after_reg"
    ))
    return builder.as_markup()

# ========== КОМАНДА START ==========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    if user_id in user_form_step:
        del user_form_step[user_id]
    if user_id in waiting_for_open_answer:
        del waiting_for_open_answer[user_id]
    
    start_text = """🇬🇧 <b>ENGLISH LEVEL TEST</b>

📊 <b>Questions (вопросов):</b> 46
⏰ <b>Time (время):</b> 30 minutes
🎯 <b>Maximum score:</b> 67 баллов

<b>Key pre-test information (Как проходит тест)</b>

1. Choose the best option or complete the gap.
2. The test is taken without dictionaries or internet.
3. Skip difficult questions.
4. You have 30 minutes.

🔍 <b>Let's begin!</b>"""
    
    await message.answer(start_text, parse_mode="HTML")
    
    user_form_step[user_id] = 'name'
    
    await message.answer(
        "📝 <b>Please provide your information:</b>\n\n"
        "1. <b>Your name and surname</b> (Ваши имя и фамилия)",
        parse_mode="HTML"
    )
    print(f"✅ User {user_id} started registration")

# ========== КОМАНДА HELP ==========
@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📋 <b>COMMANDS / КОМАНДЫ</b>\n\n"
        "🔹 /start - начать регистрацию и тест\n"
        "🔹 /time - проверить оставшееся время\n"
        "🔹 /cancel - отменить текущий тест\n"
        "🔹 /help - показать это сообщение\n\n"
        "⏱️ <b>Время:</b> 30 минут\n"
        "📊 <b>Вопросов:</b> 46\n"
        "🏆 <b>Максимум:</b> 67 баллов"
    )
    await message.answer(help_text, parse_mode="HTML")
    print(f"ℹ️ Help показан пользователю {message.from_user.id}")

# ========== КОМАНДА TIME ==========
@dp.message(Command("time"))
async def cmd_time(message: Message):
    user_id = message.from_user.id
    if user_id in user_sessions:
        session = user_sessions[user_id]
        elapsed = datetime.now() - session['start_time']
        remaining = TEST_TIMEOUT - elapsed.total_seconds()
        
        if remaining > 0:
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            await show_timer(user_id, force_show=True)
        else:
            await message.answer("⏰ <b>Time's up!</b>", parse_mode="HTML")
    else:
        await message.answer("No active test. Start with /start")

# ========== КОМАНДА CANCEL ==========
@dp.message(Command("cancel"))
async def cmd_cancel(message: Message):
    user_id = message.from_user.id
    if user_id in user_sessions:
        if user_id in user_timers:
            user_timers[user_id].cancel()
            del user_timers[user_id]
        
        del user_sessions[user_id]
        if user_id in waiting_for_open_answer:
            del waiting_for_open_answer[user_id]
        if user_id in timer_messages:
            try:
                await bot.delete_message(user_id, timer_messages[user_id])
            except:
                pass
            del timer_messages[user_id]
        
        await message.answer("❌ <b>Test cancelled.</b>", parse_mode="HTML")
        print(f"❌ Тест отменён пользователем {user_id}")
    else:
        await message.answer("No active test found.")

# ========== КОМАНДА RESULTS ==========
@dp.message(Command("results"))
async def cmd_results(message: Message):
    user_id = message.from_user.id
    
    if user_id != TEACHER_ID:
        await message.answer("⛔ <b>Access denied.</b> This command is for teacher only.", parse_mode="HTML")
        return
    
    try:
        if os.path.exists('detailed_answers.json'):
            with open('detailed_answers.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if data:
                stats_text = f"👩‍🏫 <b>TEACHER DASHBOARD</b>\n\n"
                stats_text += f"📊 <b>Всего тестов:</b> {len(data)}\n\n"
                stats_text += f"📋 <b>Все студенты:</b>\n"
                
                for i, test in enumerate(data, 1):
                    name = test.get('name', f'Student {i}')
                    score = test.get('score', 0)
                    max_score = 67
                    percentage = test.get('percentage', 0)
                    level = test.get('level', 'Unknown')
                    
                    stats_text += f"{i}. <b>{name}</b> - {score}/{max_score} ({percentage:.1f}%) - {level}\n"
                
                await message.answer(stats_text, parse_mode="HTML")
                
                builder = InlineKeyboardBuilder()
                
                for i, test in enumerate(data):
                    name = test.get('name', f'Student {i+1}')
                    score = test.get('score', 0)
                    max_score = 67
                    
                    button_text = f"{i+1}. {name} - {score}/{max_score}"
                    
                    if len(button_text) > 40:
                        short_name = name[:15] + "..." if len(name) > 15 else name
                        button_text = f"{i+1}. {short_name} - {score}/{max_score}"
                    
                    builder.add(InlineKeyboardButton(
                        text=button_text,
                        callback_data=f"view_details_{i}"
                    ))
                
                builder.adjust(1)
                
                await message.answer(
                    "📝 <b>Нажми на ученика для детального отчета:</b>",
                    parse_mode="HTML",
                    reply_markup=builder.as_markup()
                )
                
                if os.path.exists('results.csv'):
                    csv_file = FSInputFile('results.csv')
                    await message.answer_document(csv_file, caption="📊 CSV файл со всеми результатами")
                
            else:
                await message.answer("📭 <b>Нет данных о тестах.</b>", parse_mode="HTML")
        else:
            await message.answer("📭 <b>Файл с результатами не найден.</b>", parse_mode="HTML")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
        print(f"❌ Ошибка в /results: {e}")

# ========== ОБРАБОТКА СООБЩЕНИЙ ==========
@dp.message()
async def process_all_messages(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    if user_id in user_form_step:
        await process_registration_form(user_id, text, message)
        return
    
    if user_id in waiting_for_open_answer:
        await process_open_answer(user_id, text)
        return
    
    if text:
        await message.answer("Use /start to begin")

# ========== ФУНКЦИИ ПРОВЕРКИ ==========
def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def is_valid_phone(phone):
    digits = re.sub(r'\D', '', phone)
    return len(digits) >= 10

# ========== РЕГИСТРАЦИЯ ==========
async def process_registration_form(user_id, text, message):
    step = user_form_step[user_id]
    
    if step == 'name':
        if len(text) > 1:
            user_contact_info[user_id] = {'name': text}
            user_form_step[user_id] = 'email'
            await message.answer(
                "✅ <b>Name saved!</b>\n\n"
                "2. <b>Your email</b> (Ваша электронная почта)\n"
                "<i>Please enter a valid email address (e.g., example@gmail.com)</i>",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ <b>Please enter your full name (at least 2 characters).</b>", parse_mode="HTML")
    
    elif step == 'email':
        if is_valid_email(text):
            user_contact_info[user_id]['email'] = text
            user_form_step[user_id] = 'phone'
            await message.answer(
                "✅ <b>Email saved!</b>\n\n"
                "3. <b>Your phone number to get the level summary</b>\n"
                "Ваш номер телефона для получения комментариев по уровню\n"
                "<i>Please enter a valid phone number (e.g., +7 999 123-45-67 or 89991234567)</i>",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ <b>Invalid email format!</b>\n\n"
                "Please enter a valid email address:\n"
                "• Must contain @ symbol\n"
                "• Must have a domain (e.g., gmail.com, yandex.ru)\n"
                "• Example: example@gmail.com\n\n"
                "<b>Enter your email again:</b>",
                parse_mode="HTML"
            )
    
    elif step == 'phone':
        if is_valid_phone(text):
            user_contact_info[user_id]['phone'] = text
            user_form_step[user_id] = 'form_age'
            await message.answer(
                "✅ <b>Phone saved!</b>\n\n"
                "4. <b>For pupils: your form and age</b>\n"
                "Для школьников: ваш класс и возраст\n"
                "<i>For adults: enter your occupation or 'adult'</i>",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ <b>Invalid phone number!</b>\n\n"
                "Please enter a valid phone number:\n"
                "• Must contain at least 10 digits\n"
                "• Can include +, spaces, hyphens\n"
                "• Examples: +7 999 123-45-67, 89991234567, 9991234567\n\n"
                "<b>Enter your phone number again:</b>",
                parse_mode="HTML"
            )
    
    elif step == 'form_age':
        if len(text) > 0:
            user_contact_info[user_id]['form_age'] = text
            user_contact_info[user_id]['username'] = message.from_user.username or ''
            user_contact_info[user_id]['first_name'] = message.from_user.first_name or ''
            
            del user_form_step[user_id]
            
            await message.answer(
                "✅ <b>Registration completed!</b>\n\n"
                "Click the button below to start the test:",
                parse_mode="HTML",
                reply_markup=get_start_keyboard()
            )
        else:
            await message.answer("❌ <b>Please enter your form/age or occupation.</b>", parse_mode="HTML")

# ========== ОТПРАВКА ОТЧЕТА ПРЕПОДАВАТЕЛЮ ==========
async def send_quick_report_to_teacher(session, total_score, max_score, percentage, level, wrong_answers_count):
    try:
        student_name = session.get('name', 'Unknown')
        student_email = session.get('email', 'No email')
        
        report_msg = f"""🆕 <b>НОВОЕ ЗАПОЛНЕНИЕ ТЕСТА</b>

👤 <b>Студент:</b> {student_name}
📧 <b>Email:</b> {student_email}
📱 <b>Телефон:</b> {session.get('phone', 'No phone')}
🎓 <b>Класс/Возраст:</b> {session.get('form_age', 'Not specified')}

🏆 <b>Результаты:</b>
• Баллы: {total_score}/{max_score}
• Процент: {percentage:.1f}%
• Уровень: {level}
• Неверных ответов: {wrong_answers_count}
• Вопросов отвечено: {len(session.get('all_answers', []))}/46
"""
        await bot.send_message(TEACHER_ID, report_msg, parse_mode="HTML")
        
        wrong_answers = session.get('wrong_answers', [])
        if wrong_answers:
            await bot.send_message(TEACHER_ID, f"❌ <b>ВСЕ НЕВЕРНЫЕ ОТВЕТЫ ({len(wrong_answers)}):</b>", parse_mode="HTML")
            
            for wrong in wrong_answers:
                q_num = wrong.get('question_number', '?')
                q_text = wrong.get('question_text', '')
                user_ans = wrong.get('user_answer', 'N/A')
                correct_ans = wrong.get('correct_answer', 'N/A')
                
                if isinstance(correct_ans, list):
                    correct_ans = ', '.join(correct_ans)
                
                if len(q_text) > 100:
                    q_text = q_text[:97] + "..."
                if len(correct_ans) > 100:
                    correct_ans = correct_ans[:97] + "..."
                
                wrong_msg = f"<b>{q_num}.</b> {q_text}\n"
                wrong_msg += f"✗ Студент: <i>{user_ans}</i>\n"
                wrong_msg += f"✓ Правильно: {correct_ans}\n"
                
                await bot.send_message(TEACHER_ID, wrong_msg, parse_mode="HTML")
                await asyncio.sleep(0.2)
        
        print(f"✅ Отправлен полный отчет преподавателю: {student_name}")
        
    except Exception as e:
        print(f"❌ Ошибка отправки отчета преподавателю: {e}")

# ========== ТАЙМЕР ==========
async def show_timer(user_id, force_show=False):
    if user_id not in user_sessions:
        return
    
    session = user_sessions[user_id]
    elapsed = datetime.now() - session['start_time']
    remaining = TEST_TIMEOUT - elapsed.total_seconds()
    
    if remaining <= 0:
        return
    
    minutes = int(remaining // 60)
    seconds = int(remaining % 60)
    
    progress_total = 20
    progress_passed = int((TEST_TIMEOUT - remaining) / TEST_TIMEOUT * progress_total)
    progress_bar = "🟩" * progress_passed + "⬜" * (progress_total - progress_passed)
    
    current_q = session["current_question"]
    total_q = len(questions)
    
    timer_text = (
        f"⏳ <b>TIMER: {minutes:02d}:{seconds:02d}</b>\n"
        f"{progress_bar}\n"
        f"📊 Questions: {current_q}/{total_q}\n"
        f"⏰ Time left: {minutes}m {seconds}s"
    )
    
    should_show = force_show or (current_q > 0 and current_q % 5 == 0)
    
    if should_show:
        if user_id in timer_messages:
            try:
                await bot.delete_message(user_id, timer_messages[user_id])
            except:
                pass
        
        msg = await bot.send_message(user_id, timer_text, parse_mode="HTML")
        timer_messages[user_id] = msg.message_id

def truncate_button_text(text, max_length=64):
    if not text or str(text).strip() == 'nan':
        return "No text"
    
    text = str(text).strip()
    if len(text) <= max_length:
        return text
    
    return text[:max_length-3] + "..."

# ========== СТАРТ ТЕСТА ==========
@dp.callback_query(lambda c: c.data == "start_test_after_reg")
async def start_test_from_button(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    await callback.answer("Starting test...")
    
    if user_id in user_sessions:
        await callback.message.answer("⚠️ You already have an active test! Use /time or /cancel")
        return
    
    if user_id not in user_contact_info:
        await callback.message.answer("❌ Please complete registration first with /start")
        return
    
    if user_id in user_form_step:
        del user_form_step[user_id]
    if user_id in waiting_for_open_answer:
        del waiting_for_open_answer[user_id]
    
    contact_info = user_contact_info[user_id]
    
    user_sessions[user_id] = {
        "start_time": datetime.now(),
        "current_question": 0,
        "answers": {},
        "score": 0,
        "completed": False,
        "user_id": user_id,
        "username": contact_info.get('username', ''),
        "first_name": contact_info.get('first_name', ''),
        "name": contact_info.get('name', ''),
        "email": contact_info.get('email', ''),
        "phone": contact_info.get('phone', ''),
        "form_age": contact_info.get('form_age', ''),
        "all_answers": [],
        "wrong_answers": []
    }
    
    timer_task = asyncio.create_task(test_timer(user_id))
    user_timers[user_id] = timer_task
    
    await show_timer(user_id, force_show=True)
    
    await callback.message.answer(
        "🎯 <b>TEST STARTED!</b>\n\n"
        "You have <b>30 minutes</b> to complete the test.\n"
        "Answer questions in order.\n"
        "Good luck! 🍀",
        parse_mode="HTML"
    )
    
    await ask_question(user_id)

# ========== ПОКАЗ ВОПРОСА ==========
async def ask_question(user_id):
    if user_id not in user_sessions:
        return
    
    session = user_sessions[user_id]
    q_index = session["current_question"]
    
    if q_index >= len(questions):
        await finish_test(user_id)
        return
    
    question = questions[q_index]
    
    if question['type'] == 'choice':
        if q_index in [44, 45]:  # Вопросы 45 и 46 с буквами
            builder = InlineKeyboardBuilder()
            
            for i in range(len(question['options'])):
                builder.add(InlineKeyboardButton(
                    text=f"{question['options'][i]}",
                    callback_data=f"ans_{q_index}_{i}"
                ))
            
            builder.add(InlineKeyboardButton(
                text="⏭ Skip (пропустить)",
                callback_data=f"skip_{q_index}"
            ))
            
            builder.adjust(4, 1)
            
            await bot.send_message(
                user_id,
                f"<b>Question {q_index+1}/{len(questions)}</b> ({question['points']} point{'s' if question['points'] > 1 else ''})\n\n"
                f"{question['text']}",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
        else:
            builder = InlineKeyboardBuilder()
            
            for i, option in enumerate(question['options']):
                if option and str(option).strip() and str(option).strip() != 'nan':
                    button_text = truncate_button_text(str(option).strip())
                    
                    builder.add(InlineKeyboardButton(
                        text=button_text,
                        callback_data=f"ans_{q_index}_{i}"
                    ))
            
            builder.add(InlineKeyboardButton(
                text="⏭ Skip (пропустить)",
                callback_data=f"skip_{q_index}"
            ))
            
            builder.adjust(1)
            
            await bot.send_message(
                user_id,
                f"<b>Question {q_index+1}/{len(questions)}</b> ({question['points']} point{'s' if question['points'] > 1 else ''})\n\n"
                f"{question['text']}",
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
    else:
        waiting_for_open_answer[user_id] = q_index
        
        await bot.send_message(
            user_id,
            f"<b>Question {q_index+1}/{len(questions)}</b> ({question['points']} point{'s' if question['points'] > 1 else ''})\n\n"
            f"{question['text']}\n\n"
            f"<i>Type your answer (1-3 words)</i>",
            parse_mode="HTML"
        )

# ========== ОБРАБОТКА ОТВЕТОВ ==========
@dp.callback_query(lambda c: c.data.startswith('ans_') or c.data.startswith('skip_'))
async def process_answer(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in user_sessions:
        await callback.answer("")
        return
    
    session = user_sessions[user_id]
    q_index = session["current_question"]
    
    if callback.data.startswith('skip_'):
        await callback.answer("")
        
        question = questions[q_index]
        answer_data = {
            'question_number': q_index + 1,
            'question_text': question['text'],
            'user_answer': 'SKIPPED',
            'correct_answer': question.get('correct', '') if question['type'] == 'choice' else question.get('correct_answers', []),
            'is_correct': False,
            'points': question['points'],
            'timestamp': datetime.now().isoformat(),
            'question_type': question['type']
        }
        
        session["all_answers"].append(answer_data)
        session["answers"][q_index] = {'is_correct': False, 'user_answer': 'SKIPPED'}
        
        session["current_question"] += 1
        if user_id in waiting_for_open_answer:
            del waiting_for_open_answer[user_id]
        
        await show_timer(user_id)
        await ask_question(user_id)
        return
    
    if callback.data.startswith('ans_'):
        parts = callback.data.split('_')
        question_idx = int(parts[1])
        answer_idx = int(parts[2])
        
        if question_idx != q_index:
            await callback.answer("")
            return
        
        question = questions[question_idx]
        correct_answer = question['correct']
        correct_idx = ord(correct_answer) - ord('A')
        
        user_answer_text = question['options'][answer_idx]
        correct_answer_text = question['options'][correct_idx]
        
        is_correct = answer_idx == correct_idx
        if is_correct:
            session["score"] += question['points']
        
        answer_data = {
            'question_number': question_idx + 1,
            'question_text': question['text'],
            'user_answer': user_answer_text,
            'correct_answer': correct_answer_text,
            'is_correct': is_correct,
            'points': question['points'],
            'timestamp': datetime.now().isoformat(),
            'question_type': 'choice'
        }
        
        session["all_answers"].append(answer_data)
        
        if not is_correct:
            wrong_answer = {
                'question_number': question_idx + 1,
                'question_text': question['text'],
                'user_answer': user_answer_text,
                'correct_answer': correct_answer_text
            }
            session["wrong_answers"].append(wrong_answer)
        
        await callback.answer("")
        
        session["current_question"] += 1
        if user_id in waiting_for_open_answer:
            del waiting_for_open_answer[user_id]
        
        await show_timer(user_id)
        await ask_question(user_id)

# ========== ОБРАБОТКА ОТКРЫТЫХ ОТВЕТОВ ==========
async def process_open_answer(user_id, text):
    q_index = waiting_for_open_answer[user_id]
    
    if user_id not in user_sessions:
        return
    
    session = user_sessions[user_id]
    
    if q_index != session["current_question"]:
        return
    
    question = questions[q_index]
    
    if question['type'] != 'open':
        return
    
    user_answer = text.strip()
    correct_answers = question.get('correct_answers', [])
    
    is_correct = False
    matched_correct = None
    for correct in correct_answers:
        if user_answer.lower() == correct.lower():
            is_correct = True
            matched_correct = correct
            break
    
    if is_correct:
        session["score"] += question['points']
    
    answer_data = {
        'question_number': q_index + 1,
        'question_text': question['text'],
        'user_answer': user_answer,
        'correct_answer': correct_answers,
        'is_correct': is_correct,
        'points': question['points'],
        'timestamp': datetime.now().isoformat(),
        'question_type': 'open',
        'matched_correct': matched_correct if is_correct else None
    }
    
    session["all_answers"].append(answer_data)
    
    if not is_correct:
        wrong_answer = {
            'question_number': q_index + 1,
            'question_text': question['text'],
            'user_answer': user_answer,
            'correct_answer': correct_answers
        }
        session["wrong_answers"].append(wrong_answer)
    
    session["current_question"] += 1
    del waiting_for_open_answer[user_id]
    
    await show_timer(user_id)
    await ask_question(user_id)

# ========== ОБРАБОТКА КНОПОК ВЫБОРА УЧЕНИКА ==========
@dp.callback_query(lambda c: c.data.startswith('view_details_'))
async def view_student_details(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id != TEACHER_ID:
        await callback.answer("Access denied")
        return
    
    try:
        test_index = int(callback.data.split('_')[2])
        
        with open('detailed_answers.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 0 <= test_index < len(data):
            test_data = data[test_index]
            student_name = test_data.get('name', f'Student {test_index+1}')
            max_score = 67
            
            info_msg = f"""👨‍🎓 <b>ПОЛНЫЙ ОТЧЕТ - {student_name}</b>

📌 <b>Информация о студенте:</b>
• Имя: {student_name}
• Email: {test_data.get('email', 'Нет email')}
• Телефон: {test_data.get('phone', 'Нет телефона')}
• Класс/Возраст: {test_data.get('form_age', 'Не указано')}

🏆 <b>Результаты:</b>
• Баллы: {test_data.get('score', 0)}/{max_score}
• Процент: {test_data.get('percentage', 0):.1f}%
• Уровень: {test_data.get('level', 'Unknown')}
• Вопросов отвечено: {len(test_data.get('all_answers', []))}/46
• Неверных ответов: {len(test_data.get('wrong_answers', []))}
• Завершено: {'⏰ Время вышло' if test_data.get('time_up') else '✅ Да'}
"""
            await callback.message.answer(info_msg, parse_mode="HTML")
            
            all_answers = test_data.get('all_answers', [])
            if all_answers:
                await callback.message.answer(f"📝 <b>ВСЕ ОТВЕТЫ ({len(all_answers)}):</b>", parse_mode="HTML")
                
                for i in range(0, len(all_answers), 10):
                    batch = all_answers[i:i+10]
                    batch_text = ""
                    
                    for answer in batch:
                        q_num = answer.get('question_number', '?')
                        user_ans = answer.get('user_answer', 'N/A')
                        status = "✅" if answer.get('is_correct') else "❌"
                        
                        batch_text += f"<b>{q_num}.</b> {user_ans} {status}\n"
                    
                    if batch_text:
                        await callback.message.answer(batch_text, parse_mode="HTML")
                        await asyncio.sleep(0.2)
            
            wrong_answers = test_data.get('wrong_answers', [])
            if wrong_answers:
                await callback.message.answer(f"❌ <b>НЕВЕРНЫЕ ОТВЕТЫ ({len(wrong_answers)}):</b>", parse_mode="HTML")
                
                for wrong in wrong_answers:
                    q_num = wrong.get('question_number', '?')
                    q_text = wrong.get('question_text', '')
                    user_ans = wrong.get('user_answer', 'N/A')
                    correct_ans = wrong.get('correct_answer', 'N/A')
                    
                    if isinstance(correct_ans, list):
                        correct_ans = ', '.join(correct_ans)
                    
                    if len(q_text) > 80:
                        q_text = q_text[:77] + "..."
                    
                    wrong_text = f"<b>{q_num}.</b> {q_text}\n"
                    wrong_text += f"✗ Студент: <i>{user_ans}</i>\n"
                    wrong_text += f"✓ Правильно: {correct_ans}\n"
                    
                    await callback.message.answer(wrong_text, parse_mode="HTML")
                    await asyncio.sleep(0.2)
            
            await callback.answer(f"Показаны данные {student_name}")
        else:
            await callback.answer(f"Студент не найден")
            
    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)[:50]}")
        print(f"❌ Ошибка в view_student_details: {e}")

# ========== ТАЙМЕР 30 МИНУТ ==========
async def test_timer(user_id):
    await asyncio.sleep(TEST_TIMEOUT)
    
    if user_id in user_sessions and not user_sessions[user_id]['completed']:
        await bot.send_message(user_id, "⏰ <b>TIME'S UP! Test submitted.</b>", parse_mode="HTML")
        await finish_test(user_id, time_up=True)

# ========== ЗАВЕРШЕНИЕ ТЕСТА ==========
async def finish_test(user_id, time_up=False):
    if user_id not in user_sessions:
        return
    
    session = user_sessions[user_id]
    session['completed'] = True
    
    if user_id in user_timers:
        user_timers[user_id].cancel()
        del user_timers[user_id]
    
    if user_id in waiting_for_open_answer:
        del waiting_for_open_answer[user_id]
    
    if user_id in timer_messages:
        try:
            await bot.delete_message(user_id, timer_messages[user_id])
            del timer_messages[user_id]
        except:
            pass
    
    total_score = session["score"]
    max_score = 67
    percentage = (total_score / max_score * 100) if max_score > 0 else 0
    
    # Шкала уровней для начинающих
    if total_score >= 57:
        level = "Upper-Intermediate"
    elif total_score >= 40:
        level = "Intermediate"
    elif total_score >= 23:
        level = "Pre-Intermediate"
    elif total_score >= 7:
        level = "Elementary"
    else:
        level = "Starter"
    
    session["level"] = level
    session["max_score"] = max_score
    
    result_text = f"""📊 <b>TEST COMPLETED</b>

• Score: <b>{total_score}/{max_score}</b> points
• Percentage: <b>{percentage:.1f}%</b>
• Wrong answers: <b>{len(session.get('wrong_answers', []))}</b>
• Level: <b>{level}</b>
"""
    
    if time_up:
        result_text += "• Status: ⏰ Time's up\n"
    else:
        result_text += "• Status: ✅ Completed\n"
    
    await bot.send_message(user_id, result_text, parse_mode="HTML")
    
    wrong_answers = session.get("wrong_answers", [])
    if wrong_answers:
        await bot.send_message(user_id, f"📝 <b>Questions with incorrect answers ({len(wrong_answers)}):</b>", parse_mode="HTML")
        
        for i in range(0, len(wrong_answers), 3):
            batch = wrong_answers[i:i+3]
            batch_text = ""
            
            for wrong in batch:
                q_num = wrong.get('question_number', '?')
                q_text = wrong.get('question_text', '')
                
                if len(q_text) > 80:
                    q_text = q_text[:77] + "..."
                
                user_ans = wrong.get('user_answer', 'N/A')
                
                batch_text += f"<b>{q_num}.</b> {q_text}\n"
                batch_text += f"   ✗ Your answer: <i>{user_ans}</i>\n\n"
            
            if batch_text:
                await bot.send_message(user_id, batch_text, parse_mode="HTML")
                await asyncio.sleep(0.3)
    
    await save_results(session, total_score, max_score, percentage, level, time_up)
    await send_quick_report_to_teacher(session, total_score, max_score, percentage, level, len(wrong_answers))
    
    del user_sessions[user_id]

# ========== СОХРАНЕНИЕ РЕЗУЛЬТАТОВ ==========
async def save_results(session, score, max_score, percentage, level, time_up):
    try:
        csv_file = 'results.csv'
        file_exists = os.path.exists(csv_file)
        
        with open(csv_file, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            if not file_exists:
                writer.writerow([
                    'Timestamp', 'User_ID', 'Username', 'Name', 'Email', 
                    'Phone', 'Form_Age', 'Score', 'Max_Score', 'Percentage', 
                    'Level', 'Time_Up', 'Questions_Answered', 'Wrong_Answers'
                ])
            
            writer.writerow([
                datetime.now().isoformat(),
                session['user_id'],
                session.get('username', ''),
                session.get('name', ''),
                session.get('email', ''),
                session.get('phone', ''),
                session.get('form_age', ''),
                score,
                max_score,
                f"{percentage:.1f}%",
                level,
                'Yes' if time_up else 'No',
                len(session.get('all_answers', [])),
                len(session.get('wrong_answers', []))
            ])
        
        json_file = 'detailed_answers.json'
        detailed_data = {
            'timestamp': datetime.now().isoformat(),
            'user_id': session['user_id'],
            'username': session.get('username', ''),
            'name': session.get('name', ''),
            'email': session.get('email', ''),
            'phone': session.get('phone', ''),
            'form_age': session.get('form_age', ''),
            'score': score,
            'max_score': max_score,
            'percentage': percentage,
            'level': level,
            'time_up': time_up,
            'questions_answered': len(session.get('all_answers', [])),
            'wrong_answers_count': len(session.get('wrong_answers', [])),
            'all_answers': session.get('all_answers', []),
            'wrong_answers': session.get('wrong_answers', [])
        }
        
        if os.path.exists(json_file):
            with open(json_file, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
        else:
            all_data = []
        
        all_data.append(detailed_data)
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"✅ Results saved: {session.get('name')} - {score}/{max_score}")
        
    except Exception as e:
        print(f"❌ Error saving results: {e}")

# ========== ЗАПУСК БОТА ==========
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Вебхук удалён")
    
    print("=" * 60)
    print("🤖 ENGLISH TEST BOT - BEGINNER VERSION")
    print("=" * 60)
    print(f"✅ Questions: {len(questions)}")
    print(f"✅ Max score: 67")
    print(f"✅ Teacher ID: {TEACHER_ID}")
    print("=" * 60)
    print("🏆 Levels: Starter → Elementary → Pre-Int → Int → Upper Int")
    print("🎯 Бот работает 24/7 на Railway!")
    print("=" * 60)
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
