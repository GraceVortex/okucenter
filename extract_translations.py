import os
import re
import argparse
from pathlib import Path

def extract_texts_from_file(file_path):
    """
    Извлекает тексты для перевода из файла.
    Ищет тексты на русском языке в шаблонах.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Ищем тексты в различных форматах
    texts = set()
    
    # Ищем тексты в условных операторах if user_language
    pattern = r'{%\s*if\s+user_language\s*==\s*[\'"]kk[\'"]\s*%}(.*?){%\s*else\s*%}(.*?){%\s*endif\s*%}'
    matches = re.findall(pattern, content, re.DOTALL)
    for kk_text, ru_text in matches:
        ru_text = ru_text.strip()
        if ru_text and is_russian_text(ru_text):
            texts.add(ru_text)
    
    # Ищем тексты в тегах и фильтрах
    pattern = r'[{]{2}\s*[\'"](.*?)[\'"]\s*[|]\s*t\s*[}]{2}'
    matches = re.findall(pattern, content)
    for text in matches:
        if is_russian_text(text):
            texts.add(text)
    
    # Ищем тексты в тегах trans
    pattern = r'{%\s*trans\s+[\'"](.+?)[\'"]\s*%}'
    matches = re.findall(pattern, content)
    for text in matches:
        if is_russian_text(text):
            texts.add(text)
    
    # Ищем обычные тексты на русском языке в HTML-тегах
    pattern = r'>([^<>]{3,})<'
    matches = re.findall(pattern, content)
    for text in matches:
        text = text.strip()
        if text and is_russian_text(text) and not is_code(text):
            texts.add(text)
    
    return texts

def is_russian_text(text):
    """
    Проверяет, содержит ли текст русские буквы.
    """
    # Проверяем, содержит ли текст хотя бы одну русскую букву
    return bool(re.search('[а-яА-Я]', text))

def is_code(text):
    """
    Проверяет, является ли текст кодом (содержит специальные символы).
    """
    # Если текст содержит много специальных символов, вероятно, это код
    special_chars = '{}[]()<>|&^%$#@!~`*+=:;,?/\\_'
    special_count = sum(1 for char in text if char in special_chars)
    return special_count > len(text) * 0.2

def update_translations_file(texts, file_path='translations_to_do.txt'):
    """
    Обновляет файл с переводами, добавляя новые тексты.
    """
    existing_texts = set()
    
    # Читаем существующие переводы
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '|' in line:
                    ru_text = line.split('|')[0].strip()
                    existing_texts.add(ru_text)
    
    # Добавляем новые тексты
    new_texts = texts - existing_texts
    if new_texts:
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write('\n# Новые тексты для перевода\n')
            for text in sorted(new_texts):
                f.write(f'{text} | \n')
        
        print(f'Добавлено {len(new_texts)} новых текстов для перевода в {file_path}')
    else:
        print('Новых текстов для перевода не найдено')

def scan_templates(templates_dir):
    """
    Сканирует все шаблоны в указанной директории и извлекает тексты для перевода.
    """
    all_texts = set()
    
    # Рекурсивно обходим все файлы в директории
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(root, file)
                try:
                    texts = extract_texts_from_file(file_path)
                    all_texts.update(texts)
                    print(f'Обработан файл: {file_path}, найдено {len(texts)} текстов')
                except Exception as e:
                    print(f'Ошибка при обработке файла {file_path}: {e}')
    
    return all_texts

def main():
    parser = argparse.ArgumentParser(description='Извлечение текстов для перевода из шаблонов Django')
    parser.add_argument('--templates', default='templates', help='Путь к директории с шаблонами')
    parser.add_argument('--output', default='translations_to_do.txt', help='Путь к файлу с переводами')
    
    args = parser.parse_args()
    
    templates_dir = args.templates
    output_file = args.output
    
    print(f'Сканирование шаблонов в директории: {templates_dir}')
    texts = scan_templates(templates_dir)
    print(f'Всего найдено {len(texts)} уникальных текстов для перевода')
    
    update_translations_file(texts, output_file)

if __name__ == '__main__':
    main()
