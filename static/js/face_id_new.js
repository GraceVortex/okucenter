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
    const classItemsContainer = document.getElementById('class-items-container');
    const noClassesMessage = document.getElementById('no-classes-message');
    const loadingIndicator = document.getElementById('loading-indicator');
    
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
            
            // Рисуем кадр с видео на канвасе
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0, videoWidth, videoHeight);
            
            // Получаем данные изображения в формате base64
            const imageData = canvas.toDataURL('image/jpeg', 0.9);
            
            // Сохраняем захваченное изображение
            capturedImage = imageData;
            
            // Отображаем изображение в предпросмотре
            photoImage.src = imageData;
            
            // Показываем предпросмотр и скрываем камеру
            cameraContainer.style.display = 'none';
            photoPreview.style.display = 'block';
            recognitionResult.style.display = 'none';
            
            return true;
        } catch (error) {
            console.error('Ошибка при захвате изображения:', error);
            showAlert('Произошла ошибка при захвате изображения', 'danger');
            return false;
        }
    }
    
    // Функция для распознавания лица
    function recognizeFace() {
        console.log('Начинаем распознавание лица...');
        
        if (!capturedImage) {
            console.error('Нет захваченного изображения для распознавания');
            showAlert('Пожалуйста, сделайте снимок перед распознаванием', 'warning');
            return;
        }
        
        // Показываем индикатор загрузки
        loadingIndicator.style.display = 'flex';
        
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
            loadingIndicator.style.display = 'none';
            
            console.log('Результат распознавания:', data);
            
            // Показываем уведомление о результате
            if (data.success) {
                showAlert(`Студент распознан: ${data.student.name}`, 'success');
            } else {
                showAlert(data.message || 'Не удалось распознать лицо', 'warning');
                return;
            }
            
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
                        confidenceValue.className = 'fw-bold badge bg-success';
                    } else if (confidencePercent >= 70) {
                        confidenceValue.className = 'fw-bold badge bg-info';
                    } else {
                        confidenceValue.className = 'fw-bold badge bg-warning';
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
                        
                        // Добавляем обработчики для кнопок отметки
                        document.querySelectorAll('.mark-class-btn').forEach(btn => {
                            if (!btn.disabled) {
                                btn.addEventListener('click', function() {
                                    const classId = this.getAttribute('data-class-id');
                                    const studentId = this.getAttribute('data-student-id');
                                    markAttendance(classId, studentId);
                                });
                            }
                        });
                    } else {
                        // Показываем сообщение об отсутствии уроков
                        if (noClassesMessage) {
                            noClassesMessage.style.display = 'block';
                        }
                    }
                }
            }
        })
        .catch(error => {
            console.error('Ошибка при распознавании лица:', error);
            loadingIndicator.style.display = 'none';
            showAlert('Произошла ошибка при распознавании лица', 'danger');
        });
    }
    
    // Функция для отметки посещаемости
    function markAttendance(classId, studentId) {
        console.log(`Отмечаем посещаемость: класс ${classId}, студент ${studentId}`);
        
        // Показываем индикатор загрузки
        loadingIndicator.style.display = 'flex';
        
        // Отправляем запрос на сервер
        fetch('/attendance/api/face-id/mark-attendance/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                class_id: classId,
                student_id: studentId
            })
        })
        .then(response => response.json())
        .then(data => {
            // Скрываем индикатор загрузки
            loadingIndicator.style.display = 'none';
            
            if (data.success) {
                // Обновляем кнопку
                const button = document.querySelector(`button[data-class-id="${classId}"][data-student-id="${studentId}"]`);
                if (button) {
                    button.disabled = true;
                    button.classList.remove('btn-success');
                    button.classList.add('btn-secondary');
                    button.innerHTML = '<i class="bi bi-check-circle-fill me-2"></i>Отмечено';
                }
                
                // Показываем уведомление
                showAlert('Посещаемость успешно отмечена!', 'success');
                
                // Обновляем список последних отметок (если возможно)
                if (data.attendance_log) {
                    updateAttendanceLogs(data.attendance_log);
                }
            } else {
                showAlert(data.error || 'Произошла ошибка при отметке посещаемости', 'danger');
            }
        })
        .catch(error => {
            console.error('Ошибка при отметке посещаемости:', error);
            loadingIndicator.style.display = 'none';
            showAlert('Произошла ошибка при отметке посещаемости', 'danger');
        });
    }
    
    // Функция для обновления списка последних отметок
    function updateAttendanceLogs(logData) {
        const logsContainer = document.getElementById('attendance-logs');
        if (!logsContainer) return;
        
        // Создаем новую запись
        const logItem = document.createElement('div');
        logItem.className = 'card mb-3';
        logItem.innerHTML = `
            <div class="card-body py-3">
                <div class="d-flex align-items-center">
                    <div class="me-3">
                        ${logData.student_photo ? 
                          `<img src="${logData.student_photo}" class="rounded-circle" width="50" height="50" alt="Фото студента">` : 
                          `<div class="rounded-circle bg-secondary d-flex align-items-center justify-content-center text-white" style="width: 50px; height: 50px;">
                              <i class="bi bi-person-fill"></i>
                           </div>`
                        }
                    </div>
                    <div>
                        <h5 class="mb-1">${logData.student_name}</h5>
                        <p class="mb-1 text-muted">${logData.class_name}</p>
                        <small class="text-muted">${logData.time}</small>
                    </div>
                </div>
            </div>
        `;
        
        // Добавляем анимацию
        logItem.style.animation = 'fadeIn 0.5s';
        
        // Вставляем в начало списка
        if (logsContainer.firstChild) {
            logsContainer.insertBefore(logItem, logsContainer.firstChild);
        } else {
            logsContainer.appendChild(logItem);
        }
        
        // Удаляем сообщение об отсутствии записей, если оно есть
        const noLogsMessage = logsContainer.querySelector('.no-logs-message');
        if (noLogsMessage) {
            noLogsMessage.remove();
        }
    }
    
    // Функция для отображения уведомлений
    function showAlert(message, type) {
        const alertsContainer = document.getElementById('alerts-container');
        if (!alertsContainer) return;
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Закрыть"></button>
        `;
        
        alertsContainer.appendChild(alert);
        
        // Автоматически скрываем уведомление через 5 секунд
        setTimeout(() => {
            alert.classList.remove('show');
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    }
    
    // Функция для получения CSRF токена из cookies
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
    
    // Функция сброса состояния
    function resetState() {
        // Останавливаем камеру
        stopCamera();
        
        // Сбрасываем переменные
        capturedImage = null;
        recognizedStudent = null;
        
        // Скрываем все контейнеры
        photoPreview.style.display = 'none';
        recognitionResult.style.display = 'none';
        
        // Очищаем контейнер с уроками
        if (classItemsContainer) {
            classItemsContainer.innerHTML = '';
        }
        
        // Инициализируем камеру заново
        initCamera();
    }
    
    // Добавляем обработчики событий
    if (captureBtn) {
        captureBtn.addEventListener('click', function() {
            captureImage();
        });
    }
    
    if (retakeBtn) {
        retakeBtn.addEventListener('click', function() {
            // Сбрасываем состояние и показываем камеру снова
            photoPreview.style.display = 'none';
            cameraContainer.style.display = 'block';
            capturedImage = null;
        });
    }
    
    if (recognizeBtn) {
        recognizeBtn.addEventListener('click', function() {
            recognizeFace();
        });
    }
    
    // Добавляем обработчик для кнопки "Отмена"
    const cancelBtn = document.getElementById('cancel-btn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function() {
            resetState();
        });
    }
    
    // Инициализируем камеру при загрузке страницы
    initCamera();
    
    // Добавляем стили для анимации
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
    `;
    document.head.appendChild(style);
});
