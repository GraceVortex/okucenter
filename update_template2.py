import re

# Read the current template
with open('templates/core/home.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the student section in the current template
pattern = r'{% elif user.is_student %}.*?{% elif user.is_parent %}'
student_section = re.search(pattern, content, re.DOTALL).group(0)

# Create the updated student section
updated_section = '''{% elif user.is_student %}
            <!-- Блок с успеваемостью -->
            <h3 class="fw-bold mb-4">Моя успеваемость</h3>
            
            <!-- Первый ряд: Ближайший урок и Домашние задания -->
            <div class="row mb-4">
                <!-- Ближайший урок -->
                {% if next_class %}
                <div class="col-md-6 mb-3">
                    <div class="card shadow-sm h-100 border-0 rounded-4 bg-gradient" style="background-color: #e6f2ff;">
                        <div class="card-body p-4">
                            <div class="d-flex align-items-center mb-3">
                                <div class="rounded-circle p-2 me-3" style="background-color: rgba(13, 110, 253, 0.2); display: flex; align-items: center; justify-content: center;">
                                    <i class="bi bi-alarm fs-4 text-primary"></i>
                                </div>
                                <h5 class="fw-bold mb-0">Ближайший урок</h5>
                            </div>
                            
                            <div class="mb-3">
                                <h5 class="fw-bold text-primary mb-2">{{ next_class.class_name }}</h5>
                                <div class="d-flex align-items-center mb-1">
                                    <i class="bi bi-person-badge fs-5 me-2 text-muted"></i>
                                    <span class="small">{{ next_class.teacher }}</span>
                                </div>
                                <div class="d-flex align-items-center mb-1">
                                    <i class="bi bi-geo-alt fs-5 me-2 text-muted"></i>
                                    <span class="small">Кабинет: {{ next_class.room }}</span>
                                </div>
                            </div>
                            
                            <div class="bg-white p-2 rounded mb-2">
                                <div class="d-flex justify-content-between align-items-center">
                                    <div class="d-flex align-items-center">
                                        <i class="bi bi-calendar-date fs-5 me-2 text-primary"></i>
                                        <span class="small fw-bold">{{ next_class.day_name }}</span>
                                    </div>
                                    <span class="badge bg-primary">
                                        {% if next_class.days_until == 0 %}
                                            Сегодня
                                        {% elif next_class.days_until == 1 %}
                                            Завтра
                                        {% else %}
                                            Через {{ next_class.days_until }} дн.
                                        {% endif %}
                                    </span>
                                </div>
                                <div class="d-flex align-items-center mt-1">
                                    <i class="bi bi-clock fs-5 me-2 text-primary"></i>
                                    <span class="small">{{ next_class.start_time }} - {{ next_class.end_time }}</span>
                                </div>
                            </div>
                            
                            <a href="{% url 'core:schedule' %}" class="btn btn-sm btn-outline-primary w-100">
                                <i class="bi bi-calendar-week"></i> Полное расписание
                            </a>
                        </div>
                    </div>
                </div>
                {% endif %}
                
                <!-- Домашние задания -->
                <div class="col-md-6 mb-3">
                    <div class="card shadow-sm h-100 border-0 rounded-4 bg-gradient" style="background-color: #f0fff7;">
                        <div class="card-body p-4">
                            <div class="d-flex align-items-center mb-3">
                                <div class="rounded-circle p-2 me-3" style="background-color: rgba(25, 135, 84, 0.2); display: flex; align-items: center; justify-content: center;">
                                    <i class="bi bi-journal-check fs-4 text-success"></i>
                                </div>
                                <h5 class="fw-bold mb-0">Домашние задания</h5>
                            </div>
                            
                            {% if next_homework %}
                            <div class="mb-3">
                                <h5 class="fw-bold text-success mb-2">{{ next_homework.title }}</h5>
                                <div class="d-flex align-items-center mb-1">
                                    <i class="bi bi-book fs-5 me-2 text-muted"></i>
                                    <span class="small">{{ next_homework.class_name }}</span>
                                </div>
                                <div class="bg-white p-2 rounded mb-2">
                                    <div class="d-flex justify-content-between align-items-center">
                                        <div class="d-flex align-items-center">
                                            <i class="bi bi-calendar-date fs-5 me-2 text-success"></i>
                                            <span class="small fw-bold">Дедлайн</span>
                                        </div>
                                        <span class="badge bg-success">
                                            {% if next_homework.days_until == 0 %}
                                                Сегодня
                                            {% elif next_homework.days_until == 1 %}
                                                Завтра
                                            {% else %}
                                                Через {{ next_homework.days_until }} дн.
                                            {% endif %}
                                        </span>
                                    </div>
                                </div>
                            </div>
                            <a href="{% url 'classes:all_student_homework' %}" class="btn btn-sm btn-outline-success w-100">
                                <i class="bi bi-pencil-square"></i> Выполнить задание
                            </a>
                            {% elif all_homework_completed %}
                            <div class="text-center my-3">
                                <i class="bi bi-check-circle-fill text-success fs-1 mb-2"></i>
                                <p class="fw-bold text-success mb-1">Все задания выполнены!</p>
                                <p class="text-muted small">У вас нет невыполненных заданий</p>
                            </div>
                            <a href="{% url 'classes:all_student_homework' %}" class="btn btn-sm btn-outline-success w-100">
                                <i class="bi bi-journal-text"></i> Все задания
                            </a>
                            {% else %}
                            <div class="text-center my-3">
                                <p class="text-muted">Нет активных заданий</p>
                            </div>
                            <a href="{% url 'classes:all_student_homework' %}" class="btn btn-sm btn-outline-success w-100">
                                <i class="bi bi-journal-text"></i> Все задания
                            </a>
                            {% endif %}
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Второй ряд: Подробная статистика и Мои классы -->
            <div class="row mb-5">
                <!-- Подробная статистика -->
                <div class="col-md-6 mb-3">
                    <div class="card shadow-sm h-100 border-0 rounded-4 bg-gradient" style="background-color: #fff8f0;">
                        <div class="card-body p-4">
                            <div class="d-flex align-items-center mb-3">
                                <div class="rounded-circle p-2 me-3" style="background-color: rgba(255, 153, 0, 0.2); display: flex; align-items: center; justify-content: center;">
                                    <i class="bi bi-graph-up fs-4 text-warning"></i>
                                </div>
                                <h5 class="fw-bold mb-0">Подробная статистика</h5>
                            </div>
                            <h3 class="fw-bold mb-0">
                                <a href="{% url 'core:statistics' %}" class="text-decoration-none text-warning">
                                    Перейти <i class="bi bi-arrow-right"></i>
                                </a>
                            </h3>
                            <p class="text-muted mb-0 small mt-2">Подробная информация о вашей успеваемости</p>
                        </div>
                    </div>
                </div>
                
                <!-- Мои классы -->
                <div class="col-md-6 mb-3">
                    <div class="card shadow-sm h-100 border-0 rounded-4 bg-gradient" style="background-color: #f0f0ff;">
                        <div class="card-body p-4">
                            <div class="d-flex align-items-center mb-3">
                                <div class="rounded-circle p-2 me-3" style="background-color: rgba(13, 110, 253, 0.2); display: flex; align-items: center; justify-content: center;">
                                    <i class="bi bi-book fs-4 text-primary"></i>
                                </div>
                                <h5 class="fw-bold mb-0">Мои классы</h5>
                            </div>
                            
                            {% if student_classes %}
                            <div class="mb-3">
                                <div class="list-group list-group-flush">
                                    {% for enrollment in student_classes|slice:":2" %}
                                    <div class="list-group-item px-0 py-2 border-0">
                                        <h6 class="mb-1 fw-bold">{{ enrollment.class_obj.name }}</h6>
                                        <p class="mb-0 small text-muted">
                                            <i class="bi bi-person-badge me-1"></i> {{ enrollment.class_obj.teacher.full_name }}
                                        </p>
                                    </div>
                                    {% endfor %}
                                </div>
                            </div>
                            {% if student_classes.count > 2 %}
                            <p class="text-muted small text-center mb-3">И еще {{ student_classes.count|add:"-2" }} классов</p>
                            {% endif %}
                            <a href="#" class="btn btn-sm btn-outline-primary w-100">
                                <i class="bi bi-grid"></i> Все классы
                            </a>
                            {% else %}
                            <div class="text-center my-3">
                                <p class="text-muted">У вас нет активных классов</p>
                            </div>
                            {% endif %}
                        </div>
                    </div>
                </div>
            </div>
        {% elif user.is_parent %}'''

# Replace with the updated section
new_content = content.replace(student_section, updated_section)

# Write the updated content back to the template
with open('templates/core/home.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Template updated successfully!")
