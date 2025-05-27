/**
 * Face ID - JavaScript для работы с камерой и распознаванием лиц
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM загружен, инициализация Face ID...');
    
    // Получаем ссылки на DOM элементы
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const captureBtn = document.getElementById('capture-btn');
    const retakeBtn = document.getElementById('retake-btn');
    const recognizeBtn = document.getElementById('recognize-btn');
    const photoImage = document.getElementById('photo-image');
    const cameraContainer = document.getElementById('camera-container');
    const photoPreview = document.getElementById('photo-preview');
    const recognitionResult = document.getElementById('recognition-result');
    const studentName = document.getElementById('student-name');
    const studentPhoto = document.getElementById('student-photo');
    const confidenceValue = document.getElementById('confidence-value');
    const confidenceLevel = document.getElementById('confidence-level');
    const markAttendanceContainer = document.getElementById('mark-attendance-container');
    const markAttendanceBtn = document.getElementById('mark-attendance-btn');
    const classItemsContainer = document.getElementById('class-items-container');
    const noClassesMessage = document.getElementById('no-classes-message');
    const loadingIndicator = document.getElementById('loading-indicator');
    
    // Модальное окно для выбора уроков
    const modalStudentInfo = document.getElementById('modal-student-info');
    const modalNoClasses = document.getElementById('modal-no-classes');
    const modalClassesList = document.getElementById('modal-classes-list');
    
    // Глобальные переменные
    let videoStream = null;
    let capturedImage = null;
    let recognizedStudent = null;
    
    // Инициализация камеры
    function initCamera() {
        console.log('Инициализация камеры...');
        
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            console.error('Браузер не поддерживает getUserMedia API');
            showAlert('Ваш браузер не поддерживает доступ к камере. Пожалуйста, используйте современный браузер.', 'danger');
            return;
        }
        
        navigator.mediaDevices.getUserMedia({ video: true })
            .then(function(stream) {
                console.log('Доступ к камере получен успешно');
                videoStream = stream;
                video.srcObject = stream;
                video.play();
                
                cameraContainer.style.display = 'block';
                photoPreview.style.display = 'none';
                recognitionResult.style.display = 'none';
                markAttendanceContainer.style.display = 'none';
            })
            .catch(function(error) {
                console.error('Ошибка при получении доступа к камере:', error);
                showAlert('Не удалось получить доступ к камере. Пожалуйста, убедитесь, что камера подключена и разрешен доступ к ней.', 'danger');
            });
    }
    
    // Остановка камеры
    function stopCamera() {
        if (videoStream) {
            videoStream.getTracks().forEach(track => {
                track.stop();
            });
            videoStream = null;
        }
    }
    
    // Захват изображения с камеры
    function captureImage() {
        console.log('Попытка захвата изображения...');
        
        try {
            if (!video || !canvas) {
                console.error('Видео или канвас не найдены');
                showAlert('Ошибка при захвате изображения: элементы не найдены', 'danger');
                return false;
            }
            
            // Получаем размеры видео
            const videoWidth = video.videoWidth;
            const videoHeight = video.videoHeight;
            
            if (!videoWidth || !videoHeight) {
                console.error('Невозможно получить размеры видео');
                showAlert('Ошибка при захвате изображения: видео не готово', 'danger');
                return false;
            }
            
            console.log(`Оригинальный размер видео: ${videoWidth}x${videoHeight}`);
            
            // Устанавливаем размеры канваса равными размерам видео
            canvas.width = videoWidth;
            canvas.height = videoHeight;
            
            // Рисуем текущий кадр видео на канвас
            const context = canvas.getContext('2d');
            context.drawImage(video, 0, 0, videoWidth, videoHeight);
            
            console.log('Изображение захвачено на канвас');
            
            // Получаем данные изображения в формате base64 (JPEG с высоким качеством)
            capturedImage = canvas.toDataURL('image/jpeg', 0.95);
            
            console.log('Изображение преобразовано в base64');
            
            // Отображаем захваченное изображение
            photoImage.src = capturedImage;
            cameraContainer.style.display = 'none';
            photoPreview.style.display = 'block';
            
            console.log('Изображение отображено в предпросмотре');
            return true;
        } catch (error) {
            console.error('Ошибка при захвате изображения:', error);
            showAlert('Произошла ошибка при захвате изображения. Пожалуйста, попробуйте еще раз.', 'danger');
            return false;
        }
    }
    
    // Повторный захват изображения
    function retakePhoto() {
        console.log('Повторный захват изображения...');
        
        photoPreview.style.display = 'none';
        cameraContainer.style.display = 'block';
        recognitionResult.style.display = 'none';
        markAttendanceContainer.style.display = 'none';
        
        // Если камера была остановлена, перезапускаем её
        if (!videoStream) {
            initCamera();
        }
    }
    
    // Распознавание лица
    function recognizeFace() {
        console.log('Начинаем распознавание лица...');
        
        if (!capturedImage) {
            console.error('Нет захваченного изображения для распознавания');
            showAlert('Сначала сделайте снимок', 'warning');
            return;
        }
        
        // Показываем индикатор загрузки
        if (loadingIndicator) {
            loadingIndicator.style.display = 'flex';
        }
        
        // Отправляем запрос на сервер для распознавания лица
        fetch('/attendance/api/face-id/recognize/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                face_data: capturedImage
            })
        })
        .then(response => response.json())
        .then(data => {
            // Скрываем индикатор загрузки
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
            
            console.log('Получен ответ от сервера:', data);
            
            // Проверка отображения результатов через 5 секунд
            setTimeout(() => {
                console.log('face_id_debug.js?v=1745660369:37');
                console.log('recognitionResult.style.display =', recognitionResult ? recognitionResult.style.display : 'элемент не найден');
                console.log('classItemsContainer.innerHTML =', classItemsContainer ? classItemsContainer.innerHTML : 'элемент не найден');
                console.log('classItemsContainer.childElementCount =', classItemsContainer ? classItemsContainer.childElementCount : 'элемент не найден');
                console.log('noClassesMessage.style.display =', noClassesMessage ? noClassesMessage.style.display : 'элемент не найден');
            }, 5000);
            
            if (data.success) {
                // Сохраняем данные о распознанном студенте
                recognizedStudent = {
                    id: data.student.id,
                    name: data.student.name,
                    photo_url: data.student.photo_url,
                    classes: data.classes,
                    confidence: data.confidence
                };
                
                // Скрываем камеру и предпросмотр
                cameraContainer.style.display = 'none';
                photoPreview.style.display = 'none';
                
                // Показываем полноценное окно с информацией о студенте
                recognitionResult.style.display = 'block';
                
                // Отображаем имя студента
                if (studentName) {
                    studentName.textContent = data.student.name;
                }
                
                // Отображаем фото студента
                if (studentPhoto) {
                    if (data.student.photo_url) {
                        studentPhoto.src = data.student.photo_url;
                        studentPhoto.style.display = 'block';
                    } else {
                        studentPhoto.style.display = 'none';
                    }
                }
                
                // Отображаем уровень уверенности
                if (confidenceValue && confidenceLevel) {
                    const confidencePercent = Math.round(data.confidence * 100);
                    confidenceValue.textContent = `${confidencePercent}%`;
                    confidenceLevel.style.width = `${confidencePercent}%`;
                    
                    // Устанавливаем цвет индикатора уверенности
                    if (confidencePercent >= 90) {
                        confidenceLevel.className = 'progress-bar bg-success';
                    } else if (confidencePercent >= 70) {
                        confidenceLevel.className = 'progress-bar bg-info';
                    } else {
                        confidenceLevel.className = 'progress-bar bg-warning';
                    }
                }
                
                // Проверяем наличие классов у студента
                if (classItemsContainer) {
                    classItemsContainer.innerHTML = '';
                    
                    // Обновляем счетчик количества уроков
                    const classesCount = document.getElementById('classes-count');
                    if (classesCount) {
                        classesCount.textContent = data.classes ? data.classes.length : 0;
                    }
                    
                    if (data.classes && data.classes.length > 0) {
                        console.log(`Найдено ${data.classes.length} уроков для студента`);
                        
                        // Скрываем сообщение об отсутствии уроков
                        if (noClassesMessage) {
                            noClassesMessage.style.display = 'none';
                        }
                        
                        // Создаем карточки уроков с анимацией
                        data.classes.forEach((classObj, index) => {
                            const classItem = document.createElement('div');
                            classItem.className = 'class-item mb-3 p-3 border rounded bg-white shadow-sm';
                            classItem.style.animation = `fadeIn 0.3s ease ${index * 0.1}s both`;
                            
                            // Определяем статус кнопки
                            const buttonClass = classObj.marked ? 'btn-secondary' : 'btn-success';
                            const buttonIcon = classObj.marked ? 'bi-check-circle-fill' : 'bi-check-circle';
                            const buttonText = classObj.marked ? 'Отмечено' : 'Отметить';
                            
                            classItem.innerHTML = `
                                <div class="d-flex justify-content-between align-items-center">
                                    <div>
                                        <h5 class="mb-1">${classObj.name}</h5>
                                        <div class="d-flex align-items-center mb-2">
                                            <i class="bi bi-clock me-2 text-muted"></i>
                                            <span class="text-muted">${classObj.time}</span>
                                        </div>
                                    </div>
                                    <button class="btn ${buttonClass} mark-class-btn" 
                                            data-class-id="${classObj.id}" 
                                            data-student-id="${data.student.id}"
                                            ${classObj.marked ? 'disabled' : ''}>
                                        <i class="bi ${buttonIcon} me-1"></i>
                                        ${buttonText}
                                    </button>
                                </div>
                            `;
                            classItemsContainer.appendChild(classItem);
                        });
                    } else {
                        // Показываем сообщение об отсутствии уроков
                        if (noClassesMessage) {
                            noClassesMessage.style.display = 'block';
                        }
                    }
                                    markAttendanceForClass(studentId, classId, this);
                                });
                            }
                        });
                        
                        if (noClassesMessage) {
                            noClassesMessage.style.display = 'none';
                        }
                    } else {
                        console.log('У студента нет уроков');
                        if (noClassesMessage) {
                            noClassesMessage.style.display = 'block';
                        }
                    }
                }
                
                // Показываем кнопку "Отметить посещение"
                if (markAttendanceContainer) {
                    markAttendanceContainer.style.display = 'block';
                }
                
                // Показываем результат распознавания
                if (recognitionResult) {
                    recognitionResult.style.display = 'block';
                }
                
                // Показываем уведомление об успешном распознавании
                showAlert(`Лицо распознано: ${data.student.name}`, 'success');
                
            } else {
                // Показываем сообщение об ошибке
                showAlert(data.message || 'Не удалось распознать лицо', 'warning');
            }
        })
        .catch(error => {
            console.error('Ошибка при распознавании лица:', error);
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
            showAlert('Произошла ошибка при распознавании лица. Пожалуйста, попробуйте еще раз.', 'danger');
        });
    }
    
    // Заполнение модального окна данными о студенте и его уроках
    function fillClassesModal(student, classes) {
        // Заполняем информацию о студенте
        if (modalStudentInfo) {
            modalStudentInfo.innerHTML = `
                <div class="d-flex align-items-center">
                    ${student.photo_url ? `<img src="${student.photo_url}" alt="${student.name}" class="rounded-circle me-3" width="50" height="50">` : ''}
                    <div>
                        <h5 class="mb-0">${student.name}</h5>
                    </div>
                </div>
            `;
        }
        
        // Заполняем список уроков
        if (modalClassesList) {
            modalClassesList.innerHTML = '';
            
            if (classes && classes.length > 0) {
                classes.forEach(classObj => {
                    const classItem = document.createElement('div');
                    classItem.className = 'class-item mb-2 p-3 border rounded';
                    classItem.innerHTML = `
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h5 class="mb-1">${classObj.name}</h5>
                                <p class="mb-1 text-muted">${classObj.time}</p>
                            </div>
                            <button class="btn btn-sm btn-success mark-class-btn" 
                                    data-class-id="${classObj.id}" 
                                    data-student-id="${student.id}"
                                    ${classObj.marked ? 'disabled' : ''}>
                                ${classObj.marked ? 'Отмечено' : 'Отметить'}
                            </button>
                        </div>
                    `;
                    modalClassesList.appendChild(classItem);
                    
                    // Добавляем обработчик для кнопки отметки
                    const markBtn = classItem.querySelector('.mark-class-btn');
                    if (markBtn && !classObj.marked) {
                        markBtn.addEventListener('click', function() {
                            const classId = this.getAttribute('data-class-id');
                            const studentId = this.getAttribute('data-student-id');
                            markAttendanceForClass(studentId, classId, this);
                        });
                    }
                });
                
                if (modalNoClasses) {
                    modalNoClasses.style.display = 'none';
                }
            } else {
                if (modalNoClasses) {
                    modalNoClasses.style.display = 'block';
                }
            }
        }
    }
    
    // Отметка посещаемости для выбранного занятия
    function markAttendanceForClass(studentId, classId, buttonElement) {
        console.log(`Отмечаем посещаемость для студента ${studentId} на занятии ${classId}`);
        
        // Показываем индикатор загрузки на кнопке
        if (buttonElement) {
            buttonElement.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Отмечаем...';
            buttonElement.disabled = true;
        }
        
        // Отправляем запрос на сервер для отметки посещаемости
        fetch('/attendance/api/face-id/mark-attendance/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                student_id: studentId,
                class_id: classId,
                face_data: capturedImage
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Показываем сообщение об успешной отметке
                showAlert(data.message || 'Посещаемость успешно отмечена', 'success');
                
                // Обновляем кнопку
                if (buttonElement) {
                    buttonElement.innerHTML = 'Отмечено';
                    buttonElement.disabled = true;
                    buttonElement.classList.remove('btn-success');
                    buttonElement.classList.add('btn-secondary');
                }
                
            } else {
                // Показываем сообщение об ошибке
                showAlert(data.message || 'Не удалось отметить посещаемость', 'danger');
                
                // Возвращаем кнопку в исходное состояние
                if (buttonElement) {
                    buttonElement.innerHTML = 'Отметить';
                    buttonElement.disabled = false;
                }
            }
        })
        .catch(error => {
            console.error('Ошибка при отметке посещаемости:', error);
            showAlert('Произошла ошибка при отметке посещаемости. Пожалуйста, попробуйте еще раз.', 'danger');
            
            // Возвращаем кнопку в исходное состояние
            if (buttonElement) {
                buttonElement.innerHTML = 'Отметить';
                buttonElement.disabled = false;
            }
        });
    }
    
    // Получение CSRF-токена из cookies
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    // Функция для показа уведомлений
    function showAlert(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        
        // Добавляем иконку в зависимости от типа уведомления
        let icon = 'info-circle-fill';
        if (type === 'success') icon = 'check-circle-fill';
        if (type === 'warning') icon = 'exclamation-triangle-fill';
        if (type === 'danger') icon = 'exclamation-triangle-fill';
        
        alertDiv.innerHTML = `
            <i class="bi bi-${icon} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        // Добавляем уведомление в контейнер
        const alertsContainer = document.getElementById('alerts-container');
        if (alertsContainer) {
            alertsContainer.appendChild(alertDiv);
            
            // Автоматически скрываем уведомление через 5 секунд
            setTimeout(() => {
                alertDiv.remove();
            }, 5000);
        }
    }
    
    // Инициализация
    function init() {
        console.log('Инициализация Face ID...');
        
        // Проверяем наличие всех необходимых элементов DOM
        console.log('DOM элементы:');
        console.log('video:', video ? 'найден' : 'не найден');
        console.log('canvas:', canvas ? 'найден' : 'не найден');
        console.log('captureBtn:', captureBtn ? 'найден' : 'не найден');
        console.log('retakeBtn:', retakeBtn ? 'найден' : 'не найден');
        console.log('recognizeBtn:', recognizeBtn ? 'найден' : 'не найден');
        
        // Инициализируем камеру
        initCamera();
        
        // Добавляем обработчики событий с проверкой
        if (captureBtn) {
            console.log('Добавляем обработчик для кнопки Сделать снимок');
            captureBtn.addEventListener('click', function(event) {
                console.log('Кнопка Сделать снимок нажата');
                event.preventDefault();
                captureImage();
            });
        } else {
            console.error('Кнопка Сделать снимок не найдена в DOM');
        }
        
        if (retakeBtn) {
            retakeBtn.addEventListener('click', function(event) {
                event.preventDefault();
                retakePhoto();
            });
        }
        
        if (recognizeBtn) {
            recognizeBtn.addEventListener('click', function(event) {
                event.preventDefault();
                recognizeFace();
            });
        }
        
        // Добавляем обработчик для кнопки "Отметить посещение"
        if (markAttendanceBtn) {
            markAttendanceBtn.addEventListener('click', function(event) {
                event.preventDefault();
                console.log('Кнопка Отметить посещение нажата');
                
                // Показываем модальное окно
                const classesModal = new bootstrap.Modal(document.getElementById('classesModal'));
                classesModal.show();
                
                // Заполняем модальное окно данными о студенте и его уроках
                if (recognizedStudent) {
                    fillClassesModal(recognizedStudent, recognizedStudent.classes);
                }
            });
        }
    }
    
    // Запускаем инициализацию
    init();
});
