import os
import re
import glob
from bs4 import BeautifulSoup

# Путь к директории с шаблонами
templates_dir = 'templates'

# Получаем список всех русских текстов из файла переводов
def get_translations():
    translations = []
    with open('translations_to_do.txt', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('|')
            if len(parts) >= 1:
                ru_text = parts[0].strip()
                if ru_text and ru_text not in ['Русский текст']:  # Исключаем заголовок
                    translations.append(ru_text)
    
    # Сортируем по длине (от самых длинных к самым коротким)
    # чтобы избежать проблем с подстроками
    translations.sort(key=len, reverse=True)
    return translations

# Функция для обновления базового шаблона (base.html)
def update_base_template(translations):
    file_path = os.path.join(templates_dir, 'base.html')
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем, загружен ли тег i18n
        if '{% load i18n %}' not in content and content.strip():
            content = '{% load i18n %}\n' + content
        
        # Заменяем тексты на теги trans
        for text in translations:
            # Простая замена текста на тег trans
            # Ищем текст, который не находится внутри тега trans
            pattern = re.escape(text)
            replacement = '{% trans "' + text + '" %}'
            
            # Заменяем только целые слова или фразы
            content = re.sub(r'(>|\s)' + pattern + r'(<|\s)', r'\1' + replacement + r'\2', content)
        
        # Записываем обновленный контент
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Обновлен базовый шаблон: {file_path}")
        return True
    except Exception as e:
        print(f"Ошибка при обновлении базового шаблона {file_path}: {e}")
        return False

def main():
    # Получаем список переводов
    translations = get_translations()
    
    # Обновляем базовый шаблон
    update_base_template(translations)
    
    print("Обновление шаблонов завершено")

if __name__ == "__main__":
    main()
