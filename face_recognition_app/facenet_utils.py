"""
Модуль для распознавания лиц с использованием современных нейронных сетей.
Использует FaceNet для извлечения эмбеддингов лиц и сравнения их.
"""

import os
import numpy as np
import torch
import base64
import json
import logging
from io import BytesIO
from PIL import Image
from facenet_pytorch import MTCNN, InceptionResnetV1
from django.conf import settings

logger = logging.getLogger(__name__)

# Создаем директорию для моделей, если она не существует
MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
os.makedirs(MODELS_DIR, exist_ok=True)

# Инициализируем детектор лиц MTCNN и модель FaceNet
# Принудительно используем CPU для стабильной работы
device = torch.device('cpu')
logger.info(f"Принудительно используем CPU: {device}")

# Инициализируем MTCNN для обнаружения лиц
try:
    # Уменьшаем размер изображения для ускорения на CPU
    mtcnn = MTCNN(
        image_size=120, margin=0, min_face_size=20,
        thresholds=[0.6, 0.7, 0.7], factor=0.709, post_process=True,
        device='cpu', keep_all=False
    )
    logger.info("МТCNN успешно инициализирован на CPU")
except Exception as e:
    logger.error(f"Ошибка при инициализации MTCNN: {e}")
    raise

# Загружаем предобученную модель FaceNet
try:
    facenet = InceptionResnetV1(pretrained='vggface2').eval().to('cpu')
    logger.info("Модель FaceNet успешно загружена на CPU")
except Exception as e:
    logger.error(f"Ошибка при загрузке модели FaceNet: {e}")
    raise

# Константы# Глобальные настройки
FACENET_THRESHOLD = 0.75  # Порог сходства для распознавания лица (повышен для более точного распознавания)

def encode_face_data(face_features):
    """Преобразует массив numpy или тензор PyTorch в строку JSON для хранения в базе данных"""
    if isinstance(face_features, torch.Tensor):
        face_features = face_features.cpu().detach().numpy()
    return json.dumps(face_features.tolist())

def decode_face_data(face_data_str):
    """Преобразует строку JSON в массив numpy"""
    if not face_data_str:
        return None
    try:
        data = json.loads(face_data_str)
        return np.array(data, dtype=np.float32)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Ошибка декодирования данных лица: {e}")
        return None

def preprocess_image(image):
    """
    Оптимизированная функция предобработки изображения для быстрого распознавания лиц
    """
    try:
        from PIL import ImageEnhance
        
        # Проверяем, что изображение в формате RGB
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Минимальная предобработка для ускорения
        # Только самые важные улучшения
        
        # Применяем улучшение контраста
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.2)
        
        # Применяем улучшение яркости
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.1)
        
        # Пропускаем дополнительные фильтры для ускорения
        
        return image
    except Exception as e:
        return image  # Возвращаем оригинальное изображение в случае ошибки


def process_base64_image(base64_image):
    """Оптимизированная функция обработки изображения в формате base64 для быстрого распознавания лиц"""
    try:
        # Проверяем, что данные не пустые
        if not base64_image:
            return None, "Пустые данные изображения"
        
        # Обрабатываем данные в формате data:image/jpeg;base64, или data:image/png;base64,
        if ',' in base64_image:
            # Удаляем префикс и оставляем только данные base64
            _, base64_data = base64_image.split(',', 1)
            base64_image = base64_data
        
        # Проверяем, что данные не пустые
        if not base64_image or base64_image == "data:,":
            logger.error("Пустые данные изображения")
            return None, "Пустые данные изображения"
        
        # Декодируем base64 в байты
        try:
            # Добавляем паддинг, если необходимо
            padding = 4 - (len(base64_image) % 4) if len(base64_image) % 4 else 0
            if padding:
                base64_image += "=" * padding
            
            image_data = base64.b64decode(base64_image)
        except Exception as e:
            return None, f"Ошибка при декодировании изображения: {str(e)}"
        
        # Конвертируем байты в изображение PIL
        try:
            from io import BytesIO
            
            # Проверяем длину данных
            if len(image_data) < 100:
                logger.error(f"Слишком мало данных для изображения: {len(image_data)} байт")
                return None, "Недостаточно данных для изображения"
            
            # Открываем изображение напрямую из байтов
            try:
                image_buffer = BytesIO(image_data)
                image = Image.open(image_buffer)
                
                # Проверяем, что изображение загрузилось
                image.verify()  # Проверяем целостность изображения
                
                # Перезагружаем изображение после проверки
                image_buffer.seek(0)
                image = Image.open(image_buffer)
                
                # Конвертируем в RGB, если необходимо
                if image.mode != 'RGB':
                    image = image.convert('RGB')
            except Exception as e:
                logger.error(f"Ошибка при открытии изображения: {e}")
                return None, f"Ошибка при открытии изображения: {str(e)}"
            
            # Минимальная предобработка для ускорения
            # Только улучшаем контраст и яркость, пропускаем другие фильтры
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.2)
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(1.1)
            
            # Оптимизация размера изображения - только один раз изменяем размер
            width, height = image.size
            
            # Оптимальный размер для FaceNet - 160x160
            target_size = 160
            
            # Изменяем размер только если нужно
            if width != target_size or height != target_size:
                # Сохраняем соотношение сторон
                if width > height:
                    new_width = int(width * (target_size / height))
                    new_height = target_size
                else:
                    new_width = target_size
                    new_height = int(height * (target_size / width))
                
                # Используем BILINEAR вместо LANCZOS для скорости
                image = image.resize((new_width, new_height), Image.BILINEAR)
                
                # Центрируем и обрезаем до целевого размера
                left = (new_width - target_size) // 2
                top = (new_height - target_size) // 2
                right = left + target_size
                bottom = top + target_size
                
                # Обрезаем изображение до квадрата
                image = image.crop((left, top, right, bottom))
            face_tensor = mtcnn(image)
            
            if face_tensor is None:
                logger.warning("Лицо не обнаружено на изображении")
                return None, "Лицо не обнаружено на изображении"
            
            logger.info(f"Лицо успешно обнаружено, размер тензора: {face_tensor.shape}")
            
            # Получаем эмбеддинг лица с помощью FaceNet
            # Добавляем размерность батча (1, ...)
            face_tensor = face_tensor.unsqueeze(0).to('cpu')  # Принудительно используем CPU
            
            # Отключаем вычисление градиентов для ускорения
            with torch.no_grad():
                embedding = facenet(face_tensor)
            
            # Преобразуем эмбеддинг в numpy массив
            embedding = embedding.cpu().numpy().flatten()
            
            # Проверяем, что эмбеддинг не содержит NaN или бесконечностей
            if np.isnan(embedding).any() or np.isinf(embedding).any():
                logger.warning("Эмбеддинг содержит NaN или бесконечности")
                return None, "Ошибка при обработке лица: некорректные значения в эмбеддинге"
            
            # Нормализуем вектор эмбеддинга
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            else:
                logger.warning("Норма эмбеддинга равна нулю")
                return None, "Ошибка при обработке лица: нулевой эмбеддинг"
            
            logger.info(f"Эмбеддинг успешно получен, размерность: {embedding.shape}")
            
            return embedding, None
            
        except Exception as e:
            logger.error(f"Ошибка при обработке лица с помощью MTCNN/FaceNet: {e}")
            return None, f"Ошибка при обработке лица: {str(e)}"
        
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}")
        return None, f"Ошибка при обработке изображения: {str(e)}"

def compare_faces(face1_embedding, face2_embedding, threshold=FACENET_THRESHOLD):
    """Сравнивает два эмбеддинга лиц с помощью FaceNet"""
    try:
        # Добавляем дополнительное логирование
        logger.info(f"[COMPARE_FACES] Начало сравнения лиц с порогом {threshold:.4f}")
        
        # Проверяем, что эмбеддинги не None
        if face1_embedding is None or face2_embedding is None:
            logger.warning("[COMPARE_FACES] Один из эмбеддингов лица равен None")
            return False, 0.0
        
        # Проверяем размерность эмбеддингов
        if hasattr(face1_embedding, 'shape') and hasattr(face2_embedding, 'shape'):
            logger.info(f"[COMPARE_FACES] Размерность эмбеддингов: {face1_embedding.shape} и {face2_embedding.shape}")
        
        # Преобразуем в тензоры PyTorch, если они еще не являются тензорами
        try:
            if not isinstance(face1_embedding, torch.Tensor):
                face1_embedding = torch.tensor(face1_embedding, dtype=torch.float32)
            if not isinstance(face2_embedding, torch.Tensor):
                face2_embedding = torch.tensor(face2_embedding, dtype=torch.float32)
        except Exception as e:
            logger.error(f"[COMPARE_FACES] Ошибка при преобразовании в тензоры: {e}")
            return False, 0.0
        
        # Проверяем, что тензоры не содержат NaN или бесконечностей
        if torch.isnan(face1_embedding).any() or torch.isinf(face1_embedding).any() or \
           torch.isnan(face2_embedding).any() or torch.isinf(face2_embedding).any():
            logger.warning("[COMPARE_FACES] Эмбеддинги содержат NaN или бесконечности")
            return False, 0.0
        
        # Нормализуем эмбеддинги
        try:
            norm1 = face1_embedding.norm()
            norm2 = face2_embedding.norm()
            
            # Проверяем, что нормы не равны нулю
            if norm1 == 0 or norm2 == 0:
                logger.warning("[COMPARE_FACES] Норма одного из эмбеддингов равна нулю")
                return False, 0.0
                
            face1_embedding = face1_embedding / norm1
            face2_embedding = face2_embedding / norm2
        except Exception as e:
            logger.error(f"[COMPARE_FACES] Ошибка при нормализации эмбеддингов: {e}")
            return False, 0.0
        
        # Вычисляем косинусное сходство (от -1 до 1, чем ближе к 1, тем больше сходство)
        try:
            cosine_similarity = torch.sum(face1_embedding * face2_embedding).item()
            
            # Преобразуем в диапазон 0-1 для совместимости с остальным кодом
            similarity = (cosine_similarity + 1) / 2
        except Exception as e:
            logger.error(f"[COMPARE_FACES] Ошибка при вычислении косинусного сходства: {e}")
            return False, 0.0
        
        # Определяем, совпадают ли лица
        is_match = similarity >= threshold
        
        # Подробное логирование результата
        logger.info(f"[COMPARE_FACES] Сравнение лиц: сходство = {similarity:.4f} ({similarity*100:.1f}%), порог = {threshold:.4f} ({threshold*100:.1f}%), совпадение = {is_match}")
        return bool(is_match), float(similarity)
    
    except Exception as e:
        logger.error(f"[COMPARE_FACES] Ошибка при сравнении лиц: {e}")
        return False, 0.0

def register_face(user, base64_image):
    """Регистрирует лицо пользователя в базе данных"""
    try:
        # Обрабатываем изображение и получаем эмбеддинг лица
        face_embedding, error = process_base64_image(base64_image)
        
        if error:
            logger.error(f"[Регистрация лица] Ошибка при обработке изображения: {error}")
            return False, error
        
        if face_embedding is None:
            logger.error("[Регистрация лица] Не удалось получить эмбеддинг лица")
            return False, "Не удалось получить эмбеддинг лица"
        
        # Проверяем качество эмбеддинга
        import numpy as np
        embedding_norm = np.linalg.norm(face_embedding)
        logger.info(f"[Регистрация лица] Норма эмбеддинга: {embedding_norm:.6f}")
        
        # Проверяем на NaN и бесконечности
        if np.isnan(embedding_norm) or np.isinf(embedding_norm) or embedding_norm < 0.1:
            logger.error(f"[Регистрация лица] Некачественный эмбеддинг с нормой {embedding_norm:.6f}")
            return False, "Некачественное изображение лица. Попробуйте сделать снимок в лучшем освещении."
        
        # Нормализуем эмбеддинг перед сохранением
        face_embedding = face_embedding / embedding_norm
        
        # Проверяем норму после нормализации
        embedding_norm_after = np.linalg.norm(face_embedding)
        logger.info(f"[Регистрация лица] Норма эмбеддинга после нормализации: {embedding_norm_after:.6f}")
        
        # Проверяем первые значения эмбеддинга
        logger.info(f"[Регистрация лица] Первые 5 значений эмбеддинга: {face_embedding[:5]}")
        
        # Проверяем статистику эмбеддинга
        logger.info(f"[Регистрация лица] Статистика эмбеддинга: min={np.min(face_embedding):.4f}, max={np.max(face_embedding):.4f}, mean={np.mean(face_embedding):.4f}, std={np.std(face_embedding):.4f}")
        
        # Кодируем эмбеддинг лица для хранения в базе данных
        face_data = encode_face_data(face_embedding)
        
        # Сохраняем данные лица в профиле пользователя
        user.face_id_data = face_data
        user.save()
        
        # Если это студент, сохраняем изображение в поле face_image
        try:
            if hasattr(user, 'student_profile'):
                # Декодируем base64 в байты и сохраняем в face_image
                from django.core.files.base import ContentFile
                import base64
                import uuid
                import io
                from PIL import Image
                
                # Получаем только данные base64 без префикса
                if ',' in base64_image:
                    base64_image = base64_image.split(',')[1]
                
                # Создаем имя файла
                filename = f"faceid_photo_{uuid.uuid4().hex[:8].upper()}.png"
                
                try:
                    # Декодируем base64 в байты
                    image_data = base64.b64decode(base64_image)
                    
                    # Проверяем, что изображение валидно
                    img = Image.open(io.BytesIO(image_data))
                    img.verify()  # Проверяем, что файл не поврежден
                    
                    # Пересоздаем изображение в PNG для гарантии совместимости
                    img_io = io.BytesIO()
                    img = Image.open(io.BytesIO(image_data))  # Переоткрываем изображение
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    img.save(img_io, format='PNG')
                    img_io.seek(0)
                    
                    # Сохраняем в face_image
                    user.student_profile.face_image.save(filename, ContentFile(img_io.getvalue()), save=True)
                    logger.info(f"Изображение лица сохранено в профиле студента {user.username}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке изображения для сохранения: {e}")
                    # Пробуем сохранить как есть
                    user.student_profile.face_image.save(filename, ContentFile(image_data), save=True)
                    logger.info(f"Изображение лица сохранено в профиле студента {user.username} (без преобразования)")
        except Exception as e:
            logger.error(f"Ошибка при сохранении изображения лица в профиле студента: {e}")
        
        # Логируем успешную регистрацию
        logger.info(f"Лицо пользователя {user.username} успешно зарегистрировано с FaceNet")
        
        # Проверяем сохраненные данные
        decoded_features = decode_face_data(user.face_id_data)
        if decoded_features is None:
            return False, "Ошибка при проверке сохраненных данных лица"
        
        return True, "Лицо успешно зарегистрировано"
    
    except Exception as e:
        logger.error(f"Ошибка при регистрации лица: {e}")
        return False, f"Произошла ошибка: {str(e)}"

def recognize_face(base64_image, request=None, threshold=None, return_all_scores=False):
    """Оптимизированная функция распознавания лица на изображении с использованием FaceNet
    
    Args:
        base64_image: Изображение в формате base64
        request: Объект запроса Django
        threshold: Порог распознавания
        return_all_scores: Если True, возвращает сходства со всеми пользователями
    
    Returns:
        success: Успешность распознавания
        user: Пользователь, который был распознан
        error: Сообщение об ошибке
        confidence: Уверенность распознавания
        all_similarities: Список кортежей (user, confidence) для всех пользователей (если return_all_scores=True)
    """
    # Установим более строгий порог распознавания по умолчанию
    global FACENET_THRESHOLD
    DEFAULT_THRESHOLD = 0.75  # Повышаем порог по умолчанию для более точного распознавания
    # Импортируем numpy в начале функции
    import numpy as np
    
    # Устанавливаем порог распознавания
    if threshold is None:
        threshold = DEFAULT_THRESHOLD
    
    # Обновляем глобальный порог для отображения в UI
    FACENET_THRESHOLD = threshold
    
    logger.info(f"[Распознавание] Используемый порог распознавания: {threshold:.4f} ({threshold*100:.2f}%)")
    
    try:
        # Обрабатываем изображение и получаем эмбеддинг лица
        face_embedding, error = process_base64_image(base64_image)
        
        if face_embedding is None:
            return False, None, error or "Не удалось обнаружить лицо на изображении", 0.0
        
        # Получаем всех пользователей с зарегистрированными лицами
        from accounts.models import User
        users_with_faces = User.objects.exclude(face_id_data__isnull=True).exclude(face_id_data="")
        
        if not users_with_faces.exists():
            return False, None, "В системе нет зарегистрированных лиц", 0.0
        
        # Оптимизация: загружаем все эмбеддинги сразу и храним в памяти
        user_embeddings = []
        for user in users_with_faces:
            user_face_embedding = decode_face_data(user.face_id_data)
            if user_face_embedding is not None:
                user_embeddings.append((user, user_face_embedding))
        
        # Сравниваем лицо с каждым зарегистрированным лицом
        best_match = None
        best_confidence = 0.0
        
        # Отладочная информация о загруженных эмбеддингах
        logger.info(f"[Отладка] Загружено {len(user_embeddings)} эмбеддингов лиц для сравнения")
        logger.info(f"[Отладка] Текущий порог распознавания: {threshold}")
        
        # Выводим информацию о каждом пользователе с зарегистрированным лицом
        for i, (user, emb) in enumerate(user_embeddings):
            logger.info(f"[Отладка] Пользователь {i+1}: {user.username}, тип: {user.user_type}, длина эмбеддинга: {len(emb)}, норма: {np.linalg.norm(emb):.4f}")
            
        # Проверяем текущий эмбеддинг
        logger.info(f"[Отладка] Текущий эмбеддинг: длина: {len(face_embedding)}, норма: {np.linalg.norm(face_embedding):.4f}")
        
        # Проверяем первые несколько значений эмбеддинга
        logger.info(f"[Отладка] Первые 5 значений текущего эмбеддинга: {face_embedding[:5]}")
        
        if user_embeddings and len(user_embeddings) > 0:
            logger.info(f"[Отладка] Первые 5 значений эмбеддинга первого пользователя: {user_embeddings[0][1][:5]}")
        
        
        # Оптимизация: используем векторизацию для ускорения
        # numpy уже импортирован в начале функции
        
        # Создаем матрицу всех эмбеддингов
        if user_embeddings:
            # Создаем матрицу из всех эмбеддингов
            all_embeddings = np.array([emb for _, emb in user_embeddings])
            
            # Вычисляем сходство между текущим эмбеддингом и всеми сохраненными
            # Предполагаем, что эмбеддинги уже нормализованы
            # Косинусное сходство = dot(a, b) для нормализованных векторов
            
            # Проверяем нормы эмбеддингов
            face_embedding_norm = np.linalg.norm(face_embedding)
            all_embeddings_norms = np.linalg.norm(all_embeddings, axis=1)
            
            # Логируем нормы для проверки
            logger.info(f"[Отладка] Норма текущего эмбеддинга: {face_embedding_norm:.6f}")
            logger.info(f"[Отладка] Нормы сохраненных эмбеддингов (min/max/mean): {np.min(all_embeddings_norms):.6f}/{np.max(all_embeddings_norms):.6f}/{np.mean(all_embeddings_norms):.6f}")
            
            # Нормализуем эмбеддинги, если они еще не нормализованы
            if abs(face_embedding_norm - 1.0) > 1e-6:
                logger.info("[Отладка] Нормализуем текущий эмбеддинг")
                face_embedding = face_embedding / face_embedding_norm
            
            # Нормализуем сохраненные эмбеддинги, если нужно
            need_normalization = np.any(np.abs(all_embeddings_norms - 1.0) > 1e-6)
            if need_normalization:
                logger.info("[Отладка] Нормализуем сохраненные эмбеддинги")
                for i in range(len(all_embeddings)):
                    if all_embeddings_norms[i] > 0:
                        all_embeddings[i] = all_embeddings[i] / all_embeddings_norms[i]
            
            # Проверяем нормы эмбеддингов перед сравнением
            face_embedding_norm = np.linalg.norm(face_embedding)
            all_embeddings_norms = np.linalg.norm(all_embeddings, axis=1)
            
            # Логируем нормы для проверки
            logger.info(f"[Распознавание] Норма текущего эмбеддинга: {face_embedding_norm:.6f}")
            logger.info(f"[Распознавание] Нормы сохраненных эмбеддингов (min/max/mean): {np.min(all_embeddings_norms):.6f}/{np.max(all_embeddings_norms):.6f}/{np.mean(all_embeddings_norms):.6f}")
            
            # Всегда нормализуем эмбеддинги перед сравнением для более точных результатов
            if abs(face_embedding_norm - 1.0) > 1e-6:
                logger.info("[Распознавание] Нормализуем текущий эмбеддинг")
                face_embedding = face_embedding / face_embedding_norm
            
            # Нормализуем все сохраненные эмбеддинги
            for i in range(len(all_embeddings)):
                if all_embeddings_norms[i] > 0 and abs(all_embeddings_norms[i] - 1.0) > 1e-6:
                    all_embeddings[i] = all_embeddings[i] / all_embeddings_norms[i]
            
            # Вычисляем косинусное сходство после нормализации
            similarities = np.dot(all_embeddings, face_embedding)
            
            # Логируем исходные значения сходства
            logger.info(f"[Распознавание] Значения сходства (min/max/mean): {np.min(similarities):.6f}/{np.max(similarities):.6f}/{np.mean(similarities):.6f}")
            
            # Проверяем, нужно ли преобразовывать в диапазон [0, 1]
            # Косинусное сходство должно быть в диапазоне [-1, 1], но после нормализации обычно в [0, 1]
            if np.min(similarities) < 0:
                logger.info("[Распознавание] Преобразуем сходства в диапазон [0, 1]")
                similarities = (similarities + 1) / 2
            
            # Находим индекс наибольшего сходства
            best_idx = np.argmax(similarities)
            best_confidence = similarities[best_idx]
            
            # Логируем результаты сравнения
            logger.info(f"[Отладка] Лучшее совпадение: {best_confidence:.4f}, порог: {threshold}")
            
            # Создаем список всех пользователей с их сходствами
            all_user_similarities = []
            for idx, similarity in enumerate(similarities):
                all_user_similarities.append((user_embeddings[idx][0], similarity))
            
            # Сортируем по убыванию сходства
            all_user_similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Выводим топ-3 лучших совпадения
            for i, (user, conf) in enumerate(all_user_similarities[:3]):
                logger.info(f"[Распознавание] Топ-{i+1}: {user.username}, тип: {user.user_type}, сходство: {conf:.4f} ({conf*100:.2f}%)")  
                
            # Проверяем разницу между первым и вторым лучшими совпадениями
            if len(all_user_similarities) >= 2:
                top1_user, top1_conf = all_user_similarities[0]
                top2_user, top2_conf = all_user_similarities[1]
                confidence_diff = top1_conf - top2_conf
                logger.info(f"[Распознавание] Разница между 1-м и 2-м местом: {confidence_diff:.4f} ({confidence_diff*100:.2f}%)")
                
                # Если разница слишком мала, повышаем требуемый порог
                if confidence_diff < 0.1 and top1_conf < threshold + 0.1:
                    logger.warning(f"[Распознавание] Маленькая разница между лучшими совпадениями! Возможно неточное распознавание.")
            
            # Если нашли совпадение выше порога
            if best_confidence >= threshold:
                best_match = user_embeddings[best_idx][0]
                logger.info(f"[Отладка] Найдено совпадение выше порога: {best_match.username}")
            else:
                logger.info(f"[Отладка] Не найдено совпадений выше порога {threshold}")
          # Возвращаем результат
        if best_confidence >= threshold:
            best_match = user_embeddings[best_idx][0]
            logger.info(f"[Отладка] Найдено совпадение выше порога: {best_match.username}")
        else:
            logger.info(f"[Отладка] Не найдено совпадений выше порога {threshold}")
        
        # Если найдено совпадение с достаточной уверенностью
        if best_match is not None and best_confidence >= threshold:
            # Создаем запись в логе распознавания
            if request:
                from .models import FaceRecognitionLog
                FaceRecognitionLog.objects.create(
                    user=best_match,
                    success=True,
                    confidence=best_confidence,
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    device_info=request.META.get('HTTP_USER_AGENT', '')[:255]
                )
            
            # Возвращаем результат успешного распознавания
            if return_all_scores:
                return True, best_match, None, best_confidence, all_user_similarities
            else:
                return True, best_match, None, best_confidence
        
        # Если распознавание не удалось, но есть список сходств
        if return_all_scores and 'all_user_similarities' in locals():
            return False, None, "Лицо не распознано", 0.0, all_user_similarities
        else:
            return False, None, "Лицо не распознано", 0.0
    
    except Exception as e:
        error_msg = f"Произошла ошибка при распознавании лица: {str(e)}"
        logger.error(error_msg)
        if return_all_scores:
            return False, None, error_msg, 0.0, []
        else:
            return False, None, error_msg, 0.0

def mark_attendance_by_face(user, class_obj, date, status='present', request=None, confidence=None):
    """Отмечает посещаемость по распознанному лицу с использованием FaceNet"""
    try:
        from attendance.models import Attendance
        from .models import FaceAttendance
        from django.utils import timezone
        
        # Проверяем, что у пользователя есть профиль студента
        if not hasattr(user, 'student_profile') or user.student_profile is None:
            return False, "Пользователь не является студентом"
        
        # Получаем расписание для класса на указанную дату
        from classes.models import ClassSchedule
        schedule = ClassSchedule.objects.filter(
            class_obj=class_obj,
            day_of_week=date.weekday()
        ).first()
        
        if not schedule:
            return False, "Для этого класса нет расписания на указанную дату"
        
        # Создаем или обновляем запись о посещаемости
        attendance, created = Attendance.objects.update_or_create(
            student=user.student_profile,
            class_obj=class_obj,
            date=date,
            defaults={
                'class_schedule': schedule,
                'status': status,
                'reception_confirmed': True,
                'reception_confirmed_by': request.user if request else None
            }
        )
        
        # Устанавливаем значение уверенности по умолчанию, если оно не указано
        if confidence is None:
            confidence = 0.95  # Значение по умолчанию
        
        # Создаем запись о посещаемости через распознавание лица
        face_attendance = FaceAttendance.objects.create(
            attendance=attendance,
            confidence=confidence,
            reception_confirmed_by=request.user if request else None
        )
        
        logger.info(f"Посещаемость успешно отмечена для студента {user.username} в классе {class_obj.name} на дату {date} с уверенностью {confidence:.4f}")
        return True, "Посещаемость успешно отмечена"
    
    except Exception as e:
        logger.error(f"Ошибка при отметке посещаемости по лицу: {e}")
        return False, f"Произошла ошибка: {str(e)}"
