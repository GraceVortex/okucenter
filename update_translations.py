import os
import re
import polib

# Путь к файлу переводов
po_file_path = 'locale/kk/LC_MESSAGES/django.po'
# Путь к файлу с переводами
translations_file_path = 'translations_to_do.txt'

def update_translations():
    # Загружаем существующий файл переводов
    po = polib.pofile(po_file_path)
    
    # Загружаем переводы из файла
    with open(translations_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Словарь для хранения переводов
    translations = {}
    
    # Обрабатываем каждую строку с переводом
    for line in lines:
        line = line.strip()
        # Пропускаем пустые строки и комментарии
        if not line or line.startswith('#'):
            continue
        
        # Разделяем строку на русский текст и казахский перевод
        parts = line.split('|')
        if len(parts) == 2:
            ru_text = parts[0].strip()
            kk_text = parts[1].strip()
            
            # Пропускаем строки без перевода
            if not kk_text:
                continue
                
            translations[ru_text] = kk_text
    
    # Счетчик добавленных/обновленных переводов
    added_count = 0
    updated_count = 0
    
    # Обновляем существующие переводы и добавляем новые
    for ru_text, kk_text in translations.items():
        # Проверяем, есть ли уже такой перевод
        entry = po.find(ru_text)
        
        if entry:
            # Если перевод уже есть, обновляем его
            if entry.msgstr != kk_text:
                entry.msgstr = kk_text
                updated_count += 1
        else:
            # Если перевода нет, добавляем новый
            entry = polib.POEntry(
                msgid=ru_text,
                msgstr=kk_text,
                occurrences=[('templates/base.html', '1')]
            )
            po.append(entry)
            added_count += 1
    
    # Сохраняем обновленный файл переводов
    po.save(po_file_path)
    
    print(f"Обновлено {updated_count} существующих переводов")
    print(f"Добавлено {added_count} новых переводов")
    
    # Компиляция файла переводов
    try:
        po.save_as_mofile('locale/kk/LC_MESSAGES/django.mo')
        print("Файл переводов успешно скомпилирован")
    except Exception as e:
        print(f"Ошибка при компиляции файла переводов: {e}")
        print("Вы можете скомпилировать файл вручную с помощью команды 'django-admin compilemessages'")

if __name__ == "__main__":
    update_translations()
