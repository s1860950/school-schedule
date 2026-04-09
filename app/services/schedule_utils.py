"""
Утилиты для обработки расписания и генерации Excel файлов
"""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import re
from typing import List, Dict, Any
from io import BytesIO


def parse_schedule_text(text: str) -> List[List[str]]:
    """
    Парсит текст расписания в формат таблицы.
    Пытается извлечь таблицу из текста.
    """
    lines = text.strip().split('\n')
    rows = []
    
    for line in lines:
        if line.strip():
            # Удаляем лишние пробелы и разделяем по вертикальной черте или множественным пробелам
            cleaned = line.strip()
            
            # Если строка содержит вертикальные черты (таблица в формате markdown/text)
            if '|' in cleaned:
                cells = [cell.strip() for cell in cleaned.split('|') if cell.strip()]
                if cells:
                    rows.append(cells)
            # Или пытаемся разделить по множественным пробелам
            elif '  ' in cleaned:
                cells = [cell.strip() for cell in re.split(r'\s{2,}', cleaned) if cell.strip()]
                if cells and len(cells) >= 2:
                    rows.append(cells)
            # Или просто одна ячейка в строке
            elif cleaned:
                rows.append([cleaned])
    
    return rows


def create_schedule_excel(schedule_text: str) -> BytesIO:
    """
    Создает Excel файл с расписанием из текста.
    Возвращает BytesIO объект с содержимым файла.
    """
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Расписание"
    
    # Стили
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    center_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    
    # Парсим текст расписания
    rows = parse_schedule_text(schedule_text)
    
    # Если не удалось распарсить, создаем базовую таблицу
    if not rows:
        # Создаем базовую таблицу с предметами и временем
        headers = ["Время", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]
        times = [
            "8:30-9:15",
            "9:30-10:15",
            "10:30-11:15",
            "11:30-12:15",
            "13:00-13:45",
            "14:00-14:45"
        ]
        
        # Добавляем заголовки
        for col, header in enumerate(headers, 1):
            cell = worksheet.cell(row=1, column=col)
            cell.value = header
            cell.fill = header_fill
            cell.font = header_font
            cell.border = border
            cell.alignment = center_alignment
        
        # Добавляем время
        for row, time in enumerate(times, 2):
            cell = worksheet.cell(row=row, column=1)
            cell.value = time
            cell.border = border
            cell.alignment = center_alignment
            cell.font = Font(bold=True)
        
        # Установим ширину колонок
        worksheet.column_dimensions['A'].width = 15
        for col in range(2, 7):
            worksheet.column_dimensions[get_column_letter(col)].width = 20
        
        # Установим высоту для header
        worksheet.row_dimensions[1].height = 25
        
        # Добавляем пустые ячейки для данных
        for row in range(2, len(times) + 2):
            for col in range(2, 7):
                cell = worksheet.cell(row=row, column=col)
                cell.border = border
                cell.alignment = left_alignment
        
        # Добавляем текст расписания в отдельную область
        if schedule_text.strip():
            worksheet.append([])
            worksheet.append(["Сгенерированное расписание:"])
            for line in schedule_text.split('\n')[:20]:  # Первые 20 строк
                if line.strip():
                    worksheet.append([line])
    else:
        # Используем спарсенные данные
        max_cols = max(len(row) for row in rows) if rows else 1
        
        # Добавляем строки в таблицу
        for row_idx, row_data in enumerate(rows[:30], 1):  # Максимум 30 строк для главной таблицы
            for col_idx, cell_value in enumerate(row_data, 1):
                cell = worksheet.cell(row=row_idx, column=col_idx)
                cell.value = str(cell_value)
                cell.border = border
                
                # Первая строка как заголовок
                if row_idx == 1:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = center_alignment
                else:
                    cell.alignment = left_alignment
        
        # Установим ширину колонок
        for col in range(1, max_cols + 1):
            worksheet.column_dimensions[get_column_letter(col)].width = 18
    
    # Сохраняем в BytesIO
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    
    return output
