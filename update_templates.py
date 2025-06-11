import os
import re
import glob

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

# Функция для обновления шаблона
def update_template(file_path, translations):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Проверяем, загружен ли тег i18n
    if '{% load i18n %}' not in content and content.strip():
        content = '{% load i18n %}\n' + content
    
    # Заменяем тексты на теги trans
    for text in translations:
        # Экранируем специальные символы в регулярных выражениях
        escaped_text = re.escape(text)
        
        # Ищем текст, который не находится внутри тега trans
        pattern = r'(?<!\{%\s*trans\s*")' + escaped_text + r'(?!"\s*%\})'
        
        # Заменяем только если текст находится внутри HTML-тегов или как отдельное слово
        content = re.sub(
            r'(>|\s)' + pattern + r'(<|\s)', 
            r'\1{% trans "' + text + r'" %}\2', 
            content
        )
    
    # Записываем обновленный контент
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    # Получаем список переводов
    translations = get_translations()
    
    # Получаем список всех HTML-файлов в директории шаблонов
    html_files = glob.glob(os.path.join(templates_dir, '**', '*.html'), recursive=True)
    
    # Обновляем каждый файл
    for file_path in html_files:
        try:
            update_template(file_path, translations)
            print(f"Обновлен файл: {file_path}")
        except Exception as e:
            print(f"Ошибка при обновлении файла {file_path}: {e}")
    
    print(f"Всего обработано файлов: {len(html_files)}")

if __name__ == "__main__":
    main()
