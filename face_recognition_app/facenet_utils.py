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
# Используем GPU, если доступен
device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
logger.info(f"Используем устройство: {device}")

# Инициализируем MTCNN для обнаружения лиц
try:
    mtcnn = MTCNN(
        image_size=160, margin=0, min_face_size=20,
        thresholds=[0.6, 0.7, 0.7], factor=0.709, post_process=True,
        device=device, keep_all=False
    )
    logger.info("MTCNN успешно инициализирован")
except Exception as e:
    logger.error(f"Ошибка при инициализации MTCNN: {e}")
    raise

# Загружаем предобученную модель FaceNet
try:
    facenet = InceptionResnetV1(pretrained='vggface2').eval().to(device)
    logger.info("Модель FaceNet успешно загружена")
except Exception as e:
    logger.error(f"Ошибка при загрузке модели FaceNet: {e}")
    raise

# Константы для распознавания лиц
FACENET_THRESHOLD = 0.88  # Порог для FaceNet (косинусное расстояние)

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
            
            # Открываем изображение напрямую из байтов
            image_buffer = BytesIO(image_data)
            image = Image.open(image_buffer)
            
            # Конвертируем в RGB, если необходимо
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
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
        except Exception as e:
            return None, f"Ошибка при обработке изображения: {str(e)}"
        
        # Используем оптимизированные параметры MTCNN для быстрого обнаружения лица
        try:
            # Используем предустановленный MTCNN с оптимальными параметрами
            face_tensor = mtcnn(image)
            
            # Если лицо не обнаружено с первой попытки, используем запасной вариант
            # с более мягкими параметрами, но только один раз
            if face_tensor is None:
                # Используем глобальную переменную для кэширования
                global mtcnn_optimized
                if 'mtcnn_optimized' not in globals():
                    mtcnn_optimized = MTCNN(
                        image_size=160, margin=20, min_face_size=10,
                        thresholds=[0.5, 0.6, 0.6], factor=0.8,
                        post_process=True, device=device, keep_all=False
                    )
                
                # Пробуем с оптимизированными параметрами
                face_tensor = mtcnn_optimized(image)
        except Exception as e:
            return None, f"Ошибка при обнаружении лица: {str(e)}"
        
        # Если лицо все еще не обнаружено
        if face_tensor is None:
            return None, "Лицо не обнаружено на изображении"
        
        # Получаем эмбеддинг лица с помощью FaceNet
        try:
            with torch.no_grad():
                embedding = facenet(face_tensor.unsqueeze(0))
            
            # Преобразуем тензор в массив numpy
            embedding_np = embedding.cpu().numpy()[0]
            return embedding_np, None
        except Exception as e:
            return None, f"Ошибка при получении эмбеддинга лица: {str(e)}"
    
    except Exception as e:
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
    """Регистрирует лицо пользователя с использованием FaceNet"""
    try:
        # Обрабатываем изображение и получаем эмбеддинг лица
        face_embedding, error = process_base64_image(base64_image)
        
        if face_embedding is None:
            return False, error or "Не удалось обнаружить лицо на изображении"
        
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

def recognize_face(base64_image, request=None, threshold=None):
    """Оптимизированная функция распознавания лица на изображении с использованием FaceNet"""
    # Устанавливаем порог распознавания
    if threshold is None:
        threshold = FACENET_THRESHOLD
    
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
        
        # Оптимизация: используем векторизацию для ускорения
        import numpy as np
        
        # Создаем матрицу всех эмбеддингов
        if user_embeddings:
            # Создаем матрицу из всех эмбеддингов
            all_embeddings = np.array([emb for _, emb in user_embeddings])
            
            # Вычисляем сходство между текущим эмбеддингом и всеми сохраненными
            # Косинусное сходство = dot(a, b) / (norm(a) * norm(b))
            dot_products = np.dot(all_embeddings, face_embedding)
            norms = np.linalg.norm(all_embeddings, axis=1) * np.linalg.norm(face_embedding)
            similarities = dot_products / norms
            
            # Находим индекс наибольшего сходства
            best_idx = np.argmax(similarities)
            best_confidence = similarities[best_idx]
            
            # Если нашли совпадение выше порога
            if best_confidence >= threshold:
                best_match = user_embeddings[best_idx][0]
        
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
            
            return True, best_match, f"Лицо распознано как {best_match.get_full_name() or best_match.username}", best_confidence
        
        # Если совпадение не найдено
        # Создаем запись в логе распознавания (неудачную)
        if request and best_match:
            from .models import FaceRecognitionLog
            FaceRecognitionLog.objects.create(
                user=best_match,
                success=False,
                confidence=best_confidence,
                ip_address=request.META.get('REMOTE_ADDR', ''),
                device_info=request.META.get('HTTP_USER_AGENT', '')[:255]
            )
        
        return False, best_match, "Лицо не распознано", best_confidence
    
    except Exception as e:
        return False, None, f"Произошла ошибка: {str(e)}", 0.0

def check_face_data(username=None):
    """Проверяет данные лица пользователя в базе данных"""
    try:
        from accounts.models import User
        
        # Определяем, каких пользователей проверять
        if username:
            users = User.objects.filter(username=username)
            if not users.exists():
                return False, f"Пользователь {username} не найден"
        else:
            users = User.objects.exclude(face_id_data__isnull=True).exclude(face_id_data="")
        
        results = []
        
        for user in users:
            # Проверяем, что у пользователя есть данные лица
            if not user.face_id_data:
                results.append({
                    'username': user.username,
                    'status': 'error',
                    'message': 'Данные лица отсутствуют'
                })
                continue
            
            # Декодируем данные лица
            face_data = decode_face_data(user.face_id_data)
            
            if face_data is None:
                results.append({
                    'username': user.username,
                    'status': 'error',
                    'message': 'Не удалось декодировать данные лица'
                })
                continue
            
            # Проверяем тип данных и размерность
            if isinstance(face_data, np.ndarray):
                # Для FaceNet ожидаем эмбеддинг размерностью 512
                if face_data.shape == (512,):
                    results.append({
                        'username': user.username,
                        'status': 'ok',
                        'message': f'Данные FaceNet корректны, размерность: {face_data.shape}'
                    })
                else:
                    results.append({
                        'username': user.username,
                        'status': 'warning',
                        'message': f'Неожиданная размерность данных FaceNet: {face_data.shape}, ожидалось (512,)'
                    })
            else:
                results.append({
                    'username': user.username,
                    'status': 'warning',
                    'message': f'Неожиданный тип данных: {type(face_data)}'
                })
        
        return True, results
    
    except Exception as e:
        logger.error(f"Ошибка при проверке данных лица: {e}")
        return False, f"Произошла ошибка: {str(e)}"

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
