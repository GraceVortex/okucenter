"""
Оптимизированный модуль для распознавания лиц с использованием FaceNet и быстрого поиска ближайших соседей.
Использует алгоритм Annoy для эффективного поиска похожих лиц в базе данных.
"""

import os
import numpy as np
import torch
import base64
import json
import logging
import time
from io import BytesIO
from PIL import Image
from facenet_pytorch import MTCNN, InceptionResnetV1
from django.conf import settings
from annoy import AnnoyIndex
from django.db import transaction

from accounts.models import User
from .facenet_utils import process_base64_image, encode_face_data, decode_face_data, FACENET_THRESHOLD

# Настраиваем логгер
logger = logging.getLogger(__name__)

# Константы для индекса Annoy
VECTOR_SIZE = 512  # Размерность эмбеддингов FaceNet
NUM_TREES = 10     # Количество деревьев в индексе (больше = точнее, но медленнее)
SEARCH_K = -1      # Параметр поиска (-1 = автоматический выбор)
INDEX_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models', 'face_index.ann')

# Глобальный индекс и маппинг ID пользователей
face_index = None
user_id_map = {}

def build_face_index():
    """
    Строит индекс для быстрого поиска ближайших соседей на основе эмбеддингов лиц всех пользователей.
    Индекс сохраняется на диск для последующего использования.
    """
    global face_index, user_id_map
    
    logger.info("[OPTIMIZE] Начинаем построение индекса лиц")
    
    # Создаем директорию для моделей, если она не существует
    models_dir = os.path.dirname(INDEX_FILE_PATH)
    logger.info(f"[OPTIMIZE] Создаем директорию для моделей: {models_dir}")
    os.makedirs(models_dir, exist_ok=True)
    
    # Получаем всех пользователей с зарегистрированными лицами
    logger.info("[OPTIMIZE] Получаем пользователей с зарегистрированными лицами")
    users_with_faces = User.objects.exclude(face_id_data__isnull=True).exclude(face_id_data="")
    
    users_count = users_with_faces.count()
    logger.info(f"[OPTIMIZE] Найдено пользователей с зарегистрированными лицами: {users_count}")
    
    if not users_with_faces.exists():
        logger.warning("Нет пользователей с зарегистрированными лицами для построения индекса")
        return False
    
    # Создаем новый индекс
    logger.info("[OPTIMIZE] Создаем новый индекс Annoy с размерностью {VECTOR_SIZE}")
    index = AnnoyIndex(VECTOR_SIZE, 'angular')  # 'angular' для косинусного расстояния
    
    # Очищаем маппинг ID
    logger.info("[OPTIMIZE] Очищаем маппинг ID")
    user_id_map = {}
    
    # Добавляем эмбеддинги всех пользователей в индекс
    logger.info("[OPTIMIZE] Начинаем добавлять эмбеддинги пользователей в индекс")
    
    valid_embeddings_count = 0
    for i, user in enumerate(users_with_faces):
        try:
            # Декодируем данные лица пользователя
            logger.debug(f"[OPTIMIZE] Декодируем данные лица пользователя {user.username} (ID: {user.id})")
            face_embedding = decode_face_data(user.face_id_data)
            
            if face_embedding is None:
                logger.warning(f"[OPTIMIZE] Не удалось декодировать данные лица пользователя {user.username}")
                continue
            
            # Проверяем размерность эмбеддинга
            if face_embedding.shape[0] != VECTOR_SIZE:
                logger.warning(f"[OPTIMIZE] Неверная размерность эмбеддинга пользователя {user.username}: {face_embedding.shape[0]} (ожидается {VECTOR_SIZE})")
                continue
            
            # Добавляем эмбеддинг в индекс
            index.add_item(i, face_embedding)
            
            # Сохраняем маппинг между индексом и ID пользователя
            user_id_map[i] = user.id
            valid_embeddings_count += 1
            
            logger.debug(f"[OPTIMIZE] Добавлен пользователь {user.username} (ID: {user.id}) в индекс с индексом {i}")
        except Exception as e:
            logger.error(f"[OPTIMIZE] Ошибка при добавлении пользователя {user.username} в индекс: {e}")
    
    logger.info(f"[OPTIMIZE] Успешно добавлено {valid_embeddings_count} эмбеддингов из {users_count} пользователей")
    
    # Строим индекс
    if len(user_id_map) > 0:
        logger.info(f"[OPTIMIZE] Строим индекс с {NUM_TREES} деревьями")
        index.build(NUM_TREES)
        
        # Сохраняем индекс на диск
        logger.info(f"[OPTIMIZE] Сохраняем индекс на диск: {INDEX_FILE_PATH}")
        index.save(INDEX_FILE_PATH)
        
        # Сохраняем маппинг ID в JSON-файл
        logger.info(f"[OPTIMIZE] Сохраняем маппинг ID в JSON-файл: {INDEX_FILE_PATH + '.json'}")
        with open(INDEX_FILE_PATH + '.json', 'w') as f:
            json.dump(user_id_map, f)
        
        # Устанавливаем глобальный индекс
        logger.info("[OPTIMIZE] Устанавливаем глобальный индекс")
        face_index = index
        
        logger.info(f"[OPTIMIZE] Индекс лиц успешно построен и сохранен. Добавлено {len(user_id_map)} пользователей.")
        return True
    else:
        logger.warning("[OPTIMIZE] Не удалось построить индекс лиц: нет валидных эмбеддингов")
        return False

def load_face_index():
    """
    Загружает индекс для быстрого поиска ближайших соседей с диска.
    Возвращает True, если индекс успешно загружен, иначе False.
    """
    global face_index, user_id_map
    
    logger.info("[OPTIMIZE] Попытка загрузить индекс лиц")
    
    try:
        # Проверяем, существует ли файл индекса
        index_exists = os.path.exists(INDEX_FILE_PATH)
        json_exists = os.path.exists(INDEX_FILE_PATH + '.json')
        logger.info(f"[OPTIMIZE] Наличие файлов индекса: индекс={index_exists}, json={json_exists}")
        logger.info(f"[OPTIMIZE] Путь к индексу: {INDEX_FILE_PATH}")
        
        if not index_exists or not json_exists:
            logger.warning("Файлы индекса не найдены. Необходимо построить индекс.")
            logger.info("[OPTIMIZE] Пытаемся построить индекс...")
            return build_face_index()
        
        # Загружаем маппинг ID из JSON-файла
        logger.info("[OPTIMIZE] Загружаем маппинг ID из JSON-файла")
        with open(INDEX_FILE_PATH + '.json', 'r') as f:
            user_id_map = {int(k): v for k, v in json.load(f).items()}
        
        # Создаем и загружаем индекс
        logger.info("[OPTIMIZE] Создаем и загружаем индекс")
        index = AnnoyIndex(VECTOR_SIZE, 'angular')
        index.load(INDEX_FILE_PATH)
        
        # Устанавливаем глобальный индекс
        face_index = index
        
        logger.info(f"[OPTIMIZE] Индекс лиц успешно загружен. Доступно {len(user_id_map)} пользователей.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при загрузке индекса лиц: {e}")
        return False

def add_user_to_index(user):
    """
    Добавляет пользователя в индекс для быстрого поиска.
    Если индекс не загружен, загружает его.
    """
    global face_index, user_id_map
    
    # Проверяем, загружен ли индекс
    if face_index is None:
        if not load_face_index():
            logger.error("Не удалось загрузить индекс лиц")
            return False
    
    try:
        # Декодируем данные лица пользователя
        face_embedding = decode_face_data(user.face_id_data)
        
        if face_embedding is None:
            logger.warning(f"Не удалось декодировать данные лица пользователя {user.username}")
            return False
        
        # Получаем новый индекс для пользователя
        new_index = len(user_id_map)
        
        # Добавляем эмбеддинг в индекс
        face_index.add_item(new_index, face_embedding)
        
        # Сохраняем маппинг между индексом и ID пользователя
        user_id_map[new_index] = user.id
        
        # Перестраиваем индекс
        face_index.build(NUM_TREES)
        
        # Сохраняем индекс на диск
        face_index.save(INDEX_FILE_PATH)
        
        # Сохраняем маппинг ID в JSON-файл
        with open(INDEX_FILE_PATH + '.json', 'w') as f:
            json.dump(user_id_map, f)
        
        logger.info(f"Пользователь {user.username} (ID: {user.id}) успешно добавлен в индекс с индексом {new_index}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении пользователя {user.username} в индекс: {e}")
        return False

def remove_user_from_index(user_id):
    """
    Удаляет пользователя из индекса для быстрого поиска.
    Поскольку Annoy не поддерживает удаление элементов, индекс перестраивается полностью.
    """
    # Просто перестраиваем индекс полностью
    return build_face_index()

def recognize_face_optimized(base64_image, request=None, threshold=None, n_neighbors=5):
    """
    Распознает лицо на изображении с использованием оптимизированного алгоритма поиска ближайших соседей.
    
    Args:
        base64_image: Изображение в формате base64
        request: HTTP-запрос (для логирования)
        threshold: Порог уверенности для распознавания (если None, используется FACENET_THRESHOLD)
        n_neighbors: Количество ближайших соседей для поиска
        
    Returns:
        Tuple[bool, User, str, float]: (успех, пользователь, сообщение, уверенность)
    """
    logger.info(f"[OPTIMIZE] Запуск оптимизированного распознавания лица с порогом {threshold or FACENET_THRESHOLD}")
    
    # Устанавливаем порог распознавания, если он не указан
    if threshold is None:
        threshold = FACENET_THRESHOLD
    
    # Проверяем, загружен ли индекс
    global face_index, user_id_map
    logger.info(f"[OPTIMIZE] Состояние индекса: {face_index is not None}")
    
    if face_index is None:
        logger.info("[OPTIMIZE] Индекс не загружен, пытаемся загрузить...")
        if not load_face_index():
            logger.error("Не удалось загрузить индекс лиц")
            return False, None, "Ошибка при загрузке индекса лиц", 0.0
    
    try:
        # Замеряем время выполнения
        start_time = time.time()
        
        # Обрабатываем изображение и получаем эмбеддинг лица
        face_embedding, error = process_base64_image(base64_image)
        
        if face_embedding is None:
            return False, None, error or "Не удалось обнаружить лицо на изображении", 0.0
        
        # Если в индексе нет пользователей
        if len(user_id_map) == 0:
            return False, None, "В системе нет зарегистрированных лиц", 0.0
        
        # Ищем ближайших соседей
        nearest_indices, distances = face_index.get_nns_by_vector(
            face_embedding, 
            n_neighbors, 
            search_k=SEARCH_K, 
            include_distances=True
        )
        
        # Преобразуем расстояния в косинусное сходство (0-1)
        # Annoy возвращает угловое расстояние, которое нужно преобразовать в косинусное сходство
        similarities = [1.0 - (dist / 2.0) for dist in distances]
        
        # Находим лучшее совпадение
        best_match = None
        best_confidence = 0.0
        
        for i, (idx, similarity) in enumerate(zip(nearest_indices, similarities)):
            # Получаем ID пользователя из маппинга
            user_id = user_id_map.get(idx)
            if user_id is None:
                continue
            
            # Получаем пользователя из базы данных
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                continue
            
            logger.debug(f"Сравнение с {user.username}: сходство = {similarity:.4f}, порог = {threshold:.4f}")
            
            # Если это лучшее совпадение, запоминаем его
            if similarity > best_confidence:
                best_confidence = similarity
                best_match = user
        
        # Замеряем время выполнения
        elapsed_time = time.time() - start_time
        logger.info(f"Время распознавания лица: {elapsed_time:.4f} секунд")
        
        # Если найдено совпадение с достаточной уверенностью
        if best_match is not None and best_confidence >= threshold:
            # Логируем успешное распознавание
            logger.info(f"Лицо распознано как пользователь {best_match.username} с уверенностью {best_confidence:.4f}")
            
            # Создаем запись в логе распознавания
            if request:
                from .models import FaceRecognitionLog
                FaceRecognitionLog.objects.create(
                    user=best_match,
                    success=True,
                    confidence=best_confidence,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    device_info=request.META.get('HTTP_USER_AGENT', '')[:255]
                )
            
            return True, best_match, f"Лицо распознано как {best_match.get_full_name() or best_match.username}", best_confidence
        
        # Если совпадение не найдено
        logger.warning(f"Лицо не распознано. Лучшее совпадение: {best_match.username if best_match else 'нет'} с уверенностью {best_confidence:.4f}")
        
        # Создаем запись в логе распознавания (неудачную)
        if request and best_match:
            from .models import FaceRecognitionLog
            FaceRecognitionLog.objects.create(
                user=best_match,
                success=False,
                confidence=best_confidence,
                ip_address=request.META.get('REMOTE_ADDR'),
                device_info=request.META.get('HTTP_USER_AGENT', '')[:255]
            )
        
        return False, best_match, "Лицо не распознано", best_confidence
    
    except Exception as e:
        logger.error(f"Ошибка при распознавании лица: {e}")
        return False, None, f"Произошла ошибка: {str(e)}", 0.0

def register_face_optimized(user, base64_image):
    """
    Регистрирует лицо пользователя и добавляет его в индекс для быстрого поиска.
    
    Args:
        user: Пользователь для регистрации
        base64_image: Изображение лица в формате base64
        
    Returns:
        Tuple[bool, str]: (успех, сообщение)
    """
    from .facenet_utils import register_face
    
    # Регистрируем лицо с помощью стандартной функции
    success, message = register_face(user, base64_image)
    
    if success:
        # Добавляем пользователя в индекс
        if add_user_to_index(user):
            logger.info(f"Пользователь {user.username} успешно добавлен в индекс лиц")
        else:
            logger.warning(f"Не удалось добавить пользователя {user.username} в индекс лиц")
    
    return success, message

# Инициализируем индекс при импорте модуля
try:
    load_face_index()
except Exception as e:
    logger.error(f"Ошибка при инициализации индекса лиц: {e}")
