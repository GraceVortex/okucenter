@login_required
def edit_student(request, pk):
    """Редактирует студента."""
    # Проверка доступа
    if not request.user.is_admin:
        return HttpResponseForbidden("Только администраторы могут редактировать студентов.")
    
    student = get_object_or_404(Student, pk=pk)
    user = student.user
    
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            # Обновляем данные пользователя
            if user.username != form.cleaned_data['username']:
                # Проверяем, что имя пользователя уникально, исключая текущего пользователя
                if User.objects.filter(username=form.cleaned_data['username']).exclude(id=user.id).exists():
                    form.add_error('username', 'Пользователь с таким именем уже существует')
                    return render(request, 'accounts/student_form.html', {
                        'form': form,
                        'title': 'Редактирование студента',
                        'submit_text': 'Сохранить изменения'
                    })
                user.username = form.cleaned_data['username']
            if form.cleaned_data['password']:
                user.set_password(form.cleaned_data['password'])
            user.email = form.cleaned_data.get('email', '')
            user.save()
            
            # Сохраняем данные студента без создания нового пользователя
            student = form.save(commit=False)
            student.user = user  # Используем существующего пользователя
            
            # Если нужно создать нового родителя
            if form.cleaned_data.get('create_parent'):
                # Проверяем, что имя пользователя для родителя уникально
                if User.objects.filter(username=form.cleaned_data['parent_username']).exists():
                    form.add_error('parent_username', 'Пользователь с таким именем уже существует')
                    return render(request, 'accounts/student_form.html', {
                        'form': form,
                        'title': 'Редактирование студента',
                        'submit_text': 'Сохранить изменения'
                    })
                
                try:
                    # Создаем пользователя для родителя
                    parent_user = User.objects.create_user(
                        username=form.cleaned_data['parent_username'],
                        password=form.cleaned_data['parent_password'],
                        email=form.cleaned_data.get('parent_email', ''),
                        user_type='parent'
                    )
                except Exception as e:
                    # Если возникла ошибка при создании пользователя
                    form.add_error('parent_username', f'Ошибка при создании пользователя: {str(e)}')
                    return render(request, 'accounts/student_form.html', {
                        'form': form,
                        'title': 'Редактирование студента',
                        'submit_text': 'Сохранить изменения'
                    })
                
                # Создаем родителя
                parent = Parent(
                    user=parent_user,
                    full_name=form.cleaned_data['parent_full_name'],
                    phone_number=form.cleaned_data['parent_phone_number']
                )
                parent.save()
                
                # Привязываем родителя к студенту
                student.parent = parent
            
            try:
                student.save()
                logger = logging.getLogger(__name__)
                logger.info(f"Изменен студент: {student.full_name}, фото: {student.face_image}")
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Ошибка при сохранении изменений студента: {str(e)}")
                messages.error(request, f"Ошибка при сохранении изменений: {str(e)}")
                return redirect('accounts:student_list')
            
            # Обрабатываем фотографию для FaceID, если она была загружена
            face_image = request.FILES.get('face_image')
            if face_image:
                temp_path = None  # Инициализируем переменную вне блока try
                try:
                    # Проверяем размер и тип файла
                    if face_image.size > 10 * 1024 * 1024:  # 10 МБ
                        messages.error(request, "Файл слишком большой. Максимальный размер - 10 МБ")
                        logger.error(f"Ошибка: файл {face_image.name} слишком большой")
                        return redirect('accounts:student_list')
                    
                    # Проверяем тип файла
                    content_type = face_image.content_type.lower()
                    
                    if not content_type.startswith('image/'):
                        messages.error(request, "Загруженный файл не является изображением")
                        logger.error(f"Ошибка: файл {face_image.name} не является изображением ({content_type})")
                        return redirect('accounts:student_list')
                    
                    # Читаем изображение и преобразуем его в стандартный формат
                    import io
                    from PIL import Image
                    import tempfile
                    import os
                    import base64
                    from face_recognition_app.facenet_utils import register_face
                    
                    # Создаем временный файл для сохранения загруженного изображения
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                        for chunk in face_image.chunks():
                            temp_file.write(chunk)
                        temp_path = temp_file.name
                    
                    logger.info(f"Изображение сохранено во временный файл: {temp_path}")
                    
                    # Открываем изображение с помощью PIL
                    img = Image.open(temp_path)
                    
                    # Проверяем размер изображения
                    width, height = img.size
                    logger.info(f"Размер изображения: {width}x{height}")
                    
                    # Преобразуем в RGB, если необходимо
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                        logger.info(f"Изображение преобразовано в RGB")
                    
                    # Уменьшаем размер изображения, если оно слишком большое
                    if width > 1000 or height > 1000:
                        ratio = min(1000 / width, 1000 / height)
                        new_width = int(width * ratio)
                        new_height = int(height * ratio)
                        img = img.resize((new_width, new_height), Image.LANCZOS)
                        logger.info(f"Изображение уменьшено до {new_width}x{new_height}")
                    
                    logger.info("Изображение успешно обработано")
                    
                    # Сохраняем в буфер в формате JPEG с высоким качеством
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG', quality=95)
                    buffer.seek(0)
                    
                    # Сохраняем обработанное изображение во временный файл
                    with open(temp_path, 'wb') as f:
                        f.write(buffer.getvalue())
                    logger.info(f"Обработанное изображение сохранено в {temp_path}")
                    
                    # Конвертируем в base64 для FaceNet
                    base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    
                    # Регистрируем лицо пользователя с помощью FaceNet
                    # Добавляем префикс data:image/jpeg;base64, для корректной обработки
                    base64_image_with_prefix = f"data:image/jpeg;base64,{base64_image}"
                    success, message = register_face(user, base64_image_with_prefix)
                    
                    if success:
                        messages.success(request, f"Фотография для FaceID успешно загружена и обработана.")
                        
                        # Сохраняем фотографию в профиле студента
                        from django.core.files.base import ContentFile
                        # Используем обработанное изображение из буфера
                        student.face_image.save(f"faceid_{user.id}.jpg", ContentFile(buffer.getvalue()), save=True)
                        logger.info(f"Фотография сохранена в профиле студента {student.id}")
                    else:
                        messages.error(request, f"Ошибка при обработке фотографии для FaceID: {message}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке фотографии для FaceID: {e}")
                    messages.error(request, f"Произошла ошибка при обработке фотографии: {str(e)}")
                finally:
                    # Удаляем временный файл в любом случае
                    if temp_path and os.path.exists(temp_path):
                        try:
                            os.unlink(temp_path)
                            logger.info(f"Временный файл {temp_path} удален")
                        except Exception as e:
                            logger.error(f"Ошибка при удалении временного файла: {e}")
            
            messages.success(request, f"Данные студента {student.full_name} успешно обновлены.")
            return redirect('accounts:student_list')
    else:
        form = StudentForm(instance=student, initial={
            'username': user.username,
            'email': user.email,
            'password': ''  # Пустое поле для пароля
        })
    
    return render(request, 'accounts/student_form.html', {
        'form': form,
        'title': 'Редактирование студента',
        'submit_text': 'Сохранить изменения'
    })
