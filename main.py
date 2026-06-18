from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import httpx
from bs4 import BeautifulSoup
import re
from datetime import datetime
from typing import List, Dict, Optional
import asyncio

app = FastAPI(title="Расписание СФ УУНиТ API")

# URL сайта с расписанием
BASE_URL = "https://edu.str.uust.ru/"

# ID группы АИС21
GROUP_ID = 16
FACULTY_ID = 7  # Факультет математики и информационных технологий


class ScheduleParser:
    """Парсер расписания с сайта"""
    
    @staticmethod
    async def fetch_page() -> str:
        """Получить HTML страницы"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(BASE_URL)
            response.raise_for_status()
            return response.text
    
    @staticmethod
    def parse_schedule(html: str, group_name: str = "АИС21") -> Dict:
        """Распарсить расписание из HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Находим блок расписания
        raspisanie = soup.find('div', class_='raspisanie')
        if not raspisanie:
            return {"error": "Расписание не найдено"}
        
        days = []
        day_blocks = raspisanie.find_all('div', class_='day')
        
        for day_block in day_blocks:
            # Получаем название дня
            day_header = day_block.find('h2', class_='date')
            if not day_header:
                continue
                
            day_name = day_header.get_text(strip=True)
            
            # Парсим уроки
            lessons = []
            lesson_items = day_block.find_all('li', class_='lesson')
            
            for lesson in lesson_items:
                lesson_data = {}
                
                # Номер урока
                number_elem = lesson.find('div', class_='number')
                if number_elem:
                    lesson_data['number'] = number_elem.get_text(strip=True).replace('.', '')
                
                # Тип занятия
                type_elem = lesson.find('div', class_='type')
                if type_elem:
                    lesson_data['type'] = type_elem.get_text(strip=True)
                
                # Время
                time_elem = lesson.find('div', class_='time')
                if time_elem:
                    lesson_data['time'] = time_elem.get_text(strip=True)
                
                # Название предмета
                name_elem = lesson.find('div', class_='name')
                if name_elem:
                    lesson_data['subject'] = name_elem.get_text(strip=True)
                
                # Преподаватели
                prep_links = lesson.find_all('a', href=True)
                teachers = []
                for link in prep_links:
                    teacher_name = link.get_text(strip=True)
                    if teacher_name and teacher_name != '':
                        teachers.append(teacher_name)
                if teachers:
                    lesson_data['teachers'] = teachers
                
                # Кабинет
                cab_elem = lesson.find('div', class_='cab')
                if cab_elem:
                    cab_text = cab_elem.get_text(strip=True)
                    if cab_text:
                        lesson_data['cabinet'] = cab_text
                
                # Пропускаем пустые уроки
                if lesson_data and 'number' in lesson_data and lesson_data['number'] not in ['', ' ']:
                    # Проверяем, что это не пустой урок (в нем есть данные)
                    if 'subject' in lesson_data or 'type' in lesson_data:
                        lessons.append(lesson_data)
            
            if lessons:
                days.append({
                    'day': day_name,
                    'lessons': lessons
                })
        
        return {
            'group': group_name,
            'schedule': days
        }


@app.get("/")
async def root():
    return {
        "message": "API расписания СФ УУНиТ",
        "endpoints": {
            "/schedule/aiss21": "Получить расписание группы АИС21",
            "/schedule/aiss21/raw": "Получить сырое HTML расписание",
            "/schedule/aiss21/today": "Получить расписание на сегодня",
            "/schedule/aiss21/tomorrow": "Получить расписание на завтра",
        }
    }


@app.get("/schedule/aiss21")
async def get_aiss21_schedule():
    """Получить расписание группы АИС21"""
    try:
        html = await ScheduleParser.fetch_page()
        schedule = ScheduleParser.parse_schedule(html, "АИС21")
        return schedule
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при запросе к сайту: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при парсинге: {str(e)}")


@app.get("/schedule/aiss21/raw")
async def get_aiss21_raw():
    """Получить сырое HTML расписание для отладки"""
    try:
        html = await ScheduleParser.fetch_page()
        
        # Находим блок расписания
        soup = BeautifulSoup(html, 'html.parser')
        raspisanie = soup.find('div', class_='raspisanie')
        
        if raspisanie:
            return {"html": str(raspisanie)}
        return {"error": "Блок расписания не найден", "html_preview": html[:2000]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schedule/aiss21/today")
async def get_today_schedule():
    """Получить расписание на сегодня"""
    schedule = await get_aiss21_schedule()
    today = datetime.now().strftime("%d/%m/%Y")
    
    # Ищем сегодняшний день в расписании
    for day in schedule.get('schedule', []):
        if today in day.get('day', ''):
            return {
                "date": today,
                "group": schedule.get('group'),
                "lessons": day.get('lessons', [])
            }
    
    return {
        "date": today,
        "group": schedule.get('group'),
        "lessons": [],
        "message": "На сегодня занятий нет"
    }


@app.get("/schedule/aiss21/tomorrow")
async def get_tomorrow_schedule():
    """Получить расписание на завтра"""
    from datetime import timedelta
    schedule = await get_aiss21_schedule()
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
    
    for day in schedule.get('schedule', []):
        if tomorrow in day.get('day', ''):
            return {
                "date": tomorrow,
                "group": schedule.get('group'),
                "lessons": day.get('lessons', [])
            }
    
    return {
        "date": tomorrow,
        "group": schedule.get('group'),
        "lessons": [],
        "message": "На завтра занятий нет"
    }


# HTML интерфейс для быстрого просмотра
@app.get("/ui", response_class=HTMLResponse)
async def ui():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Расписание АИС21</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background: #f5f5f5;
            }
            h1 {
                color: #333;
                text-align: center;
            }
            .day-card {
                background: white;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 15px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .day-title {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                border-bottom: 2px solid #3498db;
                padding-bottom: 8px;
                margin-bottom: 12px;
            }
            .lesson {
                padding: 8px 0;
                border-bottom: 1px solid #eee;
            }
            .lesson:last-child {
                border-bottom: none;
            }
            .lesson-number {
                display: inline-block;
                width: 30px;
                font-weight: bold;
                color: #7f8c8d;
            }
            .lesson-time {
                display: inline-block;
                width: 100px;
                color: #2c3e50;
                font-weight: 500;
            }
            .lesson-type {
                display: inline-block;
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 12px;
                background: #ecf0f1;
                margin-right: 8px;
            }
            .lesson-subject {
                font-weight: 500;
                color: #2c3e50;
            }
            .lesson-teachers {
                color: #7f8c8d;
                font-size: 14px;
            }
            .lesson-cabinet {
                color: #e74c3c;
                font-size: 14px;
                margin-left: 10px;
            }
            .no-lessons {
                color: #7f8c8d;
                text-align: center;
                padding: 20px;
            }
            .refresh-btn {
                display: block;
                width: 200px;
                margin: 20px auto;
                padding: 10px;
                text-align: center;
                background: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
            }
            .refresh-btn:hover {
                background: #2980b9;
            }
            .loading {
                text-align: center;
                padding: 40px;
                color: #7f8c8d;
            }
            .today-btn, .tomorrow-btn {
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                margin: 0 5px;
            }
            .today-btn {
                background: #2ecc71;
                color: white;
            }
            .tomorrow-btn {
                background: #f39c12;
                color: white;
            }
            .buttons {
                text-align: center;
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <h1>📚 Расписание АИС21</h1>
        
        <div class="buttons">
            <button class="today-btn" onclick="loadToday()">📅 Сегодня</button>
            <button class="tomorrow-btn" onclick="loadTomorrow()">📅 Завтра</button>
            <button class="refresh-btn" onclick="loadSchedule()">🔄 Обновить</button>
        </div>
        
        <div id="schedule-container">
            <div class="loading">Загрузка расписания...</div>
        </div>

        <script>
            async function loadSchedule() {
                const container = document.getElementById('schedule-container');
                container.innerHTML = '<div class="loading">Загрузка...</div>';
                
                try {
                    const response = await fetch('/schedule/aiss21');
                    const data = await response.json();
                    renderSchedule(data);
                } catch (error) {
                    container.innerHTML = '<div class="loading">❌ Ошибка загрузки</div>';
                }
            }

            async function loadToday() {
                const container = document.getElementById('schedule-container');
                container.innerHTML = '<div class="loading">Загрузка...</div>';
                
                try {
                    const response = await fetch('/schedule/aiss21/today');
                    const data = await response.json();
                    
                    if (data.lessons && data.lessons.length > 0) {
                        container.innerHTML = `
                            <div class="day-card">
                                <div class="day-title">📅 ${data.date}</div>
                                ${data.lessons.map(lesson => renderLesson(lesson)).join('')}
                            </div>
                        `;
                    } else {
                        container.innerHTML = `
                            <div class="day-card">
                                <div class="day-title">📅 ${data.date}</div>
                                <div class="no-lessons">🎉 Занятий нет!</div>
                            </div>
                        `;
                    }
                } catch (error) {
                    container.innerHTML = '<div class="loading">❌ Ошибка загрузки</div>';
                }
            }

            async function loadTomorrow() {
                const container = document.getElementById('schedule-container');
                container.innerHTML = '<div class="loading">Загрузка...</div>';
                
                try {
                    const response = await fetch('/schedule/aiss21/tomorrow');
                    const data = await response.json();
                    
                    if (data.lessons && data.lessons.length > 0) {
                        container.innerHTML = `
                            <div class="day-card">
                                <div class="day-title">📅 ${data.date}</div>
                                ${data.lessons.map(lesson => renderLesson(lesson)).join('')}
                            </div>
                        `;
                    } else {
                        container.innerHTML = `
                            <div class="day-card">
                                <div class="day-title">📅 ${data.date}</div>
                                <div class="no-lessons">🎉 Занятий нет!</div>
                            </div>
                        `;
                    }
                } catch (error) {
                    container.innerHTML = '<div class="loading">❌ Ошибка загрузки</div>';
                }
            }

            function renderLesson(lesson) {
                const teachers = lesson.teachers ? lesson.teachers.join(', ') : '';
                const cabinet = lesson.cabinet ? `🏫 ${lesson.cabinet}` : '';
                const number = lesson.number || '';
                const time = lesson.time || '';
                const type = lesson.type || '';
                const subject = lesson.subject || '';

                return `
                    <div class="lesson">
                        <span class="lesson-number">${number}.</span>
                        <span class="lesson-time">${time}</span>
                        ${type ? `<span class="lesson-type">${type}</span>` : ''}
                        <span class="lesson-subject">${subject}</span>
                        ${teachers ? `<span class="lesson-teachers">👨‍🏫 ${teachers}</span>` : ''}
                        ${cabinet ? `<span class="lesson-cabinet">${cabinet}</span>` : ''}
                    </div>
                `;
            }

            function renderSchedule(data) {
                const container = document.getElementById('schedule-container');
                
                if (data.error) {
                    container.innerHTML = `<div class="loading">❌ ${data.error}</div>`;
                    return;
                }

                if (!data.schedule || data.schedule.length === 0) {
                    container.innerHTML = '<div class="loading">📭 Расписание не найдено</div>';
                    return;
                }

                let html = '';
                for (const day of data.schedule) {
                    if (day.lessons && day.lessons.length > 0) {
                        html += `
                            <div class="day-card">
                                <div class="day-title">${day.day}</div>
                                ${day.lessons.map(lesson => renderLesson(lesson)).join('')}
                            </div>
                        `;
                    }
                }

                if (html) {
                    container.innerHTML = html;
                } else {
                    container.innerHTML = '<div class="loading">📭 На этой неделе занятий нет</div>';
                }
            }

            // Автоматическая загрузка при открытии
            loadSchedule();
        </script>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)